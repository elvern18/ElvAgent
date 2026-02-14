# ElvAgent Testing Guide

**Purpose:** Establish testing best practices and optimal workflow for development.

---

## Testing Philosophy

We follow **Test-Driven Development (TDD)** principles with pragmatic flexibility:

1. **Write tests first** when requirements are clear
2. **Write tests after** for exploratory coding
3. **Always have tests** before merging to main
4. **Mock external dependencies** to keep tests fast and reliable
5. **Test at multiple levels** (unit, integration, end-to-end)

---

## Testing Pyramid

```
           /\
          /E2E\         End-to-End Tests (Few, slow, high value)
         /------\
        /Integr.\       Integration Tests (Some, medium speed)
       /----------\
      /   Unit     \    Unit Tests (Many, fast, focused)
     /--------------\
```

**Ratio Goal:** 70% unit, 20% integration, 10% E2E

---

## Test Types

### 1. Unit Tests (`tests/unit/`)

**Purpose:** Test individual functions/methods in isolation.

**Characteristics:**
- Very fast (<10ms per test)
- No external dependencies (database, network, files)
- Use mocks and fixtures
- Test single units of code

**Example:**
```python
@pytest.mark.unit
def test_generate_content_id():
    """Test content ID generation produces valid SHA-256."""
    from src.core.state_manager import StateManager

    manager = StateManager()
    content_id = manager.generate_content_id(
        url="https://example.com",
        title="Test"
    )

    assert len(content_id) == 64  # SHA-256 is 64 hex chars
    assert all(c in '0123456789abcdef' for c in content_id)
```

**When to use:**
- Testing pure functions
- Testing data transformations
- Testing business logic
- Testing error handling

### 2. Integration Tests (`tests/integration/`)

**Purpose:** Test how components work together.

**Characteristics:**
- Medium speed (100ms-1s per test)
- May use test database (in-memory SQLite)
- May use real file system (temp directories)
- Mock external APIs
- Test multiple components

**Example:**
```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_research_and_store_workflow(state_manager):
    """Test full workflow: research -> filter -> store."""
    # This uses real database, real researcher logic,
    # but mocked HTTP calls

    researcher = ArXivResearcher()
    # ... mock HTTP response ...
    items = await researcher.research()

    # Store in database
    for item in items:
        await state_manager.store_content(item.to_dict())

    # Verify deduplication works
    is_dup = await state_manager.check_duplicate(
        items[0].url, items[0].title
    )
    assert is_dup is True
```

**When to use:**
- Testing database operations
- Testing file I/O
- Testing workflow pipelines
- Testing component interactions

### 3. End-to-End Tests (`tests/integration/test_e2e.py`)

**Purpose:** Test complete user scenarios.

**Characteristics:**
- Slow (1-10s per test)
- May use real APIs (marked with `@requires_api`)
- Test entire application flow
- Fewer in number but high confidence

**Example:**
```python
@pytest.mark.slow
@pytest.mark.requires_api
@pytest.mark.asyncio
async def test_full_newsletter_cycle():
    """Test complete newsletter generation and publishing."""
    # This would run the entire pipeline:
    # 1. Research from all sources
    # 2. Filter and rank
    # 3. Generate newsletter
    # 4. Publish to test Discord channel
    # 5. Verify database state

    orchestrator = NewsletterOrchestrator()
    result = await orchestrator.run_hourly_cycle()

    assert result.success
    assert len(result.published_platforms) > 0
```

**When to use:**
- Testing critical user paths
- Regression testing
- Pre-deployment validation
- CI/CD gate checks

---

## Testing Workflow

### Option 1: Test-Driven Development (TDD) - Recommended for Clear Requirements

**Best for:** Well-defined features with known inputs/outputs.

```
1. Get feature requirements
   │
2. Spawn test-planner agent
   │  → Analyzes requirements
   │  → Designs test cases
   │  → Creates test plan
   │
3. Review test plan
   │  → Adjust as needed
   │  → Clarify edge cases
   │
4. Write failing tests first
   │  → Create test files
   │  → Implement test cases
   │  → Run: pytest (all fail - that's good!)
   │
5. Implement feature
   │  → Write minimal code to pass tests
   │  → Run: pytest (watch tests turn green)
   │  → Refactor with confidence
   │
6. Call test-planner for coverage review
   │  → Check for missed scenarios
   │  → Add edge case tests
   │
7. Verify 100% pass
   │  → pytest -v
   │  → pytest --cov=src
   │
8. Commit & merge
```

**Example:**
```bash
# 1. Get requirement: "Implement HuggingFace researcher"

# 2. Spawn test planner
# (Creates comprehensive test plan)

# 3. Write tests (they fail)
cat > tests/unit/test_huggingface_researcher.py << 'EOF'
@pytest.mark.unit
def test_score_relevance_llm_paper():
    researcher = HuggingFaceResearcher()
    score = researcher.score_relevance({
        "title": "Novel LLM Architecture",
        "summary": "We present a breakthrough in language models..."
    })
    assert score >= 8  # High-impact topic
EOF

# Run tests - FAIL (feature doesn't exist yet)
pytest tests/unit/test_huggingface_researcher.py

# 4. Implement feature to pass tests
# ... write HuggingFaceResearcher class ...

# Run tests - PASS
pytest tests/unit/test_huggingface_researcher.py
```

### Option 2: Test-After Development (TAD) - For Exploratory Work

**Best for:** Prototyping, unclear requirements, research spikes.

```
1. Prototype feature
   │  → Explore approach
   │  → Try different solutions
   │  → Get it working
   │
2. Call test-planner agent
   │  → Review implemented code
   │  → Design test cases
   │  → Identify edge cases
   │
3. Write comprehensive tests
   │  → Cover all paths
   │  → Test error handling
   │  → Add edge cases
   │
4. Run tests - fix failures
   │  → May find bugs!
   │  → Refine implementation
   │
5. Verify coverage
   │  → pytest --cov
   │  → Aim for >80%
   │
6. Commit with confidence
```

### Option 3: Hybrid Approach - Balanced

**Best for:** Most real-world development.

```
1. Write high-level test outline
   │  → Test public interfaces
   │  → Define expected behavior
   │
2. Implement feature
   │  → Use tests as guide
   │  → Add tests as you go
   │
3. Call test-planner for review
   │  → Find gaps
   │  → Add edge cases
   │
4. Commit
```

---

## Using the Test Planner Agent

### When to Use

**Before Implementation (Recommended):**
- Clarifies requirements
- Catches design issues early
- Guides implementation
- Prevents rework

**After Implementation:**
- Ensures completeness
- Finds edge cases
- Validates coverage
- Documents behavior

### How to Use

```python
# In your Claude Code session:

# BEFORE implementing HuggingFace researcher:
"""
I need to implement a HuggingFace researcher that:
- Fetches trending papers from https://huggingface.co/papers
- Parses paper metadata
- Scores relevance (1-10)
- Returns top 5 papers

Please use the test-planner agent to create a comprehensive test plan.
"""

# The test-planner agent will:
# 1. Analyze the requirements
# 2. Design unit tests
# 3. Design integration tests
# 4. Suggest fixtures and mocks
# 5. Identify edge cases
# 6. Output a detailed test plan

# You then review the plan and implement tests first!
```

---

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/unit/test_state_manager.py

# Run specific test
pytest tests/unit/test_state_manager.py::test_init_db

# Run tests by marker
pytest -m unit           # Only unit tests (fast!)
pytest -m integration    # Integration tests
pytest -m "not slow"     # Skip slow tests

# Run with coverage
pytest --cov=src --cov-report=html

# Run in parallel (faster)
pytest -n auto
```

### Continuous Testing (Watch Mode)

```bash
# Install pytest-watch
pip install pytest-watch

# Auto-run tests on file changes
ptw -- -v
```

### Pre-Commit Hook

Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Run tests before allowing commit

echo "Running tests..."
pytest -m "unit and not slow" -q

if [ $? -ne 0 ]; then
    echo "Tests failed. Commit aborted."
    exit 1
fi

echo "Tests passed!"
```

---

## Test Organization

### Directory Structure

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── unit/                    # Unit tests
│   ├── test_state_manager.py
│   ├── test_arxiv_researcher.py
│   ├── test_cost_tracker.py
│   └── test_formatters.py
├── integration/             # Integration tests
│   ├── test_research_pipeline.py
│   ├── test_publishing_workflow.py
│   └── test_e2e.py         # End-to-end tests
└── fixtures/                # Test data
    ├── sample_rss_feeds.py
    ├── sample_api_responses.py
    └── sample_newsletters.py
```

### Naming Conventions

- Test files: `test_<module>.py`
- Test functions: `test_<function>_<scenario>`
- Test classes: `Test<ClassName>`
- Fixtures: `<descriptive_name>` (no test_ prefix)

**Examples:**
```python
# Good
def test_generate_content_id_produces_sha256():
def test_check_duplicate_when_exists():
def test_research_handles_network_error():

# Bad (not descriptive enough)
def test_id():
def test_duplicate():
def test_research():
```

---

## Mocking Best Practices

### What to Mock

✅ **Always mock:**
- External API calls (Claude, OpenAI, Twitter, etc.)
- Network requests (HTTP, RSS feeds)
- Time/date (for consistent tests)
- Random number generation
- File system (when testing logic, not I/O)

❌ **Don't mock:**
- Your own code under test
- Database (use in-memory SQLite instead)
- Simple data structures (just create them)

### How to Mock

**Using pytest fixtures:**
```python
@pytest.fixture
def mock_httpx_client(mocker):
    """Mock httpx client for network calls."""
    mock = mocker.AsyncMock()
    mock.get.return_value.status_code = 200
    mock.get.return_value.content = b"<xml>...</xml>"
    return mock
```

**Using pytest-mock:**
```python
@pytest.mark.unit
async def test_fetch_with_mock(mocker):
    # Mock httpx.AsyncClient
    mock_client = mocker.patch('httpx.AsyncClient')
    mock_client.return_value.get.return_value.content = b"test"

    # Test your code
    result = await fetch_data()

    assert result is not None
```

---

## Coverage Goals

### Target Coverage

- **Overall:** >80% line coverage
- **Critical paths:** 100% (authentication, publishing, data storage)
- **Utilities:** >90%
- **UI/CLI:** >60% (less critical)

### Checking Coverage

```bash
# Generate coverage report
pytest --cov=src --cov-report=term-missing

# Generate HTML report (detailed)
pytest --cov=src --cov-report=html
open htmlcov/index.html

# Fail if coverage below threshold
pytest --cov=src --cov-fail-under=80
```

### What Coverage Means

- **Line coverage:** % of lines executed
- **Branch coverage:** % of if/else paths taken
- **Function coverage:** % of functions called

**Note:** 100% coverage doesn't mean bug-free! Still need good test cases.

---

## CI/CD Integration

### GitHub Actions Example

`.github/workflows/test.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v2

    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.10'

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov pytest-asyncio

    - name: Run unit tests
      run: pytest -m unit -v

    - name: Run integration tests
      run: pytest -m integration -v

    - name: Check coverage
      run: pytest --cov=src --cov-fail-under=80

    - name: Upload coverage
      uses: codecov/codecov-action@v2
```

---

## Common Testing Patterns

### Testing Async Functions

```python
@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
    assert result is not None
```

### Testing Exceptions

```python
def test_raises_error():
    with pytest.raises(ValueError, match="Invalid input"):
        process_data(None)
```

### Parametrized Tests

```python
@pytest.mark.parametrize("input,expected", [
    ("llm", 8),
    ("transformer", 9),
    ("theoretical proof", 4),
])
def test_score_various_topics(input, expected):
    score = score_relevance({"title": input})
    assert score >= expected
```

### Testing with Fixtures

```python
def test_with_database(state_manager):
    # state_manager is a fixture from conftest.py
    # Database is already initialized
    result = await state_manager.check_duplicate("url", "title")
    assert result is False
```

---

## Debugging Failed Tests

### 1. Run with verbose output
```bash
pytest -vv tests/unit/test_state_manager.py
```

### 2. Show print statements
```bash
pytest -s tests/unit/test_state_manager.py
```

### 3. Drop into debugger on failure
```bash
pytest --pdb tests/unit/test_state_manager.py
```

### 4. Run only failed tests
```bash
pytest --lf  # last failed
pytest --ff  # failed first
```

### 5. Show full diff
```bash
pytest -vv --tb=long
```

---

## Testing Checklist

Before merging to main:

- [ ] All tests pass (`pytest`)
- [ ] Coverage >80% (`pytest --cov=src --cov-fail-under=80`)
- [ ] No skipped tests without good reason
- [ ] Added tests for new features
- [ ] Added tests for bug fixes (regression tests)
- [ ] Mocked all external dependencies
- [ ] Tests run fast (<1 min for unit tests)
- [ ] Tests are independent (can run in any order)
- [ ] Test names are descriptive
- [ ] Used appropriate markers (`@pytest.mark.unit`, etc.)

---

## Summary: Optimal Testing Workflow

**For ElvAgent Development:**

1. **Planning Phase**
   - Spawn `test-planner` agent with feature requirements
   - Review comprehensive test plan
   - Adjust based on complexity

2. **Implementation Phase**
   - Write tests first (TDD) for clear features
   - Write tests after for exploratory work
   - Run tests frequently (`ptw` watch mode)

3. **Verification Phase**
   - Run full test suite: `pytest`
   - Check coverage: `pytest --cov=src --cov-report=html`
   - Review missing coverage areas

4. **Quality Gates**
   - All unit tests pass
   - Integration tests pass
   - Coverage >80%
   - No linting errors

5. **Commit**
   - Tests included in commit
   - Tests documented in docstrings
   - CI/CD runs tests automatically

This ensures high-quality, maintainable code with confidence!
