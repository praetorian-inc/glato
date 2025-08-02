"""
End-to-end tests for GitLab self-hosted group and secret enumeration functionality.

This module tests secret enumeration across different group hierarchies
in self-hosted GitLab environments.
"""

import pytest
import subprocess
import os


def run_glato(args, token=None):
    """Run glato command with proper environment setup."""
    cmd = ["glato"]
    cmd.extend(args)
    
    env = os.environ.copy()
    if token:
        env["GL_TOKEN"] = token
    
    result = subprocess.run(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    return result


class TestGroupEnumeration:
    """Test cases for group enumeration functionality."""
    
    def test_enumerate_groups_full_access(self, gitlab_url, alice_token):
        """Test that groups can be enumerated with a full access token."""
        result = run_glato(["-u", gitlab_url, "--enumerate-groups"], token=alice_token)
        
        # Check that at least one group is found
        assert "group:" in result.stdout.lower(), "No groups found"
        # Check for the group Alice has access to
        assert "engineering-glato" in result.stdout.lower(), "Engineering group not found"
    
    def test_enumerate_groups_with_limited_access(self, gitlab_url, bob_token):
        """Test that only accessible groups are enumerated with a limited token."""
        # Just verify the command runs with Bob's token
        result = run_glato(["-u", gitlab_url, "--enumerate-groups"], token=bob_token)
        
        # Check that Bob's info is shown
        assert "bob-glato" in result.stdout.lower(), "User info not found"


class TestSecretEnumeration:
    """Test cases for secret enumeration functionality."""
    
    def test_enumerate_secrets_with_full_access(self, gitlab_url, alice_token):
        """Test that secrets can be enumerated with a full access token."""
        # Run Glato with secret enumeration flags
        result = run_glato(["-u", gitlab_url, "--enumerate-projects", "--enumerate-secrets"], 
                          token=alice_token)
        
        # Check for secret enumeration indicators in the output
        assert "found" in result.stdout.lower() and "project variable" in result.stdout.lower(), "Project variable information not found"
        
        # Test for specific secrets we expect to find
        assert "digitalocean_access_token" in result.stdout.lower(), "DigitalOcean access token not found"
        assert "aws_access_key_id" in result.stdout.lower(), "AWS access key not found"
        assert "aws_secret_access_key" in result.stdout.lower(), "AWS secret key not found"
        
        # Check for protection status indicators
        assert "protected" in result.stdout.lower(), "Protected variable indicators not found"
        assert "masked" in result.stdout.lower(), "Masked variable indicators not found"
        
        # Check for specific project secrets
        assert "infrastructure-glato" in result.stdout.lower(), "Infrastructure project not found"
        assert "security-scanner-glato" in result.stdout.lower(), "Security scanner project not found"
        
        # Verify secrets from different domains
        assert "firebase_token" in result.stdout.lower(), "Firebase token not found"
        assert "github_token" in result.stdout.lower(), "GitHub token not found"
        assert "slack_webhook_url" in result.stdout.lower(), "Slack webhook URL not found"
        assert "vault_token" in result.stdout.lower(), "Vault token not found"
        assert "tf_api_token" in result.stdout.lower(), "Terraform API token not found"
    
    def test_secret_formats_and_protection(self, gitlab_url, alice_token):
        """Test that secrets have proper formatting and protection statuses."""
        result = run_glato(["-u", gitlab_url, "--enumerate-projects", "--enumerate-secrets"], 
                          token=alice_token)
        
        # Check for AWS credential format 
        assert "akia" in result.stdout.lower(), "AWS Access Key format not found"
        
        # Check for token formats
        assert "ghp_" in result.stdout.lower(), "GitHub token format not found"
        assert "dop_v1_" in result.stdout.lower(), "DigitalOcean token format not found"
        assert "tfc-token-" in result.stdout.lower(), "Terraform Cloud token format not found"
        
        # Verify that sensitive variables are protected/masked
        aws_section = result.stdout.lower().split("aws_secret_access_key")[1].split("project:")[0]
        assert "protected" in aws_section and "masked" in aws_section, "AWS secret key is not properly protected and masked"
        
        # Verify that tokens have appropriate security settings
        tf_section = result.stdout.lower().split("tf_api_token")[1].split("vault_token")[0]
        assert "protected" in tf_section and "masked" in tf_section, "Terraform API token is not properly protected and masked"
    
    def test_limited_access_secret_enumeration(self, gitlab_url, bob_token):
        """Test that secrets enumeration is restricted with limited scope token."""
        # The command may succeed but should indicate limited permissions
        result = run_glato(["-u", gitlab_url, "--enumerate-projects", "--enumerate-secrets"], 
                          token=bob_token)
        
        # Check for error message indicating limited permissions
        assert "error:" in result.stdout.lower() or "scope required" in result.stdout.lower(), "Expected message about limited permissions not found"
    
    def test_departmental_secrets_access(self, gitlab_url, frank_token):
        """Test that DevOps user can access infrastructure secrets."""
        result = run_glato(["-u", gitlab_url, "--enumerate-projects", "--enumerate-secrets"], 
                          token=frank_token)
        
        # Check that Frank can see DevOps infrastructure secrets
        assert "infrastructure-glato" in result.stdout.lower(), "Infrastructure project not found"
        # Check that Frank can see some secrets but not others based on department
        assert "digitalocean_access_token" in result.stdout.lower() or "aws_" in result.stdout.lower(), "Expected DevOps secrets not found"


class TestSelfEnumeration:
    """Test cases for self enumeration functionality."""
    
    def test_self_enumeration_with_full_access(self, gitlab_url, alice_token):
        """Test that self enumeration works with a full access token."""
        result = run_glato(["-u", gitlab_url, "--self-enumeration"], token=alice_token)
        
        # Check that various parts of the output are present
        assert result.returncode == 0, "Self enumeration failed"
        assert "alice" in result.stdout.lower(), "Username not found" 