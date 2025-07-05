"""Nox configuration for running tests across all services."""

import nox

# Python versions to test against
PYTHON_VERSIONS = ["3.11", "3.12"]

# Services to test
SERVICES = ["gateway", "shortener", "redirector", "analytics"]

# Test locations
SHARED_TESTS = "tests/shared"
SERVICE_TESTS = {
    "gateway": "services/gateway/tests",
    "shortener": "services/shortener/tests", 
    "redirector": "services/redirector/tests",
    "analytics": "services/analytics/tests"
}

# Common test dependencies
TEST_DEPS = [
    "pytest>=7.4.3",
    "pytest-asyncio>=0.21.1",
    "pytest-cov>=4.1.0",
    "pytest-mock>=3.12.0",
    "httpx>=0.25.2",
    "faker>=20.1.0",
    "factory-boy>=3.3.0",
]


@nox.session(python=PYTHON_VERSIONS)
def tests(session):
    """Run all tests."""
    session.install(*TEST_DEPS)
    
    # Install shared dependencies
    session.install("-r", "services/shared/requirements.txt", silent=True)
    
    # Run shared tests
    if session.posargs:
        session.run("pytest", *session.posargs)
    else:
        session.run(
            "pytest",
            SHARED_TESTS,
            "--cov=services/shared",
            "--cov-report=term-missing",
            "--cov-report=xml",
            "-v"
        )


@nox.session(python=PYTHON_VERSIONS)
@nox.parametrize("service", SERVICES)
def test_service(session, service):
    """Run tests for a specific service."""
    session.install(*TEST_DEPS)
    
    # Install service-specific dependencies
    requirements_file = f"services/{service}/requirements.txt"
    session.install("-r", requirements_file, silent=True)
    
    # Install shared dependencies
    session.install("-r", "services/shared/requirements.txt", silent=True)
    
    test_path = SERVICE_TESTS[service]
    
    if session.posargs:
        session.run("pytest", *session.posargs)
    else:
        session.run(
            "pytest",
            test_path,
            f"--cov=services/{service}",
            "--cov-report=term-missing",
            "--cov-report=xml",
            "-v"
        )


@nox.session(python=PYTHON_VERSIONS)
def test_integration(session):
    """Run integration tests."""
    session.install(*TEST_DEPS)
    
    # Install all service dependencies
    for service in SERVICES:
        requirements_file = f"services/{service}/requirements.txt"
        session.install("-r", requirements_file, silent=True)
    
    session.run(
        "pytest",
        "tests/integration",
        "--cov=services",
        "--cov-report=term-missing",
        "--cov-report=xml",
        "-v"
    )


@nox.session(python=PYTHON_VERSIONS)
def lint(session):
    """Run linting checks."""
    session.install("flake8", "black", "isort", "mypy")
    
    # Run black
    session.run("black", "--check", "services/", "tests/", "noxfile.py")
    
    # Run isort
    session.run("isort", "--check-only", "services/", "tests/", "noxfile.py")
    
    # Run flake8
    session.run("flake8", "services/", "tests/", "noxfile.py")
    
    # Run mypy on shared code
    session.run("mypy", "services/shared/")


@nox.session(python=PYTHON_VERSIONS)
def format(session):
    """Format code with black and isort."""
    session.install("black", "isort")
    
    session.run("black", "services/", "tests/", "noxfile.py")
    session.run("isort", "services/", "tests/", "noxfile.py")


@nox.session(python=PYTHON_VERSIONS)
def coverage(session):
    """Generate coverage report."""
    session.install(*TEST_DEPS)
    
    # Install all dependencies
    for service in SERVICES:
        requirements_file = f"services/{service}/requirements.txt"
        session.install("-r", requirements_file, silent=True)
    
    # Run all tests with coverage
    session.run(
        "pytest",
        SHARED_TESTS,
        *SERVICE_TESTS.values(),
        "tests/integration",
        "--cov=services",
        "--cov-report=html",
        "--cov-report=xml",
        "--cov-report=term-missing",
        "-v"
    )


@nox.session(python=PYTHON_VERSIONS)
def test_docker(session):
    """Run tests in Docker environment."""
    session.run(
        "docker-compose",
        "-f", "docker-compose.test.yml",
        "up", "--build", "--abort-on-container-exit",
        external=True
    )


# Convenience sessions for individual services
@nox.session(python=PYTHON_VERSIONS, name="test-gateway")
def test_gateway(session):
    """Run gateway service tests."""
    test_service(session, "gateway")


@nox.session(python=PYTHON_VERSIONS, name="test-shortener")
def test_shortener(session):
    """Run shortener service tests."""
    test_service(session, "shortener")


@nox.session(python=PYTHON_VERSIONS, name="test-redirector")
def test_redirector(session):
    """Run redirector service tests."""
    test_service(session, "redirector")


@nox.session(python=PYTHON_VERSIONS, name="test-analytics")
def test_analytics(session):
    """Run analytics service tests."""
    test_service(session, "analytics")
