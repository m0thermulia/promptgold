"""E2E plugin test with a stubbed model — no API keys."""
import promptspec.models
from promptspec import contains, prompt_test

# Monkeypatch Model.complete so no network is hit
_orig_init = promptspec.models.Model.__init__
def fake_init(self, spec, **kw):
    self.provider, self.name = spec.split(":", 1)
    self.spec = spec
    self.temperature, self.max_tokens, self.extra = 0.0, 100, kw
def fake_complete(self, system="", user="", **kw):
    return "I understand your frustration, happy to help with a refund."
promptspec.models.Model.__init__ = fake_init
promptspec.models.Model.complete = fake_complete

@prompt_test(model="fake:model")
def test_empathy(llm):
    r = llm.complete(system="support agent", user="I want a refund")
    assert contains(r, "refund")
