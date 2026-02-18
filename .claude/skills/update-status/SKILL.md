---
name: update-status
description: Compress and update STATUS.md
tags: [documentation, automation, status]
---

# Status Update Skill

Compresses STATUS.md to <100 lines while preserving all critical information by relocating details to session logs.

## Purpose

Maintain STATUS.md as a high-level "current state" document that:
- Answers "What's the current status?" in <2 minutes of reading
- Lists what's working and what's outstanding (bullets only)
- Links to session logs for detailed context
- Stays under 100 lines for easy scanning

## When to Use

Call this skill:
- After creating session log (as part of `/session-end`)
- When STATUS.md exceeds 150 lines
- At end of major milestone
- When user requests `/update-status`

## Workflow

### 1. Read Current Documentation

```bash
# Read current STATUS.md
cat docs/STATUS.md

# Get latest session log
ls -t docs/logs/*.md | head -1
cat {latest_log}

# Get git branch
git branch --show-current
```

### 2. Extract Current State

From STATUS.md and latest session log, identify:

**Phase Information:**
- Current phase name (e.g., "Phase 2B - Social Media Enhancement")
- Progress percentage (e.g., "85%")
- Whether phase is complete or in progress

**What's Working:**
- Completed components (keep as bullets)
- Functional systems (keep as bullets)
- Example: "Multi-source research (4 sources)" ✅

**What's Outstanding:**
- Incomplete work with % complete
- Blocked items with blocker reason
- Not started items with priority
- Example: "Twitter publisher (blocked - waiting API approval)"

**Platform Status:**
- Extract from current STATUS.md platform table
- Update if session made changes

**Budget/Cost:**
- Cost per newsletter
- Daily cost estimate
- Budget utilization %

### 3. Archive Historical Content

**Move to session logs (don't keep in STATUS.md):**
- Detailed implementation notes ("The ContentEnhancer orchestrator uses asyncio.gather...")
- Step-by-step instructions ("Step 1: Create orchestrator, Step 2: Update publisher...")
- Architecture diagrams longer than 15 lines
- Completed work descriptions (keep bullets only)
- Historical decisions older than current phase
- Verbose explanations
- Code examples
- Full file listings

**Keep in STATUS.md:**
- Current phase and progress %
- What's working (bullet list)
- What's outstanding (bullet list)
- Recent 5 session summaries with links
- Platform status table
- Budget summary (3-4 lines)
- Quick links (3-5 links)

### 4. Generate Compressed STATUS.md

Use this template structure (target: 85-95 lines):

```markdown
# ElvAgent Status

**Last Updated:** YYYY-MM-DD
**Phase:** {Phase Name}
**Progress:** XX%

---

## Current Focus

{2-3 sentences describing what's actively being built or next major task}

**Branch:** {branch_name}
**Next:** {One-line next action}

---

## What's Working

- {Component A} ✅
- {Component B} ✅
- {Component C} ✅
{... up to 10 items max}

## What's Outstanding

- {Component D} (XX% complete) - {reason}
- {Component E} (blocked) - {blocker}
- {Component F} (not started) - {priority}
{... up to 10 items max}

## Recent Sessions

- [{YYYY-MM-DD-N}](logs/YYYY-MM-DD-session-N.md): {1-line summary}
{... last 5 sessions}

## Quick Links

- **Last Session:** [docs/logs/YYYY-MM-DD-session-N.md](logs/YYYY-MM-DD-session-N.md)
- **Active Plan:** `.claude/plans/{current-plan}.md` (if exists)
- **Tests:** `pytest tests/ -v`
- **Run Newsletter:** `python src/main.py --mode=production`

## Platform Status

| Platform | Status | Notes |
|----------|--------|-------|
| Telegram | ✅ | Working |
| Markdown | ✅ | Working |
| Twitter | ⏸️ | Needs Elevated Access |
| Discord | ⏳ | Needs webhook config |
| Instagram | ⏸️ | Optional |

## Architecture Summary

{High-level diagram or 5-10 line description}

Example:
```
Research (4 sources) → ContentPipeline (filter/rank)
                    → ContentEnhancer (AI headlines/takeaways)
                    → Publishers (Telegram, Markdown, etc.)
                    → Database (state tracking)
```

## Budget Status

- **Per Newsletter:** $X.XX
- **Daily (24 cycles):** $X.XX / $3.00 budget
- **Margin:** XX% ✅/⚠️

---

**How to Resume:** `Read docs/STATUS.md and latest session log`
```

### 5. Verify Line Count

```bash
wc -l docs/STATUS.md
```

Target: 85-95 lines (max 100 lines)

If over 100 lines, further compress:
- Reduce "What's Working" bullets (keep top 8 only)
- Reduce "What's Outstanding" bullets (keep top 8 only)
- Simplify architecture diagram
- Remove extra sections

### 6. Add Latest Session to Recent Sessions

Format:
```markdown
- [2026-02-17-1](logs/2026-02-17-session-1.md): Completed ContentEnhancer and Telegram integration
```

Keep only last 5 sessions. Remove older ones.

### 7. Write Updated STATUS.md

- Overwrite `docs/STATUS.md` with compressed version
- Preserve Markdown formatting
- Ensure all links work

### 8. Optionally Create Commit

If user wants to commit:
```bash
git add docs/STATUS.md
git commit -m "docs: Compress STATUS.md (session YYYY-MM-DD-N)"
```

## Compression Rules

### Maximum Line Counts by Section

| Section | Max Lines |
|---------|-----------|
| Header + Current Focus | 10 |
| What's Working | 10 |
| What's Outstanding | 10 |
| Recent Sessions | 6 |
| Quick Links | 6 |
| Platform Status | 8 |
| Architecture Summary | 15 |
| Budget Status | 5 |
| Footer | 3 |
| **TOTAL** | **~85-95 lines** |

### What to Archive

**Archive if:**
- ✅ Historical (older than current phase)
- ✅ Implementation details
- ✅ Step-by-step instructions
- ✅ Verbose explanations
- ✅ Detailed architecture diagrams
- ✅ Code examples
- ✅ File listings
- ✅ Duplicate information

**Keep if:**
- ❌ Current phase status
- ❌ Active work items
- ❌ Platform status
- ❌ Budget metrics
- ❌ Quick links
- ❌ Recent session summaries

## Output Format

Return summary to user:

```
✅ STATUS.md updated

Compression:
- Before: XXX lines
- After: XX lines
- Reduction: XX% ✓

Changes:
- Updated progress: 60% → 85%
- Added session: 2026-02-17-1
- Archived detailed notes to session log

STATUS.md now shows:
- {Brief summary of current state}
- {What's working}
- {What's next}

To commit:
git add docs/STATUS.md
git commit -m "docs: Compress STATUS.md (session YYYY-MM-DD-N)"
```

## Error Handling

- If STATUS.md doesn't exist, create from template
- If no session logs exist, create minimal STATUS.md
- If can't determine current phase, ask user with AskUserQuestion
- If over 100 lines after compression, show warning and suggest manual review
- If no git branch info, use "N/A"

## Examples

### Example: After ContentEnhancer Session

**Before (345 lines):**
```markdown
# ElvAgent Development Status

Last Updated: 2026-02-16 (Late Evening) 🚀

## 🎉 MAJOR MILESTONES ACHIEVED
1. ✅ Multi-Source Research - 4 sources running in parallel
...
{340+ more lines of detailed content}
```

**After (87 lines):**
```markdown
# ElvAgent Status

**Last Updated:** 2026-02-17
**Phase:** Phase 2B - Social Media Enhancement
**Progress:** 100%

---

## Current Focus

Phase 2B complete! Next: End-to-end testing and monitoring enhancement quality.

**Branch:** agent-2-research
**Next:** Test with real Telegram, monitor 5 newsletters

---

## What's Working

- Multi-source research (ArXiv, HuggingFace, Reddit, TechCrunch) ✅
- Content pipeline (dedupe, filter, rank) ✅
- ContentEnhancer (AI headlines, takeaways) ✅
- TelegramPublisher (5-message format) ✅
- Database state tracking ✅

## What's Outstanding

- End-to-end testing (needs real Telegram test)
- Enhancement quality monitoring (1 day)
- Twitter publisher (blocked - waiting API approval)
- Discord publisher (needs webhook config)

## Recent Sessions

- [2026-02-17-1](logs/2026-02-17-session-1.md): Completed ContentEnhancer + Telegram integration
- [2026-02-16-2](logs/2026-02-16-session-2.md): Multi-source research + 60% social enhancement
- [2026-02-16-1](logs/2026-02-16-session-1.md): Twitter, Instagram, Telegram publishers

## Quick Links

- **Last Session:** [docs/logs/2026-02-17-session-1.md](logs/2026-02-17-session-1.md)
- **Tests:** `pytest tests/ -v` (119/119 passing)
- **Run:** `python src/main.py --mode=production`

## Platform Status

| Platform | Status | Notes |
|----------|--------|-------|
| Telegram | ✅ | 5-message format |
| Markdown | ✅ | Local files |
| Twitter | ⏸️ | Needs API approval |
| Discord | ⏳ | Config pending |

## Architecture Summary

```
4 Research Sources → ContentPipeline → ContentEnhancer
                                          ├→ Headlines (AI)
                                          ├→ Takeaways (AI)
                                          └→ Formatting
                                     → Publishers (Telegram, etc.)
```

## Budget Status

- **Per Newsletter:** $0.042
- **Daily (24 cycles):** $1.01 / $3.00
- **Margin:** 66% under budget ✅

---

**Resume:** `Read docs/STATUS.md and latest session log`
```

## Session Log Integration

The compressed STATUS.md should reference session logs for details:

```markdown
## What's Working

- Multi-source research ✅
  (See [session 2026-02-16-2](logs/2026-02-16-session-2.md) for implementation details)
```

But prefer to keep it even simpler - just bullets without parenthetical notes.

## Usage

This skill is invoked:
- Manually by user: `/update-status`
- Automatically by `/session-end` orchestrator
- When STATUS.md grows beyond 150 lines

The compressed STATUS.md provides quick overview while session logs preserve all details.
