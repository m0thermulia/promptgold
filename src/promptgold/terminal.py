"""Pretty terminal renderer — ANSI colors, zero dependencies.

Respects NO_COLOR (https://no-color.org) and non-TTY output (CI logs get
plain text). This is the 'dashboard in the terminal': per-test lines plus a
summary box.
"""

from __future__ import annotations

import os
import sys

from promptgold.results import PromptTestResult, RunResults

GOLD = "\033[33m"
GREEN = "\033[32m"
RED = "\033[31m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"

WIDTH = 60


def _colors_enabled() -> bool:
    if os.environ.get("NO_COLOR") is not None:
        return False
    return sys.stdout.isatty()


class _Painter:
    def __init__(self, enabled: bool):
        self.enabled = enabled

    def __call__(self, text: str, *styles: str) -> str:
        if not self.enabled or not styles:
            return text
        return "".join(styles) + text + RESET


def _fmt_cost(cost: float | None) -> str:
    return f"${cost:.4f}" if cost is not None else "—"


def render_line(t: PromptTestResult, paint: _Painter) -> str:
    icon = paint("✓", GREEN, BOLD) if t.passed else paint("✗", RED, BOLD)
    meta = []
    if t.latency_ms:
        meta.append(f"{t.latency_ms / 1000:.1f}s")
    meta.append(_fmt_cost(t.cost_usd))
    if t.cassette != "live":
        meta.append(f"({t.cassette})")
    return f" {icon} {t.name:<34} {paint(' '.join(meta), DIM)}"


def render(run: RunResults, use_color: bool | None = None) -> str:
    paint = _Painter(_colors_enabled() if use_color is None else use_color)
    lines = []
    title = " promptgold "
    pad = (WIDTH - len(title)) // 2
    lines.append(paint("─" * pad + title + "─" * (WIDTH - pad - len(title)), GOLD))

    for t in run.tests:
        lines.append(render_line(t, paint))
        for v in t.verdicts:
            if v.regressed:
                old = "PASS" if v.expected else "FAIL"
                new = "PASS" if v.actual else "FAIL"
                lines.append(
                    paint(f"    {v.criterion!r}: {old} → {new}", RED)
                )
        if t.error:
            lines.append(paint(f"    {t.error}", RED))

    lines.append(paint("─" * WIDTH, GOLD))
    summary = (
        f" {len(run.tests)} tests · {paint(f'{run.passed} passed', GREEN)} · "
        f"{paint(f'{run.failed} failed', RED) if run.failed else '0 failed'}"
    )
    extras = []
    if run.total_cost is not None:
        extras.append(_fmt_cost(run.total_cost))
    if run.recorded or run.replayed:
        extras.append(f"{run.replayed} replayed, {run.recorded} recorded")
    if extras:
        summary += paint(" · " + " · ".join(extras), DIM)
    lines.append(summary)
    return "\n".join(lines)
