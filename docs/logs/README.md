# Session Logs

This directory contains session handover logs for ElvAgent development. Each log provides complete context for resuming work in the next session.

## Purpose

Session logs serve as "shift handovers" between development sessions, ensuring:
- **Continuity** - Next session can pick up exactly where previous left off
- **Context** - Understand what was done, why, and what's next
- **Decisions** - Record architectural and implementation choices with rationale
- **Metrics** - Track progress, costs, and test coverage

## Naming Convention

```
YYYY-MM-DD-session-N.md
```

Examples:
- `2026-02-16-session-1.md` - First session on Feb 16
- `2026-02-16-session-2.md` - Second session on Feb 16 (later in day)
- `2026-02-17-session-1.md` - First session on Feb 17

## Log Structure

Each log contains:

1. **Session Metadata** - Duration, branch, phase, progress
2. **Session Goal** - What we aimed to accomplish
3. **Changes Made** - Files created/modified/deleted
4. **Key Decisions** - Choices made with context and rationale
5. **Metrics** - LOC, tests, costs, budget utilization
6. **Next Steps** - Immediate tasks, blocked items, outstanding work
7. **Handover Notes** - Critical context for next session

## How to Use

### Starting a New Session

1. Read `docs/STATUS.md` for high-level current state
2. Read the most recent session log for detailed context
3. Start work from the "Next Steps" section

Example:
```bash
# At start of session
cat docs/STATUS.md
cat docs/logs/2026-02-17-session-1.md

# Begin work
source .venv/bin/activate
# Continue from "Next Steps" in log
```

### Ending a Session

Use the `/session-end` skill to automatically:
1. Create a new session log
2. Update STATUS.md
3. Show git status and next session command

Or manually invoke:
- `/log-session` - Create log only
- `/update-status` - Update STATUS.md only

## Detail Level

Logs use "hybrid" detail level:
- **Concise** - No verbose explanations or full code listings
- **Comprehensive** - Enough detail to understand decisions and resume work
- **Contextual** - Key decisions, gotchas, and patterns documented

Think: "What would I need to know to continue this work tomorrow?"

## Automation

Session logs are created via the `/log-session` skill, which:
- Gathers data from git (diff, log, branch)
- Infers context from conversation
- Fills template with session details
- Auto-increments session number
- Creates proper conventional commit

Claude will suggest creating logs when:
- Context usage >75%
- Session duration >2 hours
- User invokes `/session-end`

## Storage

- **Location:** `docs/logs/`
- **Format:** Markdown
- **Size:** ~2-3KB per log
- **Retention:** Keep all logs (searchable history)

## Historical Sessions

- `2026-02-16-session-1.md` - Multi-platform publishing (Twitter, Instagram, Telegram)
- `2026-02-16-session-2.md` - Multi-source research + social enhancement (60%)
- More sessions will be added as development continues...

---

**Related Documentation:**
- `docs/STATUS.md` - High-level current state (<100 lines)
- `.claude/CLAUDE.md` - Project guidelines and patterns
- `.claude/plans/` - Implementation plans for features
