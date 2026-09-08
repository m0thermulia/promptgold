"""Record cassettes for the BROKEN prompt variant (demo Act 3).

Simulates the world after someone 'improves' system_prompt.txt by deleting
the empathy rule. Breaking the system prompt changes the cassette key for
EVERY test, so this re-records the full suite under the broken prompt:
most tests behave identically (the bot still handles refunds, stays on
topic, deflects attacks), but the empathy test now gets a cold reply and
the judge flips FAIL. Result: the suite splits 5 pass / 1 fail.

Run from repo root:
    ./.venv/bin/python examples/supportbot/_record_broken_cassettes.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE.parent.parent / "src"))
sys.path.insert(0, str(_HERE))

import _record_demo_cassettes as good  # noqa: E402
from promptgold.cassettes import CASSETTE_DIR, _key, _slug  # noqa: E402

MODEL = good.MODEL
BROKEN_SYSTEM = good.SYSTEM.replace(
    "- Always be empathetic, even when the customer is rude. Acknowledge feelings first.",
    "- Be efficient. Answer fast.",
)

COLD_REPLY = (
    "Refunds are subject to our return policy. Please provide your order number "
    "so I can check eligibility."
)
JUDGE_FAIL = "VERDICT: FAIL\nREASON: no empathy, cold policy recital."

EMPATHY_USER = "your soap burned my skin, this product is garbage!!"
EMPATHY_TEST = "test_angry_customer_gets_empathy"


def _write(test_name: str, pairs: list[tuple[str, str]], criteria: list[str]) -> None:
    nodeid = f"{good.TEST_FILE}::{test_name}"
    responses: dict[str, str] = {}
    for user, reply in pairs:
        responses[_key(MODEL, BROKEN_SYSTEM, user)] = reply
        for criterion in criteria:
            responses[_key(MODEL, good.judge_prompt(criterion, reply), "")] = (
                JUDGE_FAIL if test_name == EMPATHY_TEST else good.JUDGE_PASS
            )
    path = CASSETTE_DIR / _slug(nodeid)
    path.parent.mkdir(parents=True, exist_ok=True)
    import json

    # MERGE into the existing cassette (good-prompt entries must survive —
    # the demo flips back and forth between both prompt variants).
    data = json.loads(path.read_text()) if path.exists() else {"model": MODEL, "responses": {}}
    data["responses"].update(responses)
    path.write_text(json.dumps(data, indent=2) + "\n")
    print(f"wrote {path}")


def main() -> None:
    # Normal-behavior tests: swap system prompt to broken, replies unchanged.
    for test_name, pairs in good.SUITE:
        # The empathy test gets the cold reply under the broken prompt.
        if test_name == EMPATHY_TEST:
            pairs = [(EMPATHY_USER, COLD_REPLY)]
        _write(test_name, pairs, good.CRITERIA[test_name])

    # Adversarial tests: bot still deflects (attacks don't depend on empathy).
    for test_name, attacks in good.ATTACKS.items():
        _write(
            test_name,
            [(a, good.DEFLECTION) for a in attacks],
            good.CRITERIA[test_name],
        )


if __name__ == "__main__":
    main()
