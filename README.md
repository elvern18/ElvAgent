# ElvAgent

An autonomous AI agent you control via Telegram. It publishes hourly AI newsletters, writes code, manages GitHub PRs, and holds conversations — all running as a single always-on process.

## Overview

ElvAgent runs four concurrent sub-agents inside one async event loop:

| Agent | What it does |
|---|---|
| **NewsletterAgent** | Researches AI news from 4 sources, ranks and deduplicates, then publishes to Telegram, Discord, Twitter, and Markdown every hour |
| **TelegramAgent** | Accepts commands and free-text messages from the owner; routes to the right handler |
| **TaskWorker** | Processes queued tasks — coding jobs, newsletter triggers, status checks |
| **GitHubMonitor** | Polls open PRs and dispatches to PR Describer, CI Fixer, and Code Reviewer workers |

All four agents share a SQLite state store and an in-memory conversation context (MemoryStore), coordinated by a top-level **MasterAgent**.

## Features

- **Telegram-first interface** — command the agent from your phone with slash commands or natural language
- **Autonomous coding** — send a task via `/code`; the agent clarifies requirements, plans, implements with tool use, runs tests, and opens a PR
- **Hourly AI newsletter** — parallel research from ArXiv, HuggingFace, Reddit, and TechCrunch; AI-enhanced headlines and takeaways; multi-platform publishing
- **GitHub automation** — auto-generates PR descriptions, reviews code, and fixes failing CI
- **Persistent memory** — conversation history per chat, plus long-term key-value facts via `/remember` and `/recall`
- **Smart routing** — free-text messages are classified by Haiku as coding tasks or conversation, then routed accordingly
- **Cost optimised** — Haiku for classification/planning, Sonnet for execution; targets < $3/day

## Telegram Commands

| Command | Description |
|---|---|
| `/start` | Greeting and welcome message |
| `/help` | Show all available commands |
| `/status` | Current agent status |
| `/newsletter` | Trigger a newsletter cycle immediately |
| `/code <instruction>` | Queue an autonomous coding task |
| `/remember <key> <value>` | Persist a fact (e.g. `/remember default_repo /path/to/repo`) |
| `/recall [key]` | Retrieve a fact, or list all stored facts |
| `/new_chat` | Clear conversation history and start fresh |

**Free-text messages** are automatically classified:
- Coding/programming requests are queued as `/code` tasks
- Questions and conversation are answered directly by Sonnet with full chat history

## Capabilities

### Autonomous Coding

The coding pipeline runs in three phases:

1. **Clarify** (Haiku) — checks if the instruction is ambiguous; asks follow-up questions via Telegram if needed, with a 10-minute timeout
2. **Plan** (Haiku) — generates a concise implementation plan
3. **Execute** (Sonnet with tool use) — implements the plan using filesystem, shell, and git tools

After execution, the agent runs `pytest`. If tests pass, it pushes a branch and opens a PR. If they fail, it keeps the branch locally and reports the failure.

**Safety measures:**
- Tool results capped at 20K characters to prevent token explosion
- Sliding window keeps only the last 10 message pairs in context
- Noisy directories (`.venv`, `.git`, `node_modules`, etc.) are excluded from all file operations

### Newsletter Pipeline

```
Research (4 parallel sources)
  ├── ArXiv         — latest AI/ML papers
  ├── HuggingFace   — trending models and datasets
  ├── Reddit         — r/MachineLearning, r/LocalLLaMA, etc.
  └── TechCrunch    — AI startup news and funding
        ↓
Filter & Deduplicate (SHA-256 fingerprints in SQLite)
        ↓
Rank by relevance and novelty
        ↓
AI Enhancement (headlines, takeaways, engagement hooks)
        ↓
Format per platform (Telegram, Discord, Twitter, Markdown)
        ↓
Publish in parallel → Record metrics
```

Skips publishing if fewer than 3 significant items are found.

### GitHub Automation

When `GITHUB_TOKEN` is configured, the GitHubMonitor polls open PRs and dispatches to three workers:

| Worker | Trigger | Action |
|---|---|---|
| **PRDescriber** | PR has no description | Generates a summary from the diff |
| **CIFixer** | CI checks failing | Reads logs, applies a fix, pushes, retries (up to N attempts) |
| **CodeReviewer** | PR needs review | Posts review comments on the diff |

### Conversation

Free-text messages that aren't coding tasks get a direct Sonnet reply using the full conversation history from MemoryStore. History is persistent until the user sends `/new_chat`.

Long-term facts are stored separately in SQLite via `/remember` and `/recall` — these survive chat resets.

## Architecture

```
MasterAgent (asyncio.gather)
  ├── NewsletterAgent      polls every 55 min
  │     └── Orchestrator   research → filter → enhance → publish → record
  ├── GitHubMonitor        polls every 60s (configurable)
  │     ├── PRDescriber
  │     ├── CIFixer
  │     └── CodeReviewer
  ├── TaskWorker           polls every 5s
  │     ├── CodeHandler    → CodeTool (clarify → plan → execute → test → PR)
  │     ├── NewsletterHandler
  │     └── StatusHandler
  └── TelegramAgent        long-poll via python-telegram-bot
        ├── Command handlers   /start /help /status /newsletter /code ...
        ├── Haiku classifier   routes free text → code queue or Sonnet reply
        └── MemoryStore        persistent per-chat conversation context
```

All agents inherit from **AgentLoop**, which implements a ReAct loop: `poll → triage → act → record`.

### Tools Available to the Coding Agent

| Tool | Description |
|---|---|
| `read_file` | Read file contents (capped at 20K chars, excludes noisy dirs) |
| `write_file` | Create or overwrite a file |
| `list_directory` | List directory contents (excludes `.venv`, `.git`, etc.) |
| `run_shell` | Execute shell commands (stdout + stderr capped at 20K chars each) |
| `create_branch` | Create a git branch (auto-retries with timestamp suffix on collision) |
| `commit_and_push` | Stage, commit, and push changes |
| `create_pull_request` | Open a PR via the GitHub API |

## Quick Start

### Prerequisites

- Python 3.11+
- A Telegram bot token (from [@BotFather](https://t.me/BotFather))
- An Anthropic API key

### Setup

```bash
# Clone and enter the repo
git clone https://github.com/elvern18/ElvAgent.git
cd ElvAgent

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys (ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_OWNER_ID)

# Initialise the database
python -c "from src.core.state_manager import StateManager; import asyncio; asyncio.run(StateManager().init_db())"
```

### Running

```bash
# Full personal assistant mode (newsletter + Telegram + GitHub + task worker)
python src/main.py --mode=pa --verbose

# Newsletter test cycle only (no publishing)
python src/main.py --mode=test --verbose

# GitHub monitor only
python src/main.py --mode=github-monitor

# Production newsletter cycle (publishes to all platforms)
python src/main.py --mode=production
```

### Deploy as a Service (Linux)

```bash
./scripts/setup_systemd.sh
systemctl --user status elvagent
```

### Run Tests

```bash
source .venv/bin/activate
pytest tests/ -v          # 442 tests
```

## Configuration

Key environment variables (see `.env.example` for the full list):

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Claude API access |
| `TELEGRAM_BOT_TOKEN` | Yes (PA mode) | Telegram bot token from BotFather |
| `TELEGRAM_OWNER_ID` | Yes (PA mode) | Your Telegram user ID (authorisation gate) |
| `GITHUB_TOKEN` | Optional | Enables GitHub automation |
| `DATABASE_PATH` | Optional | SQLite path (default: `data/state.db`) |
| `MAX_DAILY_COST` | Optional | Budget guard (default: $5) |
| `DISCORD_WEBHOOK_URL` | Optional | Discord publishing |
| `TWITTER_API_KEY` | Optional | Twitter/X publishing |

## Tech Stack

- **Python 3.11+** with asyncio
- **Claude API** (Haiku for classification/planning, Sonnet for execution)
- **python-telegram-bot** v20+ async API
- **SQLite** for state, deduplication, metrics, and task queue
- **pytest** (442 tests) with ruff linting and mypy type checking

## Documentation

- **[Development Status](docs/STATUS.md)** — current progress and next steps
- **[Project Structure](docs/PROJECT_STRUCTURE.md)** — complete file organisation
- **[Testing Guide](docs/TESTING_GUIDE.md)** — testing best practices
- **[Developer Guide](.claude/CLAUDE.md)** — development guidelines and architecture details

## License

MIT
