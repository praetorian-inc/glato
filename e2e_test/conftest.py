"""
Configuration for end-to-end tests using pytest.
This file provides fixtures and configuration for testing against a real GitLab instance.
"""

import os
import pytest
import subprocess
import json
from pathlib import Path


def pytest_addoption(parser):
    """Add command-line options for testing with GitLab."""
    parser.addoption(
        "--gitlab-url", 
        default=None,  # No default - will be determined per test
        help="GitLab instance URL for testing (optional - auto-detected per test)"
    )
    parser.addoption(
        "--tokens-file", 
        default=os.environ.get("GLATO_TEST_TOKENS_FILE", "terraform-self-hosted/gitlab_tokens.env"),
        help="Path to the file containing GitLab test tokens"
    )


@pytest.fixture(scope="function")  # Changed from session to function scope
def gitlab_url(request):
    """Return the GitLab URL to use for tests, auto-detected based on test name."""
    # Check if URL was explicitly provided via command line
    explicit_url = request.config.getoption("--gitlab-url")
    if explicit_url:
        return explicit_url
    
    # Auto-detect based on test name/path
    test_name = request.node.name.lower()
    test_file = str(request.node.fspath).lower()
    
    # Check if this is a SaaS test
    is_saas_test = (
        "saas" in test_name or 
        "saas" in test_file or
        "test_runner_e2e_verification" in test_file or  # This file tests SaaS runners
        "saas" in str(request.node.cls).lower() if request.node.cls else False
    )
    
    if is_saas_test:
        return os.environ.get("SAAS_GITLAB_URL", "https://gitlab.com")
    else:
        return (os.environ.get("SELF_HOSTED_GITLAB_URL") or 
                os.environ.get("GITLAB_URL", "https://gitlab.com"))


@pytest.fixture(scope="session")
def tokens_file(request):
    """Return the path to the tokens file for backward compatibility."""
    return request.config.getoption("--tokens-file")


@pytest.fixture(scope="session")
def tokens(request):
    """Load GitLab tokens from the tokens file or environment variables."""
    tokens_file = request.config.getoption("--tokens-file")
    tokens = {}
    
    # Try to load from file first
    if Path(tokens_file).exists():
        try:
            with open(tokens_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and line.startswith('export ') and '=' in line:
                        # Extract token name and value from export statements
                        name, value = line.replace('export ', '', 1).split('=', 1)
                        tokens[name] = value.strip('"').strip("'")
        except Exception as e:
            print(f"Warning: Failed to read tokens file {tokens_file}: {e}")
    
    # Fallback to environment variables
    env_token_names = [
        # Self-hosted tokens (standardized names)
        'SELF_HOSTED_ALICE_TOKEN',
        'SELF_HOSTED_BOB_TOKEN',
        'SELF_HOSTED_IRENE_TOKEN',
        'SELF_HOSTED_ADMIN_TOKEN',
        
        # SaaS tokens (standardized names)  
        'SAAS_ALICE_TOKEN',
        'SAAS_BOB_TOKEN',
        'SAAS_IRENE_TOKEN',
        'SAAS_ADMIN_TOKEN',
        
        # Additional specialized roles (if needed)
        'SELF_HOSTED_CAROL_TOKEN',
        'SELF_HOSTED_DAVE_TOKEN',
        'SELF_HOSTED_EVE_TOKEN',
        'SELF_HOSTED_FRANK_TOKEN',
        'SELF_HOSTED_GRACE_TOKEN',
        'SELF_HOSTED_HENRY_TOKEN'
    ]
    
    for env_name in env_token_names:
        if env_name in os.environ:
            tokens[env_name] = os.environ[env_name]
    
    if not tokens:
        print(f"Warning: No tokens found in {tokens_file} or environment variables. Some tests may be skipped.")
    
    return tokens


@pytest.fixture(scope="session")
def alice_token(tokens):
    """Return Alice's full API access token for self-hosted testing."""
    token_name = "SELF_HOSTED_ALICE_TOKEN"
    if token_name not in tokens:
        pytest.skip(f"Token {token_name} not found. Please set SELF_HOSTED_ALICE_TOKEN environment variable.")
    return tokens[token_name]


@pytest.fixture(scope="session")
def bob_token(tokens):
    """Return Bob's read-only API token for self-hosted testing."""
    token_name = "SELF_HOSTED_BOB_TOKEN"
    if token_name not in tokens:
        pytest.skip(f"Token {token_name} not found. Please set SELF_HOSTED_BOB_TOKEN environment variable.")
    return tokens[token_name]


@pytest.fixture(scope="session")
def carol_token(tokens):
    """Return Carol's limited access token for self-hosted testing."""
    token_name = "SELF_HOSTED_CAROL_TOKEN"
    if token_name not in tokens:
        pytest.skip(f"Token {token_name} not found. Please set SELF_HOSTED_CAROL_TOKEN environment variable.")
    return tokens[token_name]


@pytest.fixture(scope="session")
def dave_token(tokens):
    """Return Dave's developer access token for self-hosted testing."""
    token_name = "SELF_HOSTED_DAVE_TOKEN"
    if token_name not in tokens:
        pytest.skip(f"Token {token_name} not found. Please set SELF_HOSTED_DAVE_TOKEN environment variable.")
    return tokens[token_name]


@pytest.fixture(scope="session")
def eve_token(tokens):
    """Return Eve's product access token for self-hosted testing."""
    token_name = "SELF_HOSTED_EVE_TOKEN"
    if token_name not in tokens:
        pytest.skip(f"Token {token_name} not found. Please set SELF_HOSTED_EVE_TOKEN environment variable.")
    return tokens[token_name]


@pytest.fixture(scope="session")
def frank_token(tokens):
    """Return Frank's DevOps access token for self-hosted testing."""
    token_name = "SELF_HOSTED_FRANK_TOKEN"
    if token_name not in tokens:
        pytest.skip(f"Token {token_name} not found. Please set SELF_HOSTED_FRANK_TOKEN environment variable.")
    return tokens[token_name]


@pytest.fixture(scope="session")
def grace_token(tokens):
    """Return Grace's security access token for self-hosted testing."""
    token_name = "SELF_HOSTED_GRACE_TOKEN"
    if token_name not in tokens:
        pytest.skip(f"Token {token_name} not found. Please set SELF_HOSTED_GRACE_TOKEN environment variable.")
    return tokens[token_name]


@pytest.fixture(scope="session")
def henry_token(tokens):
    """Return Henry's finance access token for self-hosted testing."""
    token_name = "SELF_HOSTED_HENRY_TOKEN"
    if token_name not in tokens:
        pytest.skip(f"Token {token_name} not found. Please set SELF_HOSTED_HENRY_TOKEN environment variable.")
    return tokens[token_name]


@pytest.fixture(scope="session")
def irene_token(tokens):
    """Return Irene's executive access token for self-hosted testing."""
    token_name = "SELF_HOSTED_IRENE_TOKEN"
    if token_name not in tokens:
        pytest.skip(f"Token {token_name} not found. Please set SELF_HOSTED_IRENE_TOKEN environment variable.")
    return tokens[token_name]


@pytest.fixture(scope="session")
def alice_token_saas(tokens):
    """Return Alice's token for SaaS testing."""
    token_name = "SAAS_ALICE_TOKEN"
    if token_name in tokens:
        return tokens[token_name]
    if token_name in os.environ:
        return os.environ[token_name]
    pytest.skip(f"Token {token_name} not found. Please set SAAS_ALICE_TOKEN environment variable.")


@pytest.fixture(scope="session")
def bob_token_saas(tokens):
    """Return Bob's token for SaaS testing."""
    token_name = "SAAS_BOB_TOKEN"
    if token_name in tokens:
        return tokens[token_name]
    if token_name in os.environ:
        return os.environ[token_name]
    pytest.skip(f"Token {token_name} not found. Please set SAAS_BOB_TOKEN environment variable.")


@pytest.fixture(scope="session")
def irene_token_saas(tokens):
    """Return Irene's token for SaaS testing."""
    token_name = "SAAS_IRENE_TOKEN"
    if token_name in tokens:
        return tokens[token_name]
    if token_name in os.environ:
        return os.environ[token_name]
    pytest.skip(f"Token {token_name} not found. Please set SAAS_IRENE_TOKEN environment variable.")


@pytest.fixture(scope="session")
def test_project_path_saas():
    """Return the test project path for SaaS environment."""
    # Use an actual project that exists in the GitLab environment
    return "engineering-glato/eng-repo-glato"           