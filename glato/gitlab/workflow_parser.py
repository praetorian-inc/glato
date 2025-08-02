"""Module for parsing GitLab CI workflow files and extracting variables."""

from typing import Optional, Dict, List, Set, Tuple
import yaml
from dataclasses import dataclass
from urllib.parse import urlparse
import fnmatch
import os
import re


@dataclass
class IncludeRule:
    """Represents a rule for when to include a file"""
    if_condition: Optional[str] = None
    when: Optional[str] = None
    variables: Optional[Dict[str, str]] = None


@dataclass
class IncludeFile:
    """Represents a file to be included in the workflow"""
    type: str  # local, remote, template, project
    path: str  # For local/remote, or file path for project includes
    project: Optional[str] = None  # For project includes
    ref: Optional[str] = None  # For project includes
    artifact: Optional[bool] = False  # If include is from job artifact
    rules: Optional[List[IncludeRule]] = None  # Rules for when to include
    is_wildcard: bool = False  # Whether the path contains wildcards
    is_downstream: bool = False  # Whether the included file is a downstream pipeline


@dataclass
class WorkflowVariable:
    """Represents a variable found in a workflow file"""
    name: str
    source_file: str
    context: str  # Where in the file it was found (script, rules, etc.)
    is_predefined: bool = False
    is_local: bool = False

    def __hash__(self):
        # Create a unique hash based on the variable's identifying attributes
        return hash((self.name, self.source_file, self.context))

    def __eq__(self, other):
        if not isinstance(other, WorkflowVariable):
            return False
        return (self.name == other.name and
                self.source_file == other.source_file and
                self.context == other.context)


@dataclass
class WorkflowRunnerTag:
    """Represents a runner tag found in a workflow file"""
    tag: str
    job_name: str
    source_file: str
    is_required: bool = True  # Whether the tag is explicitly required
    context: str = "job_tags"  # Context where the tag was found

    def __hash__(self):
        return hash((self.tag, self.job_name, self.source_file))

    def __eq__(self, other):
        if not isinstance(other, WorkflowRunnerTag):
            return False
        return (self.tag == other.tag and
                self.job_name == other.job_name and
                self.source_file == other.source_file)


class WorkflowSecretParser:
    """Parser for extracting potential secret variables from GitLab CI workflows"""

    def __init__(self, api):
        self.api = api
        self.processed_files = set()  # Track files we've processed to avoid cycles
        self.max_depth = 10
        self.current_depth = 0

    PREDEFINED_VARS = {
        'CHAT_CHANNEL',
        'CHAT_INPUT',
        'CHAT_USER_ID',
        'CI',
        'CI_API_V4_URL',
        'CI_API_GRAPHQL_URL',
        'CI_BUILDS_DIR',
        'CI_COMMIT_AUTHOR',
        'CI_COMMIT_BEFORE_SHA',
        'CI_COMMIT_BRANCH',
        'CI_COMMIT_DESCRIPTION',
        'CI_COMMIT_MESSAGE',
        'CI_COMMIT_REF_NAME',
        'CI_COMMIT_REF_PROTECTED',
        'CI_COMMIT_REF_SLUG',
        'CI_COMMIT_SHA',
        'CI_COMMIT_SHORT_SHA',
        'CI_COMMIT_TAG',
        'CI_COMMIT_TAG_MESSAGE',
        'CI_COMMIT_TIMESTAMP',
        'CI_COMMIT_TITLE',
        'CI_CONCURRENT_ID',
        'CI_CONCURRENT_PROJECT_ID',
        'CI_CONFIG_PATH',
        'CI_DEBUG_TRACE',
        'CI_DEBUG_SERVICES',
        'CI_DEFAULT_BRANCH',
        'CI_DEPENDENCY_PROXY_DIRECT_GROUP_IMAGE_PREFIX',
        'CI_DEPENDENCY_PROXY_GROUP_IMAGE_PREFIX',
        'CI_DEPLOY_FREEZE',
        'CI_DISPOSABLE_ENVIRONMENT',
        'CI_ENVIRONMENT_NAME',
        'CI_ENVIRONMENT_SLUG',
        'CI_ENVIRONMENT_URL',
        'CI_ENVIRONMENT_ACTION',
        'CI_ENVIRONMENT_TIER',
        'CI_GITLAB_FIPS_MODE',
        'CI_HAS_OPEN_REQUIREMENTS',
        'CI_JOB_ID',
        'CI_JOB_IMAGE',
        'CI_JOB_MANUAL',
        'CI_JOB_NAME',
        'CI_JOB_NAME_SLUG',
        'CI_JOB_STAGE',
        'CI_JOB_STATUS',
        'CI_JOB_TIMEOUT',
        'CI_JOB_TOKEN',
        'CI_JOB_URL',
        'CI_JOB_STARTED_AT',
        'CI_KUBERNETES_ACTIVE',
        'CI_NODE_INDEX',
        'CI_NODE_TOTAL',
        'CI_OPEN_MERGE_REQUESTS',
        'CI_PAGES_DOMAIN',
        'CI_PAGES_URL',
        'CI_PIPELINE_ID',
        'CI_PIPELINE_IID',
        'CI_PIPELINE_SOURCE',
        'CI_PIPELINE_TRIGGERED',
        'CI_PIPELINE_URL',
        'CI_PIPELINE_CREATED_AT',
        'CI_PIPELINE_NAME',
        'CI_PROJECT_DIR',
        'CI_PROJECT_ID',
        'CI_PROJECT_NAME',
        'CI_PROJECT_NAMESPACE',
        'CI_PROJECT_NAMESPACE_ID',
        'CI_PROJECT_PATH_SLUG',
        'CI_PROJECT_PATH',
        'CI_PROJECT_REPOSITORY_LANGUAGES',
        'CI_PROJECT_ROOT_NAMESPACE',
        'CI_PROJECT_TITLE',
        'CI_PROJECT_DESCRIPTION',
        'CI_PROJECT_URL',
        'CI_PROJECT_VISIBILITY',
        'CI_PROJECT_CLASSIFICATION_LABEL',
        'CI_REGISTRY',
        'CI_REGISTRY_IMAGE',
        'CI_RELEASE_DESCRIPTION',
        'CI_REPOSITORY_URL',
        'CI_RUNNER_DESCRIPTION',
        'CI_RUNNER_EXECUTABLE_ARCH',
        'CI_RUNNER_ID',
        'CI_RUNNER_REVISION',
        'CI_RUNNER_SHORT_TOKEN',
        'CI_RUNNER_TAGS',
        'CI_RUNNER_VERSION',
        'CI_SERVER_FQDN',
        'CI_SERVER_HOST',
        'CI_SERVER_NAME',
        'CI_SERVER_PORT',
        'CI_SERVER_PROTOCOL',
        'CI_SERVER_SHELL_SSH_HOST',
        'CI_SERVER_SHELL_SSH_PORT',
        'CI_SERVER_REVISION',
        'CI_SERVER_TLS_CA_FILE',
        'CI_SERVER_TLS_CERT_FILE',
        'CI_SERVER_TLS_KEY_FILE',
        'CI_SERVER_URL',
        'CI_SERVER_VERSION_MAJOR',
        'CI_SERVER_VERSION_MINOR',
        'CI_SERVER_VERSION_PATCH',
        'CI_SERVER_VERSION',
        'CI_SERVER',
        'CI_SHARED_ENVIRONMENT',
        'CI_TEMPLATE_REGISTRY_HOST',
        'CI_TRIGGER_SHORT_TOKEN',
        'GITLAB_CI',
        'GITLAB_FEATURES',
        'GITLAB_USER_EMAIL',
        'GITLAB_USER_ID',
        'GITLAB_USER_LOGIN',
        'GITLAB_USER_NAME',
        'KUBECONFIG',
        'TRIGGER_PAYLOAD',
        'CI_MERGE_REQUEST_APPROVED',
        'CI_MERGE_REQUEST_ASSIGNEES',
        'CI_MERGE_REQUEST_DIFF_BASE_SHA',
        'CI_MERGE_REQUEST_DIFF_ID',
        'CI_MERGE_REQUEST_EVENT_TYPE',
        'CI_MERGE_REQUEST_DESCRIPTION',
        'CI_MERGE_REQUEST_DESCRIPTION_IS_TRUNCATED',
        'CI_MERGE_REQUEST_ID',
        'CI_MERGE_REQUEST_IID',
        'CI_MERGE_REQUEST_LABELS',
        'CI_MERGE_REQUEST_MILESTONE',
        'CI_MERGE_REQUEST_PROJECT_ID',
        'CI_MERGE_REQUEST_PROJECT_PATH',
        'CI_MERGE_REQUEST_PROJECT_URL',
        'CI_MERGE_REQUEST_REF_PATH',
        'CI_MERGE_REQUEST_SOURCE_BRANCH_NAME',
        'CI_MERGE_REQUEST_SOURCE_BRANCH_PROTECTED',
        'CI_MERGE_REQUEST_SOURCE_BRANCH_SHA',
        'CI_MERGE_REQUEST_SOURCE_PROJECT_ID',
        'CI_MERGE_REQUEST_SOURCE_PROJECT_PATH',
        'CI_MERGE_REQUEST_SOURCE_PROJECT_URL',
        'CI_MERGE_REQUEST_SQUASH_ON_MERGE',
        'CI_MERGE_REQUEST_TARGET_BRANCH_NAME',
        'CI_MERGE_REQUEST_TARGET_BRANCH_PROTECTED',
        'CI_MERGE_REQUEST_TARGET_BRANCH_SHA',
        'CI_MERGE_REQUEST_TITLE',
        'CI_EXTERNAL_PULL_REQUEST_IID',
        'CI_EXTERNAL_PULL_REQUEST_SOURCE_REPOSITORY',
        'CI_EXTERNAL_PULL_REQUEST_TARGET_REPOSITORY',
        'PATH',
        'CI_EXTERNAL_PULL_REQUEST_SOURCE_BRANCH_NAME',
        'CI_EXTERNAL_PULL_REQUEST_SOURCE_BRANCH_SHA',
        'CI_EXTERNAL_PULL_REQUEST_TARGET_BRANCH_NAME',
        'CI_EXTERNAL_PULL_REQUEST_TARGET_BRANCH_SHA'}

    def get_workflow_file(
            self,
            project_id: int,
            ref: str = 'main',
            path: str = '.gitlab-ci.yml') -> Optional[str]:
        """Retrieve a workflow file from GitLab

        Args:
            project_id: Project ID
            ref: Branch/tag reference
            path: Path to workflow file

        Returns:
            String content of workflow file if found, None otherwise
        """
        return self.api.get_file_content(project_id, path, ref)

    def parse_workflow_yaml(self, content: str) -> Optional[Dict]:
        """Parse workflow YAML with proper error handling and GitLab tag support"""
        from ..gitlab.secrets import Secrets
        try:
            class GitLabCILoader(yaml.SafeLoader):
                """Custom loader for GitLab CI YAML"""
                pass

            def reference_constructor(loader, node):
                """Handle !reference tags
                e.g., !reference [.docker-image, script]"""
                if isinstance(node, yaml.SequenceNode):
                    value = loader.construct_sequence(node)
                    return value
                return loader.construct_scalar(node)

            def include_constructor(loader, node):
                """Handle !include tags"""
                if isinstance(node, yaml.ScalarNode):
                    value = loader.construct_scalar(node)
                    return value
                return None

            # Only handle tags we explicitly know about
            known_tags = {
                '!reference': reference_constructor,
                '!include': include_constructor
            }

            for tag, constructor in known_tags.items():
                GitLabCILoader.add_constructor(tag, constructor)

            # Parse YAML with custom loader
            try:
                parsed = yaml.load(content, Loader=GitLabCILoader)
            except yaml.constructor.ConstructorError as e:
                print(f"Unknown YAML tag encountered: {e}")
                # Fallback to ignoring unknown tags if needed
                parsed = yaml.load(content, Loader=yaml.SafeLoader)

            if not parsed:
                return {}

            # First collect template jobs from includes if any
            template_jobs = {}
            if 'include' in parsed:
                includes = self.extract_includes(parsed)
                for inc in includes:
                    if inc.type == 'template':
                        template_content = Secrets.get_template_content(
                            self.api, inc.path)
                        if template_content:
                            template_yaml = yaml.safe_load(template_content)
                            if template_yaml and isinstance(
                                    template_yaml, dict):
                                template_jobs.update(template_yaml)

            # Handle extends after initial parsing
            resolved = self._resolve_extends(parsed, template_jobs)
            return resolved

        except yaml.YAMLError as e:
            print(f"Error parsing workflow YAML: {str(e)}")
            return None
        except Exception as e:
            print(f"Unexpected error parsing workflow YAML: {str(e)}")
            return None

    def _resolve_extends(self, config: Dict, template_jobs: Dict) -> Dict:
        """Resolve extends keywords in GitLab CI configuration"""
        resolved = {}

        # First pass: collect all jobs including hidden ones
        for name, job in config.items():
            resolved[name] = job.copy() if isinstance(job, dict) else job

        # Add template jobs to the resolution namespace
        for name, job in template_jobs.items():
            if name not in resolved:  # Don't override local jobs
                resolved[name] = job.copy()

        # Second pass: resolve extends
        for name, job in resolved.items():
            if isinstance(job, dict) and 'extends' in job:
                resolved[name] = self._resolve_job_extends(job, resolved)

        return resolved

    def extract_includes(self, yaml_dict: Dict) -> List[IncludeFile]:
        """Extract all include directives from the YAML

        Args:
            yaml_dict: Parsed YAML dictionary

        Returns:
            List of IncludeFile objects
        """
        includes = []
        if 'include' not in yaml_dict:
            return includes

        include_data = yaml_dict['include']

        # Handle different include formats
        if isinstance(include_data, str):
            # Simple include: 'path/to/file.yml'
            includes.extend(self._process_simple_include(include_data))

        elif isinstance(include_data, list):
            # Array of includes
            for inc in include_data:
                if isinstance(inc, str):
                    # Simple include in array
                    includes.extend(self._process_simple_include(inc))
                elif isinstance(inc, dict):
                    # Complex include in array
                    includes.extend(self._process_complex_include(inc))

        elif isinstance(include_data, dict):
            # Single complex include
            includes.extend(self._process_complex_include(include_data))

        return includes

    def _process_simple_include(self, path: str) -> List[IncludeFile]:
        """Process a simple include string

        Args:
            path: Include path string

        Returns:
            List of IncludeFile objects
        """
        # Check if it's a project include
        if path.startswith('project: '):
            project = path.replace('project: ', '').strip()
            return [IncludeFile(
                type='project',
                path='.gitlab-ci.yml',  # Default file if none specified
                project=project
            )]

        # Check if it's a template include
        if path.startswith('template: '):
            template = path.replace('template: ', '').strip()
            return [IncludeFile(
                type='template',
                path=template
            )]

        # Check if it's a remote include
        if path.startswith(('http://', 'https://')):
            return [IncludeFile(
                type='remote',
                path=path
            )]

        # Otherwise it's a local include
        return [IncludeFile(
            type='local',
            path=path
        )]

    def _resolve_job_extends(
            self,
            job: Dict,
            all_jobs: Dict,
            templates: Dict = None,
            stack: Set[str] = None) -> Dict:
        """Resolve extends for a single job

        Args:
            job: Job configuration to resolve
            all_jobs: All jobs from current file
            templates: Jobs from included templates
            stack: Set of jobs being processed (for cycle detection)
        """
        if stack is None:
            stack = set()

        if 'extends' not in job:
            return job

        extends = job.pop('extends')
        if isinstance(extends, str):
            extends = [extends]
       # print("Extends: "+str(extends))

        result = {}
        for parent in extends:
            if parent in stack:
                print(f"Warning: extends cycle detected with {parent}")
                continue

            # First check current file
            if parent in all_jobs:
                stack.add(parent)
                parent_config = self._resolve_job_extends(
                    all_jobs[parent].copy(), all_jobs, templates, stack)
                stack.remove(parent)
                result = self._merge_job_configs(result, parent_config)
                continue

            # Then check included templates
            if templates and parent in templates:
                stack.add(parent)
                parent_config = self._resolve_job_extends(
                    templates[parent].copy(), templates, templates, stack)
                stack.remove(parent)
                result = self._merge_job_configs(result, parent_config)
                continue

            # TODO: there are still some issues with extends tracking
            # print(f"Warning: extended job {parent} not found")

        # Finally merge in the current job's config
        return self._merge_job_configs(result, job)

    def _merge_job_configs(self, base: Dict, override: Dict) -> Dict:
        """Merge job configurations according to GitLab's rules"""
        result = base.copy()
        for key, value in override.items():
            if key not in result:
                result[key] = value
            elif isinstance(value, dict) and isinstance(result[key], dict):
                result[key] = self._merge_job_configs(result[key], value)
            else:
                result[key] = value
        return result

    def _resolve_yaml_aliases(self, data):
        """Resolve YAML aliases, merge keys, and tags in the data structure

        Args:
            data: YAML data structure to process

        Returns:
            Processed data structure with resolved aliases and merge keys
        """
        if isinstance(data, dict):
            # Handle merge keys with multiple sources
            if '<<' in data:
                merged = {}
                # Process normal keys first
                for k, v in data.items():
                    if k != '<<':
                        merged[k] = self._resolve_yaml_aliases(v)

                # Process merge sources in order
                merge_sources = data['<<']
                if isinstance(merge_sources, list):
                    # Multiple merge sources
                    for source in merge_sources:
                        if isinstance(source, dict):
                            for k, v in source.items():
                                if k not in merged:  # Don't override existing keys
                                    merged[k] = self._resolve_yaml_aliases(v)
                elif isinstance(merge_sources, dict):
                    # Single merge source
                    for k, v in merge_sources.items():
                        if k not in merged:  # Don't override existing keys
                            merged[k] = self._resolve_yaml_aliases(v)

                return merged

            # Process regular dictionary
            return {k: self._resolve_yaml_aliases(v) for k, v in data.items()}

        elif isinstance(data, list):
            return [self._resolve_yaml_aliases(item) for item in data]

        return data

    def _process_complex_include(
            self, include_dict: Dict) -> List[IncludeFile]:
        """Process a complex include dictionary

        Args:
            include_dict: Include specification dictionary

        Returns:
            List of IncludeFile objects
        """
        includes = []

        # Resolve any YAML aliases first
        include_dict = self._resolve_yaml_aliases(include_dict)

        # Extract rules if present
        rules = None
        if 'rules' in include_dict:
            rules = []
            for rule in include_dict['rules']:
                rules.append(IncludeRule(
                    if_condition=rule.get('if'),
                    when=rule.get('when'),
                    variables=rule.get('variables')
                ))

        # Handle each type of include
        if 'local' in include_dict:
            path = include_dict['local']
            includes.append(IncludeFile(
                type='local',
                path=path,
                rules=rules,
                is_wildcard='*' in path
            ))

        elif 'remote' in include_dict:
            path = include_dict['remote']
            includes.append(IncludeFile(
                type='remote',
                path=path,
                rules=rules
            ))

        elif 'template' in include_dict:
            path = include_dict['template']
            includes.append(IncludeFile(
                type='template',
                path=path,
                rules=rules
            ))

        elif 'project' in include_dict:
            # Handle project includes which can have multiple files
            project = include_dict['project']
            ref = include_dict.get('ref')
            file_spec = include_dict.get('file', '.gitlab-ci.yml')
            artifact = include_dict.get('artifact', False)

            # Handle both single file and array of files
            if isinstance(file_spec, list):
                for file_path in file_spec:
                    includes.append(IncludeFile(
                        type='project',
                        path=file_path,
                        project=project,
                        ref=ref,
                        artifact=artifact,
                        rules=rules,
                        is_wildcard='*' in file_path
                    ))
            else:
                includes.append(IncludeFile(
                    type='project',
                    path=file_spec,
                    project=project,
                    ref=ref,
                    artifact=artifact,
                    rules=rules,
                    is_wildcard='*' in file_spec
                ))

        return includes

    def _validate_include(self, include: IncludeFile) -> bool:
        """Validate if an include should be processed

        Args:
            include: IncludeFile object to validate

        Returns:
            bool: True if include should be processed
        """
        # Skip remote includes as specified
        if include.type == 'remote':
            return False

        # Skip artifact includes as they require job execution
        if include.artifact:
            return False

        # Skip if rules specify 'when: never'
        if include.rules:
            for rule in include.rules:
                if rule.when == 'never':
                    return False

        # Validate file extension
        if not (include.path.endswith('.yml')
                or include.path.endswith('.yaml')):
            if not include.is_wildcard:  # Allow wildcards to end differently
                return False

        # Check depth
        if self.current_depth >= self.max_depth:
            return False

        return True

    def _expand_wildcard_paths(
            self,
            project_id: int,
            include: IncludeFile) -> List[str]:
        """Expand wildcard paths in project includes

        Args:
            project_id: Current project ID
            include: IncludeFile with potential wildcards

        Returns:
            List of concrete file paths
        """
        if not include.is_wildcard:
            return [include.path]

        # Use GitLab API to list files in project
        ref = include.ref or 'main'
        try:
            res = self.api._call_get(
                f'/projects/{project_id}/repository/tree',
                params={'ref': ref, 'recursive': True}
            )

            if not res or res.status_code != 200:
                return [include.path]

            files = res.json()
            matching_files = []

            for file_info in files:
                if file_info['type'] == 'blob':  # Only match files, not directories
                    if fnmatch.fnmatch(file_info['path'], include.path):
                        matching_files.append(file_info['path'])

            return matching_files

        except Exception as e:
            print(f"Error expanding wildcard paths: {str(e)}")
            return [include.path]

    def extract_variables(
            self,
            yaml_dict: Dict,
            source_file: str) -> Set[WorkflowVariable]:
        """Extract all variables from a workflow YAML

        Args:
            yaml_dict: Parsed YAML dictionary
            source_file: Path/name of the source file for context

        Returns:
            Set of WorkflowVariable objects
        """
        variables = set()

        # First get local variables to exclude them
        local_vars = self._get_local_variables(yaml_dict)

        # Extract variables from different contexts
        variables.update(
            self._extract_script_variables(
                yaml_dict,
                source_file,
                local_vars))
        variables.update(
            self._extract_rule_variables(
                yaml_dict,
                source_file,
                local_vars))
        variables.update(
            self._extract_environment_variables(
                yaml_dict, source_file, local_vars))
        variables.update(
            self._extract_job_setting_variables(
                yaml_dict, source_file, local_vars))
        variables.update(
            self._extract_trigger_variables(
                yaml_dict,
                source_file,
                local_vars))

        return variables

    def extract_runner_tags(
            self,
            yaml_dict: Dict,
            source_file: str,
            include_resolved: bool = True) -> Set[WorkflowRunnerTag]:
        """Extract runner tags from a workflow YAML

        Args:
            yaml_dict: Parsed YAML dictionary
            source_file: Path/name of the source file for context
            include_resolved: Whether to include tags from resolved includes/templates

        Returns:
            Set of WorkflowRunnerTag objects
        """
        runner_tags = set()

        # Extract tags from job configurations
        for job_name, job_config in yaml_dict.items():
            if isinstance(
                    job_config,
                    dict) and not job_name.startswith('.') and job_name not in [
                    'variables',
                    'stages',
                    'include',
                    'default',
                    'workflow']:
                # Check for explicit tags in job
                if 'tags' in job_config:
                    tags = job_config['tags']
                    if isinstance(tags, list):
                        for tag in tags:
                            if isinstance(tag, str):
                                context = "job_tags"
                                if self._is_variable_tag(tag):
                                    context = "variable_tags"
                                runner_tags.add(WorkflowRunnerTag(
                                    tag=tag,
                                    job_name=job_name,
                                    source_file=source_file,
                                    is_required=True,
                                    context=context
                                ))
                    elif isinstance(tags, str):
                        context = "job_tags"
                        if self._is_variable_tag(tags):
                            context = "variable_tags"
                        runner_tags.add(WorkflowRunnerTag(
                            tag=tags,
                            job_name=job_name,
                            source_file=source_file,
                            is_required=True,
                            context=context
                        ))

                # Check for inherited tags from extends (only if job doesn't have explicit tags)
                # Note: This handles direct inheritance but not deep nested
                # extends chains
                if 'extends' in job_config and 'tags' not in job_config:
                    extends = job_config['extends']
                    if isinstance(extends, str):
                        extends = [extends]
                    for parent_job in extends:
                        if parent_job in yaml_dict and isinstance(
                                yaml_dict[parent_job], dict):
                            parent_config = yaml_dict[parent_job]
                            if 'tags' in parent_config:
                                parent_tags = parent_config['tags']
                                if isinstance(parent_tags, list):
                                    for tag in parent_tags:
                                        if isinstance(tag, str):
                                            runner_tags.add(
                                                WorkflowRunnerTag(
                                                    tag=tag,
                                                    job_name=job_name,
                                                    source_file=source_file,
                                                    is_required=True,
                                                    context=f"inherited_from_{parent_job}"))
                                elif isinstance(parent_tags, str):
                                    runner_tags.add(WorkflowRunnerTag(
                                        tag=parent_tags,
                                        job_name=job_name,
                                        source_file=source_file,
                                        is_required=True,
                                        context=f"inherited_from_{parent_job}"
                                    ))

                # Check for tags in rules (conditional tags)
                if 'rules' in job_config:
                    rules = job_config['rules']
                    if isinstance(rules, list):
                        for i, rule in enumerate(rules):
                            if isinstance(rule, dict) and 'tags' in rule:
                                rule_tags = rule['tags']
                                if isinstance(rule_tags, list):
                                    for tag in rule_tags:
                                        if isinstance(tag, str):
                                            # Note: Rule conditions not
                                            # evaluated, just extracting
                                            # possible tags
                                            runner_tags.add(WorkflowRunnerTag(
                                                tag=tag,
                                                job_name=job_name,
                                                source_file=source_file,
                                                is_required=False,  # Conditional
                                                context=f"rule_{i}_tags"
                                            ))
                                elif isinstance(rule_tags, str):
                                    runner_tags.add(WorkflowRunnerTag(
                                        tag=rule_tags,
                                        job_name=job_name,
                                        source_file=source_file,
                                        is_required=False,  # Conditional
                                        context=f"rule_{i}_tags"
                                    ))

        # Check default tags that apply to all jobs
        if 'default' in yaml_dict and isinstance(yaml_dict['default'], dict):
            default_config = yaml_dict['default']
            if 'tags' in default_config:
                default_tags = default_config['tags']
                if isinstance(default_tags, list):
                    for tag in default_tags:
                        if isinstance(tag, str):
                            # Apply default tags to all jobs that don't have
                            # explicit tags AND don't extend a job with tags
                            for job_name, job_config in yaml_dict.items():
                                if (
                                    isinstance(
                                        job_config,
                                        dict) and not job_name.startswith('.') and job_name not in [
                                        'variables',
                                        'stages',
                                        'include',
                                        'default',
                                        'workflow'] and 'tags' not in job_config and not self._job_inherits_tags(
                                        job_config,
                                        yaml_dict)):
                                    runner_tags.add(WorkflowRunnerTag(
                                        tag=tag,
                                        job_name=job_name,
                                        source_file=source_file,
                                        is_required=True,
                                        context="default_tags"
                                    ))
                elif isinstance(default_tags, str):
                    for job_name, job_config in yaml_dict.items():
                        if (
                            isinstance(
                                job_config,
                                dict) and not job_name.startswith('.') and job_name not in [
                                'variables',
                                'stages',
                                'include',
                                'default',
                                'workflow'] and 'tags' not in job_config and not self._job_inherits_tags(
                                job_config,
                                yaml_dict)):
                            runner_tags.add(WorkflowRunnerTag(
                                tag=default_tags,
                                job_name=job_name,
                                source_file=source_file,
                                is_required=True,
                                context="default_tags"
                            ))

        return runner_tags

    def _job_inherits_tags(self, job_config: Dict, yaml_dict: Dict) -> bool:
        """Check if a job inherits tags from a parent via extends

        Args:
            job_config: Job configuration dictionary
            yaml_dict: Full YAML dictionary

        Returns:
            bool: True if job inherits tags from parent
        """
        if 'extends' not in job_config:
            return False

        extends = job_config['extends']
        if isinstance(extends, str):
            extends = [extends]

        for parent_job in extends:
            if parent_job in yaml_dict and isinstance(
                    yaml_dict[parent_job], dict):
                parent_config = yaml_dict[parent_job]
                if 'tags' in parent_config:
                    return True

        return False

    def _is_variable_tag(self, tag: str) -> bool:
        """Check if a tag contains GitLab CI variables

        Args:
            tag: Tag string to check

        Returns:
            bool: True if tag contains variables
        """
        import re
        variable_patterns = [
            r'\$[A-Za-z_][A-Za-z0-9_]*',  # $VAR
            r'\$\{[A-Za-z_][A-Za-z0-9_]*\}',  # ${VAR}
        ]

        for pattern in variable_patterns:
            if re.search(pattern, tag):
                return True
        return False

    def extract_runner_info_from_logs(
            self, project_id: int, ref: str = 'main') -> Dict[str, any]:
        """Extract runner information from GitLab CI pipeline logs

        Args:
            project_id: Project ID to fetch logs from
            ref: Branch/tag reference to check pipelines for

        Returns:
            Dictionary containing runner usage information
        """
        runner_info = {
            'self_hosted_runners': set(),
            'shared_runners_used': False,
            'runner_tags_used': set(),
            'pipeline_count': 0,
            'jobs_analyzed': 0
        }

        try:
            # Get recent pipelines for the project
            pipelines_res = self.api._call_get(
                f'/projects/{project_id}/pipelines',
                params={
                    'ref': ref,
                    'per_page': 10})

            if not pipelines_res or pipelines_res.status_code != 200:
                return runner_info

            pipelines = pipelines_res.json()
            runner_info['pipeline_count'] = len(pipelines)

            for pipeline in pipelines[:5]:  # Analyze last 5 pipelines
                pipeline_id = pipeline['id']

                # Get jobs for this pipeline
                jobs_res = self.api._call_get(
                    f'/projects/{project_id}/pipelines/{pipeline_id}/jobs')
                if not jobs_res or jobs_res.status_code != 200:
                    continue

                jobs = jobs_res.json()

                for job in jobs:
                    runner_info['jobs_analyzed'] += 1

                    # Check if job used a runner
                    if 'runner' in job and job['runner']:
                        runner = job['runner']

                        # Check if it's a self-hosted runner
                        if not runner.get('is_shared', True):
                            runner_info['self_hosted_runners'].add(
                                runner.get('description', 'Unknown'))

                            # Extract tags if available
                            if 'tag_list' in runner and runner['tag_list']:
                                runner_info['runner_tags_used'].update(
                                    runner['tag_list'])
                        else:
                            runner_info['shared_runners_used'] = True

                    # Try to get job trace/log for additional runner
                    # information
                    trace_res = self.api._call_get(
                        f'/projects/{project_id}/jobs/{job["id"]}/trace')
                    if trace_res and trace_res.status_code == 200:
                        trace_content = trace_res.text if hasattr(
                            trace_res, 'text') else str(trace_res)

                        # Look for runner information in logs
                        runner_patterns = [
                            r'Running with gitlab-runner [\d\.]+ \([a-f0-9]+\) on (.+?) \([a-f0-9]+\)',
                            r'Running on (.+?) via',
                            r'Executing "step_script" stage of the job script on (.+?)$']

                        for pattern in runner_patterns:
                            matches = re.findall(
                                pattern, trace_content, re.MULTILINE)
                            for match in matches:
                                if match and not match.startswith(
                                        'runner-'):  # Likely self-hosted
                                    runner_info['self_hosted_runners'].add(
                                        match.strip())

        except Exception as e:
            print(f"Error extracting runner info from logs: {str(e)}")

        # Convert sets to lists for JSON serialization
        runner_info['self_hosted_runners'] = list(
            runner_info['self_hosted_runners'])
        runner_info['runner_tags_used'] = list(runner_info['runner_tags_used'])

        return runner_info

    def _get_local_variables(self, yaml_dict: Dict) -> Set[str]:
        """Extract variables defined in the variables section

        Args:
            yaml_dict: Parsed YAML dictionary

        Returns:
            Set of local variable names
        """
        local_vars = set()

        # Global variables
        if 'variables' in yaml_dict:
            variables = yaml_dict['variables']
            # Only try to get keys if it's actually a dictionary
            if isinstance(variables, dict):
                local_vars.update(variables.keys())

        # Job-level variables
        for job_name, job_config in yaml_dict.items():
            if isinstance(job_config, dict):
                if 'variables' in job_config:
                    variables = job_config['variables']
                    if isinstance(variables, dict):
                        local_vars.update(variables.keys())

        return local_vars

    def _extract_script_variables(
            self,
            yaml_dict: Dict,
            source_file: str,
            local_vars: Set[str]) -> Set[WorkflowVariable]:
        """Extract variables from script sections

        Args:
            yaml_dict: Parsed YAML dictionary
            source_file: Source file path/name
            local_vars: Set of local variable names

        Returns:
            Set of WorkflowVariable objects
        """
        variables = set()
        script_sections = ['before_script', 'script', 'after_script']

        def flatten_script_content(content):
            """Helper to flatten script content into a single string"""
            if isinstance(content, str):
                return content
            elif isinstance(content, list):
                # Recursively flatten any nested lists and join with newlines
                return '\n'.join(
                    flatten_script_content(item) if isinstance(item, (list, str))
                    else str(item)
                    for item in content
                )
            else:
                return str(content)

        # Check global script sections
        for section in script_sections:
            if section in yaml_dict:
                script_content = yaml_dict[section]
                flattened_content = flatten_script_content(script_content)
                variables.update(self._extract_variables_from_string(
                    flattened_content, f'global_{section}',
                    source_file, local_vars
                ))

        # Check job-level script sections
        for job_name, job_config in yaml_dict.items():
            if isinstance(job_config, dict):
                for section in script_sections:
                    if section in job_config:
                        script_content = job_config[section]
                        flattened_content = flatten_script_content(
                            script_content)
                        variables.update(self._extract_variables_from_string(
                            flattened_content, f'job_{job_name}_{section}',
                            source_file, local_vars
                        ))

        return variables

    def _extract_rule_variables(self, yaml_dict: Dict, source_file: str,
                                local_vars: Set[str]) -> Set[WorkflowVariable]:
        """Extract variables from rules conditions

        Args:
            yaml_dict: Parsed YAML dictionary
            source_file: Source file path/name
            local_vars: Set of local variable names

        Returns:
            Set of WorkflowVariable objects
        """
        variables = set()

        def process_rules(rules, context_prefix):
            if isinstance(rules, list):
                for i, rule in enumerate(rules):
                    if isinstance(rule, dict):
                        if 'if' in rule:
                            variables.update(self._extract_variables_from_string(
                                str(rule['if']),
                                f'{context_prefix}_rule_{i}',
                                source_file,
                                local_vars
                            ))

        # Global rules
        if 'rules' in yaml_dict:
            process_rules(yaml_dict['rules'], 'global')

        # Job-level rules
        for job_name, job_config in yaml_dict.items():
            if isinstance(job_config, dict):
                if 'rules' in job_config:
                    process_rules(job_config['rules'], f'job_{job_name}')

        return variables

    def _extract_environment_variables(
            self,
            yaml_dict: Dict,
            source_file: str,
            local_vars: Set[str]) -> Set[WorkflowVariable]:
        """Extract variables from environment configurations

        Args:
            yaml_dict: Parsed YAML dictionary
            source_file: Source file path/name
            local_vars: Set of local variable names

        Returns:
            Set of WorkflowVariable objects
        """
        variables = set()

        def process_environment(env_config, context_prefix):
            if isinstance(env_config, dict):
                for key, value in env_config.items():
                    variables.update(self._extract_variables_from_string(
                        str(value), f'{context_prefix}_environment_{key}',
                        source_file, local_vars
                    ))

        # Global environment
        if 'environment' in yaml_dict:
            process_environment(yaml_dict['environment'], 'global')

        # Job-level environment
        for job_name, job_config in yaml_dict.items():
            if isinstance(job_config, dict):
                if 'environment' in job_config:
                    process_environment(
                        job_config['environment'], f'job_{job_name}')

        return variables

    def _extract_job_setting_variables(
            self,
            yaml_dict: Dict,
            source_file: str,
            local_vars: Set[str]) -> Set[WorkflowVariable]:
        """Extract variables from job settings that could contain secrets.

        Examines job-level settings like image, services, cache keys, etc. that
        might reference secret variables.
        """
        variables = set()

        # Settings that might contain variables/secrets
        settings = ['image', 'services', 'cache:key', 'artifacts:name']

        for job_name, job_config in yaml_dict.items():
            if isinstance(job_config, dict):
                for setting in settings:
                    setting_parts = setting.split(':')
                    current_level = job_config

                    for part in setting_parts[:-1]:
                        if part in current_level and isinstance(
                                current_level[part], dict):
                            current_level = current_level[part]
                        else:
                            current_level = None
                            break

                    if current_level and setting_parts[-1] in current_level:
                        value = current_level[setting_parts[-1]]
                        variables.update(self._extract_variables_from_string(
                            str(value),
                            f'job_{job_name}_{setting}',
                            source_file,
                            local_vars
                        ))

        return variables

    def _extract_trigger_variables(
            self,
            yaml_dict: Dict,
            source_file: str,
            local_vars: Set[str]) -> Set[WorkflowVariable]:
        """Extract variables from trigger configurations

        Args:
            yaml_dict: Parsed YAML dictionary
            source_file: Source file path/name
            local_vars: Set of local variable names

        Returns:
            Set of WorkflowVariable objects
        """
        variables = set()

        for job_name, job_config in yaml_dict.items():
            if isinstance(job_config, dict):
                if 'trigger' in job_config:
                    trigger_config = job_config['trigger']
                    if isinstance(trigger_config, dict):
                        if 'variables' in trigger_config:
                            for var_name, var_value in trigger_config['variables'].items(
                            ):
                                variables.update(
                                    self._extract_variables_from_string(
                                        str(var_value),
                                        f'job_{job_name}_trigger',
                                        source_file,
                                        local_vars))

        return variables

    def _extract_variables_from_string(
            self,
            content: str,
            context: str,
            source_file: str,
            local_vars: Set[str]) -> Set[WorkflowVariable]:
        """Extract variables from a string using regex

        Args:
            content: String to search for variables
            context: Context where the string was found
            source_file: Source file path/name
            local_vars: Set of local variable names to exclude

        Returns:
            Set of WorkflowVariable objects
        """
        variables = set()

        # Match different GitLab variable syntaxes
        patterns = [
            # Bash/Shell style
            r'\$([A-Za-z_][A-Za-z0-9_]*)',  # $VAR
            # ${VAR} or ${VAR:-default}
            r'\$\{([A-Za-z_][A-Za-z0-9_]*)(:-[^}]+)?\}',
            r'\$\{([A-Za-z_][A-Za-z0-9_]*):\+[^}]+\}',  # ${VAR:+value}
            # ${VAR:offset:length}
            r'\$\{([A-Za-z_][A-Za-z0-9_]*):[\d]+:[\d]+\}',
            r'\$\[([A-Za-z_][A-Za-z0-9_]*)\]',  # $[VAR]
            r'\$\(([A-Za-z_][A-Za-z0-9_]*)\)',  # $(VAR)

            # PowerShell style
            r'\$env:([A-Za-z_][A-Za-z0-9_]*)',  # $env:VAR
            r'\$\{env:([A-Za-z_][A-Za-z0-9_]*)\}',  # ${env:VAR}

            # Windows Batch style
            r'%([A-Za-z_][A-Za-z0-9_]*)%',  # %VAR%

            # YAML string variations
            r'"?\$\$([A-Za-z_][A-Za-z0-9_]*)"?',  # $$VAR or "$$VAR"
            r'"\$\{([A-Za-z_][A-Za-z0-9_]*)\}"',  # "${VAR}"
            r"'\$\{([A-Za-z_][A-Za-z0-9_]*)\}'",  # '${VAR}'

            # Variables in quotes
            r'"?\$([A-Za-z_][A-Za-z0-9_]*)"?',  # "$VAR"
            r"'\$([A-Za-z_][A-Za-z0-9_]*)'",  # '$VAR'

            # Escaped variables in scripts
            r'\\\$([A-Za-z_][A-Za-z0-9_]*)',  # \$VAR
            r'\\\$\{([A-Za-z_][A-Za-z0-9_]*)\}',  # \${VAR}

            # Multiple vars in one string
            # VAR1-VAR2
            r'[^$]\$([A-Za-z_][A-Za-z0-9_]*)-\$([A-Za-z_][A-Za-z0-9_]*)'

            r'<<:\s*\*([A-Za-z_][A-Za-z0-9_]*)',  # YAML alias
            r'!\s*reference\s+\[([\w\.]+),\s*([^\]]+)\]',  # Reference tag

            # Parent-child pipeline variables
            # Simplified pattern for demo
            r'trigger:.*?variables:.*?\$([A-Za-z_][A-Za-z0-9_]*)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                # Handle tuple results from regex groups
                if isinstance(match, tuple):
                    # First group is always the variable name
                    var_name = match[0]
                else:
                    var_name = match

                # Skip if it's a local or predefined variable
                if var_name in local_vars or var_name in self.PREDEFINED_VARS:
                    continue

                variables.add(WorkflowVariable(
                    name=var_name,
                    source_file=source_file,
                    context=context,
                    is_predefined=var_name in self.PREDEFINED_VARS,
                    is_local=var_name in local_vars
                ))

        return variables
