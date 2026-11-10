# Forum threads and readable posts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One Discord forum post per design, with readable message templates.

**Architecture:** `post.py` gains `--thread-name`/`--thread` on webhook execute; `wait_approval.py` treats every non-webhook message in a thread as discussion; design-approval uses both and fixes three message templates.

**Tech Stack:** Python 3 stdlib, unittest with a fake Discord API (`http.server`).

**Spec:** docs/specs/2026-11-10-forum-threads-and-readable-posts.md

## Global Constraints

- Standard library only. Gate: `python3 -m unittest discover tests`.
- Text-channel fallback triggers on HTTP 400 with code `220003` ("Webhooks can only create threads in forum channels"), confirmed against Discord 2026-11-10.
- No Claude attribution in commits or PRs.

---

### Task 1: post.py threads

**Files:** Modify `skills/discord-post/post.py`. Create `tests/test_post.py`.

- [ ] Write tests (fake webhook endpoint; `DISCORD_API` env rewrites `https://discord.com/api` so the URL check still applies to real URLs):
  - `--thread-name T --json` against a forum webhook sends `thread_name: T`, prints `thread_id` = returned `channel_id`, and `url` uses that channel.
  - `--thread 77` sends `?thread_id=77` and no `thread_name`.
  - A text-channel webhook answering 400/220003 to `thread_name`: the post is resent without it and `--json` prints `"thread_id": null`.
- [ ] Run, watch fail. Implement. Run, pass. Commit.

### Task 2: wait_approval.py in a thread

**Files:** Modify `skills/discord-post/wait_approval.py`, `tests/test_wait_approval.py`.

- [ ] Write tests (fake channel lookup returns `type`; messages carry `webhook_id`):
  - In a thread (type 11), a non-reply message newer than `--message` is discussion; webhook messages are not.
  - In a thread, reactions on an older version's message do not decide.
  - Existing text-channel tests stay green.
- [ ] Run, watch fail. Implement. Run, pass. Commit.

### Task 3: docs and templates

**Files:** `skills/discord-post/SKILL.md`, `skills/design-approval/SKILL.md`, `README.md`, `docs/design.md`.

- [ ] discord-post: document `--thread-name`, `--thread`, `thread_id`, thread discussion, forum setup.
- [ ] design-approval: step 2 creates the forum post and stores `thread_id`; steps 3, 4, 9 use the thread; the three templates from the spec, plus "dry-run first".
- [ ] README setup; `docs/design.md` moves threads out of "Not now".
- [ ] Commit.
