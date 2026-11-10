# Design: one forum thread per design, readable posts

Status: proposed 2026-11-10.

## Problem

Every design, revision and PR report is a separate message in one text channel. With several
designs in flight the channel interleaves them, and the `↪ follows <url>` links are the only thing
holding a design's history together. The messages themselves are hard to read: title, summary,
bullets, repos and the reaction legend are consecutive lines with no spacing, no headings, bare
issue numbers and bare URLs.

## Decisions

### 1. A forum post per design (`post.py`)

- The webhook points at a Discord **Forum** channel.
- `--thread-name "<title>"` creates a forum post through the webhook (`thread_name` on execute).
  The returned message's `channel_id` is the new thread's id; `--json` prints it as `thread_id`.
- `--thread <thread_id>` posts into an existing thread (`?thread_id=` on execute).
- Jump URLs use the posted message's own `channel_id`, not the webhook's, so they point inside the
  thread.
- If the webhook points at a text channel, Discord refuses `thread_name`. `post.py` then posts
  without it and prints `"thread_id": null`, so a text-channel setup works as it does today. The
  exact refusal (status and code) is confirmed against Discord during implementation.

### 2. Waiting inside a thread (`wait_approval.py`)

- Reactions count only on the message given by `--message` (the newest version), as today.
- At start, one channel lookup tells whether `--channel` is a thread (types 10, 11, 12). In a
  thread, every message newer than `--message` that the webhook did not send is discussion, whether
  or not it is a Discord reply. In a text channel, discussion stays the reply chain.
- `--return-on-reply` and `--seen` are unchanged.
- No new flags.

### 3. design-approval flow

- Step 2 posts v1 with `--thread-name "<title>"` and stores `thread_id` in the state file.
- Revisions (step 4) and the report (step 9) post with `--thread <thread_id>` and drop
  `--link-to`. Without a `thread_id` (text channel), they keep `--link-to`.
- Waits pass `--channel <thread_id>` when there is one.

### 4. Readable messages

design-approval fixes three templates. Rules for all of them: a `##` heading, a blank line between
sections, `-` bullets, masked links with suppressed previews (`[#3070](<url>)`), and `-#` subtext
for the reaction legend. Check the layout with `post.py --dry-run` before posting.

Design (v1):

```
## 💡 Design v1 · <title>
Fixes [#<n>](<<issue url>>) · <repos>

**Problem**
<one or two sentences>

**Proposal**
- <decision>
- <decision>

**Out of scope**
- <item>

-# 👍 go · 🔁 revise · 👎 stop · discuss in this thread
```

Revision (vN): heading `## 🔁 Design vN · <title>`, then a **Changed** section listing what differs
from the previous version and who asked for it, then the same sections as v1.

Report:

```
## ✅ PRs ready · <title>
1. [<repo>#<n>](<<pr url>>) (merge first)
2. [<repo>#<n>](<<pr url>>)

**Gates**
<one line: new failures or none; pre-existing failures named>
```

A partial result uses `## ⚠️ Partial · <title>` and names each repo without a PR and why.

### 5. Setup

README and discord-post `SKILL.md`: create a Forum channel, add a webhook to it and write its URL
to `~/.config/discord-post/webhook`. The bot needs View Channel and Read Message History on the
forum; it stays read-only.

## Testing

Test first, against the fake Discord API in `tests/` (extended with webhook execute, forum post
creation and thread messages):

- `--thread-name` creates a forum post and `--json` returns its `thread_id`.
- `--thread` posts into that thread; the jump URL points inside it.
- A text-channel webhook refuses `thread_name`; `post.py` falls back and returns `thread_id: null`.
- In a thread, a non-reply message counts as discussion; the webhook's own messages do not.
- In a thread, reactions on an older version's message do not decide.
- In a text channel, discussion is still the reply chain (existing tests stay green).

## Not now

Forum tags for status (waiting, approved, PR open): setting tags on an existing post needs the bot
to have Manage Threads, which ends its read-only role.

## Repositories

| Repo | Path | Changes | Merge order |
|---|---|---|---|
| design-approval-skills | /home/froid/design-approval-skills | post.py, wait_approval.py, both SKILL.md, README, tests | 1 |
