"""Unit tests for workflow runner tag parsing functionality"""

import unittest
from unittest.mock import Mock
from glato.gitlab.workflow_parser import WorkflowSecretParser, WorkflowRunnerTag


class TestWorkflowRunnerParsing(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_api = Mock()
        self.parser = WorkflowSecretParser(self.mock_api)
        
    def test_extract_runner_tags_simple_job(self):
        """Test extracting runner tags from a simple job configuration"""
        yaml_dict = {
            'stages': ['test'],
            'test_job': {
                'stage': 'test',
                'tags': ['docker', 'linux'],
                'script': ['echo "test"']
            }
        }
        
        tags = self.parser.extract_runner_tags(yaml_dict, '.gitlab-ci.yml')
        
        self.assertEqual(len(tags), 2)
        tag_values = {tag.tag for tag in tags}
        self.assertEqual(tag_values, {'docker', 'linux'})
        
        # Check tag properties
        for tag in tags:
            self.assertEqual(tag.job_name, 'test_job')
            self.assertEqual(tag.source_file, '.gitlab-ci.yml')
            self.assertEqual(tag.context, 'job_tags')
            self.assertTrue(tag.is_required)
            
    def test_extract_runner_tags_with_extends(self):
        """Test extracting runner tags with job inheritance"""
        yaml_dict = {
            '.base_job': {
                'tags': ['shared', 'docker'],
                'image': 'ubuntu:20.04'
            },
            'test_job': {
                'extends': '.base_job',
                'script': ['echo "test"']
            }
        }
        
        tags = self.parser.extract_runner_tags(yaml_dict, '.gitlab-ci.yml')
        
        self.assertEqual(len(tags), 2)
        tag_values = {tag.tag for tag in tags}
        self.assertEqual(tag_values, {'shared', 'docker'})
        
        # Check inheritance context
        for tag in tags:
            self.assertEqual(tag.job_name, 'test_job')
            self.assertEqual(tag.context, 'inherited_from_.base_job')
            
    def test_extract_runner_tags_with_default(self):
        """Test extracting runner tags from default configuration"""
        yaml_dict = {
            'default': {
                'tags': ['default-runner']
            },
            'test_job': {
                'script': ['echo "test"']
            },
            'custom_job': {
                'tags': ['custom'],
                'script': ['echo "custom"']
            }
        }
        
        tags = self.parser.extract_runner_tags(yaml_dict, '.gitlab-ci.yml')
        
        # Should have 1 default tag for test_job and 1 custom tag for custom_job
        self.assertEqual(len(tags), 2)
        
        tag_by_job = {}
        for tag in tags:
            tag_by_job[tag.job_name] = tag
            
        # test_job should inherit default tag
        self.assertEqual(tag_by_job['test_job'].tag, 'default-runner')
        self.assertEqual(tag_by_job['test_job'].context, 'default_tags')
        
        # custom_job should have its explicit tag
        self.assertEqual(tag_by_job['custom_job'].tag, 'custom')
        self.assertEqual(tag_by_job['custom_job'].context, 'job_tags')
        
    def test_extract_runner_tags_no_tags(self):
        """Test handling of jobs without runner tags"""
        yaml_dict = {
            'test_job': {
                'script': ['echo "test"']
            }
        }
        
        tags = self.parser.extract_runner_tags(yaml_dict, '.gitlab-ci.yml')
        
        self.assertEqual(len(tags), 0)
        
    def test_extract_runner_tags_string_tag(self):
        """Test handling of single string tag instead of list"""
        yaml_dict = {
            'test_job': {
                'tags': 'single-tag',
                'script': ['echo "test"']
            }
        }
        
        tags = self.parser.extract_runner_tags(yaml_dict, '.gitlab-ci.yml')
        
        self.assertEqual(len(tags), 1)
        tag = list(tags)[0]
        self.assertEqual(tag.tag, 'single-tag')
        self.assertEqual(tag.job_name, 'test_job')
        
    def test_extract_runner_tags_ignores_non_jobs(self):
        """Test that non-job sections are ignored"""
        yaml_dict = {
            'variables': {'VAR': 'value'},
            'stages': ['test'],
            'include': ['other.yml'],
            'default': {'image': 'ubuntu'},
            'workflow': {'rules': []},
            '.hidden_job': {'tags': ['hidden']},
            'actual_job': {
                'tags': ['visible'],
                'script': ['echo "test"']
            }
        }
        
        tags = self.parser.extract_runner_tags(yaml_dict, '.gitlab-ci.yml')
        
        # Should only extract from actual_job
        self.assertEqual(len(tags), 1)
        tag = list(tags)[0]
        self.assertEqual(tag.tag, 'visible')
        self.assertEqual(tag.job_name, 'actual_job')
        
    def test_extract_runner_info_from_logs_no_pipelines(self):
        """Test log parsing when no pipelines exist"""
        # Mock API response for no pipelines
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        self.mock_api._call_get.return_value = mock_response
        
        result = self.parser.extract_runner_info_from_logs(123)
        
        expected = {
            'self_hosted_runners': [],
            'shared_runners_used': False,
            'runner_tags_used': [],
            'pipeline_count': 0,
            'jobs_analyzed': 0
        }
        
        self.assertEqual(result, expected)
        
    def test_workflow_runner_tag_equality(self):
        """Test WorkflowRunnerTag equality and hashing"""
        tag1 = WorkflowRunnerTag('docker', 'job1', 'file1')
        tag2 = WorkflowRunnerTag('docker', 'job1', 'file1')
        tag3 = WorkflowRunnerTag('linux', 'job1', 'file1')
        
        self.assertEqual(tag1, tag2)
        self.assertNotEqual(tag1, tag3)
        self.assertEqual(hash(tag1), hash(tag2))
        self.assertNotEqual(hash(tag1), hash(tag3))
        
    def test_workflow_runner_tag_in_set(self):
        """Test that WorkflowRunnerTag works properly in sets"""
        tag1 = WorkflowRunnerTag('docker', 'job1', 'file1')
        tag2 = WorkflowRunnerTag('docker', 'job1', 'file1')  # Duplicate
        tag3 = WorkflowRunnerTag('linux', 'job1', 'file1')
        
        tag_set = {tag1, tag2, tag3}
        
        # Should only have 2 unique tags
        self.assertEqual(len(tag_set), 2)

    def test_default_tags_not_applied_to_extends_jobs(self):
        """Test that jobs with extends don't get default tags if parent has tags"""
        yaml_dict = {
            'default': {
                'tags': ['default-tag']
            },
            '.base': {
                'tags': ['base-tag']
            },
            'job_with_extends': {
                'extends': '.base',
                'script': ['echo test']
            },
            'job_plain': {
                'script': ['echo test']
            }
        }
        
        tags = self.parser.extract_runner_tags(yaml_dict, 'test.yml')
        
        # Group by job
        tags_by_job = {}
        for tag in tags:
            if tag.job_name not in tags_by_job:
                tags_by_job[tag.job_name] = []
            tags_by_job[tag.job_name].append(tag)
        
        # job_with_extends should only have inherited tags, not default
        extends_tags = [t.tag for t in tags_by_job['job_with_extends']]
        self.assertEqual(extends_tags, ['base-tag'])
        
        # job_plain should have default tags
        plain_tags = [t.tag for t in tags_by_job['job_plain']]
        self.assertEqual(plain_tags, ['default-tag'])

    def test_extract_runner_tags_from_rules(self):
        """Test extracting runner tags from job rules"""
        yaml_dict = {
            'deploy_job': {
                'script': ['echo deploy'],
                'rules': [
                    {
                        'if': '$CI_COMMIT_BRANCH == "main"',
                        'tags': ['production-runner']
                    },
                    {
                        'when': 'manual',
                        'tags': ['manual-runner', 'staging-runner']
                    }
                ]
            }
        }
        
        tags = self.parser.extract_runner_tags(yaml_dict, 'test.yml')
        
        # Should extract all possible tags from rules
        tag_values = {tag.tag for tag in tags}
        self.assertEqual(tag_values, {'production-runner', 'manual-runner', 'staging-runner'})
        
        # All should be conditional (not required)
        for tag in tags:
            self.assertFalse(tag.is_required)
            self.assertTrue(tag.context.startswith('rule_'))

    def test_extract_variable_tags(self):
        """Test detection and handling of variable-based tags"""
        yaml_dict = {
            'variable_job': {
                'tags': ['$RUNNER_TYPE', '${CUSTOM_RUNNER}', 'static-tag'],
                'script': ['echo test']
            }
        }
        
        tags = self.parser.extract_runner_tags(yaml_dict, 'test.yml')
        
        # Group by context
        tags_by_context = {}
        for tag in tags:
            if tag.context not in tags_by_context:
                tags_by_context[tag.context] = []
            tags_by_context[tag.context].append(tag.tag)
        
        # Variable tags should be identified
        self.assertIn('variable_tags', tags_by_context)
        self.assertIn('$RUNNER_TYPE', tags_by_context['variable_tags'])
        self.assertIn('${CUSTOM_RUNNER}', tags_by_context['variable_tags'])
        
        # Static tags should remain normal
        self.assertIn('job_tags', tags_by_context)
        self.assertIn('static-tag', tags_by_context['job_tags'])


if __name__ == '__main__':
    unittest.main()