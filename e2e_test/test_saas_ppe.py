"""
End-to-end tests for GitLab SaaS Privileged Project Exfiltration (PPE) functionality.

This module tests the PPE functionality which creates branches and merge requests
to exfiltrate project data on GitLab SaaS.

Test Assumptions:
- alice_token has full API access and can execute PPE attacks
- bob_token has read_api scope only (insufficient for PPE)
- Project "product-glato/api-glato/api-service-glato" exists and is accessible
- GitLab runners are properly configured and online
"""

import os
import time
import pytest
import subprocess
import tempfile
import json
import re
from pathlib import Path


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


class TestPPEExfiltration:
    """Test cases for PPE secret exfiltration functionality."""
    
    def test_ppe_successful_exfiltration(self, gitlab_url, alice_token_saas):
        """Test that PPE can successfully exfiltrate secrets from a GitLab project."""
        result = run_glato([
            "-u", "https://gitlab.com",  # Force GitLab.com for SaaS testing
            "--exfil-secrets-via-ppe",
            "--project-path", "product-glato/api-glato/api-service-glato"
        ], token=alice_token_saas)
        
        assert result.returncode == 0, f"PPE exfiltration failed: {result.stderr}"
        
        assert "Beginning Secrets Exfiltration" in result.stdout, "PPE process not started"
        assert "Printing decrypted output of secrets exfiltration" in result.stdout, "Decrypted output header not found"
        assert "-----------------" in result.stdout, "Output section markers not found"
    
    def test_ppe_with_branch_parameter(self, gitlab_url, alice_token_saas):
        """Test PPE exfiltration with custom branch parameter."""
        result = run_glato([
            "-u", "https://gitlab.com",
            "--exfil-secrets-via-ppe",
            "--project-path", "product-glato/api-glato/api-service-glato",
            "--branch", "main"  # Use main instead of test-branch
        ], token=alice_token_saas)
        
        assert result.returncode == 0, f"PPE with branch parameter failed: {result.stderr}"
        assert "decrypted output" in result.stdout.lower(), "Decrypted output not found"
    
    def test_ppe_error_handling_invalid_project(self, gitlab_url, alice_token_saas):
        """Test PPE error handling when targeting an invalid or inaccessible project."""
        result = run_glato([
            "-u", "https://gitlab.com",
            "--exfil-secrets-via-ppe",
            "--project-path", "nonexistent/invalid-project"
        ], token=alice_token_saas)
        
        assert result.returncode != 0, "Expected failure for invalid project"
        assert ("error" in result.stderr.lower() or "error" in result.stdout.lower() or
                "not found" in result.stderr.lower() or "not found" in result.stdout.lower()), "Error message not found"
    
    def test_ppe_error_handling_insufficient_permissions(self, gitlab_url, bob_token_saas):
        """Test PPE error handling when user lacks sufficient permissions."""
        result = run_glato([
            "-u", "https://gitlab.com",
            "--exfil-secrets-via-ppe",
            "--project-path", "product-glato/api-glato/api-service-glato"
        ], token=bob_token_saas)
        
        assert "Error: api scope required" in result.stdout, "Expected API scope error message not found"
    
    def test_ppe_missing_project_path_error(self, gitlab_url, alice_token_saas):
        """Test that PPE fails when project-path is not provided."""
        result = run_glato([
            "-u", "https://gitlab.com",
            "--exfil-secrets-via-ppe"
        ], token=alice_token_saas)
        
        assert result.returncode != 0, "Expected failure for missing project-path"
        output_text = (result.stdout + " " + result.stderr).lower()
        assert "project-path" in output_text, "Missing project-path error not found"
    
    def test_ppe_cleanup_verification(self, gitlab_url, alice_token_saas):
        """Test that PPE output includes proper cleanup indicators."""
        result = run_glato([
            "-u", "https://gitlab.com",
            "--exfil-secrets-via-ppe",
            "--project-path", "product-glato/api-glato/api-service-glato"
        ], token=alice_token_saas)
        
        assert result.returncode == 0, f"PPE exfiltration failed: {result.stderr}"
        
        essential_indicators = [
            "Beginning Secrets Exfiltration",
            "Awaiting pipeline execution results",
            "Pipeline Status =",
            "Printing decrypted output"
        ]
        
        for indicator in essential_indicators:
            assert any(indicator in line for line in result.stdout.split('\n')), f"Missing essential indicator: {indicator}"
            
        assert any("Creating .gitlab-ci.yml" in line or "Updating .gitlab-ci.yml" in line 
                  for line in result.stdout.split('\n')), "Missing .gitlab-ci.yml creation/update indicator"

    def test_ppe_output_validation(self, gitlab_url, alice_token_saas):
        """Test that PPE produces valid output with user information and execution details."""
        result = run_glato([
            "-u", "https://gitlab.com",
            "--exfil-secrets-via-ppe",
            "--project-path", "product-glato/api-glato/api-service-glato"
        ], token=alice_token_saas)
        
        assert result.returncode == 0, f"PPE exfiltration failed: {result.stderr}"
        
        assert "Printing decrypted output of secrets exfiltration" in result.stdout
        assert "-----------------" in result.stdout
        
        lines = result.stdout.split('\n')
        start_idx = None
        end_idx = None
        for i, line in enumerate(lines):
            if line.strip() == "-----------------":
                if start_idx is None:
                    start_idx = i + 1
                else:
                    end_idx = i
                    break
        
        assert start_idx is not None and end_idx is not None, "Could not find decrypted content markers"
        decrypted_content = '\n'.join(lines[start_idx:end_idx])
        
        print(f"\nDecrypted content preview (first 200 chars): {decrypted_content[:200]}...")
        
        user_info_patterns = [
            "User ID:", 
            "Username:", 
            "Email:",
            "Token Name:"
        ]
        
        for pattern in user_info_patterns:
            assert pattern in decrypted_content, f"Missing expected user information: {pattern}"
            
        pipeline_patterns = [
            "Beginning Secrets Exfiltration",
            "branch",
            "Pipeline Status"
        ]
        
        for pattern in pipeline_patterns:
            assert pattern in decrypted_content, f"Missing expected pipeline information: {pattern}"
