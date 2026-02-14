# ElvAgent Project Structure

**Generated:** 2026-02-15
**Status:** Phase 1 Foundation - 45% Complete

---

## Directory Tree

```
ElvAgent/
├── .claude/                          # Claude Code configuration
│   ├── CLAUDE.md                     # Development guidelines
│   ├── agents/
│   │   └── content-researcher.md     # Research subagent spec
│   └── skills/
│       └── research-arxiv/
│           └── SKILL.md              # ArXiv research skill
│
├── data/                             # Data storage
│   ├── images/                       # Generated images (future)
│   ├── newsletters/                  # Published markdown files (future)
│   └── state.db                      # SQLite database (created on init)
│
├── logs/                             # Application logs
│   └── stdout.log                    # Main log file (production)
│
├── scripts/                          # Utility scripts
│   └── test_foundation.py            # Foundation test suite ✓
│
├── src/                              # Source code
│   ├── __init__.py
│   ├── main.py                       # Main entry point ✓
│   │
│   ├── config/                       # Configuration
│   │   ├── __init__.py
│   │   ├── settings.py               # Pydantic settings ✓
│   │   └── constants.py              # Application constants ✓
│   │
│   ├── core/                         # Core functionality
│   │   ├── __init__.py
│   │   ├── state_manager.py          # Database operations ✓
│   │   ├── orchestrator.py           # Main coordinator (TODO)
│   │   └── content_pipeline.py       # Pipeline stages (TODO)
│   │
│   ├── research/                     # Content researchers
│   │   ├── __init__.py
│   │   ├── base.py                   # BaseResearcher class ✓
│   │   ├── arxiv_researcher.py       # ArXiv papers ✓
│   │   ├── huggingface_researcher.py # HF papers (TODO)
│   │   ├── funding_researcher.py     # Funding news (TODO)
│   │   └── ai_news_researcher.py     # General news (TODO)
│   │
│   ├── analysis/                     # Content analysis
│   │   ├── content_filter.py         # Deduplication (TODO)
│   │   ├── content_ranker.py         # Importance scoring (TODO)
│   │   └── summarizer.py             # Claude summarization (TODO)
│   │
│   ├── publishing/                   # Multi-platform publishers
│   │   ├── __init__.py
│   │   ├── base.py                   # BasePublisher class ✓
│   │   ├── markdown_publisher.py     # Markdown files (TODO)
│   │   ├── discord_publisher.py      # Discord webhooks (TODO)
│   │   ├── twitter_publisher.py      # X/Twitter (TODO)
│   │   ├── instagram_publisher.py    # Instagram reels (TODO)
│   │   ├── telegram_publisher.py     # Telegram (TODO)
│   │   └── formatters/               # Platform-specific formatting (TODO)
│   │
│   ├── media/                        # Media generation
│   │   ├── image_generator.py        # AI image generation (TODO)
│   │   └── video_creator.py          # Reel creation (TODO)
│   │
│   ├── mcp_servers/                  # MCP servers for Claude
│   │   ├── database_server.py        # SQLite MCP (TODO - HIGH PRIORITY)
│   │   ├── filesystem_server.py      # File ops MCP (TODO)
│   │   ├── web_scraper_server.py     # Web scraping MCP (TODO)
│   │   └── social_media_server.py    # Social APIs MCP (TODO)
│   │
│   └── utils/                        # Utilities
│       ├── __init__.py
│       ├── logger.py                 # Structured logging ✓
│       ├── cost_tracker.py           # API cost tracking ✓
│       ├── rate_limiter.py           # Token bucket rate limiter ✓
│       └── retry.py                  # Exponential backoff ✓
│
├── tests/                            # Test suite
│   ├── __init__.py
│   ├── unit/                         # Unit tests (TODO)
│   ├── integration/                  # Integration tests (TODO)
│   └── fixtures/                     # Test fixtures (TODO)
│
├── .env.example                      # Environment variables template ✓
├── .gitignore                        # Git ignore rules ✓
├── CLAUDE.md                         # → .claude/CLAUDE.md
├── IMPLEMENTATION_PROGRESS.md        # Current progress report ✓
├── PROJECT_STRUCTURE.md              # This file ✓
├── README.md                         # Project overview ✓
├── STATUS.md                         # Development status ✓
├── requirements.txt                  # Python dependencies ✓
└── com.elvagent.newsletter.plist     # launchd config (TODO)
```

---

## Component Status Legend

- ✓ **Complete:** Implemented and tested
- **TODO:** Not yet implemented
- **TODO - HIGH PRIORITY:** Blocks other work

---

## File Breakdown by Category

### Configuration (4 files) - 100% Complete
- ✓ `.env.example` - Environment variable template
- ✓ `requirements.txt` - Python dependencies
- ✓ `src/config/settings.py` - Pydantic settings
- ✓ `src/config/constants.py` - Application constants

### Documentation (6 files) - 100% Complete
- ✓ `.claude/CLAUDE.md` - Development guidelines
- ✓ `README.md` - Project overview
- ✓ `STATUS.md` - Current progress
- ✓ `IMPLEMENTATION_PROGRESS.md` - Detailed progress
- ✓ `PROJECT_STRUCTURE.md` - This file
- ✓ `.gitignore` - Git ignore rules

### Core Infrastructure (4/6 files) - 67% Complete
- ✓ `src/core/state_manager.py` - Database operations (393 lines)
- ✓ `src/utils/logger.py` - Structured logging (95 lines)
- ✓ `src/utils/cost_tracker.py` - Cost tracking (190 lines)
- ✓ `src/utils/rate_limiter.py` - Rate limiting (130 lines)
- ✓ `src/utils/retry.py` - Retry logic (188 lines)
- `src/core/orchestrator.py` - TODO

### Research Layer (2/5 files) - 40% Complete
- ✓ `src/research/base.py` - Base class (227 lines)
- ✓ `src/research/arxiv_researcher.py` - ArXiv (215 lines)
- `src/research/huggingface_researcher.py` - TODO
- `src/research/funding_researcher.py` - TODO
- `src/research/ai_news_researcher.py` - TODO

### Publishing Layer (1/7 files) - 14% Complete
- ✓ `src/publishing/base.py` - Base class (218 lines)
- `src/publishing/markdown_publisher.py` - TODO
- `src/publishing/discord_publisher.py` - TODO
- `src/publishing/twitter_publisher.py` - TODO
- `src/publishing/instagram_publisher.py` - TODO
- `src/publishing/telegram_publisher.py` - TODO
- `src/publishing/formatters/` - TODO

### MCP Servers (1/4 files) - 25% Complete
- ✓ `src/mcp_servers/database_server.py` - Database MCP server (321 lines)
- `src/mcp_servers/filesystem_server.py` - TODO
- `src/mcp_servers/web_scraper_server.py` - TODO
- `src/mcp_servers/social_media_server.py` - TODO

### Skills & Agents (2/6 files) - 33% Complete
- ✓ `.claude/skills/research-arxiv/SKILL.md` - ArXiv skill
- ✓ `.claude/agents/content-researcher.md` - Research agent
- `research-huggingface/SKILL.md` - TODO
- `research-funding/SKILL.md` - TODO
- `content-curation/SKILL.md` - TODO
- `publish-newsletter/SKILL.md` - TODO
- `generate-reel-image/SKILL.md` - TODO

### Tests (3/4 categories) - 75% Complete
- ✓ `scripts/test_foundation.py` - Foundation tests (210 lines)
- ✓ `tests/unit/test_state_manager.py` - State manager tests (9 tests)
- ✓ `tests/unit/test_database_server.py` - MCP server tests (7 tests)
- ✓ `tests/conftest.py` - Shared fixtures (154 lines)
- `tests/integration/` - TODO

### Entry Points (1/1 files) - 100% Complete
- ✓ `src/main.py` - Main application (88 lines)

---

## Total Statistics

- **Total Files Created:** 26
- **Python Files:** 15 (10 complete, 5 TODO)
- **Markdown Files:** 6 (all complete)
- **Configuration Files:** 3 (all complete)
- **Lines of Code (Written):** ~2,100
- **Lines of Code (Planned):** ~5,000+

---

## Git Branch Structure

```
main (base)
  ├── agent-1-data-layer (+1 commit)
  │   └── Data layer complete
  │       - State manager
  │       - All utilities
  │       - Base classes
  │
  ├── agent-2-research (+2 commits, merged from agent-1)
  │   └── Research foundation
  │       - ArXiv researcher
  │       - Research skill
  │       - Researcher agent spec
  │       - Main entry point
  │       - Test suite
  │
  ├── agent-3-publishing (base)
  │   └── Not started
  │
  └── agent-4-orchestration (base)
      └── Not started
```

---

## Database Schema (SQLite)

### Tables Created

1. **published_items**
   - Tracks all published content
   - Fields: content_id, source, title, url, published_at, newsletter_date, category, metadata
   - Indexes: content_id, published_at

2. **newsletters**
   - Newsletter publication history
   - Fields: date, item_count, platforms_published, skip_reason, created_at

3. **publishing_logs**
   - Per-platform publishing status
   - Fields: newsletter_id, platform, status, error_message, attempt_count, published_at

4. **api_metrics**
   - API usage and cost tracking
   - Fields: date, api_name, request_count, token_count, estimated_cost
   - Unique constraint: (date, api_name)

5. **content_fingerprints**
   - SHA-256 based deduplication
   - Fields: content_hash, first_seen, source

---

## Key Design Patterns Used

### 1. Abstract Base Classes
- `BaseResearcher` - Template for all researchers
- `BasePublisher` - Template for all publishers
- Ensures consistent interfaces
- Enables polymorphism

### 2. Async/Await Throughout
- All I/O operations are async
- Better concurrency for parallel work
- Modern Python best practice

### 3. Dependency Injection
- Settings injected via Pydantic
- Database path configurable
- Easy testing with mocks

### 4. Factory Pattern (Planned)
- Research factory creates appropriate researcher
- Publisher factory creates appropriate publisher
- Centralized instantiation

### 5. Strategy Pattern
- Different research strategies per source
- Different formatting strategies per platform
- Swappable implementations

### 6. Repository Pattern
- StateManager abstracts database operations
- Clean separation of data access
- Easy to swap SQLite for PostgreSQL later

---

## Next 5 Files to Create (Priority Order)

1. **src/mcp_servers/database_server.py** (HIGH PRIORITY)
   - Enables Claude to query database
   - Unblocks intelligent deduplication
   - Required for full agent autonomy

2. **src/research/huggingface_researcher.py**
   - Second research source
   - Tests researcher pattern
   - Adds content diversity

3. **src/publishing/markdown_publisher.py**
   - Simplest publisher to test pipeline
   - No API dependencies
   - Quick feedback loop

4. **src/core/content_pipeline.py**
   - Coordinates workflow stages
   - Implements business logic
   - Needed before full orchestration

5. **src/analysis/content_filter.py**
   - Deduplication logic
   - Quality filtering
   - Required for pipeline

---

## How to Navigate This Codebase

### Starting Points
- `src/main.py` - Application entry point
- `.claude/CLAUDE.md` - Development guidelines
- `IMPLEMENTATION_PROGRESS.md` - Current progress

### Understanding the Flow
1. `main.py` initializes settings and logging
2. Orchestrator coordinates the pipeline
3. Researchers fetch content in parallel (subagents)
4. Pipeline filters, ranks, summarizes
5. Publishers distribute to platforms
6. State manager tracks everything

### Testing
- Run `python scripts/test_foundation.py` to verify foundation
- Unit tests will go in `tests/unit/`
- Integration tests will go in `tests/integration/`

### Adding Features
- New researcher? Extend `BaseResearcher`
- New publisher? Extend `BasePublisher`
- New utility? Add to `src/utils/`
- New skill? Create in `.claude/skills/`

---

## Dependencies Overview

### Core Dependencies
- `anthropic` - Claude API client
- `mcp` - Model Context Protocol
- `pydantic` - Settings validation
- `aiosqlite` - Async SQLite

### Research Dependencies
- `httpx` - Async HTTP client
- `feedparser` - RSS parsing
- `beautifulsoup4` - HTML parsing

### Publishing Dependencies
- `discord-webhook` - Discord
- `tweepy` - Twitter/X
- `python-telegram-bot` - Telegram
- Instagram Graph API (via requests)

### Utilities
- `structlog` - Structured logging
- `tenacity` - Retry logic
- `Pillow` - Image processing
- `openai` - DALL-E image generation

---

This structure is designed for:
- ✅ Modularity - Each component is independent
- ✅ Testability - Easy to test in isolation
- ✅ Scalability - Can add sources/platforms easily
- ✅ Maintainability - Clear organization
- ✅ Observability - Comprehensive logging and metrics
