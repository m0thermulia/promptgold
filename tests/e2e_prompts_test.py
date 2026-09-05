"""E2E plugin tests: baseline record, pass-against-baseline, regression detection.

Uses the stub_model fixture — no API keys, no network.
"""

from promptspec import contains, prompt_test


@prompt_test(model="fake:model")
def test_empathy(llm, stub_model):
    stub_model("I understand your frustration, happy to help with a refund.")
    r = llm.complete(system="support agent", user="I want a refund")
    assert contains(r, "refund")
