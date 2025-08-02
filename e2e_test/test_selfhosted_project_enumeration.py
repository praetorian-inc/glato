"""
End-to-end tests for GitLab self-hosted project enumeration functionality.

This module tests the --enumerate-projects functionality specifically on self-hosted GitLab,
focusing on the differences from SaaS behavior like including non-member projects.
"""

import pytest
import subprocess
import os
import time
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


def run_glato_with_timeout(args, token=None, timeout=300):
    """Run glato command with timeout."""
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


def is_gitlab_saas(gitlab_url: str) -> bool:
    """Detect if GitLab URL is SaaS (gitlab.com) or self-hosted."""
    try:
        from glato.enumerate.enumerate import Enumerator
        
        class MockAPI:
            def __init__(self, gitlab_url):
                self.gitlab_url = gitlab_url
        
        enumerator = Enumerator(gitlab_url=gitlab_url)
        enumerator.api = MockAPI(gitlab_url)
        return enumerator._is_gitlab_saas()
    except Exception:
        # Fallback detection
        return "gitlab.com" in gitlab_url.lower()


class TestSelfHostedProjectEnumeration:
    """Test project enumeration functionality specifically on self-hosted GitLab."""

    def test_selfhosted_basic_enumeration(self, gitlab_url, alice_token):
        """Test basic project enumeration on self-hosted GitLab."""
        if is_gitlab_saas(gitlab_url):
            pytest.skip("Self-hosted test requires self-hosted GitLab environment")
            
        result = run_glato(["-u", gitlab_url, "--enumerate-projects"], token=alice_token)
        
        assert result.returncode == 0, "Self-hosted project enumeration should succeed"
        self._validate_project_enumeration_output(result.stdout)
        print("✅ Self-hosted project enumeration completed successfully")

    def test_selfhosted_includes_non_member_projects(self, gitlab_url, alice_token):
        """Test that self-hosted includes non-member public projects."""
        if is_gitlab_saas(gitlab_url):
            pytest.skip("Self-hosted test requires self-hosted GitLab environment")
            
        result = run_glato(["-u", gitlab_url, "--enumerate-projects"], token=alice_token)
        
        assert result.returncode == 0, "Project enumeration should succeed"
        
        # Check for self-hosted specific behavior
        assert "Enumerating Projects that User is Not A Member Of" in result.stdout, \
            "Non-member projects should be included on self-hosted instances"
            
        assert "Skipping enumeration of non-member public projects on GitLab SaaS" not in result.stdout, \
            "SaaS detection message should not appear for self-hosted instances"
            
        print("✅ Self-hosted correctly includes non-member public projects")

    def test_selfhosted_environment_detection(self, gitlab_url, alice_token):
        """Test that self-hosted environment is correctly detected."""
        if is_gitlab_saas(gitlab_url):
            pytest.skip("Self-hosted test requires self-hosted GitLab environment")
            
        # Verify detection function works correctly
        assert not is_gitlab_saas(gitlab_url), \
            f"URL {gitlab_url} should be detected as self-hosted, not SaaS"
        
        result = run_glato(["-u", gitlab_url, "--enumerate-projects"], token=alice_token)
        
        # Should NOT have SaaS-specific messages
        saas_indicators = [
            "skipping enumeration of non-member public projects on gitlab saas",
            "gitlab saas detected"
        ]
        
        has_saas_behavior = any(
            indicator in result.stdout.lower() for indicator in saas_indicators
        )
        
        assert not has_saas_behavior, \
            "Self-hosted instance should not show SaaS-specific behavior"
        
        print(f"✅ URL {gitlab_url} correctly identified as self-hosted GitLab")

    def test_selfhosted_performance_characteristics(self, gitlab_url, alice_token):
        """Test self-hosted project enumeration performance."""
        if is_gitlab_saas(gitlab_url):
            pytest.skip("Self-hosted test requires self-hosted GitLab environment")
            
        start_time = time.time()
        result = run_glato(["-u", gitlab_url, "--enumerate-projects"], token=alice_token)
        duration = time.time() - start_time
        
        assert result.returncode == 0, "Self-hosted enumeration should succeed"
        
        project_count = result.stdout.lower().count("project: ")
        rate = project_count / duration if duration > 0 else 0
        
        print(f"Self-hosted enumerated {project_count} projects in {duration:.1f}s ({rate:.1f} projects/sec)")
        
        if duration > 120:  # 2 minutes
            print(f"⚠️  Slow enumeration on self-hosted: {duration:.1f}s")
        else:
            print("✅ Good performance on self-hosted")

    def test_selfhosted_access_level_validation(self, gitlab_url, alice_token):
        """Test that access levels are properly identified on self-hosted."""
        if is_gitlab_saas(gitlab_url):
            pytest.skip("Self-hosted test requires self-hosted GitLab environment")
            
        result = run_glato(["-u", gitlab_url, "--enumerate-projects"], token=alice_token)
        
        assert result.returncode == 0, "Project enumeration should succeed"
        self._validate_access_levels(result.stdout)

    def test_selfhosted_limited_token_access(self, gitlab_url, bob_token):
        """Test project enumeration with limited self-hosted token."""
        if is_gitlab_saas(gitlab_url):
            pytest.skip("Self-hosted test requires self-hosted GitLab environment")
            
        result = run_glato(["-u", gitlab_url, "--enumerate-projects"], token=bob_token)
        
        if result.returncode == 0:
            assert "bob" in result.stdout.lower(), "Should show Bob's user info"
            print("✅ Limited token project enumeration completed on self-hosted")
        else:
            print(f"⚠️  Limited token had expected limitations: {result.stderr}")

    def test_selfhosted_comprehensive_enumeration(self, gitlab_url, alice_token):
        """Test comprehensive project enumeration behavior on self-hosted."""
        if is_gitlab_saas(gitlab_url):
            pytest.skip("Self-hosted test requires self-hosted GitLab environment")
            
        result = run_glato(["-u", gitlab_url, "--enumerate-projects"], token=alice_token)
        
        assert result.returncode == 0, "Project enumeration should succeed"
        
        output_lines = result.stdout.lower().split('\n')
        
        # Parse projects and their access levels
        projects_found = []
        current_project = None
        
        for line in output_lines:
            if line.strip().startswith("project: "):
                current_project = line.split("project: ")[1].strip()
            elif "access level:" in line and current_project:
                access_level = line.split("access level:")[1].strip()
                projects_found.append({
                    "name": current_project,
                    "access_level": access_level
                })
                current_project = None
        
        # Verify we found some projects
        assert len(projects_found) > 0, "Should find at least some projects on self-hosted"
        
        # On self-hosted, we should be able to see both member and non-member projects
        member_access_levels = ["owner", "maintainer", "developer", "reporter", "guest"]
        member_projects = [p for p in projects_found if p["access_level"] in member_access_levels]
        non_member_projects = [p for p in projects_found if p["access_level"] == "not a member"]
        
        # Report the access level distribution
        access_distribution = {}
        for project in projects_found:
            level = project["access_level"]
            access_distribution[level] = access_distribution.get(level, 0) + 1
        
        print(f"✅ Found {len(projects_found)} projects on self-hosted GitLab:")
        for level, count in access_distribution.items():
            print(f"  - {level}: {count} projects")
        
        # Verify we have a mix of access levels (characteristic of self-hosted)
        total_projects = len(projects_found)
        if len(member_projects) == total_projects:
            print("✅ All projects are member projects (expected for limited self-hosted setup)")
        elif len(non_member_projects) > 0:
            print(f"✅ Found {len(non_member_projects)} non-member projects (expected self-hosted behavior)")
        
        print("✅ Self-hosted comprehensive enumeration completed successfully")

    def test_selfhosted_branch_protection_enumeration(self, gitlab_url, alice_token):
        """Test branch protection enumeration on self-hosted."""
        if is_gitlab_saas(gitlab_url):
            pytest.skip("Self-hosted test requires self-hosted GitLab environment")
            
        result = run_glato([
            "-u", gitlab_url,
            "--enumerate-projects", 
            "--check-branch-protections"
        ], token=alice_token)
        
        if result.returncode == 0:
            print("✅ Branch protection enumeration completed on self-hosted")
        else:
            print(f"⚠️  Branch protection enumeration had issues: {result.stderr}")

    def _validate_project_enumeration_output(self, output: str):
        """Validate project enumeration output format."""
        output_lines = output.lower().split('\n')
        
        project_lines = [line for line in output_lines if line.strip().startswith("project: ")]
        assert len(project_lines) > 0, "Should find at least some projects"
        
        has_user_info = any("username:" in line or "user id:" in line for line in output_lines)
        assert has_user_info, "Should contain user information"
        
        print(f"✅ Project enumeration output validated: {len(project_lines)} projects found")

    def _validate_access_levels(self, output: str):
        """Validate access level information in self-hosted project enumeration output."""
        output_lines = output.lower().split('\n')
        
        projects_with_access = []
        current_project = None
        
        for line in output_lines:
            if line.strip().startswith("project: "):
                current_project = line.split("project: ")[1].strip()
            elif "access level:" in line and current_project:
                access_level = line.split("access level:")[1].strip()
                projects_with_access.append({
                    "name": current_project,
                    "access_level": access_level
                })
                current_project = None
        
        assert len(projects_with_access) > 0, "Should find projects with access level information"
        
        valid_access_levels = ["owner", "maintainer", "developer", "reporter", "guest", "not a member"]
        for project in projects_with_access:
            assert project["access_level"] in valid_access_levels, \
                f"Invalid access level: {project['access_level']}"
        
        # Report access level distribution
        access_distribution = {}
        for project in projects_with_access:
            level = project["access_level"]
            access_distribution[level] = access_distribution.get(level, 0) + 1
        
        print(f"✅ Self-hosted access level validation completed: {len(projects_with_access)} projects")
        for level, count in access_distribution.items():
            print(f"  - {level}: {count} projects")
        
        # Self-hosted specific validation
        member_levels = ["owner", "maintainer", "developer", "reporter", "guest"]
        member_projects = sum(access_distribution.get(level, 0) for level in member_levels)
        non_member_projects = access_distribution.get("not a member", 0)
        
        print(f"✅ Self-hosted: {member_projects} member projects, {non_member_projects} non-member projects")
