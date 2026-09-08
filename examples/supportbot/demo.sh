#!/bin/bash
# Demo script for the promptgold GIF: bless -> break -> red -> fix -> green.
# Run inside asciinema from the repo root:
#   asciinema rec -c "bash examples/supportbot/demo.sh" /tmp/promptgold.cast
set -e
cd "$(dirname "$0")/../.."
export TERM=xterm-256color

P=examples/supportbot/system_prompt.txt
PY=./.venv/bin/pytest

type_out() { printf '%s\n' "$1"; sleep 1.2; }

type_out '$ # 1. baseline the bots behavior'
type_out "\$ pytest examples/supportbot/ --bless"
$PY examples/supportbot/ --bless -q 2>&1 | tail -10
sleep 2

type_out ''
type_out '$ # 2. someone "improves" the prompt: deletes the empathy rule'
type_out '$ vi system_prompt.txt   # *delete one line, ship it*'
sed -i '' 's/- Always be empathetic, even when the customer is rude. Acknowledge feelings first./- Be efficient. Answer fast./' $P
sleep 1.5

type_out ''
type_out '$ # 3. run the tests'
type_out '$ pytest examples/supportbot/'
$PY examples/supportbot/ -q 2>&1 | tail -12 || true
sleep 3

type_out ''
type_out '$ # 4. revert the prompt, bless again'
git checkout $P 2>/dev/null || true
type_out '$ pytest examples/supportbot/'
$PY examples/supportbot/ -q 2>&1 | tail -10
sleep 3
