"""Static HTML report renderer — the 'dashboard' you open in a browser.

One self-contained .html file: inline CSS, zero JS dependencies, no CDN —
works offline, attachable to emails/Slack/PRs.

Design language: scrappy punk zine, not SaaS dashboard. Warm paper, tape
corners, rubber stamps, typewriter masthead, marker highlights. The brand is
'built by hope only' — the report should look pasted together by the same
people who spray-painted the motto. Data comes from the same RunResults
model as the terminal output.
"""

from __future__ import annotations

import html
import time

from promptgold.results import RunResults

_CSS = """
:root { --paper: #f3ede0; --ink: #2a2521; --gold: #d4a017; --red: #c95a4e;
        --green: #5a9e7a; --dim: #8a7f70; --card: #faf6ec; --peach: #f6dfc4;
        --mint: #d9e9d4; --lav: #e3dcf0; }
* { box-sizing: border-box; margin: 0; }
body { background: var(--paper); color: var(--ink); padding: 2.5rem 1.5rem;
       font: 15px/1.55 ui-monospace, "SF Mono", Menlo, monospace;
       background-image: repeating-linear-gradient(0deg, transparent,
         transparent 27px, rgba(26,26,26,.03) 28px); }
.wrap { max-width: 880px; margin: 0 auto; }

.masthead { margin-bottom: 2rem; position: relative; }
.masthead .kicker { font-size: .7rem; letter-spacing: 3px; color: var(--dim);
                    text-transform: uppercase; }
.masthead h1 { font-size: 2.6rem; letter-spacing: -1.5px; line-height: 1;
               margin: .2rem 0 .4rem; }
.masthead h1 .coin { display: inline-block; background: var(--gold);
                     border: 2px solid var(--ink); border-radius: 50%;
                     width: 2.2rem; height: 2.2rem; text-align: center;
                     line-height: 2rem; font-size: 1.2rem;
                     box-shadow: 2px 2px 0 var(--ink); margin-right: .4rem;
                     vertical-align: baseline; }
.masthead .rule { border: 0; border-top: 3px solid var(--ink); margin-top: .8rem; }
.masthead .rule + .rule { border-top-width: 1px; margin-top: 3px; }
.masthead .date { position: absolute; right: 0; top: .2rem; color: var(--dim);
                  font-size: .75rem; }

.stats { display: flex; gap: 1.1rem; margin-bottom: 2rem; flex-wrap: wrap; }
.stat { background: var(--card); border: 2px solid var(--ink); padding: .8rem 1.2rem .7rem;
        min-width: 110px; box-shadow: 5px 5px 0 rgba(42,37,33,.7);
        position: relative; }
.stat::before { content: ""; position: absolute; top: -9px; left: 50%;
        width: 44px; height: 14px; margin-left: -22px;
        background: rgba(212,160,23,.4); border: 1px solid rgba(42,37,33,.15);
        transform: rotate(-1.5deg); }
.stat .num { font-size: 1.7rem; font-weight: bold; line-height: 1.1; }
.stat .label { color: var(--dim); font-size: .65rem; text-transform: uppercase;
               letter-spacing: 2px; margin-top: .15rem; }
.stat.tests { background: var(--lav); }
.stat.green { background: var(--mint); } .stat.red { background: var(--peach); }
.stat.gold { background: #f2e5bd; }
.stat.green .num { color: var(--green); } .stat.red .num { color: var(--red); }
.stat.gold .num { color: var(--gold); }

.test { background: var(--card); border: 2px solid var(--ink); margin-bottom: 1.1rem;
        box-shadow: 5px 5px 0 rgba(42,37,33,.7); position: relative; }
.test-head { display: flex; align-items: center; gap: .8rem; padding: .8rem 1rem; }
.stamp { display: inline-block; padding: .2rem .6rem; border: 2.5px solid currentColor;
         border-radius: 4px; font-size: .72rem; font-weight: bold; letter-spacing: 2px;
         transform: rotate(-2.5deg); flex-shrink: 0; }
.stamp.pass { color: var(--green); } .stamp.fail { color: var(--red); }
.test-name { font-weight: bold; }
.meta { margin-left: auto; color: var(--dim); font-size: .78rem; white-space: nowrap; }
.verdicts { border-top: 2px dashed var(--ink); padding: .6rem 1rem .8rem; }
.verdict { padding: .2rem 0; font-size: .86rem; }
.verdict .criterion { color: var(--dim); }
.v-pass { color: var(--green); font-weight: bold; }
.v-fail { color: var(--red); font-weight: bold; }
.regress { background: linear-gradient(transparent 55%, rgba(201,90,78,.35) 55%);
           padding: 0 .2rem; }
.error { color: var(--red); padding: .6rem 1rem; border-top: 2px dashed var(--ink);
         font-size: .85rem; white-space: pre-wrap; }

footer { color: var(--dim); font-size: .75rem; text-align: center; margin-top: 2.4rem; }
footer .motto { color: var(--ink); background: linear-gradient(transparent 40%,
                rgba(212,160,23,.65) 40%); padding: 0 .4rem; font-weight: bold; }
"""


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def _fmt_cost(cost: float | None) -> str:
    return f"${cost:.4f}" if cost is not None else "—"


def _render_test(t) -> str:
    state = "pass" if t.passed else "fail"
    label = "PASS" if t.passed else "FAIL"
    meta_bits = []
    if t.latency_ms:
        meta_bits.append(f"{t.latency_ms / 1000:.1f}s")
    meta_bits.append(_fmt_cost(t.cost_usd))
    if t.cassette != "live":
        meta_bits.append(t.cassette)
    meta_bits.append(_esc(t.model))

    rows = []
    for v in t.verdicts:
        actual = "PASS" if v.actual else "FAIL"
        cls = "v-pass" if v.actual else "v-fail"
        row = f'<div class="verdict"><span class="criterion">{_esc(v.criterion)}</span> '
        if v.regressed:
            expected = "PASS" if v.expected else "FAIL"
            row += f'<span class="{cls} regress">{expected} → {actual}</span>'
        else:
            row += f'<span class="{cls}">{actual}</span>'
        if v.reason:
            row += f' <span class="criterion">— {_esc(v.reason)}</span>'
        row += "</div>"
        rows.append(row)

    error_html = f'<div class="error">{_esc(t.error)}</div>' if t.error else ""
    verdicts_html = f'<div class="verdicts">{"".join(rows)}</div>' if rows else ""

    return f"""
<div class="test">
  <div class="test-head">
    <span class="stamp {state}">{label}</span>
    <span class="test-name">{_esc(t.name)}</span>
    <span class="meta">{' · '.join(meta_bits)}</span>
  </div>
  {verdicts_html}
  {error_html}
</div>"""


def render(run: RunResults) -> str:
    cost = _fmt_cost(run.total_cost)
    cassette = (
        f"{run.replayed} replayed · {run.recorded} recorded"
        if (run.replayed or run.recorded)
        else "all live"
    )
    generated = time.strftime("%Y-%m-%d %H:%M")
    tests_html = "".join(_render_test(t) for t in run.tests)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>promptgold report</title>
<style>{_CSS}</style>
</head>
<body>
<div class="wrap">
<header class="masthead">
  <div class="kicker">test report · pytest for prompts</div>
  <h1><span class="coin">🪙</span>promptgold</h1>
  <span class="date">{generated}</span>
  <hr class="rule"><hr class="rule">
</header>
<div class="stats">
  <div class="stat tests"><div class="num">{len(run.tests)}</div>
    <div class="label">tests</div></div>
  <div class="stat green"><div class="num">{run.passed}</div><div class="label">passed</div></div>
  <div class="stat red"><div class="num">{run.failed}</div><div class="label">failed</div></div>
  <div class="stat gold"><div class="num">{cost}</div><div class="label">cost</div></div>
  <div class="stat"><div class="num" style="font-size:.9rem">{cassette}</div>
    <div class="label">cassettes</div></div>
</div>
{tests_html}
<footer>
  generated by promptgold · <span class="motto">built by hope only</span>
  — the hope is now tested
</footer>
</div>
</body>
</html>
"""
