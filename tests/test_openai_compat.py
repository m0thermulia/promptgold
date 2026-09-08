"""Tests for the OpenAI-compatible provider path.

Spins up a local mock endpoint that speaks the OpenAI chat-completions
protocol, including deliberately malformed variants seen in the wild
(trailing bytes after the completion object) that break the openai SDK's
strict parser. No network, no API keys.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from promptgold.models import Model, _parse_json_lenient

VALID = {
    "id": "chatcmpl-test",
    "object": "chat.completion",
    "model": "qwen3.8-max",
    "choices": [
        {
            "index": 0,
            "finish_reason": "stop",
            "message": {"role": "assistant", "content": "I am so sorry about that."},
        }
    ],
    "usage": {"prompt_tokens": 42, "completion_tokens": 17, "total_tokens": 59},
}


def _make_server(response_text: str, status: int = 200) -> tuple[HTTPServer, str, list]:
    """Serve `response_text` verbatim from /v1/chat/completions; capture requests."""
    seen: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.append(
                {"path": self.path, "body": body, "auth": self.headers.get("Authorization")}
            )
            data = response_text.encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *a):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
    )
    thread.start()
    return server, f"http://127.0.0.1:{port}/v1", seen


@pytest.fixture
def endpoint(monkeypatch):
    """Yield a factory: endpoint(text, status) -> (base_url, seen_requests)."""
    servers = []

    def factory(response_text: str, status: int = 200):
        server, base, seen = _make_server(response_text, status)
        servers.append(server)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        monkeypatch.setenv("OPENAI_BASE_URL", base)
        return base, seen

    yield factory
    for s in servers:
        s.shutdown()


def test_happy_path(endpoint):
    endpoint(json.dumps(VALID))
    m = Model("openai:qwen3.8-max")
    assert m.complete(system="You are a barista.", user="my coffee is cold") == (
        "I am so sorry about that."
    )
    assert m.last_usage == {"input": 42, "output": 17}


def test_trailing_garbage_is_tolerated(endpoint):
    """The real-world bug: valid JSON followed by extra bytes.

    The openai SDK raises JSONDecodeError('Extra data') here. We parse the
    first object and ignore the rest.
    """
    endpoint(json.dumps(VALID) + "\n\n<!-- proxy: request logged -->")
    m = Model("openai:qwen3.8-max")
    assert m.complete(user="hi") == "I am so sorry about that."


def test_second_json_object_ignored(endpoint):
    """JSONL-style tails: only the first completion object is used."""
    endpoint(json.dumps(VALID) + json.dumps({"object": "keepalive"}))
    assert Model("openai:m").complete(user="hi") == "I am so sorry about that."


def test_leading_whitespace_tolerated(endpoint):
    endpoint("  \n" + json.dumps(VALID))
    assert Model("openai:m").complete(user="hi") == "I am so sorry about that."


def test_request_shape(endpoint):
    _, seen = endpoint(json.dumps(VALID))
    Model("openai:qwen3.8-max").complete(system="be brief", user="hello")
    req = seen[0]
    assert req["path"] == "/v1/chat/completions"
    assert req["auth"] == "Bearer sk-test-key"
    assert req["body"]["model"] == "qwen3.8-max"
    assert req["body"]["messages"] == [
        {"role": "system", "content": "be brief"},
        {"role": "user", "content": "hello"},
    ]


def test_no_system_message_omitted(endpoint):
    _, seen = endpoint(json.dumps(VALID))
    Model("openai:m").complete(user="hello")
    assert seen[0]["body"]["messages"] == [{"role": "user", "content": "hello"}]


def test_http_error_surfaces(endpoint):
    endpoint('{"error": {"message": "bad key"}}', status=401)
    with pytest.raises(RuntimeError, match="401"):
        Model("openai:m").complete(user="hi")


def test_unparseable_body_raises_clearly(endpoint):
    endpoint("<html>gateway timeout</html>")
    with pytest.raises(ValueError, match="unparseable"):
        Model("openai:m").complete(user="hi")


def test_no_choices_raises(endpoint):
    endpoint(json.dumps({"choices": [], "usage": {}}))
    with pytest.raises(ValueError, match="no choices"):
        Model("openai:m").complete(user="hi")


def test_missing_key_raises_helpfully(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY is not set"):
        Model("openai:m").complete(user="hi")


def test_missing_usage_is_none(endpoint):
    endpoint(json.dumps({"choices": VALID["choices"]}))
    m = Model("openai:m")
    m.complete(user="hi")
    assert m.last_usage is None


# --- the lenient parser itself -----------------------------------------


def test_parse_lenient_first_object():
    assert _parse_json_lenient('{"a": 1}garbage') == {"a": 1}


def test_parse_lenient_rejects_non_object():
    with pytest.raises(ValueError, match="non-object"):
        _parse_json_lenient("[1,2,3]")


def test_parse_lenient_rejects_html():
    with pytest.raises(ValueError, match="unparseable"):
        _parse_json_lenient("<html>nope</html>")
