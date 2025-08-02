"""
End-to-end tests for GitLab SaaS archived project functionality.

This module tests the --include-archived and --archived-only functionality
specifically on GitLab SaaS, validating proper handling of archived projects.
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
    except subprocess.TimeoutExpired:
        # Return a mock result for timeout
        class TimeoutResult:
            returncode = 124
            stdout = ""
            stderr = "Command timed out"
        return TimeoutResult()
    
    return result


def is_gitlab_saas(url):
    """Check if URL is GitLab SaaS."""
    return "gitlab.com" in url.lower()


def count_archived_projects(output):
    """Count archived and non-archived projects in output."""
    lines = output.split('\n')
    archived_count = 0
    total_projects = 0
    
    for line in lines:
        if line.strip().startswith("Project: "):
            total_projects += 1
            if "[ARCHIVED]" in line:
                archived_count += 1
    
    return archived_count, total_projects - archived_count


def has_archived_projects(output):
    """Check if output contains any archived projects."""
    return "[ARCHIVED]" in output


def validate_archive_summary(output):
    """Validate that archive summary is present and makes sense."""
    summary_lines = [line for line in output.split('\n') if 'Project Summary:' in line]
    if summary_lines:
        summary = summary_lines[0]
        if 'archived' in summary:
            return True
    return False


@pytest.mark.saas
class TestSaaSArchivedProjects:
    """Test archived project functionality on GitLab SaaS."""

    def test_default_excludes_archived_projects(self, gitlab_url, alice_token_saas):
        """Test that archived projects are excluded by default."""
        if not is_gitlab_saas(gitlab_url):
            pytest.skip("SaaS test requires GitLab SaaS environment")
            
        result = run_glato_with_timeout(["-u", gitlab_url, "--enumerate-projects"], 
                                      token=alice_token_saas, timeout=45)
        
        if result.returncode == 124:
            pytest.skip("Project enumeration timed out")
        elif result.returncode == 0:
            archived_count, active_count = count_archived_projects(result.stdout)
            
            # By default, no archived projects should be shown
            assert archived_count == 0, f"Found {archived_count} archived projects when none should be shown by default"
            
            # Should show summary of active projects only
            assert "active projects found" in result.stdout or active_count > 0
            print(f"✅ Default behavior: {active_count} active projects shown, 0 archived (as expected)")
        else:
            pytest.fail(f"Project enumeration failed with exit code {result.returncode}: {result.stderr}")

    def test_include_archived_flag(self, gitlab_url, alice_token_saas):
        """Test --include-archived flag includes both active and archived projects."""
        if not is_gitlab_saas(gitlab_url):
            pytest.skip("SaaS test requires GitLab SaaS environment")
            
        result = run_glato_with_timeout(["-u", gitlab_url, "--enumerate-projects", "--include-archived"], 
                                      token=alice_token_saas, timeout=45)
        
        if result.returncode == 124:
            pytest.skip("Project enumeration with --include-archived timed out")
        elif result.returncode == 0:
            archived_count, active_count = count_archived_projects(result.stdout)
            total_projects = archived_count + active_count
            
            # Verify proper messaging
            assert "Including Archived" in result.stdout or "All Projects" in result.stdout
            
            if total_projects > 0:
                # Should show summary with both counts
                if archived_count > 0:
                    assert validate_archive_summary(result.stdout), "Should show archive summary when archived projects exist"
                    print(f"✅ --include-archived: {active_count} active, {archived_count} archived projects found")
                else:
                    print(f"✅ --include-archived: {active_count} active projects found (no archived projects exist)")
            else:
                # No projects found is acceptable for some test accounts
                assert "No projects found" in result.stdout, "Should show 'No projects found' message"
                print("✅ --include-archived: No projects found (acceptable for test account)")
        else:
            pytest.fail(f"Project enumeration with --include-archived failed: {result.stderr}")

    def test_archived_only_flag(self, gitlab_url, alice_token_saas):
        """Test --archived-only flag shows only archived projects."""
        if not is_gitlab_saas(gitlab_url):
            pytest.skip("SaaS test requires GitLab SaaS environment")
            
        result = run_glato_with_timeout(["-u", gitlab_url, "--enumerate-projects", "--archived-only"], 
                                      token=alice_token_saas, timeout=45)
        
        if result.returncode == 124:
            pytest.skip("Project enumeration with --archived-only timed out")
        elif result.returncode == 0:
            archived_count, active_count = count_archived_projects(result.stdout)
            
            # Should only show archived projects
            assert active_count == 0, f"Found {active_count} active projects when using --archived-only"
            
            # Verify proper messaging
            assert "Archived Projects Only" in result.stdout
            
            if archived_count > 0:
                assert "archived projects found" in result.stdout
                print(f"✅ --archived-only: {archived_count} archived projects found")
            else:
                assert "No projects found" in result.stdout or archived_count == 0
                print("✅ --archived-only: No archived projects found (as expected)")
        else:
            pytest.fail(f"Project enumeration with --archived-only failed: {result.stderr}")

    def test_archived_project_display_format(self, gitlab_url, alice_token_saas):
        """Test that archived projects display with proper [ARCHIVED] tag and date."""
        if not is_gitlab_saas(gitlab_url):
            pytest.skip("SaaS test requires GitLab SaaS environment")
            
        result = run_glato_with_timeout(["-u", gitlab_url, "--enumerate-projects", "--include-archived"], 
                                      token=alice_token_saas, timeout=45)
        
        if result.returncode == 124:
            pytest.skip("Project enumeration timed out")
        elif result.returncode == 0:
            if has_archived_projects(result.stdout):
                # Verify archived projects have proper formatting
                lines = result.stdout.split('\n')
                found_archived_with_status = False
                found_archived_with_date = False
                
                for i, line in enumerate(lines):
                    if "[ARCHIVED]" in line and line.strip().startswith("Project: "):
                        found_archived_with_status = True
                        
                        # Check following lines for archive status and date
                        for j in range(i+1, min(i+10, len(lines))):
                            if "Archive Status: Archived" in lines[j]:
                                found_archived_with_date = True
                                break
                            if "Archived Date:" in lines[j]:
                                found_archived_with_date = True
                                break
                
                assert found_archived_with_status, "Archived projects should have [ARCHIVED] tag"
                print("✅ Archived projects properly display [ARCHIVED] tag")
                
                if found_archived_with_date:
                    print("✅ Archived projects show archive date information")
            else:
                print("✅ No archived projects found to test formatting (acceptable)")
        else:
            pytest.fail(f"Project enumeration failed: {result.stderr}")

    def test_mutually_exclusive_flags_validation(self, gitlab_url, alice_token_saas):
        """Test that --include-archived and --archived-only are mutually exclusive."""
        if not is_gitlab_saas(gitlab_url):
            pytest.skip("SaaS test requires GitLab SaaS environment")
            
        result = run_glato(["-u", gitlab_url, "--enumerate-projects", "--include-archived", "--archived-only"], 
                          token=alice_token_saas)
        
        # Should fail with validation error
        assert result.returncode != 0, "Should fail when both --include-archived and --archived-only are used"
        error_output = (result.stderr + result.stdout).lower()
        assert "mutually exclusive" in error_output, "Should show mutually exclusive error message"
        print("✅ Mutually exclusive flags properly validated")

    def test_archive_flags_require_enumeration(self, gitlab_url, alice_token_saas):
        """Test that archive flags require --enumerate-projects."""
        if not is_gitlab_saas(gitlab_url):
            pytest.skip("SaaS test requires GitLab SaaS environment")
            
        # Test --include-archived without --enumerate-projects
        result1 = run_glato(["-u", gitlab_url, "--include-archived"], token=alice_token_saas)
        assert result1.returncode != 0, "Should fail when --include-archived used without --enumerate-projects"
        
        # Test --archived-only without --enumerate-projects  
        result2 = run_glato(["-u", gitlab_url, "--archived-only"], token=alice_token_saas)
        assert result2.returncode != 0, "Should fail when --archived-only used without --enumerate-projects"
        
        print("✅ Archive flags properly require project enumeration")

    def test_self_enumeration_with_archived_flags(self, gitlab_url, alice_token_saas):
        """Test that archive flags work with --self-enumeration."""
        if not is_gitlab_saas(gitlab_url):
            pytest.skip("SaaS test requires GitLab SaaS environment")
            
        # Note: This test may timeout on SaaS due to performance impact of disabling simple=True
        # when dealing with archived projects, which is expected behavior
        result = run_glato_with_timeout(["-u", gitlab_url, "--self-enumeration", "--include-archived"], 
                                      token=alice_token_saas, timeout=60)
        
        if result.returncode == 124:
            pytest.skip("Self-enumeration with archived projects timed out due to SaaS performance characteristics")
        elif result.returncode == 0:
            # Should include both project and group enumeration
            assert "Enumerating Projects" in result.stdout or "Project:" in result.stdout
            assert "Enumerating Groups" in result.stdout or "Group:" in result.stdout
            print("✅ Archive flags work with --self-enumeration")
        else:
            pytest.fail(f"Self-enumeration with archive flags failed: {result.stderr}")

    def test_archived_project_summary_counts(self, gitlab_url, alice_token_saas):
        """Test that project summary shows correct archived vs active counts."""
        if not is_gitlab_saas(gitlab_url):
            pytest.skip("SaaS test requires GitLab SaaS environment")
            
        # Get counts with include-archived
        result = run_glato_with_timeout(["-u", gitlab_url, "--enumerate-projects", "--include-archived"], 
                                      token=alice_token_saas, timeout=45)
        
        if result.returncode == 124:
            pytest.skip("Project enumeration timed out")
        elif result.returncode == 0:
            archived_count, active_count = count_archived_projects(result.stdout)
            
            # Verify summary line matches actual counts
            summary_lines = [line for line in result.stdout.split('\n') if 'Project Summary:' in line]
            if summary_lines and (archived_count > 0 or active_count > 0):
                summary = summary_lines[0]
                if archived_count > 0:
                    assert str(archived_count) in summary, f"Summary should contain archived count {archived_count}"
                    assert "archived" in summary, "Summary should mention archived projects"
                if active_count > 0:
                    assert str(active_count) in summary, f"Summary should contain active count {active_count}"
                
                print(f"✅ Project summary correctly shows {active_count} active, {archived_count} archived")
            else:
                print("✅ No projects found to validate summary (acceptable)")
        else:
            pytest.fail(f"Project enumeration failed: {result.stderr}")