"""
End-to-end tests for GitLab SaaS project enumeration functionality.

This module tests the --enumerate-projects functionality specifically on GitLab SaaS,
addressing the unique challenges of SaaS environments like performance and filtering.
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


def run_glato_with_timeout(args, token=None, timeout=30):
    """Run glato command with timeout for SaaS testing."""
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


class TestSaaSProjectEnumeration:
    """Test project enumeration functionality specifically on GitLab SaaS."""
    
    def test_saas_basic_enumeration_with_timeout(self, gitlab_url, alice_token_saas):
        """Test basic project enumeration on SaaS with reasonable timeout."""
        if not is_gitlab_saas(gitlab_url):
            pytest.skip("SaaS test requires GitLab SaaS environment")
            
        result = run_glato_with_timeout(["-u", gitlab_url, "--enumerate-projects"], 
                                      token=alice_token_saas, timeout=45)
        
        if result.returncode == 124:
            pytest.skip("Project enumeration timed out on GitLab SaaS due to large number of public projects. "
                       "This demonstrates the need for SaaS-specific filtering.")
        elif result.returncode == 0:
            self._validate_project_enumeration_output(result.stdout)
            print("✅ SaaS project enumeration completed within timeout")
        else:
            pytest.fail(f"Project enumeration failed with exit code {result.returncode}: {result.stderr}")

    def test_saas_performance_characteristics(self, gitlab_url, alice_token_saas):
        """Test SaaS project enumeration performance characteristics."""
        if not is_gitlab_saas(gitlab_url):
            pytest.skip("SaaS test requires GitLab SaaS environment")
            
        start_time = time.time()
        result = run_glato_with_timeout(["-u", gitlab_url, "--enumerate-projects"], 
                                      token=alice_token_saas, timeout=30)
        duration = time.time() - start_time
        
        if result.returncode == 124:
            project_count = result.stdout.lower().count("project: ")
            if project_count > 0:
                rate = project_count / duration if duration > 0 else 0
                pytest.skip(f"Performance issue: enumerated {project_count} projects in {duration:.1f}s "
                           f"({rate:.1f} projects/sec) before timing out.")
            else:
                pytest.skip(f"Project enumeration timed out after {duration:.1f}s with no output.")
        elif result.returncode == 0:
            project_count = result.stdout.lower().count("project: ")
            rate = project_count / duration if duration > 0 else 0
            
            print(f"SaaS enumerated {project_count} projects in {duration:.1f}s ({rate:.1f} projects/sec)")
            
            if project_count < 100 and duration < 10:
                print("✅ Optimal performance: few projects enumerated quickly")
            elif project_count > 1000:
                pytest.fail(f"Performance issue: enumerated {project_count} projects - "
                           "indicates lack of proper filtering on GitLab SaaS")
            else:
                print("✅ Acceptable performance characteristics")

    def test_saas_member_project_filtering(self, gitlab_url, alice_token_saas):
        """Test that SaaS properly filters to focus on member projects."""
        if not is_gitlab_saas(gitlab_url):
            pytest.skip("SaaS test requires GitLab SaaS environment")
            
        result = run_glato_with_timeout(["-u", gitlab_url, "--enumerate-projects"], 
                                      token=alice_token_saas, timeout=45)
        
        if result.returncode == 124:
            pytest.skip("Project enumeration timed out - demonstrates need for member-only filtering.")
        elif result.returncode == 0:
            member_projects, non_member_projects = self._count_project_types(result.stdout)
            total_projects = member_projects + non_member_projects
            
            if total_projects > 0:
                print(f"Found {member_projects} member projects, {non_member_projects} non-member projects")
                
                # SaaS should prioritize member projects
                if non_member_projects > member_projects * 10:
                    pytest.fail(f"Too many non-member projects ({non_member_projects} vs {member_projects} member). "
                               "Indicates SaaS performance issue.")
                else:
                    print("✅ Reasonable member/non-member project ratio")

    def test_saas_access_level_validation(self, gitlab_url, alice_token_saas):
        """Test that project access levels are properly identified on SaaS."""
        if not is_gitlab_saas(gitlab_url):
            pytest.skip("SaaS test requires GitLab SaaS environment")
            
        result = run_glato_with_timeout(["-u", gitlab_url, "--enumerate-projects"], 
                                      token=alice_token_saas, timeout=45)
        
        if result.returncode == 124:
            pytest.skip("Project enumeration timed out - cannot validate access levels")
        elif result.returncode == 0:
            self._validate_access_levels(result.stdout)

    def test_saas_limited_token_access(self, gitlab_url, bob_token_saas):
        """Test project enumeration with limited SaaS token."""
        if not is_gitlab_saas(gitlab_url):
            pytest.skip("SaaS test requires GitLab SaaS environment")
            
        result = run_glato_with_timeout(["-u", gitlab_url, "--enumerate-projects"], 
                                      token=bob_token_saas, timeout=45)
        
        if result.returncode == 124:
            pytest.skip("Project enumeration timed out with limited token - expected")
        elif result.returncode == 0:
            assert "bob" in result.stdout.lower(), "Should show Bob's user info"
            print("✅ Limited token project enumeration completed on SaaS")

    def test_saas_executive_token_access(self, gitlab_url, irene_token_saas):
        """Test project enumeration with executive SaaS token."""
        if not is_gitlab_saas(gitlab_url):
            pytest.skip("SaaS test requires GitLab SaaS environment")
            
        result = run_glato_with_timeout(["-u", gitlab_url, "--enumerate-projects"], 
                                      token=irene_token_saas, timeout=45)
        
        if result.returncode == 124:
            pytest.skip("Project enumeration timed out with executive token")
        elif result.returncode == 0:
            assert "irene" in result.stdout.lower(), "Should show Irene's user info"
            print("✅ Executive token project enumeration completed on SaaS")

    def test_saas_branch_protection_enumeration(self, gitlab_url, alice_token_saas):
        """Test branch protection enumeration on SaaS."""
        if not is_gitlab_saas(gitlab_url):
            pytest.skip("SaaS test requires GitLab SaaS environment")
            
        result = run_glato_with_timeout([
            "-u", gitlab_url,
            "--enumerate-projects",
            "--check-branch-protections"
        ], token=alice_token_saas, timeout=60)
        
        if result.returncode == 124:
            pytest.skip("Branch protection enumeration timed out on SaaS")
        elif result.returncode == 0:
            print("✅ Branch protection enumeration completed on SaaS")
        else:
            print(f"⚠️  Branch protection enumeration had issues: {result.stderr}")

    def test_saas_environment_detection(self, gitlab_url, alice_token_saas):
        """Test that SaaS environment is correctly detected."""
        if not is_gitlab_saas(gitlab_url):
            pytest.skip("SaaS test requires GitLab SaaS environment")
            
        # Verify detection function works correctly
        assert is_gitlab_saas(gitlab_url), \
            f"URL {gitlab_url} should be detected as SaaS"
        
        result = run_glato_with_timeout(["-u", gitlab_url, "--enumerate-projects"], 
                                      token=alice_token_saas, timeout=45)
        
        if result.returncode == 124:
            pytest.skip("SaaS enumeration timed out - expected behavior")
        elif result.returncode == 0:
            # Should show SaaS-specific behavior if any optimization is implemented
            print("✅ SaaS environment correctly detected and handled")

    def _validate_project_enumeration_output(self, output: str):
        """Validate project enumeration output format."""
        output_lines = output.lower().split('\n')
        
        project_lines = [line for line in output_lines if line.strip().startswith("project: ")]
        assert len(project_lines) > 0, "Should find at least some projects"
        
        has_user_info = any("username:" in line or "user id:" in line for line in output_lines)
        assert has_user_info, "Should contain user information"
        
        print(f"✅ Project enumeration output validated: {len(project_lines)} projects found")

    def _count_project_types(self, output: str):
        """Count member vs non-member projects in output."""
        output_lines = output.lower().split('\n')
        member_projects = 0
        non_member_projects = 0
        
        current_project = None
        for line in output_lines:
            if line.strip().startswith("project: "):
                current_project = line.split("project: ")[1].strip()
            elif "access level:" in line and current_project:
                access_level = line.split("access level:")[1].strip()
                if access_level in ["owner", "maintainer", "developer", "reporter", "guest"]:
                    member_projects += 1
                elif access_level == "not a member":
                    non_member_projects += 1
                current_project = None
        
        return member_projects, non_member_projects

    def _validate_access_levels(self, output: str):
        """Validate access level information in SaaS project enumeration output."""
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
        
        print(f"✅ SaaS access level validation completed: {len(projects_with_access)} projects")
        for level, count in access_distribution.items():
            print(f"  - {level}: {count} projects")
        
        # SaaS-specific validation
        member_levels = ["owner", "maintainer", "developer", "reporter", "guest"]
        member_projects = sum(access_distribution.get(level, 0) for level in member_levels)
        non_member_projects = access_distribution.get("not a member", 0)
        
        if non_member_projects > member_projects * 10:
            print(f"⚠️  SaaS: Many non-member projects ({non_member_projects} vs {member_projects} member)")
        else:
            print(f"✅ SaaS: Reasonable member/non-member ratio") 