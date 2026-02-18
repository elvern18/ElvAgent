---
name: log-session
description: Create session handover log
tags: [documentation, automation, session]
---

# Session Logging Skill

Creates comprehensive session handover logs for development continuity.

## Purpose

Generate a structured log that documents:
- What was accomplished
- Why decisions were made
- What's next
- Critical context for resuming work

Think of this as a "shift handover" in a hospital - the next session needs enough context to pick up seamlessly.

## When to Use

Call this skill:
- At end of development session (before stopping work)
- When context usage >75%
- After completing a major milestone
- When user requests `/log-session`
- As part of `/session-end` workflow

## Workflow

### 1. Gather Session Metadata
- Current date (YYYY-MM-DD)
- Git branch (`git branch --show-current`)
- Session start time (estimate from conversation or use "~X hours")
- Current phase and progress (from STATUS.md or conversation)

### 2. Collect Changes
```bash
# Get file changes
git diff --name-status HEAD

# Get uncommitted files
git status --porcelain

# Get recent commits (this session)
git log --oneline -10

# Get line changes
git diff --stat
```

### 3. Determine Session Number
- Check existing logs: `ls docs/logs/YYYY-MM-DD-session-*.md`
- Auto-increment N (if `session-1.md` exists, create `session-2.md`)
- First session of day = `session-1.md`

### 4. Infer Session Details

From conversation context, extract:

**Session Goal:**
- What was the main objective?
- Was it from STATUS.md "Active Work" or user request?

**Changes Made:**
- Files created (new files in git status)
- Files modified (modified files in git diff)
- Files deleted (deleted files in git status)

**Key Decisions:**
- What architectural choices were made?
- What alternatives were considered?
- Why was a particular approach chosen?
- What impact does this have?

**Metrics:**
- Lines added/deleted (from `git diff --stat`)
- Tests added (check test file changes)
- Tests passing (run `pytest --collect-only 2>&1 | grep "test" | wc -l` or use existing counts)
- Cost per newsletter (if mentioned in conversation)
- Budget utilization (cost / $3.00 daily budget)

**Next Steps:**
- What tasks remain from this work?
- What's blocked and why?
- What's the recommended next action?

**Handover Notes:**
- What's working well?
- What's in progress (% complete)?
- Any known issues or gotchas?
- Critical context the next session must know

### 5. Fill Template

Use this template structure:

```markdown
# Session YYYY-MM-DD-N

**Duration:** HH:MM - HH:MM (~X hours)
**Branch:** {branch_name}
**Phase:** {phase_name}
**Progress:** XX% → YY%

---

## Session Goal

{What we aimed to accomplish this session}

## Changes Made

### Files Created
- `path/to/file.py` - Brief description

### Files Modified
- `path/to/file.py` - What changed and why

### Files Deleted
- `path/to/file.py` - Reason for deletion

## Key Decisions

### Decision: {Title}
**Context:** Why this decision needed to be made
**Options:** A vs B (briefly)
**Chosen:** A
**Rationale:** Why A was better
**Impact:** What this affects

{Repeat for each major decision}

## Metrics

- **Lines Added:** +XXX
- **Lines Deleted:** -XXX
- **Tests Added:** XX
- **Tests Passing:** XXX/XXX
- **Cost per Newsletter:** $X.XX (if applicable)
- **Budget Utilization:** XX%

## Next Steps

### Immediate (Next Session)
1. Task 1 - Description (est. XX min)
2. Task 2 - Description (est. XX min)

### Blocked Items
- What's blocked and why

### Outstanding Work
- Component A (XX% complete)
- Component B (needs X)

## Handover Notes

**What's Working:**
- Component X fully functional with tests

**What's In Progress:**
- Component Y at 60% (missing orchestrator)

**Known Issues:**
- Issue 1: Description with workaround
- Issue 2: Description with plan

**Critical Context:**
{Essential knowledge for next session - architectural decisions, patterns established, gotchas discovered}

---

**Next Session Start:** `Read docs/STATUS.md and this log, then {specific action}`
```

### 6. Write Log File

- Path: `docs/logs/YYYY-MM-DD-session-N.md`
- Ensure `docs/logs/` directory exists
- Use proper formatting and Markdown

### 7. Optionally Create Commit

If user wants to commit immediately:
```bash
git add docs/logs/YYYY-MM-DD-session-N.md
git commit -m "docs: Add session log YYYY-MM-DD-N"
```

Otherwise, show what was created and let user commit later.

## Output Format

Return summary to user:

```
✅ Session log created: docs/logs/YYYY-MM-DD-session-N.md

Session Summary:
- Duration: ~X hours
- Files changed: N
- Key decisions: N
- Next steps: N tasks

To commit:
git add docs/logs/YYYY-MM-DD-session-N.md
git commit -m "docs: Add session log YYYY-MM-DD-N"

Next session start command:
Read docs/STATUS.md and docs/logs/YYYY-MM-DD-session-N.md, then {action}
```

## Detail Level Guidelines

**Be concise but comprehensive:**
- ✅ "Implemented ContentEnhancer orchestrator (245 lines) with parallel agent execution"
- ❌ "Created a file called content_enhancer.py with lots of code"
- ❌ "Implemented ContentEnhancer class with init, enhance_newsletter, _enhance_single_item, _enhance_with_retry, organize_by_category, and format_category_messages methods that coordinate headline writers, takeaway generators, engagement enrichers, and social formatters..."

**Focus on "why" not "what":**
- ✅ "Chose Sonnet for headlines ($0.001 each) over Haiku for better creativity despite higher cost"
- ❌ "Used Sonnet for headlines"

**Capture critical context:**
- ✅ "IMPORTANT: Time window was changed from 1hr to 24hr because different sources update at different frequencies"
- ❌ "Changed time window config"

## Error Handling

- If git commands fail, use conversation context only
- If can't determine session number, default to `session-1.md`
- If metrics unavailable, use "N/A" or estimates
- If no clear decisions made, note "Session focused on implementation following existing plan"
- If unable to gather data, ask user for key details with AskUserQuestion

## Examples

### Example 1: Feature Implementation Session
```markdown
# Session 2026-02-17-1

**Duration:** 09:00 - 12:30 (~3.5 hours)
**Branch:** agent-2-research
**Phase:** Phase 2B - Social Media Enhancement
**Progress:** 60% → 100%

## Session Goal
Complete ContentEnhancer orchestrator and integrate with TelegramPublisher for AI-enhanced multi-category messages.

## Changes Made

### Files Created
- `src/publishing/content_enhancer.py` - Orchestrator for 4 enhancement agents

### Files Modified
- `src/publishing/telegram_publisher.py` - Added enhancement flow

## Key Decisions

### Decision: Parallel vs Sequential Enhancement
**Context:** Need to enhance 15 items with 4 different agents (headline, takeaway, metrics, formatting)
**Options:**
- A: Sequential (headline → takeaway → metrics → format)
- B: Parallel (all 15 headlines simultaneously, then all 15 takeaways)
**Chosen:** B (Parallel)
**Rationale:** 10x faster (15 concurrent API calls vs 60 sequential), cost same, rate limits OK
**Impact:** Reduces enhancement time from ~45s to ~5s per newsletter

## Metrics

- **Lines Added:** +340
- **Lines Deleted:** -15
- **Tests Added:** 8
- **Tests Passing:** 119/119
- **Cost per Newsletter:** $0.042
- **Budget Utilization:** 1.4% ($1.01/$3.00 daily)

## Next Steps

### Immediate (Next Session)
1. End-to-end test with real Telegram (20 min)
2. Monitor enhancement quality over 5 newsletters (1 day)
3. Adjust headline prompts if needed (30 min)

### Blocked Items
None

### Outstanding Work
- Twitter publisher (waiting on API approval)
- Instagram publisher (user opted for simpler platforms first)

## Handover Notes

**What's Working:**
- ContentEnhancer fully functional with retry logic
- TelegramPublisher sending 5-message format
- All 119 tests passing
- Cost well under budget

**What's In Progress:**
- Nothing - Phase 2B complete!

**Known Issues:**
None

**Critical Context:**
- Enhancement uses parallel asyncio.gather for speed
- Fallback templates used if AI fails after 3 retries
- Each category limited to 5 items max (configurable in constants.py)

---

**Next Session Start:** `Read docs/STATUS.md and this log, then test end-to-end with real Telegram`
```

## Usage

This skill is invoked:
- Manually by user: `/log-session`
- Automatically by `/session-end` orchestrator skill
- When Claude suggests at natural stopping points

The log enables perfect continuity between sessions without needing to re-explain context.
