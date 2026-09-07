"""Tests for the adversarial pack — corpus shape and scan helper."""

from __future__ import annotations

from promptgold.adversarial import CATEGORIES, injections, jailbreaks, leak_probes, topic_escapes


def test_corpus_sizes():
    assert len(jailbreaks()) >= 10
    assert len(injections()) >= 10
    assert len(leak_probes()) >= 10
    assert len(topic_escapes()) >= 10


def test_no_empty_or_duplicate_attacks():
    for name, fn in CATEGORIES.items():
        attacks = fn()
        assert all(a.strip() for a in attacks), f"{name} has an empty attack"
        assert len(attacks) == len(set(attacks)), f"{name} has duplicates"


def test_categories_cover_all_packs():
    assert set(CATEGORIES) == {"jailbreak", "injection", "leak", "escape"}
    for fn in CATEGORIES.values():
        assert callable(fn)


def test_attacks_are_user_inputs_not_instructions():
    """Attacks must be strings a USER could send — no placeholders to fill."""
    for fn in CATEGORIES.values():
        for attack in fn():
            assert "{system_prompt}" not in attack
            assert isinstance(attack, str)
