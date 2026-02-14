# ElvAgent - AI Newsletter Agent

An autonomous AI newsletter agent that curates and publishes AI news every hour to multiple platforms.

## Overview

ElvAgent automatically:
- Researches AI news from 4 parallel sources (ArXiv, HuggingFace, funding news, general AI news)
- Filters and deduplicates content using SQLite
- Ranks content by importance and novelty
- Generates professional newsletters with AI summarization
- Creates Instagram reels with AI-generated images
- Publishes to Discord, X/Twitter, Instagram, Telegram, and Markdown files
- Runs autonomously every hour via launchd on Mac Mini

## Features

- **Parallel Research:** 4 concurrent subagents research different AI news sources
- **Smart Filtering:** Deduplication and relevance scoring prevent noise
- **Multi-Platform Publishing:** Simultaneous publishing to 5 platforms
- **Cost Optimized:** Targets <$3/day using efficient model selection
- **MCP Servers:** Clean architecture with Model Context Protocol
- **Skills & Subagents:** Demonstrates advanced Claude Code patterns

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Initialize database:**
   ```bash
   python -c "from src.core.state_manager import StateManager; StateManager().init_db()"
   ```

4. **Test run:**
   ```bash
   python src/main.py --mode=test --verbose
   ```

5. **Install as service (Mac):**
   ```bash
   ./scripts/setup_launchd.sh
   ```

## Architecture

```
Hourly Trigger (launchd)
    ↓
Research Stage (4 Parallel Subagents)
    ├─ ArXiv Papers
    ├─ HuggingFace Papers
    ├─ Startup Funding News
    └─ General AI News
    ↓
Filter & Deduplicate (SQLite check)
    ↓
Rank & Analyze (Content Analyst Subagent)
    ↓
Skip if < 3 significant items? → Yes: Log & Exit
    ↓ No
Summarize (Claude medium-depth)
    ↓
Format (Platform-specific)
    ↓
Generate Media (Instagram reel image → video)
    ↓
Publish (5 platforms in parallel)
    ↓
Update State & Track Costs
```

## Project Structure

See [CLAUDE.md](.claude/CLAUDE.md) for detailed architecture documentation.

## Development Status

See [STATUS.md](STATUS.md) for current progress.

## Learning Goals

This project demonstrates:
- MCP server implementation
- Claude skills and subagents
- Autonomous agent patterns
- Multi-platform content distribution
- Cost-optimized AI workflows

## License

MIT
