"""E2E plugin tests: bless golden file, pass against it, detect regression.

Uses the stub_model fixture — no API keys, no network.
"""

from promptgold import contains, judge, prompt_test


@prompt_test(model="openai:gpt-4o-mini")
def test_empathy(llm, stub_model):
    stub_model("I understand your frustration, happy to help with a refund.")
    r = llm.complete(system="support agent", user="I want a refund")
    assert contains(r, "refund")
    assert judge(r, "Is this empathetic?", model=llm.model)
