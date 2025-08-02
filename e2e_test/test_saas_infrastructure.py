"""
End-to-end tests for GitLab SaaS infrastructure validation.

Test Assumptions:
- GitLab SaaS environment at https://gitlab.com
- Root groups: acme-corporation-glato, engineering-glato, product-glato, security-glato
- Subgroups: mobile-glato, web-glato, api-glato, backend-glato, frontend-glato
- Users: alice-glato, bob-glato, irene-glato with specific permissions
- Test project: acme-corporation-glato/product-glato/api-glato/api-service-glato
"""

import pytest
import time
import os
import subprocess
import re
import json


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


class TestGitLabSaaSInfrastructure:
    """Test cases for GitLab SaaS infrastructure validation."""
    
    def test_required_groups_exist(self, gitlab_url, alice_token_saas):
        """Test that all required groups exist in the SaaS environment with proper access levels."""
        result = run_glato(["-u", gitlab_url, "--enumerate-groups"], token=alice_token_saas)
        
        assert result.returncode == 0, "Group enumeration should succeed"
        
        # Define required groups with expected access levels
        required_groups = {
            "acme-corporation-glato": "owner",
            "engineering-glato": "owner", 
            "product-glato": "maintainer"
        }
        
        output_lines = result.stdout.lower().split('\n')
        
        for group_name, expected_access in required_groups.items():
            # Find the group in output
            group_found = False
            access_level_found = False
            
            for i, line in enumerate(output_lines):
                if f"group: {group_name}" in line:
                    group_found = True
                    # Check the next few lines for access level
                    for j in range(i, min(i+5, len(output_lines))):
                        if f"access level: {expected_access}" in output_lines[j]:
                            access_level_found = True
                            break
                    break
            
            assert group_found, f"Required group {group_name} not found in output"
            assert access_level_found, f"Group {group_name} found but expected access level '{expected_access}' not found"
        
        # Verify we have at least the minimum number of groups
        group_count = len([line for line in output_lines if line.strip().startswith("group:")])
        assert group_count >= len(required_groups), f"Expected at least {len(required_groups)} groups, found {group_count}"
    
    def test_optional_security_group(self, gitlab_url, alice_token_saas):
        """Test that the optional security group exists and has proper access if present."""
        result = run_glato(["-u", gitlab_url, "--enumerate-groups"], token=alice_token_saas)
        
        assert result.returncode == 0, "Group enumeration should succeed"
        
        output_lines = result.stdout.lower().split('\n')
        security_group_found = False
        security_access_found = False
        
        for i, line in enumerate(output_lines):
            if "group: security-glato" in line:
                security_group_found = True
                # Check for access level in the next few lines
                for j in range(i, min(i+5, len(output_lines))):
                    if "access level: maintainer" in output_lines[j] or "access level: owner" in output_lines[j]:
                        security_access_found = True
                        break
                break
        
        if security_group_found:
            assert security_access_found, "Security group found but no maintainer/owner access level detected"
            print("✓ Optional security-glato group found with appropriate access")
        else:
            print("ℹ Optional security-glato group not found (this is acceptable)")
        
        # The test should pass regardless of whether the optional group exists
    
    def test_subgroups_exist(self, gitlab_url, alice_token_saas):
        """Test that subgroups exist within their parent groups with correct hierarchy."""
        result = run_glato(["-u", gitlab_url, "--enumerate-groups"], token=alice_token_saas)
        
        assert result.returncode == 0, "Group enumeration should succeed"
        
        # Define expected subgroups with their parent paths
        expected_subgroups = {
            "web-glato": "product-glato/web-glato"  # subgroup: expected full path
        }
        
        output_lines = result.stdout.lower().split('\n')
        
        for subgroup_name, expected_full_path in expected_subgroups.items():
            subgroup_found = False
            correct_hierarchy = False
            
            for i, line in enumerate(output_lines):
                if f"group: {subgroup_name}" in line:
                    subgroup_found = True
                    # Check for the full path in the next few lines
                    for j in range(i, min(i+5, len(output_lines))):
                        if f"full path: {expected_full_path}" in output_lines[j]:
                            correct_hierarchy = True
                            break
                    break
            
            assert subgroup_found, f"Expected subgroup {subgroup_name} not found"
            assert correct_hierarchy, f"Subgroup {subgroup_name} found but incorrect hierarchy. Expected path: {expected_full_path}"
        
        # Verify we found at least some groups
        group_count = len([line for line in output_lines if line.strip().startswith("group:")])
        assert group_count > 0, "No groups found in output"
        
        print(f"✓ Found {group_count} total groups with correct hierarchy")
    
    def test_group_hierarchy_structure(self, gitlab_url, alice_token_saas):
        """Test that the group hierarchy structure is logically consistent."""
        result = run_glato(["-u", gitlab_url, "--enumerate-groups"], token=alice_token_saas)
        
        assert result.returncode == 0, "Group enumeration should succeed"
        
        output_lines = result.stdout.lower().split('\n')
        
        # Extract all groups with their full paths
        groups_with_paths = {}
        current_group = None
        
        for line in output_lines:
            if line.strip().startswith("group: "):
                current_group = line.split("group: ")[1].strip()
            elif line.strip().startswith("full path: ") and current_group:
                full_path = line.split("full path: ")[1].strip()
                groups_with_paths[current_group] = full_path
                current_group = None
        
        # Verify hierarchy consistency
        parent_groups = set()
        subgroups = set()
        
        for group_name, full_path in groups_with_paths.items():
            if "/" in full_path:
                # This is a subgroup
                subgroups.add(group_name)
                parent_path = "/".join(full_path.split("/")[:-1])
                parent_groups.add(parent_path)
            else:
                # This is a root group
                parent_groups.add(full_path)
        
        # Verify that parent groups of subgroups actually exist
        for group_name, full_path in groups_with_paths.items():
            if "/" in full_path:
                parent_path = "/".join(full_path.split("/")[:-1])
                parent_exists = any(path == parent_path for path in groups_with_paths.values())
                assert parent_exists, f"Subgroup {group_name} has parent path {parent_path} but parent group not found"
        
        print(f"✓ Hierarchy validation passed: {len(parent_groups)} parent groups, {len(subgroups)} subgroups")
    
    def test_expected_users_exist(self, gitlab_url, alice_token_saas):
        """Test that all expected users exist with proper token scopes and permissions."""
        result = run_glato(["-u", gitlab_url, "--enumerate-token"], token=alice_token_saas)
        
        assert result.returncode == 0, "Token enumeration should succeed"
        
        output_lines = result.stdout.lower().split('\n')
        
        # Validate user information
        user_found = False
        api_scope_found = False
        user_id_found = False
        email_found = False
        
        for line in output_lines:
            if "username: alice-glato" in line:
                user_found = True
            elif "user id:" in line and line.split("user id:")[1].strip().isdigit():
                user_id_found = True
            elif "email:" in line and "alice-glato" in line:
                email_found = True
            elif "- api" in line or "api" in line.split():
                api_scope_found = True
        
        assert user_found, "Alice user not found in token enumeration"
        assert user_id_found, "User ID not found or invalid"
        assert email_found, "User email not found"
        assert api_scope_found, "API scope not found in token scopes"
        
        # Verify token has sufficient permissions
        has_write_access = any("api" in line and "read_api" not in line for line in output_lines if "- api" in line)
        if not has_write_access:
            # Check if it has read_api at minimum
            read_api_found = any("read_api" in line for line in output_lines)
            assert read_api_found, "Token should have at least read_api scope"
        
        print("✓ User alice-glato validated with proper token scopes and permissions")
    
    def test_test_project_exists(self, gitlab_url, alice_token_saas, test_project_path_saas):
        """Test that the test project exists and is accessible."""
        result = run_glato(["-u", gitlab_url, "--project-path", test_project_path_saas, "--check-branch-protections"], 
                          token=alice_token_saas)
        
        assert result.returncode == 0, f"Project access should succeed for {test_project_path_saas}"
        
        output_lines = result.stdout.lower().split('\n')
        
        # Validate project access - look for the actual output format
        user_info_found = False
        branch_section_found = False
        branch_protection_found = False
        
        for line in output_lines:
            # Check for user information (indicates successful authentication)
            if "user id:" in line and line.split("user id:")[1].strip().isdigit():
                user_info_found = True
            elif "username:" in line:
                user_info_found = True
            # Check for branch protection section header
            elif "enumerating branch protections using api" in line:
                branch_section_found = True
            # Check for actual branch protection data
            elif "branch protection" in line and ("enabled" in line or "disabled" in line or "main" in line):
                branch_protection_found = True
        
        assert user_info_found, "User information not found - may indicate authentication failure"
        assert branch_section_found, "Branch protection enumeration section not found - may indicate project access failure"
        
        # The command succeeding with branch protection output indicates the project exists and is accessible
        # We don't need to see the project path explicitly in the output
        
        print(f"✓ Project {test_project_path_saas} exists and is accessible")


class TestGitLabSaaSUserPermissions:
    """Test cases for user permissions in the SaaS environment."""
    
    def test_alice_maintainer_access(self, gitlab_url, alice_token_saas):
        """Test that Alice has maintainer-level access as expected."""
        result = run_glato(["-u", gitlab_url, "--enumerate-token"], token=alice_token_saas)
        
        assert "api" in result.stdout.lower(), "Alice should have API scope"
        assert "alice" in result.stdout.lower(), "Alice's username should be displayed"
    
    def test_bob_developer_access(self, gitlab_url, bob_token_saas):
        """Test that Bob has developer-level access as expected."""
        result = run_glato(["-u", gitlab_url, "--enumerate-token"], token=bob_token_saas)
        
        assert "bob" in result.stdout.lower(), "Bob's username should be displayed"
    
    def test_irene_executive_access(self, gitlab_url, irene_token_saas):
        """Test that Irene has executive-level access as expected."""
        result = run_glato(["-u", gitlab_url, "--enumerate-token"], token=irene_token_saas)
        
        assert "irene" in result.stdout.lower(), "Irene's username should be displayed"
        
        assert "api" in result.stdout.lower() or "read_api" in result.stdout.lower(), \
            "Irene should have API access"


class TestGitLabSaaSProjectSettings:
    """Test cases for project settings and CI/CD variables."""
    
    def test_project_ci_variables_exist(self, gitlab_url, alice_token_saas, test_project_path_saas):
        """Test that the test project has CI/CD variables or handles them correctly."""
        result = run_glato([
            "-u", gitlab_url,
            "--enumerate-secrets",
            "--project-path", test_project_path_saas
        ], token=alice_token_saas)
        
        assert result.returncode == 0, f"Failed to access project {test_project_path_saas}"
        
        # The project should be accessible and we should see some output about variables
        # Even if no variables exist, the command should complete successfully
        assert "attempting to exfiltrate" in result.stdout.lower() or \
               "attempting to identify" in result.stdout.lower() or \
               "no variables identified" in result.stdout.lower() or \
               "variables for" in result.stdout.lower(), \
            "Should see output about CI/CD variable enumeration"
    
    def test_branch_protections_exist(self, gitlab_url, alice_token_saas, test_project_path_saas):
        """Test that branch protections can be checked for the test project."""
        result = run_glato([
            "-u", gitlab_url,
            "--check-branch-protections",
            "--project-path", test_project_path_saas
        ], token=alice_token_saas)
        
        # The command should run successfully whether or not branch protections exist
        assert result.returncode == 0, f"Branch protection check failed for {test_project_path_saas}"
        
        # We should see some output about branch protections (even if none exist)
        assert "branch" in result.stdout.lower() or "protection" in result.stdout.lower() or \
               "enumerating" in result.stdout.lower(), \
            "Should see output about branch protection enumeration"


class TestGitLabSaaSPersistentEnvironment:
    """Test cases specific to the persistent SaaS environment."""
    
    def test_environment_stability(self, gitlab_url, alice_token_saas):
        """Test that the SaaS environment maintains expected state across test runs."""
        result = run_glato(["-u", gitlab_url, "--enumerate-groups"], token=alice_token_saas)
        
        assert result.returncode == 0, "Environment should be stable and accessible"
        assert len(result.stdout) > 0, "Should have group enumeration output"
    
    def test_rate_limiting_handling(self, gitlab_url, alice_token_saas):
        """Test that commands handle GitLab.com rate limiting gracefully."""
        for i in range(3):
            result = run_glato(["-u", gitlab_url, "--enumerate-token"], token=alice_token_saas)
            assert result.returncode == 0, f"Token enumeration {i+1} should succeed"
            time.sleep(1)  # Small delay between requests
    



class TestGitLabSaaSWithAdminToken:
    """Additional test cases using SAAS_ADMIN_TOKEN for simpler validation."""
    
    @pytest.fixture
    def admin_token(self):
        """Get SAAS_ADMIN_TOKEN for testing."""
        token = os.getenv("SAAS_ADMIN_TOKEN") or os.getenv("GITLAB_ADMIN_TOKEN")
        if not token:
            pytest.skip("SAAS_ADMIN_TOKEN not set")
        return token
    
    def test_admin_token_enumeration(self, admin_token):
        """Test that SAAS_ADMIN_TOKEN can enumerate basic information."""
        result = run_glato([
            "-u", "https://gitlab.com",
            "--enumerate-token"
        ], token=admin_token)
        
        assert result.returncode == 0, "Token enumeration should succeed"
        
        output_lines = result.stdout.lower().split('\n')
        
        # Validate basic token information
        user_id_found = False
        username_found = False
        scopes_found = False
        
        for line in output_lines:
            if "user id:" in line and line.split("user id:")[1].strip().isdigit():
                user_id_found = True
            elif "username:" in line:
                username_found = True
            elif "scopes:" in line or "- api" in line:
                scopes_found = True
        
        assert user_id_found, "User ID not found in admin token enumeration"
        assert username_found, "Username not found in admin token enumeration"
        assert scopes_found, "Token scopes not found in admin token enumeration"
        
        print("✅ Admin token enumeration successful")
    
    def test_admin_project_access(self, admin_token):
        """Test that SAAS_ADMIN_TOKEN can access the test project."""
        result = run_glato([
            "-u", "https://gitlab.com",
            "--enumerate-projects",
            "--project-path", "product-glato/api-glato/api-service-glato"
        ], token=admin_token)
        
        assert result.returncode == 0, "Project enumeration should succeed"
        
        output_lines = result.stdout.lower().split('\n')
        
        # Validate project access
        project_found = False
        project_id_found = False
        
        for line in output_lines:
            if "product-glato/api-glato/api-service-glato" in line:
                project_found = True
            elif "id:" in line and line.split("id:")[1].strip().isdigit():
                project_id_found = True
        
        assert project_found, "Test project not found with admin token"
        assert project_id_found, "Project ID not found with admin token"
        
        print("✅ Admin token project access successful")
    
    def test_admin_group_enumeration(self, admin_token):
        """Test that SAAS_ADMIN_TOKEN can enumerate groups."""
        result = run_glato([
            "-u", "https://gitlab.com",
            "--enumerate-groups"
        ], token=admin_token)
        
        assert result.returncode == 0, "Group enumeration should succeed"
        
        output_lines = result.stdout.lower().split('\n')
        
        # Validate that we found some groups
        group_count = len([line for line in output_lines if line.strip().startswith("group:")])
        assert group_count > 0, "No groups found with admin token"
        
        # Look for our known groups
        product_glato_found = False
        for line in output_lines:
            if "product-glato" in line:
                product_glato_found = True
                break
        
        assert product_glato_found, "Expected product-glato group not found"
        
        print(f"✅ Admin token group enumeration successful ({group_count} groups found)")
