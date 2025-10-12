# SALTED Test Suite

This directory contains the test suite for SALTED, organized by test type and functionality.

## Test Structure

### `test_integration.py`
- **Integration tests** that test end-to-end functionality
- Tests real network calls to verify full application behavior
- Includes file processing tests for HTML, Markdown, TeX, and BibTeX
- Tests exception handling with real dead links

### `test_url_check.py`
- **Unit tests** for URL checking functionality with mocking
- Focuses on previously untested components (22% coverage gap)
- Tests critical fixes like HEAD→GET fallback logic
- Covers network exception scenarios and status code handling

## Key Test Coverage

### ✅ **Well Tested (Previously)**
- URL extraction from different file formats (Parser)
- File discovery and filtering (FileFinder)
- Worker recommendation algorithm
- Basic integration scenarios

### 🆕 **Newly Added Unit Tests**
- **HEAD Request Fallback** - Tests our performance fix for servers that don't support HEAD
- **HTTP Status Code Matrix** - Tests all response code paths (200, 301, 404, 429, 500, etc.)
- **Network Exception Handling** - Tests timeout, connection errors, malformed responses
- **Session Management** - Tests aiohttp session creation/cleanup
- **Edge Cases** - Boundary conditions and error scenarios

## Running Tests

```bash
# Run all tests
python -m pytest

# Run only integration tests
python -m pytest tests/test_integration.py

# Run only unit tests
python -m pytest tests/test_url_check.py

# Run with coverage
python -m coverage run --source salted -m pytest
python -m coverage report
python -m coverage html
```

## Test Categories

### Integration Tests (17 tests)
- File parsing and URL extraction
- End-to-end link checking with real network calls
- Multi-file processing scenarios
- Dead link detection and exception raising

### Unit Tests (21 tests)
- Mocked network scenarios
- Isolated component testing
- Error condition simulation
- Performance optimization validation

**Total: 38 tests covering critical functionality and edge cases**

## Dependencies

Required test packages:
- `pytest` - Test framework
- `pytest-asyncio` - Async test support
- `pytest-mock` - Mocking utilities
- `pyfakefs` - Filesystem mocking
- `coverage` - Coverage analysis