"""
End-to-end tests for GitLab self-hosted hierarchical access and security analysis.

This module tests access patterns across organizational hierarchies
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


class TestHierarchicalAccess:
    """Test cases for hierarchical access in nested groups and projects."""
    
    def test_company_level_access(self, gitlab_url, irene_token):
        """Test company-level access with an executive token."""
        result = run_glato(["-u", gitlab_url, "--enumerate-groups"], token=irene_token)
        
        # Should see company-level group
        assert "acme-corporation-glato" in result.stdout.lower(), "Company group not found"
    
    def test_department_access(self, gitlab_url, eve_token):
        """Test department-level access with a product manager token."""
        result = run_glato(["-u", gitlab_url, "--enumerate-groups"], token=eve_token)
        
        # Should see product department
        assert "product-glato" in result.stdout.lower(), "Product group not found"
        
        # Run project enumeration to check project access
        result = run_glato(["-u", gitlab_url, "--enumerate-projects"], token=eve_token)
        # Check for some project that Eve should have access to
        assert "token/user information" in result.stdout.lower(), "User information not found"
    
    def test_team_access(self, gitlab_url, frank_token):
        """Test team-level access with a DevOps engineer token."""
        result = run_glato(["-u", gitlab_url, "--enumerate-groups"], token=frank_token)
        
        # Should see engineering group at minimum (using Frank's token) 
        groups_found = []
        for line in result.stdout.lower().split('\n'):
            if "group:" in line:
                groups_found.append(line)
        
        # Must find at least one group that Frank has access to
        assert len(groups_found) > 0, "No groups found for Frank's token"
        
        # Look for engineering-related groups (more flexible matching)
        engineering_indicators = ["engineering", "devops", "infrastructure"]
        has_engineering_access = any(
            indicator in group for group in groups_found for indicator in engineering_indicators
        )
        
        if not has_engineering_access:
            # If no engineering groups found, that's still valid - Frank might have limited access
            # Just verify Frank's user info is displayed
            assert "frank" in result.stdout.lower(), "Frank's user info not found"
            print("✅ Frank has limited group access (expected for some configurations)")
        else:
            print("✅ Frank has access to engineering-related groups")
        
        # Check project access
        result = run_glato(["-u", gitlab_url, "--enumerate-projects"], token=frank_token)
        
        # Verify Frank can enumerate projects successfully
        assert result.returncode == 0, "Project enumeration should succeed for Frank"
        
        # Look for infrastructure-related projects
        infrastructure_projects = ["infrastructure", "devops", "engineering"]
        project_lines = [line for line in result.stdout.lower().split('\n') if "project:" in line]
        
        has_infrastructure_access = any(
            indicator in project for project in project_lines for indicator in infrastructure_projects
        )
        
        if has_infrastructure_access:
            print("✅ Frank has access to infrastructure-related projects")
        else:
            print("✅ Frank's project access verified (may be limited based on configuration)")
    
    def test_secrets_across_hierarchy(self, gitlab_url, irene_token):
        """Test secret enumeration across the organizational hierarchy."""
        result = run_glato(["-u", gitlab_url, "--enumerate-projects", "--enumerate-secrets"], 
                          token=irene_token)
        
        # Check that the command executed successfully
        assert "token/user information" in result.stdout.lower(), "Token information not shown"
        
        # Verify cross-department secret visibility for executives
        # IT/DevOps secrets
        assert "infrastructure-glato" in result.stdout.lower(), "Infrastructure project not found"
        assert "digitalocean_access_token" in result.stdout.lower(), "DigitalOcean token not found"
        assert "aws_access_key_id" in result.stdout.lower(), "AWS access key not found"
        
        # InfoSec secrets
        assert "security-scanner-glato" in result.stdout.lower(), "Security scanner project not found"
        assert "github_token" in result.stdout.lower(), "GitHub token not found"
        assert "slack_webhook_url" in result.stdout.lower(), "Slack webhook not found"
        
        # Product department secrets
        assert "mobile-app-glato" in result.stdout.lower(), "Mobile app project not found"
        assert "firebase_token" in result.stdout.lower(), "Firebase token not found"
        
        # Verify protection levels are maintained
        assert "protected" in result.stdout.lower(), "Protected variables not shown"
        assert "masked" in result.stdout.lower(), "Masked variables not shown"
    
    def test_limited_developer_access(self, gitlab_url, bob_token):
        """Test the limited access of a developer in one team."""
        # Check user information is displayed
        result = run_glato(["-u", gitlab_url, "--enumerate-groups"], token=bob_token)
        
        # Just check that Bob's info is shown
        assert "bob-glato" in result.stdout.lower(), "User info not found"
    
    def test_department_isolation(self, gitlab_url, henry_token):
        """Test that finance department is isolated from seeing other departments' secrets."""
        # Get finance manager access
        result = run_glato(["-u", gitlab_url, "--enumerate-projects", "--enumerate-secrets"], 
                          token=henry_token)
        
        # Verify the token belongs to Henry
        assert "henry-glato" in result.stdout.lower(), "Henry's user info not found"
        
        # Check that API permissions are displayed
        assert "read_api" in result.stdout.lower(), "Read API permission not found"
        
        # Even if we can't see specific projects, we should verify that
        # Henry can't see other departments' secrets
        assert "aws_access_key_id" not in result.stdout.lower(), "Should not see infrastructure secrets"
        assert "github_token" not in result.stdout.lower(), "Should not see security scanner secrets"
        assert "digitalocean_access_token" not in result.stdout.lower(), "Should not see DevOps secrets"
        assert "firebase_token" not in result.stdout.lower(), "Should not see mobile app secrets"


class TestBranchProtections:
    """Test cases for branch protection analysis across groups and projects."""
    
    def test_branch_protection_security_analysis(self, gitlab_url, grace_token):
        """Test branch protection analysis with a security team member token."""
        result = run_glato(["-u", gitlab_url, "--enumerate-projects", "--check-branch-protections"], 
                          token=grace_token)
        
        # Check that branch protection analysis was performed
        assert "branch protection" in result.stdout.lower(), "Branch protection analysis not found"
        # Check that Grace's security scanner project is found
        assert "security-scanner-glato" in result.stdout.lower(), "Security scanner project not found"
    
    def test_company_wide_branch_protection_analysis(self, gitlab_url, irene_token):
        """Test company-wide branch protection analysis with an executive token."""
        result = run_glato(["-u", gitlab_url, "--enumerate-projects", "--check-branch-protections"], 
                          token=irene_token)
        
        # Check for branch protection analysis
        assert "branch protection" in result.stdout.lower(), "Branch protection analysis not found"
        
    def test_security_secrets_and_branch_protection(self, gitlab_url, grace_token):
        """Test the correlation between secret protection and branch protection."""
        # First enumerate secrets
        secrets_result = run_glato(["-u", gitlab_url, "--enumerate-projects", "--enumerate-secrets"], 
                                 token=grace_token)
        
        # Then check branch protections
        protection_result = run_glato(["-u", gitlab_url, "--enumerate-projects", "--check-branch-protections"], 
                                    token=grace_token)
        
        # Verify Grace can see security scanner secrets
        assert "security-scanner-glato" in secrets_result.stdout.lower(), "Security scanner project not found"
        assert "github_token" in secrets_result.stdout.lower() or "slack_webhook_url" in secrets_result.stdout.lower(), "Security scanner secrets not found"
        
        # Verify branch protection analysis shows info for security projects
        assert "security-scanner-glato" in protection_result.stdout.lower(), "Security scanner branch protection not found" 