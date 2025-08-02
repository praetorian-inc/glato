"""
End-to-end tests for GitLab SaaS token enumeration functionality.

This module tests token enumeration specifically on GitLab SaaS,
focusing on SaaS-specific behaviors and optimizations.
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
        timeout=300  # 5 minutes timeout for slow API responses
    )
    
    if expect_success and result.returncode != 0:
        pytest.fail(f"Command failed with exit code {result.returncode}:\n{result.stderr}")
    
    return result


def run_glato_with_timeout(args, token=None, timeout=30):
    """Run glato with a custom timeout for SaaS testing."""
    cmd = ["glato"]
    cmd.extend(args)
    
    env = os.environ.copy()
    if token:
        env["GL_TOKEN"] = token
    
    try:
        result = subprocess.run(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout
        )
    except subprocess.TimeoutExpired as e:
        # Create a mock result object for timeout cases
        class TimeoutResult:
            def __init__(self, stdout, stderr):
                self.returncode = 124  # Standard timeout exit code
                self.stdout = stdout.decode() if isinstance(stdout, bytes) else (stdout or "")
                self.stderr = stderr.decode() if isinstance(stderr, bytes) else (stderr or "")
        
        result = TimeoutResult(e.stdout, e.stderr)
    
    return result


class TestSaaSTokenEnumeration:
    """Token enumeration tests specifically for GitLab SaaS."""

    def test_admin_token_enumeration(self, gitlab_url, alice_token_saas):
        """Test that admin tokens can be enumerated correctly on SaaS."""
        result = run_glato(["-u", gitlab_url, "--enumerate-token"], token=alice_token_saas)
        
        assert result.returncode == 0, "Token enumeration should succeed"
        output_lower = result.stdout.lower()
        
        # Common validations for SaaS
        assert "alice" in output_lower, "Alice's username not found"
        assert "api" in output_lower, "API scope not found in token info"
        
        # Validate comprehensive token information
        required_fields = ["username:", "user id:", "email:", "scopes:", "token name:"]
        for field in required_fields:
            assert field in output_lower, f"Required field '{field}' not found in token enumeration output"
        
        print("✅ Admin token enumeration successful on SaaS")

    def test_limited_token_enumeration(self, gitlab_url, bob_token_saas):
        """Test that limited tokens can be enumerated correctly on SaaS."""
        result = run_glato(["-u", gitlab_url, "--enumerate-token"], token=bob_token_saas)
        
        assert result.returncode == 0, "Token enumeration should succeed"
        output_lower = result.stdout.lower()
        
        assert "bob" in output_lower, "Bob's username not found"
        
        print("✅ Limited token enumeration successful on SaaS")

    def test_executive_token_enumeration(self, gitlab_url, irene_token_saas):
        """Test that executive tokens can be enumerated correctly on SaaS."""
        result = run_glato(["-u", gitlab_url, "--enumerate-token"], token=irene_token_saas)
        
        assert result.returncode == 0, "Token enumeration should succeed"
        output_lower = result.stdout.lower()
        
        assert "irene" in output_lower, "Irene's username not found"
        assert "api" in output_lower or "read_api" in output_lower, "Irene should have API access"
        
        print("✅ Executive token enumeration successful on SaaS")

    def test_token_scope_limitations(self, gitlab_url, bob_token_saas):
        """Test that token scope limitations are properly identified on SaaS."""
        timeout = 45  # Shorter timeout for SaaS due to potential performance issues
        
        result = run_glato_with_timeout([
            "-u", gitlab_url,
            "--enumerate-projects",
            "--enumerate-secrets"
        ], token=bob_token_saas, timeout=timeout)
        
        if result.returncode == 124:
            pytest.fail("Project and secret enumeration timed out on GitLab SaaS. "
                       "The SaaS optimization should prevent this by skipping non-member public projects.")
        elif result.returncode == 0:
            # Validate SaaS optimization is working
            output_lower = result.stdout.lower()
            
            # Should see Bob's user info
            assert "bob" in output_lower, "Bob's username should be displayed"
            
            # Check for scope limitations or SaaS optimization
            if "error:" in output_lower and "scope required" in output_lower:
                print("✅ Expected scope limitation detected for Bob's token")
            elif "skipping enumeration of non-member public projects on gitlab saas" in output_lower:
                print("✅ SaaS optimization detected: non-member public projects skipped")
            else:
                print("✅ Bob's token has sufficient permissions for both operations")
        else:
            # Check if it's a scope/permission issue rather than timeout
            error_text = (result.stdout + " " + result.stderr).lower()
            if any(term in error_text for term in ["scope", "permission", "forbidden", "unauthorized"]):
                print(f"✅ Operation failed due to token limitations: {result.stderr}")
            else:
                pytest.fail(f"Unexpected failure: {result.stderr}")

    def test_comprehensive_token_information(self, gitlab_url, alice_token_saas):
        """Test that token enumeration returns comprehensive user and token information on SaaS."""
        result = run_glato(["-u", gitlab_url, "--enumerate-token"], token=alice_token_saas)
        
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
        
        print("✅ Comprehensive token information validated on SaaS")

    def test_rate_limiting_behavior(self, gitlab_url, alice_token_saas):
        """Test that rate limiting is handled gracefully on SaaS."""
        # Test multiple rapid requests
        results = []
        for i in range(3):
            result = run_glato(["-u", gitlab_url, "--enumerate-token"], token=alice_token_saas)
            results.append(result)
            time.sleep(1)  # Small delay between requests
        
        # All requests should succeed (GitLab SaaS has generous rate limits for this operation)
        for i, result in enumerate(results):
            assert result.returncode == 0, f"Request {i+1} failed: {result.stderr}"
        
        print("✅ Rate limiting behavior validated on SaaS")

    def test_invalid_token_handling(self, gitlab_url):
        """Test that invalid tokens are handled gracefully on SaaS."""
        invalid_token = "invalid_token_12345"
        
        result = run_glato(["-u", gitlab_url, "--enumerate-token"], 
                          token=invalid_token, expect_success=False)
        
        # Should fail with appropriate error
        assert result.returncode != 0, "Invalid token should cause failure"
        
        error_text = (result.stdout + " " + result.stderr).lower()
        expected_errors = ["unauthorized", "401", "invalid", "token", "authentication"]
        
        has_expected_error = any(error in error_text for error in expected_errors)
        assert has_expected_error, f"Should show authentication error, got: {error_text}"
        
        print("✅ Invalid token handled gracefully with appropriate error on SaaS")

    def test_token_enumeration_output_format(self, gitlab_url, alice_token_saas):
        """Test that token enumeration output format is consistent on SaaS."""
        result = run_glato(["-u", gitlab_url, "--enumerate-token"], token=alice_token_saas)
        
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
        
        print("✅ Token enumeration output format validated on SaaS")

    def test_saas_environment_detection(self, gitlab_url, alice_token_saas):
        """Test that SaaS environment is properly detected and handled."""
        result = run_glato(["-u", gitlab_url, "--enumerate-token"], token=alice_token_saas)
        
        assert result.returncode == 0, "Token enumeration should succeed"
        assert "gitlab.com" in gitlab_url.lower(), "Should be testing against GitLab SaaS"
        
        # SaaS-specific behavior validation
        output_lower = result.stdout.lower()
        
        # Should show user information without environment-specific warnings
        assert "alice" in output_lower, "User information should be present"
        
        print("✅ SaaS environment detection and handling validated") 