# ElvAgent Documentation

This folder contains all project documentation organized for easy reference.

## 📋 Documentation Files

### Development Progress
- **[STATUS.md](STATUS.md)** - Current development status, active work, and next steps
  - Updated regularly during development
  - Check here first to see where we are and what's next
  - Includes metrics, checklists, and completion percentages

### Project Information
- **[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)** - Complete project file structure
  - Directory tree with descriptions
  - Component status (complete/in-progress/TODO)
  - File breakdown by category
  - Navigation guide for the codebase

- **[IMPLEMENTATION_PROGRESS.md](IMPLEMENTATION_PROGRESS.md)** - Detailed day-by-day progress
  - What's been built
  - Architecture decisions
  - Lessons learned
  - Next priorities

### Development Guides
- **[TESTING_GUIDE.md](TESTING_GUIDE.md)** - Comprehensive testing documentation
  - Testing philosophy and best practices
  - How to use the test-planner agent
  - TDD vs TAD workflows
  - Running tests and checking coverage
  - CI/CD integration

## 🎯 Quick Reference

**Starting development?**
1. Read [STATUS.md](STATUS.md) for current phase
2. Check [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) to understand the codebase
3. Follow [TESTING_GUIDE.md](TESTING_GUIDE.md) for testing workflow

**Looking for something specific?**
- Current tasks: `docs/STATUS.md` → Active Work section
- File locations: `docs/PROJECT_STRUCTURE.md` → Directory Tree
- How to test: `docs/TESTING_GUIDE.md` → Testing Workflow
- What's done: `docs/IMPLEMENTATION_PROGRESS.md` → What's Been Built

## 📍 Other Important Files

Located at the project root:
- **[README.md](../README.md)** - Project overview and quick start
- **[.claude/CLAUDE.md](../.claude/CLAUDE.md)** - Development guidelines (auto-read by Claude)
- **[.env.example](../.env.example)** - Environment configuration template
- **[requirements.txt](../requirements.txt)** - Python dependencies

## 🔄 Keeping Documentation Updated

Documentation is updated:
- **After each major feature** - Update STATUS.md and PROJECT_STRUCTURE.md
- **At phase milestones** - Update IMPLEMENTATION_PROGRESS.md with lessons learned
- **When testing patterns change** - Update TESTING_GUIDE.md

Claude Code automatically reads `.claude/CLAUDE.md` and can be directed to other docs as needed.
