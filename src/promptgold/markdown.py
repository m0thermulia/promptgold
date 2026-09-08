"""Markdown summary for PR comments — same RunResults data as the other renderers.

GitHub-flavored markdown: status header, stats line, results table, and a
collapsible "What broke" section. Posted to PRs by the promptgold GitHub
Action, or written directly with `pytest --promptgold-markdown=summary.md`.
"""

from __future__ import annotations

from promptgold.results import RunResults

MAX_TESTS = 50  # keep the comment readable; GitHub caps at 65k chars
MAX_CHARS = 60_000


def _fmt_cost(cost: float | None) -> str:
    return f"${cost:.4f}" if cost is not None else "—"


def _verdict_cell(t) -> str:
    """Compact verdict cell: run-together repeats become '5× PASS'."""
    if not t.verdicts:
        return "error" if t.error else "—"
    bits = []
    for v in t.verdicts:
        actual = "PASS" if v.actual else "FAIL"
        if v.regressed:
            expected = "PASS" if v.expected else "FAIL"
            cell = f"~~{expected}~~ **{actual}**"
        else:
            cell = actual
        if bits and bits[-1][0] == cell:
            bits[-1][1] += 1
        else:
            bits.append([cell, 1])
    return ", ".join(f"{n}× {c}" if n > 1 else c for c, n in bits)


def render(run: RunResults) -> str:
    status = "❌" if run.failed else "✅"
    lines = [f"## 🪙 promptgold {status}", ""]

    bits = [f"**{len(run.tests)}** tests", f"**{run.passed}** passed"]
    if run.failed:
        bits.append(f"**{run.failed}** failed")
    if run.total_cost is not None:
        bits.append(_fmt_cost(run.total_cost))
    if run.replayed or run.recorded:
        bits.append(f"{run.replayed} replayed · {run.recorded} recorded")
    lines.append(" · ".join(bits))
    lines.append("")

    lines.append("| test | verdict | cost | source |")
    lines.append("|---|---|---|---|")
    for t in run.tests[:MAX_TESTS]:
        icon = "✅" if t.passed else "❌"
        verdict = _verdict_cell(t)
        name = t.name.replace("|", "\\|")
        lines.append(
            f"| {icon} `{name}` | {verdict} | {_fmt_cost(t.cost_usd)} | {t.cassette} |"
        )
    if len(run.tests) > MAX_TESTS:
        lines.append(f"| … | *{len(run.tests) - MAX_TESTS} more* | | |")

    regressions = [(t, v) for t in run.tests for v in t.verdicts if v.regressed]
    errors = [t for t in run.tests if t.error]
    if regressions or errors:
        lines.append("")
        lines.append("<details><summary>What broke</summary>")
        lines.append("")
        for t, v in regressions:
            expected = "PASS" if v.expected else "FAIL"
            actual = "PASS" if v.actual else "FAIL"
            # Backticks neutralize HTML/pipes inside model-written criteria.
            criterion = v.criterion.replace("`", "'")
            lines.append(f"- **`{t.name}`** — `{criterion}`: {expected} → **{actual}**")
            if v.reason:
                lines.append(f"  - reason now: {v.reason}")
        for t in errors:
            lines.append(f"- **`{t.name}`** — `{t.error}`")
        lines.append("")
        lines.append("</details>")

    lines.append("")
    lines.append("*built by hope only — the hope is now tested*")

    out = "\n".join(lines)
    if len(out) > MAX_CHARS:
        out = out[:MAX_CHARS] + "\n\n*(truncated)*"
    return out
