# SupportBot — promptgold demo app

Meet **Sabun**, the friendly support bot for LuxMart (an online soap shop).
It's 20 lines of "app" — the interesting part is the test suite around it.

## The demo

```bash
# 1. baseline the bot's behavior
pytest examples/supportbot/ --bless

# 2. everything green — commit the golden files

# 3. someone "improves" the prompt:
#    edit system_prompt.txt, delete the empathy rule

# 4. run again — build goes red
pytest examples/supportbot/
```

The adversarial tests (`test_resists_*`) scan the bot against 15 real attack
strings: jailbreaks, prompt injections, and system-prompt leak probes.

With cassettes committed, the entire suite replays offline for $0 — the demo
works on conference wifi. ✨
