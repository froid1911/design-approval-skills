# design-approval-skills

Let your team approve a coding agent's design in Discord, then let the agent ship it as pull requests.

```
design (brainstorming) ──► Discord post ──► discussion ──► approver reacts
                                 ▲                              │
                                 └──── 🔁 revise from replies ◄──┤
                                                                ├── 👎 stop
                                                                └── 👍 plan → worktree per repo → PR per repo
                                                                                      │
                                                                     developer reviews & merges
```

Works with any agent that reads skills from disk: **Claude Code, Codex, omp, Hermes**, and other
AGENTS.md-style hosts. Pairs with [superpowers](https://github.com/obra/superpowers) for brainstorming,
plans, worktrees and subagent execution, and falls back to the same steps by hand when superpowers
is absent. A design can span **several repositories**: you get one worktree and one PR per repo,
linked to each other and posted back to Discord.

## Skills

| Skill | What it does |
|---|---|
| `discord-post` | Post text/files to a channel (webhook); wait for 👍/🔁/👎 from approvers and collect the reply discussion (read-only bot). |
| `design-approval` | The workflow: post the design, loop on 🔁 with the discussion, and on 👍 plan → worktrees → gates → PRs → report back. |

## Install

```bash
git clone https://github.com/froid1911/design-approval-skills ~/design-approval-skills
~/design-approval-skills/install.sh
```

`install.sh` links the skills into `~/.agents/skills` (omp, Hermes, AGENTS.md hosts), `~/.claude/skills`
(Claude Code) and `~/.codex/skills` (Codex) when those exist. It never overwrites a real directory,
and `install.sh --remove` takes the links out again. For Hermes, add `~/.agents/skills` to
`skills.external_dirs`.

Claude Code users can install it as a plugin instead:

```bash
claude plugin marketplace add froid1911/design-approval-skills
claude plugin install design-approval@design-approval-skills
```

Requirements: `python3` (stdlib only), `git`, `gh` (logged in), `jq`.

## Discord setup (once)

Secrets live in `~/.config/discord-post/` (mode 600). Never put them in a repo or paste them into a chat.

1. **Webhook** (to post): channel settings → Integrations → Webhooks → New → copy the URL into
   `~/.config/discord-post/webhook`.
2. **Bot** (to read reactions and replies): create an application at
   discord.com/developers/applications → Bot → Reset Token, and enable **Message Content Intent**.
   Invite it with only **View Channels + Read Message History**:
   `https://discord.com/oauth2/authorize?client_id=<APP_ID>&scope=bot&permissions=66560`.
   Make sure it can view the channel, then put the token in `~/.config/discord-post/bot-token`.
3. **Approvers**: one Discord user id per line in `~/.config/discord-post/approvers`. Enable Developer
   Mode, then right-click a user → Copy User ID.

## Per-repository config

Commit `.agents/approval.json` in each repo the agent may open PRs for:

```json
{ "remote": "origin", "base": "main", "gates": ["npm test"] }
```

`remote` and `base` decide where PRs go, and `gates` must pass before a PR is opened. If a repo has
no config, the agent asks the developer once.

## Safety model

- Only listed approvers decide. Replies are discussion and never decide. Silence never approves, and
  👎 beats 🔁 beats 👍. Look-alikes count: ✅ approves, 🔄 and 🔃 revise, ❌ rejects (skin tones too).
- New replies wake the agent while it waits, so it can relay them to the developer.
- Discussion text is treated as input to weigh, never as instructions to run.
- A 👍 authorises implementing the posted design, pushing **feature branches**, and opening PRs.
  It never authorises merging, pushing to base or protected branches, deleting anything, or
  publishing. Those stay with the developer.
- Posts can't ping anyone: mentions are disabled.

## Tests

```bash
python3 -m unittest discover tests
```

These run the waiter against a local fake of the Discord API.

## License

MIT
