"""
Real GitLab self-hosted infrastructure e2e tests for runner tag parsing functionality.

This module tests the runner tag parsing feature against real self-hosted GitLab projects
that were specifically created with diverse GitLab CI configurations.
"""

import os
import pytest
import time
from glato.enumerate.enumerate import Enumerator
from glato.gitlab.workflow_parser import WorkflowSecretParser


class TestRunnerTagParsingReal:
    """Real infrastructure tests for runner tag parsing functionality."""
    
    # Self-hosted Test Projects (created in runner-tag-tests group)
    SELFHOSTED_PROJECTS = {
        'basic': {
            'id': 9,
            'path': 'runner-tag-tests/runner-tags-basic',
            'name': 'runner-tags-basic'
        },
        'advanced': {
            'id': 10,
            'path': 'runner-tag-tests/runner-tags-advanced',
            'name': 'runner-tags-advanced'
        },
        'include': {
            'id': 11,
            'path': 'runner-tag-tests/runner-tags-include',
            'name': 'runner-tags-include'
        },
        'matrix': {
            'id': 12,
            'path': 'runner-tag-tests/runner-tags-matrix',
            'name': 'runner-tags-matrix'
        }
    }


class TestSelfHostedRunnerTagParsingReal(TestRunnerTagParsingReal):
    """Self-hosted GitLab real infrastructure tests."""
    
    @pytest.fixture(autouse=True)
    def setup(self, gitlab_url, tokens):
        """Set up test environment for self-hosted testing."""
        # For self-hosted tests, use the specific self-hosted URL
        self.gitlab_url = os.getenv('SELF_HOSTED_GITLAB_URL', '').rstrip('/')
        self.token = (
            tokens.get('SELF_HOSTED_ADMIN_TOKEN') or 
            tokens.get('SELF_HOSTED_ALICE_TOKEN') or
            os.getenv("SELF_HOSTED_ADMIN_TOKEN") or
            os.getenv("SELF_HOSTED_ALICE_TOKEN")
        )
        
        if not self.gitlab_url or not self.token:
            pytest.skip("Self-hosted GitLab environment not configured")
        
        print(f"🔧 Setup complete for self-hosted runner tag parsing tests")
        print(f"   URL: {self.gitlab_url}")

    def test_basic_runner_tag_parsing_selfhosted(self, capsys):
        """Test basic runner tag parsing with real self-hosted project."""
        print("🧪 Testing basic runner tag parsing on real self-hosted project...")
        
        enumerator = Enumerator(
            token=self.token,
            gitlab_url=self.gitlab_url
        )
        
        project_id = self.SELFHOSTED_PROJECTS['basic']['id']
        enumerator._analyze_workflow_runner_requirements(project_id)
        
        captured = capsys.readouterr()
        output = captured.out
        
        # Verify parsing worked
        assert "[*] Analyzing GitLab CI workflows for runner requirements..." in output
        assert "[+] Found workflow file: .gitlab-ci.yml" in output
        
        # Verify tags detected
        assert "docker" in output
        assert "linux" in output
        assert "kubernetes" in output
        
        print("✅ Self-hosted basic runner tag parsing test passed")

    def test_advanced_runner_tag_parsing_selfhosted(self, capsys):
        """Test advanced runner tag parsing on self-hosted."""
        print("🧪 Testing advanced runner tag parsing on self-hosted...")
        
        enumerator = Enumerator(
            token=self.token,
            gitlab_url=self.gitlab_url
        )
        
        project_id = self.SELFHOSTED_PROJECTS['advanced']['id']
        enumerator._analyze_workflow_runner_requirements(project_id)
        
        captured = capsys.readouterr()
        output = captured.out
        
        # Verify advanced features
        assert "production" in output
        assert "secure" in output
        assert "$RUNNER_TYPE" in output or "custom-runner" in output
        
        print("✅ Self-hosted advanced runner tag parsing test passed")

    def test_workflow_parser_direct_selfhosted(self):
        """Test workflow parser directly against self-hosted project."""
        print("🧪 Testing workflow parser directly on self-hosted...")
        
        from glato.gitlab.api import Api
        
        api = Api(pat=self.token, gitlab_url=self.gitlab_url)
        parser = WorkflowSecretParser(api)
        
        project_id = self.SELFHOSTED_PROJECTS['basic']['id']
        workflow_content = parser.get_workflow_file(project_id, path='.gitlab-ci.yml')
        
        assert workflow_content is not None, "Should fetch workflow file"
        assert "build_job:" in workflow_content, "Should contain build_job"
        
        # Parse and extract tags
        parsed_yaml = parser.parse_workflow_yaml(workflow_content)
        runner_tags = parser.extract_runner_tags(parsed_yaml, '.gitlab-ci.yml')
        
        assert len(runner_tags) > 0, "Should extract runner tags"
        
        print(f"✅ Self-hosted direct parser test passed - found {len(runner_tags)} tags")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])