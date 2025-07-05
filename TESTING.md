# Testing Guide

This document describes the testing setup and how to run tests for the URL Shortener Platform.

## Overview

The project uses a comprehensive testing setup with:
- **pytest** for test execution
- **nox** for test automation and environment management
- **pytest-cov** for coverage reporting
- **pytest-asyncio** for async test support
- **pytest-mock** for mocking
- **factory-boy** and **faker** for test data generation

## Test Structure

```
tests/
├── shared/                 # Tests for shared utilities and models
│   ├── test_utils.py
│   ├── test_models.py
│   └── __init__.py
├── integration/           # Integration tests
│   ├── test_url_shortening_flow.py
│   └── __init__.py
└── __init__.py

services/
├── gateway/tests/         # Gateway service tests
├── shortener/tests/       # Shortener service tests
├── redirector/tests/      # Redirector service tests
└── analytics/tests/       # Analytics service tests
```

## Running Tests

### Prerequisites

1. Install development dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```

2. Install nox:
   ```bash
   pip install nox
   ```

### Using Nox (Recommended)

Nox provides isolated environments and handles dependency installation automatically.

#### Run all tests:
```bash
nox -s tests
```

#### Run tests for a specific service:
```bash
nox -s test-gateway
nox -s test-shortener
nox -s test-redirector
nox -s test-analytics
```

#### Run tests with coverage:
```bash
nox -s coverage
```

#### Run integration tests:
```bash
nox -s test_integration
```

#### Run linting:
```bash
nox -s lint
```

#### Format code:
```bash
nox -s format
```

### Using pytest directly

If you prefer to run tests directly with pytest:

#### Run all tests:
```bash
pytest
```

#### Run tests for a specific service:
```bash
pytest services/shortener/tests/
```

#### Run tests with coverage:
```bash
pytest --cov=services --cov-report=html --cov-report=term-missing
```

#### Run specific test files:
```bash
pytest tests/shared/test_utils.py
```

#### Run tests with specific markers:
```bash
pytest -m "not slow"          # Skip slow tests
pytest -m "unit"              # Run only unit tests
pytest -m "integration"       # Run only integration tests
```

### Using Docker

Run tests in a containerized environment:

```bash
docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit
```

This will:
- Start test databases (PostgreSQL, Redis, Kafka)
- Run the full test suite with coverage
- Generate coverage reports

## Test Configuration

### pytest.ini

The `pytest.ini` file contains pytest configuration:
- Test discovery patterns
- Coverage settings
- Test markers
- Warning filters

### noxfile.py

The `noxfile.py` defines test sessions:
- Python versions to test against (3.11, 3.12)
- Test dependencies
- Coverage configuration
- Linting and formatting

## Writing Tests

### Test Structure

Follow these conventions:

```python
"""Tests for [module/feature description]."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from services.shared.models import URLCreate


class TestFeatureName:
    """Test [feature] functionality."""

    @pytest.fixture
    def sample_data(self):
        """Create sample test data."""
        return URLCreate(original_url="https://example.com")

    @pytest.mark.asyncio
    async def test_async_function(self, sample_data):
        """Test async functionality."""
        # Test implementation
        assert True

    def test_sync_function(self):
        """Test sync functionality."""
        # Test implementation
        assert True
```

### Test Markers

Use these markers to categorize tests:

```python
@pytest.mark.unit          # Unit tests
@pytest.mark.integration   # Integration tests
@pytest.mark.slow          # Slow-running tests
@pytest.mark.redis         # Tests requiring Redis
@pytest.mark.database      # Tests requiring database
@pytest.mark.kafka         # Tests requiring Kafka
```

### Async Tests

For async functions, use `@pytest.mark.asyncio`:

```python
@pytest.mark.asyncio
async def test_async_service_method(self):
    """Test async service method."""
    service = URLService()
    result = await service.create_short_url(db, url_data)
    assert result is not None
```

### Mocking

Use pytest-mock for mocking:

```python
def test_with_mock(self, mocker):
    """Test with mocked dependencies."""
    mock_redis = mocker.patch('services.shared.redis_client.get_redis_manager')
    mock_redis.return_value.get.return_value = None
    
    # Test implementation
```

### Fixtures

Create reusable fixtures:

```python
@pytest.fixture
def mock_db_session():
    """Create mock database session."""
    return AsyncMock(spec=AsyncSession)

@pytest.fixture
def sample_url_record():
    """Create sample URL record."""
    url_record = URL()
    url_record.id = uuid4()
    url_record.short_code = "abc123"
    return url_record
```

## Coverage

### Coverage Reports

Coverage reports are generated in multiple formats:
- Terminal output with missing lines
- HTML report in `htmlcov/` directory
- XML report for CI/CD integration

### Coverage Targets

- Minimum coverage: 80%
- Aim for 90%+ coverage on critical paths
- 100% coverage on utility functions

### Viewing Coverage

Open the HTML coverage report:
```bash
open htmlcov/index.html
```

## Continuous Integration

Tests run automatically in GitHub Actions:
- On every push to main/develop branches
- On every pull request
- Multiple Python versions (3.11, 3.12)
- Full test suite with coverage reporting

## Test Data

### Factories

Use factory-boy for creating test data:

```python
import factory
from services.shared.models import URLCreate

class URLCreateFactory(factory.Factory):
    class Meta:
        model = URLCreate
    
    original_url = factory.Faker('url')
    custom_code = factory.Faker('slug')
```

### Faker

Use faker for generating realistic test data:

```python
from faker import Faker

fake = Faker()

def test_with_fake_data():
    url = fake.url()
    email = fake.email()
    name = fake.name()
```

## Debugging Tests

### Running specific tests:
```bash
pytest tests/shared/test_utils.py::TestShortCodeGeneration::test_generate_short_code_default_length -v
```

### Running with pdb:
```bash
pytest --pdb
```

### Running with verbose output:
```bash
pytest -v -s
```

### Running failed tests only:
```bash
pytest --lf
```

## Best Practices

1. **Test Naming**: Use descriptive test names that explain what is being tested
2. **Test Isolation**: Each test should be independent and not rely on other tests
3. **Mock External Dependencies**: Mock databases, APIs, and external services
4. **Test Edge Cases**: Include tests for error conditions and edge cases
5. **Keep Tests Fast**: Unit tests should run quickly; use integration tests for slower scenarios
6. **Use Fixtures**: Create reusable fixtures for common test data and setup
7. **Test Documentation**: Include docstrings explaining what each test verifies

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure PYTHONPATH includes the project root
2. **Async Test Failures**: Use `@pytest.mark.asyncio` for async tests
3. **Database Connection Issues**: Check test database configuration
4. **Mock Not Working**: Verify mock patch paths are correct

### Getting Help

- Check test output for detailed error messages
- Use `pytest --tb=long` for full tracebacks
- Review test logs in CI/CD for environment-specific issues
