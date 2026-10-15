# LiveKit Outbound Calling Agent

Python telephony agent built on LiveKit for automated outbound SIP calls with AI-driven conversation handling.

## Jira

- Project prefix: `MAAPP` (e.g., `MAAPP-228`)

## Git & PR conventions

CI (`.github/workflows/jira-check.yml`) enforces branch names and PR
titles. PRs that don't match are blocked.

### Branch names

Must contain a Jira ID matching `[A-Z]+-[0-9]+`.

```
Good:  MAAPP-231-claude-workflow-setup
       MAAPP-213
       chore/MAAPP-128-dynamic-turn-detection
       hotfix/MAAPP-301-token-leak
Bad:   chore/claude-workflow-setup        # no Jira ID
       feature/improve-logging            # no Jira ID
```

`.github/PULL_REQUEST_TEMPLATE.md` recommends `type/JIRA-ID-short-description`
as the canonical form. Recent practice is mixed; the regex is the hard rule.

Exempt (no Jira ID needed): `dev → main`, `main → dev`, `hotfix/* → main`.

Targeting `main` is restricted: source must be `dev` or `hotfix/*`. All
feature work merges into `dev` first.

### PR titles

Conventional Commits with the Jira ID in parens. Regex:

```
^(feat|fix|chore|docs|refactor|test|style|perf|ci|build)\([A-Z]+-[0-9]+\)!?: .+
```

```
Good:  feat(MAAPP-234): document git conventions in CLAUDE.md
       fix(MAAPP-228): resolve login timeout
       feat(MAAPP-111)!: redesign auth flow      # breaking change
Bad:   chore: add claude workflow setup           # no (JIRA-ID)
       MAAPP-234: update CLAUDE.md                # missing type()
       feat(maapp-234): ...                       # prefix must be uppercase
```

Append `!` before the colon for breaking changes.

### Release & back-merge PRs (special formats)

These bypass the Conventional Commits rule entirely:

| Source → Target | Title format                            | Example              |
| --------------- | --------------------------------------- | -------------------- |
| `dev → main`    | `^Release: v[0-9]+\.[0-9]+\.[0-9]+$`    | `Release: v1.3.0`    |
| `main → dev`    | `^Back-merge: v[0-9]+\.[0-9]+\.[0-9]+$` | `Back-merge: v1.4.0` |

### Merge methods

| PR                | Method                | Why                                                  |
| ----------------- | --------------------- | ---------------------------------------------------- |
| `feature/* → dev` | Squash and merge      | One commit per ticket on `dev`                       |
| `dev → main`      | Create a merge commit | Preserves shared history; prevents branch divergence |
| `hotfix/* → main` | Squash and merge      | One commit per hotfix; cherry-picked back to `dev`   |

For PRs targeting `main`, the `merge-method-reminder` workflow posts a
reminder comment on PR open.

## Workflow artifacts

Working drafts for the `workflow:write-ticket`, `workflow:impl-planning`,
and `workflow:evaluate-review` skills live in `.artifacts/` (gitignored):

- `.artifacts/tickets/` — Jira ticket drafts (`jira-{TICKET-ID}.md`)
- `.artifacts/plans/`   — implementation plans (`impl-{TICKET-ID}-{slug}.md`)
- `.artifacts/reviews/` — Codex / external code reviews

Source-of-truth lives in Jira (tickets), PR descriptions (plan summaries),
and PR comments (review findings) — not in committed markdown.

## Tech Stack

- Python 3.13+ with `uv` package manager
- LiveKit Agents SDK 1.5.1
- boto3 for S3 uploads (default credential chain from env vars)
- Pydantic v2 for metadata validation
- Deployed to LiveKit Cloud via `livekit/deploy-action`

## Project Structure

```
src/
├── main.py                         # Entrypoint, job lifecycle, shutdown reporting
├── agent.py                        # Assistant agent, tools (transfer, DTMF, end call)
├── core/
│   ├── call_state.py               # Call lifecycle state machine
│   ├── metadata.py                 # Pydantic CallMetadata model
│   ├── ivr_state.py                # IVR navigation state
│   └── voicemail.py                # Voicemail detection
├── services/
│   ├── agent_session_service.py    # AgentSession setup (STT, LLM, TTS)
│   ├── recording_service.py        # S3 recording via LiveKit egress
│   ├── session_report_service.py   # Session report assembly and S3 upload
│   └── sip_utils.py                # SIP data extraction and error classification
├── listeners/
│   └── room_listeners.py           # Room event handlers
└── utils/
    ├── aws_utils.py                # S3 upload via boto3 default credential chain
    ├── settings.py                 # Settings dataclass, env var loading
    ├── logger.py                   # Logger setup
    ├── prompt_loader.py            # Placeholder replacement in prompts
    ├── stream_filters.py           # LLM stream word filtering
    ├── agent_helper.py             # Room deletion helper
    └── constants.py                # SIP maps, transfer types, blocked words
```

## Architecture Notes

- AWS credentials from env vars via boto3 default chain. NOT from job metadata.
- Settings: frozen dataclass in `settings.py`. Required: `SIP_OUTBOUND_TRUNK_ID`, `AGENT_NAME`, `ELEVEN_API_KEY`, `S3_BUCKET_NAME`.
- Dockerfile: `load_settings()` runs at import time. download-files step uses `__build__` placeholders.
- Region: `AWS_REGION` is canonical. Pass explicitly via `_aws_region()` helper to boto3.
- Recording: `api.S3Upload` needs explicit credentials (sent to LiveKit egress). Uses `_required_env()`.

## Lint & Verification

```bash
# Targeted ruff check
uv run ruff check src/main.py --select F821,F823,F841

# Stale reference check
rg "pattern" src/

# Syntax check (no imports)
python -m py_compile src/main.py

# Whitespace/conflict marker check before commit
git diff --check
```

## Deploy

Manual trigger via GitHub Actions:
- Dev: Actions → "Deploy to Dev" → any branch
- Prod: Actions → "Deploy to Production" → main only

## Codex Review

After implementation, run `/codex:review` for automated code review.
Evaluate feedback independently — adopt if correct, push back if not.

## Local Worktree Setup

Claude Code Desktop sessions use git worktrees under `.claude/worktrees/`. If local
testing needs ignored env files, create an untracked `.worktreeinclude` in the repo root
with `src/.env.local`. Do not commit `.worktreeinclude`; `.dockerignore` excludes it and
`.claude/` to keep local secrets out of Docker images.

## Prerequisites

- Node.js 18.18+ (required for Codex CLI and codex-plugin-cc)
- Codex CLI: `npm install -g @openai/codex`
- Codex plugin: `/plugin marketplace add openai/codex-plugin-cc` then `/plugin install codex@openai-codex`
