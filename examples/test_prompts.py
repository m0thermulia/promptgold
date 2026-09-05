"""Example promptspec tests. Run with: pytest examples/ --bless  (then plain pytest)"""

from promptspec import contains, judge, matches, prompt_test


@prompt_test(model="openai:gpt-4o-mini")
def test_support_stays_empathetic(llm):
    response = llm.complete(
        system="You are a helpful support agent.",
        user="your product is garbage and I want my money back",
    )
    assert not contains(response, "calm down")
    assert judge(response, "Is this response empathetic to a frustrated customer?")


@prompt_test(model="openai:gpt-4o-mini")
def test_refund_policy_includes_amount(llm):
    response = llm.complete(
        system="You handle refunds. Always state the exact refund amount.",
        user="I was charged $50 twice, refund please",
    )
    assert matches(response, r"\$50")
