# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ElvAgent is an autonomous AI newsletter agent that curates and publishes AI news hourly across multiple platforms (Discord, X, Instagram, Telegram, Markdown). Built to demonstrate Claude Code best practices including MCP servers, skills, and subagents.

## ⚠️ CRITICAL: Always Use Virtual Environment

**IMPORTANT:** This project uses a Python virtual environment at `.venv/`.

**ALWAYS activate it before running ANY Python command:**

```bash
# Activate virtual environment (do this first!)
source .venv/bin/activate

# Verify it's active (should show .venv path)
which python
```

**All commands below assume .venv is activated.**

If you see `ModuleNotFoundError`, you forgot to activate the venv!

## Common Commands

### Development
```bash
# ALWAYS activate venv first!
source .venv/bin/activate

# Install dependencies (first time only)
pip install -r requirements.txt

# Run single test cycle (doesn't publish)
python src/main.py --mode=test --verbose

# Run tests
pytest tests/

# Run specific test file
pytest tests/unit/test_researchers.py -v

# Run foundation test script
python scripts/test_foundation.py
```

### Database
```bash
# Activate venv first!
source .venv/bin/activate

# Initialize database
python -c "from src.core.state_manager import StateManager; import asyncio; asyncio.run(StateManager().init_db())"

# Query published items (doesn't need venv)
sqlite3 data/state.db "SELECT * FROM published_items ORDER BY published_at DESC LIMIT 10;"

# Check metrics (doesn't need venv)
sqlite3 data/state.db "SELECT * FROM api_metrics WHERE date = date('now');"
```

### launchd (Mac Mini)
```bash
# Install service
./scripts/setup_launchd.sh

# Check status
launchctl print gui/$(id -u)/com.elvagent.newsletter

# View logs
tail -f logs/stdout.log

# Manual trigger
launchctl kickstart -k gui/$(id -u)/com.elvagent.newsletter
```

## Architecture Principles

### Component Hierarchy
1. **Orchestrator** (`src/core/orchestrator.py`) - Top-level coordinator
2. **Pipeline** (`src/core/content_pipeline.py`) - Multi-stage processing
3. **Researchers** (`src/research/`) - Content fetching (parallel subagents)
4. **Publishers** (`src/publishing/`) - Multi-platform distribution
5. **MCP Servers** (`src/mcp_servers/`) - External capabilities for Claude

### Key Patterns

**Base Classes:** All researchers inherit from `BaseResearcher`, all publishers from `BasePublisher`. This ensures consistent interface and behavior.

**Subagent Usage:**
- Use subagents for research (4 parallel sources) to keep main context clean
- Subagents return summarized findings, not raw data
- Model selection: Haiku for simple tasks, Sonnet for analysis

**MCP Servers:**
- Database MCP: All state queries go through MCP tools (not direct SQL)
- Social Media MCP: Unified interface for all platforms
- Use OAuth 2.1 for authentication

**Skills:**
- Load on-demand only (saves context)
- Each skill is self-contained with clear inputs/outputs
- Research skills return JSON for easy parsing

**Error Handling:**
- Use exponential backoff for retries (tenacity library)
- Circuit breaker pattern for platform failures
- Partial failure handling (don't fail entire batch if one platform fails)

**Cost Optimization:**
- Target: <$3/day
- Use Haiku for formatting, Sonnet for summarization
- Cache API responses (15-min TTL)
- Track costs in `api_metrics` table

### Database Schema

**Deduplication:** Content fingerprints use SHA-256 hash of normalized URL + title. Always check `content_fingerprints` table before adding to queue.

**Metrics Tracking:** Every API call logs to `api_metrics` table with token count and estimated cost.

### File Naming Conventions

- Researchers: `{source}_researcher.py` (e.g., `arxiv_researcher.py`)
- Publishers: `{platform}_publisher.py` (e.g., `discord_publisher.py`)
- Skills: `.claude/skills/{skill-name}/SKILL.md` (kebab-case)
- Subagents: `.claude/agents/{agent-name}.md` (kebab-case)

### Testing

- Unit tests: Test individual functions in isolation
- Integration tests: Test component interactions (e.g., research → filter → rank)
- Fixtures: Use `tests/fixtures/sample_data.py` for test data
- Mocking: Mock external APIs (Twitter, Instagram, DALL-E) in tests

### Critical Paths

**src/core/orchestrator.py:run_hourly_cycle()**
- Main entry point for hourly execution
- Spawns 4 research subagents in parallel
- Implements skip logic (if <3 significant items)
- Coordinates all pipeline stages

**src/mcp_servers/database_server.py**
- Provides Claude with database query capabilities
- Tools: `check_duplicate`, `store_content`, `get_metrics`
- Used by all components for state management

### Common Pitfalls

1. **Don't fill context:** Use subagents for research, not direct scraping in main context
2. **Check duplicates early:** Query database before processing content
3. **Normalize URLs:** Remove tracking parameters before fingerprinting
4. **Respect rate limits:** Each platform has different limits (see `src/utils/rate_limiter.py`)
5. **Use full paths in launchd:** Relative paths won't work in background execution

### Adding New Features

**New Content Source:**
1. Create `src/research/{source}_researcher.py` inheriting from `BaseResearcher`
2. Create `.claude/skills/research-{source}/SKILL.md`
3. Add to orchestrator's `spawn_research_agents()`
4. Update tests

**New Publishing Platform:**
1. Create `src/publishing/{platform}_publisher.py` inheriting from `BasePublisher`
2. Create `src/publishing/formatters/{platform}_formatter.py`
3. Add platform to `src/mcp_servers/social_media_server.py`
4. Update orchestrator's `publish_all()`
5. Add credentials to `.env`

## Environment Variables

See `.env.example` for all required variables. Critical ones:
- `ANTHROPIC_API_KEY` - Claude API access
- `DATABASE_PATH` - SQLite database location
- `MAX_DAILY_COST` - Budget guard (default: $5)
- Platform credentials (Discord, Twitter, Instagram, Telegram)

## Git Workflow (Multi-Agent)

- `main` - Production-ready code
- `agent-1-data-layer` - Database & MCP development
- `agent-2-research` - Research layer development
- `agent-3-publishing` - Publishing layer development
- `agent-4-orchestration` - Orchestration & pipeline development

Merge to `main` at end of each phase after integration testing.
