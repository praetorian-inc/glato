"""
Configuration for GitLab SaaS end-to-end tests using pytest.
This file provides fixtures and configuration for testing against GitLab.com (SaaS).
"""

import os
import pytest
from pathlib import Path


def pytest_addoption(parser):
    """Add command-line options for testing with GitLab SaaS."""
    parser.addoption(
        "--gitlab-url", 
        default=(os.environ.get("SAAS_GITLAB_URL") or 
                os.environ.get("GITLAB_URL", "https://gitlab.com")),
        help="GitLab SaaS URL for testing (default: https://gitlab.com)"
    )
    parser.addoption(
        "--tokens-file", 
        default=os.environ.get("GLATO_TEST_TOKENS_FILE", "terraform-gitlab-saas/gitlab_tokens.env"),
        help="Path to the file containing GitLab SaaS test tokens"
    )


@pytest.fixture(scope="session")
def gitlab_url(request):
    """Return the GitLab SaaS URL to use for tests."""
    return request.config.getoption("--gitlab-url")


@pytest.fixture(scope="session")
def tokens_file_saas(request):
    """Return the path to the SaaS tokens file."""
    return request.config.getoption("--tokens-file")


@pytest.fixture(scope="session")
def tokens_saas(request):
    """Load GitLab SaaS tokens from the tokens file or environment variables."""
    tokens_file = request.config.getoption("--tokens-file")
    tokens = {}
    
    if Path(tokens_file).exists():
        try:
            with open(tokens_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and line.startswith('export ') and '=' in line:
                        name, value = line.replace('export ', '', 1).split('=', 1)
                        tokens[name] = value.strip('"').strip("'")
        except Exception as e:
            print(f"Warning: Failed to read tokens file {tokens_file}: {e}")
    
    # Environment variables for standardized SaaS token names only
    saas_env_token_names = [
        # Standardized SaaS token names
        'SAAS_ALICE_TOKEN',
        'SAAS_BOB_TOKEN',
        'SAAS_IRENE_TOKEN',
        'SAAS_ADMIN_TOKEN'
    ]
    
    for env_name in saas_env_token_names:
        if env_name in os.environ:
            tokens[env_name] = os.environ[env_name]
    
    if not tokens:
        print(f"Warning: No SaaS tokens found in {tokens_file} or environment variables. Some tests may be skipped.")
    
    return tokens


@pytest.fixture(scope="session")
def alice_token_saas(tokens_saas):
    """Return Alice's token for SaaS testing."""
    token_name = "SAAS_ALICE_TOKEN"
    if token_name not in tokens_saas:
        pytest.skip(f"Token {token_name} not found in SaaS tokens file")
    return tokens_saas[token_name]


@pytest.fixture(scope="session")
def bob_token_saas(tokens_saas):
    """Return Bob's token for SaaS testing."""
    token_name = "SAAS_BOB_TOKEN"
    if token_name not in tokens_saas:
        pytest.skip(f"Token {token_name} not found in SaaS tokens file")
    return tokens_saas[token_name]


@pytest.fixture(scope="session")
def irene_token_saas(tokens_saas):
    """Return Irene's token for SaaS testing."""
    token_name = "SAAS_IRENE_TOKEN"
    if token_name not in tokens_saas:
        pytest.skip(f"Token {token_name} not found in SaaS tokens file")
    return tokens_saas[token_name]


@pytest.fixture(scope="session")
def test_project_path_saas():
    """Return the test project path for SaaS environment."""
    return "acme-corporation-glato/product-glato/api-glato/api-service-glato"
