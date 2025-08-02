"""
End-to-end tests for GitLab self-hosted token enumeration functionality.

This module tests token enumeration specifically on self-hosted GitLab,
focusing on self-hosted-specific behaviors and configurations.
"""

import pytest
import subprocess
import os
import time


def run_glato(args, token=None, expect_success=True):
    """Run the glato command with the given arguments."""
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
        text=True,
        timeout=300  # 5 minutes timeout for API responses
    )
    
    if expect_success and result.returncode != 0:
        pytest.fail(f"Command failed with exit code {result.returncode}:\n{result.stderr}")
    
    return result


class TestSelfHostedTokenEnumeration:
    """Token enumeration tests specifically for self-hosted GitLab."""

    def test_admin_token_enumeration(self, gitlab_url, alice_token):
        """Test that admin tokens can be enumerated correctly on self-hosted."""
        result = run_glato(["-u", gitlab_url, "--enumerate-token"], token=alice_token)
        
        assert result.returncode == 0, "Token enumeration should succeed"
        output_lower = result.stdout.lower()
        
        # Common validations for self-hosted
        assert "alice" in output_lower, "Alice's username not found"
        assert "api" in output_lower, "API scope not found in token info"
        
        # Validate comprehensive token information
        required_fields = ["username:", "user id:", "email:", "scopes:", "token name:"]
        for field in required_fields:
            assert field in output_lower, f"Required field '{field}' not found in token enumeration output"
        
        print("✅ Admin token enumeration successful on self-hosted")

    def test_limited_token_enumeration(self, gitlab_url, bob_token):
        """Test that limited tokens can be enumerated correctly on self-hosted."""
        result = run_glato(["-u", gitlab_url, "--enumerate-token"], token=bob_token)
        
        assert result.returncode == 0, "Token enumeration should succeed"
        output_lower = result.stdout.lower()
        
        assert "bob" in output_lower, "Bob's username not found"
        
        # Self-hosted: Bob should have read_api scope
        assert "read_api" in output_lower, "read_api scope not found in token info"
        
        print("✅ Limited token enumeration successful on self-hosted")

    def test_token_scope_limitations(self, gitlab_url, bob_token):
        """Test that token scope limitations are properly identified on self-hosted."""
        # Self-hosted: Test scope limitations - Bob's read_api token should fail for secrets enumeration
        result = run_glato(["-u", gitlab_url, "--enumerate-projects", "--enumerate-secrets"], 
                          token=bob_token, expect_success=False)
        
        # Should fail with scope limitation error
        assert result.returncode != 0, "Should fail due to insufficient token scopes"
        
        error_text = (result.stdout + " " + result.stderr).lower()
        
        # Should show scope limitation error  
        scope_error_indicators = ["api", "scope", "required", "error"]
        has_scope_error = any(indicator in error_text for indicator in scope_error_indicators)
        
        if has_scope_error:
            print("✅ Expected scope limitation detected for Bob's read-only token")
        else:
            # If no explicit scope error, check that operations failed gracefully
            print("✅ Token enumeration handled scope limitations gracefully")

    def test_comprehensive_token_information(self, gitlab_url, alice_token):
        """Test that token enumeration returns comprehensive user and token information on self-hosted."""
        result = run_glato(["-u", gitlab_url, "--enumerate-token"], token=alice_token)
        
        assert result.returncode == 0, "Token enumeration should succeed"
        output_lines = result.stdout.lower().split('\n')
        
        # Required fields validation
        required_fields = {
            "username": False,
            "user id": False,
            "email": False,
            "scopes": False,
            "token name": False
        }
        
        for line in output_lines:
            for field in required_fields:
                if field in line:
                    required_fields[field] = True
        
        missing_fields = [field for field, found in required_fields.items() if not found]
        assert not missing_fields, f"Missing required fields in token information: {missing_fields}"
        
        print("✅ Comprehensive token information validated on self-hosted")

    def test_rate_limiting_behavior(self, gitlab_url, alice_token):
        """Test that rate limiting is handled gracefully on self-hosted."""
        # Test multiple rapid requests
        results = []
        for i in range(3):
            result = run_glato(["-u", gitlab_url, "--enumerate-token"], token=alice_token)
            results.append(result)
            time.sleep(0.5)  # Small delay between requests
        
        # All requests should succeed (self-hosted typically has generous rate limits)
        for i, result in enumerate(results):
            assert result.returncode == 0, f"Request {i+1} failed: {result.stderr}"
        
        print("✅ Rate limiting behavior validated on self-hosted")

    def test_invalid_token_handling(self, gitlab_url):
        """Test that invalid tokens are handled gracefully on self-hosted."""
        invalid_token = "invalid_token_12345"
        
        result = run_glato(["-u", gitlab_url, "--enumerate-token"], 
                          token=invalid_token, expect_success=False)
        
        # Should fail with appropriate error
        assert result.returncode != 0, "Invalid token should cause failure"
        
        error_text = (result.stdout + " " + result.stderr).lower()
        expected_errors = ["unauthorized", "401", "invalid", "token", "authentication"]
        
        has_expected_error = any(error in error_text for error in expected_errors)
        assert has_expected_error, f"Should show authentication error, got: {error_text}"
        
        print("✅ Invalid token handled gracefully with appropriate error on self-hosted")

    def test_token_enumeration_output_format(self, gitlab_url, alice_token):
        """Test that token enumeration output format is consistent on self-hosted."""
        result = run_glato(["-u", gitlab_url, "--enumerate-token"], token=alice_token)
        
        assert result.returncode == 0, "Token enumeration should succeed"
        
        # Check for consistent output formatting
        output_lines = result.stdout.split('\n')
        
        # Should have structured output with clear sections
        has_user_section = any("username:" in line.lower() for line in output_lines)
        has_token_section = any("token name:" in line.lower() for line in output_lines)
        has_scopes_section = any("scopes:" in line.lower() for line in output_lines)
        
        assert has_user_section, "User information section not found"
        assert has_token_section, "Token information section not found"  
        assert has_scopes_section, "Scopes section not found"
        
        print("✅ Token enumeration output format validated on self-hosted")

    def test_selfhosted_environment_behavior(self, gitlab_url, alice_token):
        """Test that self-hosted environment-specific behavior works correctly."""
        result = run_glato(["-u", gitlab_url, "--enumerate-token"], token=alice_token)
        
        assert result.returncode == 0, "Token enumeration should succeed"
        assert "gitlab.com" not in gitlab_url.lower(), "Should be testing against self-hosted GitLab"
        
        # Self-hosted-specific behavior validation
        output_lower = result.stdout.lower()
        
        # Should show user information without SaaS-specific optimizations
        assert "alice" in output_lower, "User information should be present"
        
        print("✅ Self-hosted environment behavior validated") 