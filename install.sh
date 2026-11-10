#!/bin/sh
# Link the skills in this repo into every agent host found on this machine.
#   ./install.sh            link (idempotent; never overwrites a real directory)
#   ./install.sh --remove   remove the links this script made
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
MODE=${1:-link}

link_into() {  # $1 = skills dir of a host
  dir=$1
  mkdir -p "$dir"
  for skill in "$HERE"/skills/*/; do
    name=$(basename "$skill"); target="$dir/$name"
    if [ "$MODE" = "--remove" ]; then
      [ -L "$target" ] && [ "$(readlink -f "$target")" = "$(readlink -f "$skill")" ] && rm "$target" && echo "removed $target"
      continue
    fi
    if [ -L "$target" ]; then
      ln -sfn "${skill%/}" "$target"
    elif [ -e "$target" ]; then
      echo "skip $target: exists and is not a link (move it away to install)"; continue
    else
      ln -s "${skill%/}" "$target"
    fi
    echo "linked $target"
  done
}

link_into "$HOME/.agents/skills"                         # omp, Hermes (via external_dirs), AGENTS.md hosts
[ -d "$HOME/.claude" ] && link_into "$HOME/.claude/skills"  # Claude Code
[ -d "$HOME/.codex" ] && link_into "$HOME/.codex/skills"    # Codex

if [ "$MODE" != "--remove" ]; then
  mkdir -p "$HOME/.config/discord-post" && chmod 700 "$HOME/.config/discord-post"
  cat <<MSG

Next:
  - Hermes: hermes config set skills.external_dirs '["~/.agents/skills"]'  (append if you already have entries)
  - Discord setup (webhook, bot, approvers): see skills/discord-post/SKILL.md → Setup
  - Restart your agent sessions so they pick up the skills.
MSG
fi
