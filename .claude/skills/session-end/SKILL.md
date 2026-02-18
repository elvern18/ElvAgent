---
name: session-end
description: Complete session documentation workflow
tags: [documentation, automation, orchestration]
---

# Session End Skill

Orchestrates the complete session end workflow by calling `/log-session` and `/update-status` skills in sequence.

## Purpose

Provides a single command to:
1. Create comprehensive session handover log
2. Compress and update STATUS.md
3. Show git status
4. Generate next session start command
5. **Auto-commit documentation** (no prompt needed)

Ensures documentation is always committed and up-to-date before ending a session.

## When to Use

Call this skill:
- User explicitly requests `/session-end`
- End of development session (before stopping work)
- When context usage >75% (Claude suggests)
- After completing a major milestone
- Before switching branches or agents

## Workflow

### Stage 1: Create Session Log

Call the `/log-session` skill:

```
Invoke Skill: log-session
```

This will:
- Gather session data from git
- Fill session log template
- Write to `docs/logs/YYYY-MM-DD-session-N.md`
- Return summary

**Wait for completion** before proceeding to Stage 2.

**Error handling:**
- If `/log-session` fails, ask user if they want to continue with manual log
- If user declines, abort workflow
- If user agrees, continue to Stage 2

### Stage 2: Update STATUS.md

Call the `/update-status` skill:

```
Invoke Skill: update-status
```

This will:
- Read current STATUS.md and latest session log
- Compress STATUS.md to <100 lines
- Archive details to session logs
- Preserve all critical information
- Return compression summary

**Wait for completion** before proceeding to Stage 3.

**Error handling:**
- If `/update-status` fails, warn user but don't block
- STATUS.md can be updated manually later
- Continue to Stage 3

### Stage 3: Show Git Status

Display current git state:

```bash
git status
```

Show:
- Modified files (should include docs/STATUS.md)
- New files (should include docs/logs/YYYY-MM-DD-session-N.md)
- Staged changes
- Untracked files

Help user understand what documentation changes were made.

### Stage 4: Generate Summary

Create comprehensive session end summary:

```
✅ Session Documentation Complete

📝 Session Log: docs/logs/YYYY-MM-DD-session-N.md
   - Duration: ~X hours
   - Files changed: N
   - Key decisions: N
   - Next steps: N tasks

📊 STATUS.md: Compressed
   - Before: XXX lines
   - After: XX lines
   - Updated with session YYYY-MM-DD-N

Git Status:
M  docs/STATUS.md
A  docs/logs/YYYY-MM-DD-session-N.md
?? {other uncommitted files}

Next Session Start:
Read docs/STATUS.md and docs/logs/YYYY-MM-DD-session-N.md, then {specific action}

Ready to continue or stop work!
```

### Stage 5: Auto-Commit Documentation

Automatically commit the documentation without asking. Always run:

```bash
git add docs/STATUS.md docs/logs/YYYY-MM-DD-session-N.md
git commit -m "docs: Session YYYY-MM-DD-N - {brief summary}

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

Extract the commit hash from the output and show it in the summary.

**If commit fails** (e.g. pre-commit hook error or nothing to commit):
- If nothing to commit: note "Documentation already committed" and skip
- If hook fails: fix the issue (trailing whitespace, etc.) and retry once
- If still fails: show the manual command and continue

## Output Format

Always return structured summary:

```
═══════════════════════════════════════════════════════════
  SESSION DOCUMENTATION COMPLETE
═══════════════════════════════════════════════════════════

📝 Session Log
   File: docs/logs/2026-02-17-session-1.md
   Duration: ~3.5 hours
   Changes: 8 files
   Decisions: 3 key decisions
   Next: End-to-end testing

📊 STATUS.md
   Compressed: 345 → 87 lines (75% reduction)
   Progress: 60% → 100%
   Updated: 2026-02-17

📋 Git Status
   M  docs/STATUS.md
   A  docs/logs/2026-02-17-session-1.md
   M  src/publishing/content_enhancer.py
   M  src/publishing/telegram_publisher.py

───────────────────────────────────────────────────────────

📦 Documentation Committed
   Commit: abc1234 docs: Session 2026-02-17-1 - ContentEnhancer complete

───────────────────────────────────────────────────────────

NEXT SESSION START:
$ Read docs/STATUS.md and docs/logs/2026-02-17-session-1.md
$ Then: Test end-to-end with real Telegram

═══════════════════════════════════════════════════════════
```

## Automation Triggers

Claude should **suggest** (not force) running `/session-end` when:

1. **Context usage >75%**
   - "Context is at 76%. Should I run `/session-end` to document this session?"

2. **Session duration >2 hours** (estimated from conversation)
   - "We've been working for 2.5 hours. Should I run `/session-end`?"

3. **Major milestone complete**
   - "Phase 2B is complete! Should I run `/session-end` to document it?"

4. **User says they're stopping**
   - User: "I'm done for today"
   - Claude: "Should I run `/session-end` to create handover documentation?"

**User can always:**
- Accept suggestion: "yes" or "/session-end"
- Decline: "no" or "not yet"
- Manually invoke later: "/session-end" at any time

## Error Handling

**If `/log-session` fails:**
```
⚠️  Session log creation failed: {error}

Options:
1. Retry /log-session
2. Continue with /update-status only
3. Abort and fix manually

What would you like to do?
```

**If `/update-status` fails:**
```
⚠️  STATUS.md update failed: {error}

Session log was created successfully.
You can update STATUS.md manually or retry /update-status later.

Continue with git status summary? (yes/no)
```

**If both fail:**
```
❌ Session documentation failed

Both /log-session and /update-status encountered errors.
Please create session log and update STATUS.md manually.

Git status:
{show git status}
```

## Conventional Commits

Documentation commits should follow format:

```bash
# Session documentation
git commit -m "docs: Session YYYY-MM-DD-N - {brief summary}"

# Example
git commit -m "docs: Session 2026-02-17-1 - ContentEnhancer complete"
```

Brief summary should be:
- 3-5 words
- Describes main accomplishment
- Imperative mood ("Complete X" not "Completed X")

Examples:
- "docs: Session 2026-02-17-1 - ContentEnhancer complete"
- "docs: Session 2026-02-17-2 - Multi-source integration"
- "docs: Session 2026-02-18-1 - Twitter API setup"

## Usage Examples

### Example 1: End of Feature Implementation

```
User: "I think we're done for today"

Claude: "We've been working for 3 hours and completed ContentEnhancer.
         Should I run /session-end to document this session?"

User: "yes"

Claude: [Invokes /log-session]
        ✅ Session log created: docs/logs/2026-02-17-session-1.md

        [Invokes /update-status]
        ✅ STATUS.md compressed: 345 → 87 lines

        [Shows summary]
        ═══════════════════════════════════════════════════════════
          SESSION DOCUMENTATION COMPLETE
        ═══════════════════════════════════════════════════════════
        ...
```

### Example 2: High Context Usage

```
Claude: "Context usage is at 78%. Should I run /session-end to document
         this session before we lose context?"

User: "yes please"

Claude: [Executes /session-end workflow]
        ...
```

### Example 3: Manual Invocation

```
User: "/session-end"

Claude: [Executes workflow immediately]
        ...
```

### Example 4: User Declines

```
Claude: "We've been working for 2 hours. Should I run /session-end?"

User: "not yet, want to finish this test first"

Claude: "No problem! Just let me know when you're ready."
```

## Integration with Other Skills

**Related skills:**
- `/log-session` - Can be called independently
- `/update-status` - Can be called independently

**Relationship:**
- `/session-end` = `/log-session` + `/update-status` + summary
- Users can call individual skills if they only want one
- `/session-end` is the recommended workflow for complete documentation

## Session Continuity

After running `/session-end`, the next session should start with:

```bash
# Read both documentation files
Read docs/STATUS.md and docs/logs/YYYY-MM-DD-session-N.md

# Then continue from Next Steps
{Continue with specific action from session log}
```

This ensures perfect continuity without re-explaining context.

## Benefits

**For the user:**
- One command documents entire session
- No manual documentation work
- Perfect session continuity
- Searchable session history

**For Claude (next session):**
- Complete context from session log
- High-level overview from STATUS.md
- Clear next steps
- No need to re-read entire history

**For the project:**
- Comprehensive documentation
- Clear decision history
- Progress tracking
- Knowledge preservation

## Usage

This skill is invoked:
- Manually: User types `/session-end`
- Suggested: Claude proposes when appropriate (context, time, milestone)
- Never forced: User can always decline

The workflow ensures documentation is always up-to-date when ending sessions.
