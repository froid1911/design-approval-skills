# Design: Discord design approval → worktree → pull request

Status: agreed 2026-11-10.

## Goal
A developer works with a coding agent (Claude Code, Codex, omp, Hermes, …) with superpowers. When a
design is finished it goes to Discord, the team discusses it there, and an approver decides:
👍 go, 🔁 revise from the discussion, 👎 stop. On 👍 the agent one-shots the design on git
worktrees and opens pull requests, which the developer reviews and merges.

## Decisions
- **Agent-agnostic**: plain-markdown skills in `~/.agents/skills` with links for each host; scripts are
  python3 stdlib.
- **Posting**: Discord webhook. Webhooks cannot reply, so later posts link back (`--link-to`).
- **Reading**: a read-only bot (View Channels + Read Message History, Message Content intent). A
  webhook can't read.
- **Decision**: approver reactions only. Replies are discussion, collected through reply chains. The
  approver ends the discussion with 🔁; a first reply or a quiet period doesn't. 👎 > 🔁 > 👍.
- **Multi-repo**: the spec lists its repositories and merge order; one worktree and one PR per repo,
  with sibling PRs cross-linked.
- **PR target**: per-repo `.agents/approval.json` (remote, base, gates). If it's missing, ask once.
- **State**: `~/.local/state/design-approval/<topic>.json`, so a wait survives a new session and
  repos stay clean.
- **Authority**: a 👍 covers implementing, pushing feature branches and opening PRs. Never merge,
  base-branch pushes, deletion or publishing.
- **Failure**: no PR for a repo whose gates fail; partial results are reported as partial.

## Not now
Threads (webhooks can only create them in forum channels), auto-addressing PR review comments,
publishing to the omp skill registry.
