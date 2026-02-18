---
name: session-start
description: Load session context and resume work
tags: [documentation, automation, session, onboarding]
---

# Session Start Skill

Automatically loads context at the beginning of a development session by reading STATUS.md and the latest session log.

## Purpose

Provides a clean session start workflow:
- Automatically finds and reads the latest session log
- Reads current STATUS.md
- Summarizes current state
- Shows next steps
- Prepares Claude to continue work seamlessly

Think of this as "clocking in" at the start of your shift - you get the full handover from the previous session.

## When to Use

Call this skill:
- At the **beginning** of every development session
- When user invokes `/session-start`
- When starting work after a break
- When another developer (or Claude instance) needs to pick up work

## Workflow

### 1. Find Latest Session Log

```bash
# Get most recent log file (by modification time)
ls -t docs/logs/*.md | head -1
```

If no logs found:
- Check if `docs/logs/` directory exists
- If empty, notify user that this is the first session
- Continue with STATUS.md only

### 2. Read Documentation

Read in this order:
1. **STATUS.md** - High-level current state
2. **Latest session log** - Detailed handover context

### 3. Extract Key Information

From STATUS.md:
- Current phase and progress %
- What's working (completed components)
- What's outstanding (incomplete work)
- Platform status
- Budget status

From latest session log:
- Session goal (what was being worked on)
- Changes made (files created/modified)
- Key decisions (architectural choices)
- Next steps (immediate tasks)
- Handover notes (critical context)
- Known issues (blockers, gotchas)

### 4. Generate Summary

Create a formatted summary:

```
═══════════════════════════════════════════════════════════
  SESSION START - {DATE}
═══════════════════════════════════════════════════════════

📊 PROJECT STATUS

Phase: {Phase Name}
Progress: XX%
Branch: {branch_name}

───────────────────────────────────────────────────────────

✅ WHAT'S WORKING

- {Component A}
- {Component B}
- {Component C}

───────────────────────────────────────────────────────────

⏳ WHAT'S OUTSTANDING

- {Component D} (XX% complete) - {reason}
- {Component E} (blocked) - {blocker}
- {Component F} (not started) - {priority}

───────────────────────────────────────────────────────────

📝 LAST SESSION: {YYYY-MM-DD-session-N}

Goal: {What was being worked on}

Completed:
- {Change 1}
- {Change 2}

Decisions Made:
- {Decision 1}: {Rationale}
- {Decision 2}: {Rationale}

───────────────────────────────────────────────────────────

🎯 NEXT STEPS (from last session)

1. {Task 1} - {estimated time}
2. {Task 2} - {estimated time}
3. {Task 3} - {estimated time}

───────────────────────────────────────────────────────────

⚠️  KNOWN ISSUES

- {Issue 1}: {Description + workaround}
- {Issue 2}: {Description + plan}

───────────────────────────────────────────────────────────

💡 CRITICAL CONTEXT

{Essential knowledge from handover notes - architectural decisions,
patterns, gotchas that the session must know}

───────────────────────────────────────────────────────────

🚀 READY TO START

I've loaded the full context from STATUS.md and the latest
session log. I understand where we are and what's next.

Should I proceed with: {First task from Next Steps}?

═══════════════════════════════════════════════════════════
```

### 5. Confirm Next Action

After showing summary, ask user:
```
Should I proceed with {first task from Next Steps}, or would you like to work on something else?
```

This gives user control while providing a clear default path forward.

## Output Format

The skill should return a comprehensive, scannable summary that includes:

**Structure:**
1. Header with current date
2. Project status (phase, progress, branch)
3. What's working (bullets)
4. What's outstanding (bullets)
5. Last session summary (goal, completed, decisions)
6. Next steps (numbered list)
7. Known issues (warnings)
8. Critical context (essential knowledge)
9. Ready to start (confirmation + suggested next action)

**Formatting:**
- Use visual separators (lines, emojis) for scannability
- Keep bullets concise
- Highlight critical information
- End with clear call to action

## Error Handling

**If no session logs exist:**
```
📊 SESSION START - First Session

No previous session logs found. This appears to be the first session
or the session log system is newly set up.

Current Status (from STATUS.md):
- Phase: {phase}
- Progress: XX%
- What's working: {bullets}
- What's outstanding: {bullets}

Ready to start! What would you like to work on?
```

**If STATUS.md doesn't exist:**
```
⚠️  STATUS.md not found

Expected location: docs/STATUS.md

This appears to be a fresh repository or STATUS.md has been moved.
Would you like me to:
1. Create a new STATUS.md
2. Search for STATUS.md in the repository
3. Continue without it
```

**If docs/logs/ directory doesn't exist:**
```
📊 SESSION START

Session logs directory not found. Reading STATUS.md only.

{Show STATUS.md contents}

Note: Session logs are stored in docs/logs/. You can create them
with /session-end at the end of your session.
```

**If session log is corrupted or unreadable:**
```
⚠️  Could not read session log: {filename}

Reading STATUS.md only. You may need to review the session log manually.

{Show STATUS.md contents}
```

## Integration with Other Skills

**Relationship:**
- `/session-start` (beginning) ←→ `/session-end` (end)
- Forms complete session lifecycle

**Workflow:**
```
Day 1: /session-start → work → /session-end
       (creates session-1.md)

Day 2: /session-start → work → /session-end
       (reads session-1.md, creates session-2.md)

Day 3: /session-start → work → /session-end
       (reads session-2.md, creates session-3.md)
```

## User Experience

**Without /session-start:**
```
User: "Read docs/STATUS.md and docs/logs/2026-02-17-session-1.md"
Claude: [Reads both files manually]
User: "What should I work on?"
Claude: "Based on the files, you should work on X"
```

**With /session-start:**
```
User: "/session-start"
Claude: [Shows formatted summary with all context]
        "Ready to start! Should I proceed with {task from Next Steps}?"
User: "yes"
Claude: [Begins work immediately]
```

**Benefit:** One command loads everything and provides clear path forward.

## Examples

### Example 1: Normal Session Start

```
User: "/session-start"

Claude:
═══════════════════════════════════════════════════════════
  SESSION START - 2026-02-17
═══════════════════════════════════════════════════════════

📊 PROJECT STATUS

Phase: Phase 2B - Social Media Enhancement
Progress: 85%
Branch: agent-1-data-layer

───────────────────────────────────────────────────────────

✅ WHAT'S WORKING

- Multi-source research (ArXiv, HuggingFace, Reddit, TechCrunch) ✅
- Content pipeline (dedupe, filter, rank) ✅
- AI enhancement agents (headlines, takeaways, formatting) ✅
- TelegramPublisher (basic format) ✅
- Documentation automation skills ✅

───────────────────────────────────────────────────────────

⏳ WHAT'S OUTSTANDING

- ContentEnhancer orchestrator (60% - needs coordination)
- TelegramPublisher enhancement integration
- End-to-end testing with AI-enhanced content
- Twitter publisher (blocked - API approval)

───────────────────────────────────────────────────────────

📝 LAST SESSION: 2026-02-16-session-2

Goal: Multi-source research + Social enhancement implementation

Completed:
- Added 3 research sources (HuggingFace, Reddit, TechCrunch)
- Implemented 4 AI enhancement agents
- Created data models and templates
- Extended time window from 1hr to 24hr

Decisions Made:
- Parallel enhancement: 15 concurrent agents for speed
- Hybrid approach: AI with template fallback
- 24hr time window: Accommodates all source frequencies

───────────────────────────────────────────────────────────

🎯 NEXT STEPS

1. Create ContentEnhancer orchestrator (45 min)
2. Update TelegramPublisher for enhancement integration (20 min)
3. Integration test with real data (20 min)
4. End-to-end test with Telegram (20 min)

───────────────────────────────────────────────────────────

⚠️  KNOWN ISSUES

None - all components working!

───────────────────────────────────────────────────────────

💡 CRITICAL CONTEXT

- Phase 2B is 60% complete (4 of 6 files done)
- Context window at 72% when stopped (natural break point)
- Parallel agent execution pattern: asyncio.gather for 15 concurrent calls
- Fallback strategy: Retry 3x with exponential backoff, then templates
- Category organization: Max 5 items per category
- Cost tracking: $0.042/newsletter, 66% under budget

───────────────────────────────────────────────────────────

🚀 READY TO START

I've loaded the full context from STATUS.md and session
2026-02-16-2. I understand we're implementing the ContentEnhancer
orchestrator to coordinate the 4 AI enhancement agents.

Should I proceed with creating src/publishing/content_enhancer.py?

═══════════════════════════════════════════════════════════
```

### Example 2: First Session (No Logs)

```
User: "/session-start"

Claude:
═══════════════════════════════════════════════════════════
  SESSION START - 2026-02-15 (First Session)
═══════════════════════════════════════════════════════════

No previous session logs found. This appears to be the first
session or the session log system is newly set up.

📊 CURRENT STATUS (from STATUS.md)

Phase: Phase 1 - Foundation
Progress: 45%

✅ What's Working:
- Database state manager ✅
- ArXiv researcher ✅
- Base classes (BaseResearcher, BasePublisher) ✅

⏳ What's Outstanding:
- Multi-source research (needs 3 more sources)
- Publishers (Discord, Twitter, Telegram, etc.)
- Orchestrator implementation

───────────────────────────────────────────────────────────

🚀 READY TO START

What would you like to work on?

═══════════════════════════════════════════════════════════
```

## Commands Used

```bash
# Find latest session log
ls -t docs/logs/*.md | head -1

# Get current branch
git branch --show-current

# Read files
cat docs/STATUS.md
cat docs/logs/{latest}.md
```

## Usage

This skill is invoked:
- Manually by user: `/session-start`
- At the beginning of development sessions
- When resuming work after a break
- When onboarding a new developer/Claude instance

The skill provides perfect session continuity by automatically loading all necessary context.

## Relationship to Workflow

```
Session Lifecycle:

/session-start          (load context, show summary, suggest next action)
    ↓
[Development Work]      (implement features, fix bugs, etc.)
    ↓
/session-end           (create log, compress STATUS.md, show next steps)

Next Session:

/session-start          (auto-loads previous session's log)
    ↓
[Continue Work]
    ↓
/session-end
```

This creates a perfect loop where each session seamlessly continues from the previous one.
