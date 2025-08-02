"""
Real GitLab SaaS infrastructure e2e tests for runner tag parsing functionality.

This module tests the runner tag parsing feature against real GitLab SaaS projects
that were specifically created with diverse GitLab CI configurations.
"""

import os
import pytest
import time
from glato.enumerate.enumerate import Enumerator
from glato.gitlab.workflow_parser import WorkflowSecretParser


class TestRunnerTagParsingReal:
    """Real infrastructure tests for runner tag parsing functionality."""
    
    # SaaS Test Projects (created in api-glato group)
    SAAS_PROJECTS = {
        'basic': {
            'id': 70569298,
            'path': 'product-glato/api-glato/runner-tags-basic-glato',
            'name': 'runner-tags-basic-glato'
        },
        'advanced': {
            'id': 70569302,
            'path': 'product-glato/api-glato/runner-tags-advanced-glato', 
            'name': 'runner-tags-advanced-glato'
        },
        'include': {
            'id': 70569304,
            'path': 'product-glato/api-glato/runner-tags-include-glato',
            'name': 'runner-tags-include-glato'
        },
        'matrix': {
            'id': 70569309,
            'path': 'product-glato/api-glato/runner-tags-matrix-glato',
            'name': 'runner-tags-matrix-glato'
        }
    }


class TestSaaSRunnerTagParsingReal(TestRunnerTagParsingReal):
    """GitLab SaaS real infrastructure tests."""
    
    @pytest.fixture(autouse=True)
    def setup(self, gitlab_url, tokens):
        """Set up test environment for SaaS testing."""
        self.gitlab_url = gitlab_url
        self.token = (
            tokens.get('SAAS_ADMIN_TOKEN') or 
            tokens.get('SAAS_ALICE_TOKEN') or
            os.getenv("SAAS_ADMIN_TOKEN") or
            os.getenv("SAAS_ALICE_TOKEN")
        )
        assert self.token, "SaaS admin or alice token required"
        
        print(f"🔧 Setup complete for SaaS runner tag parsing tests")

    def test_basic_runner_tag_parsing_real(self, capsys):
        """Test basic runner tag parsing with real GitLab SaaS project."""
        print("🧪 Testing basic runner tag parsing on real SaaS project...")
        
        # Create enumerator with developer access simulation
        enumerator = Enumerator(
            token=self.token,
            gitlab_url=self.gitlab_url
        )
        
        # Test the actual runner tag parsing functionality
        project_id = self.SAAS_PROJECTS['basic']['id']
        enumerator._analyze_workflow_runner_requirements(project_id)
        
        # Capture output
        captured = capsys.readouterr()
        output = captured.out
        
        # Verify basic CI parsing worked
        assert "[*] Analyzing GitLab CI workflows for runner requirements..." in output
        assert "[+] Found workflow file: .gitlab-ci.yml" in output
        assert "[*] Runner Tags Required by Workflow:" in output
        
        # Verify specific tags from basic configuration
        assert "build_job" in output
        assert "test_job" in output
        assert "docker" in output
        assert "linux" in output
        assert "kubernetes" in output
        assert "test-env" in output
        
        print("✅ Basic runner tag parsing test passed")

    def test_advanced_runner_tag_parsing_real(self, capsys):
        """Test advanced runner tag parsing with rules and variables."""
        print("🧪 Testing advanced runner tag parsing on real SaaS project...")
        
        enumerator = Enumerator(
            token=self.token,
            gitlab_url=self.gitlab_url
        )
        
        project_id = self.SAAS_PROJECTS['advanced']['id']
        enumerator._analyze_workflow_runner_requirements(project_id)
        
        captured = capsys.readouterr()
        output = captured.out
        
        # Verify advanced features are detected
        assert "build_job" in output
        assert "dynamic_job" in output
        assert "conditional_deploy" in output
        
        # Verify inheritance
        assert "production" in output
        assert "secure" in output
        
        # Verify variables
        assert "$RUNNER_TYPE" in output or "custom-runner" in output
        
        # Verify conditional tags
        assert "prod-runner" in output or "staging-runner" in output
        
        print("✅ Advanced runner tag parsing test passed")

    def test_matrix_runner_tag_parsing_real(self, capsys):
        """Test matrix/parallel job runner tag parsing."""
        print("🧪 Testing matrix runner tag parsing on real SaaS project...")
        
        enumerator = Enumerator(
            token=self.token,
            gitlab_url=self.gitlab_url
        )
        
        project_id = self.SAAS_PROJECTS['matrix']['id']
        enumerator._analyze_workflow_runner_requirements(project_id)
        
        captured = capsys.readouterr()
        output = captured.out
        
        # Verify matrix job parsing
        assert "matrix_test" in output
        assert "parallel_job" in output
        
        # Verify platform-specific tags (variables)
        assert "$PLATFORM" in output or "$RUNNER_TYPE" in output
        
        print("✅ Matrix runner tag parsing test passed")

    def test_workflow_parser_direct_saas(self):
        """Test workflow parser directly against SaaS project."""
        print("🧪 Testing workflow parser directly on SaaS...")
        
        from glato.gitlab.api import Api
        
        # Create API client
        api = Api(pat=self.token, gitlab_url=self.gitlab_url)
        parser = WorkflowSecretParser(api)
        
        # Test getting and parsing workflow file
        project_id = self.SAAS_PROJECTS['basic']['id']
        workflow_content = parser.get_workflow_file(project_id, path='.gitlab-ci.yml')
        
        assert workflow_content is not None, "Should be able to fetch workflow file"
        assert "stages:" in workflow_content, "Workflow should contain stages"
        assert "build_job:" in workflow_content, "Workflow should contain build_job"
        assert "tags:" in workflow_content, "Workflow should contain tags"
        
        # Parse the workflow
        parsed_yaml = parser.parse_workflow_yaml(workflow_content)
        assert parsed_yaml is not None, "Should be able to parse workflow YAML"
        
        # Extract runner tags
        runner_tags = parser.extract_runner_tags(parsed_yaml, '.gitlab-ci.yml')
        assert len(runner_tags) > 0, "Should extract runner tags"
        
        # Verify specific tags
        tag_values = {tag.tag for tag in runner_tags}
        assert 'docker' in tag_values, "Should find docker tag"
        assert 'linux' in tag_values, "Should find linux tag"
        assert 'kubernetes' in tag_values, "Should find kubernetes tag"
        
        print(f"✅ Direct workflow parser test passed - found {len(runner_tags)} tags")

    def test_log_parsing_saas(self):
        """Test pipeline log parsing functionality on SaaS."""
        print("🧪 Testing pipeline log parsing on SaaS...")
        
        from glato.gitlab.api import Api
        
        api = Api(pat=self.token, gitlab_url=self.gitlab_url)
        parser = WorkflowSecretParser(api)
        
        # Test log parsing (may have no pipelines, that's ok)
        project_id = self.SAAS_PROJECTS['basic']['id']
        log_info = parser.extract_runner_info_from_logs(project_id)
        
        # Verify structure
        assert isinstance(log_info, dict), "Should return dict"
        assert 'self_hosted_runners' in log_info, "Should have self_hosted_runners key"
        assert 'shared_runners_used' in log_info, "Should have shared_runners_used key"
        assert 'runner_tags_used' in log_info, "Should have runner_tags_used key"
        assert 'pipeline_count' in log_info, "Should have pipeline_count key"
        assert 'jobs_analyzed' in log_info, "Should have jobs_analyzed key"
        
        print(f"✅ Log parsing test passed - analyzed {log_info['pipeline_count']} pipelines")


class TestRunnerTagParsingComparison:
    """Compare runner tag parsing between SaaS and self-hosted."""
    
    def test_parsing_consistency_between_environments(self):
        """Test that parsing works consistently between SaaS and self-hosted."""
        print("🧪 Testing parsing consistency between environments...")
        
        from glato.gitlab.api import Api
        from glato.gitlab.workflow_parser import WorkflowSecretParser
        
        # Test basic CI content parsing (independent of environment)
        test_ci_content = '''
stages:
  - build
  - test

build_job:
  stage: build
  tags: ['docker', 'linux']
  script: ['echo "build"']

test_job:
  stage: test
  tags: ['kubernetes', 'test-env']
  script: ['echo "test"']
'''
        
        # Create mock API for parsing
        mock_api = type('MockAPI', (), {})()
        parser = WorkflowSecretParser(mock_api)
        
        # Parse the content
        parsed_yaml = parser.parse_workflow_yaml(test_ci_content)
        assert parsed_yaml is not None, "Should parse test CI content"
        
        # Extract tags
        runner_tags = parser.extract_runner_tags(parsed_yaml, 'test.yml')
        
        # Verify expected tags
        tag_values = {tag.tag for tag in runner_tags}
        expected_tags = {'docker', 'linux', 'kubernetes', 'test-env'}
        
        assert tag_values == expected_tags, f"Expected {expected_tags}, got {tag_values}"
        
        print("✅ Parsing consistency test passed")

    def test_variable_tag_detection(self):
        """Test variable tag detection works correctly."""
        print("🧪 Testing variable tag detection...")
        
        from glato.gitlab.workflow_parser import WorkflowSecretParser
        
        test_ci_content = '''
variables:
  RUNNER_TYPE: "custom-runner"

job_with_variables:
  tags: ['$RUNNER_TYPE', '${CUSTOM_TAG}', 'static-tag']
  script: ['echo "test"']
'''
        
        mock_api = type('MockAPI', (), {})()
        parser = WorkflowSecretParser(mock_api)
        
        parsed_yaml = parser.parse_workflow_yaml(test_ci_content)
        runner_tags = parser.extract_runner_tags(parsed_yaml, 'test.yml')
        
        # Check variable detection
        variable_tags = [tag for tag in runner_tags if tag.context == 'variable_tags']
        static_tags = [tag for tag in runner_tags if tag.context == 'job_tags']
        
        assert len(variable_tags) == 2, "Should detect 2 variable tags"
        assert len(static_tags) == 1, "Should detect 1 static tag"
        
        variable_tag_values = {tag.tag for tag in variable_tags}
        assert '$RUNNER_TYPE' in variable_tag_values, "Should detect $RUNNER_TYPE"
        assert '${CUSTOM_TAG}' in variable_tag_values, "Should detect ${CUSTOM_TAG}"
        
        static_tag_values = {tag.tag for tag in static_tags}
        assert 'static-tag' in static_tag_values, "Should detect static-tag"
        
        print("✅ Variable tag detection test passed")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])