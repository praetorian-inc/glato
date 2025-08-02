# Copyright 2023-2025 Praetorian Security, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import Generator, Dict, Optional, Tuple, Set, List
from ..models.group import Group, GroupAccess
from ..models.project import Project, ProjectAccess, BranchProtection
import requests
from ..gitlab.api import *
from ..gitlab.secrets import *
from ..gitlab.workflow_parser import WorkflowSecretParser, WorkflowRunnerTag
import json
from ..models.user import *
from ..models.runner import *


class Enumerator:
    """Class holding all high level logic for enumerating GitLab, whether it is
    a user's entire access, individual groups, or repositories.
    """

    def __init__(
            self,
            token: Optional[str] = None,
            cookies: Optional[Dict] = None,
            proxy: Optional[str] = None,
            verify_ssl: bool = True,
            gitlab_url: str = 'https://gitlab.com',
            config_path: Optional[str] = None,
            throttle: Optional[int] = None,
            check_branch_protection: bool = False):
        """Initialize with dependency on Api's centralized caching."""
        self.api = Api(pat=token, cookies=cookies, proxy=proxy,
                       verify_ssl=verify_ssl, gitlab_url=gitlab_url,
                       config_path=config_path, throttle=throttle)
        self.setup_complete = False
        self.scopes = []
        self._user_info = None
        self.check_branch_protection = check_branch_protection
        self.runners_list = []
        self.instance_runner_enum_complete = False
        self.full_runner_enum_complete = False

        # Unique runner tracking by level
        self.unique_runners = {
            'instance_type': {},  # runner_id -> Runner object
            'group_type': {},     # runner_id -> Runner object
            'project_type': {}    # runner_id -> Runner object
        }

        # Runner tag analysis tracking
        self.runner_tags_by_project = {}  # project_id -> set of WorkflowRunnerTag
        self.projects_analyzed = set()
        self.workflow_files_found = 0
        self.pipelines_analyzed = 0

    def _is_gitlab_saas(self) -> bool:
        """Check if the GitLab instance is SaaS (gitlab.com)"""
        if hasattr(self.api, 'gitlab_url'):
            return 'gitlab.com' in self.api.gitlab_url.lower()
        return False

    def enumerate_groups(
            self, secrets_enum=False) -> Generator[Group, None, None]:
        if not self.setup_complete:
            self._user_info = User.setup_user_info(self.api)
            self.setup_complete = True

        if not self._user_info or not self._user_info.userid:
            print("Error: Unable to retrieve user information")
            return

        processed_groups = set()  # Track processed groups to avoid duplicates

        # print("Enumerating Groups...")
        for group in self.enumerate_direct_groups(secrets_enum):
            processed_groups.add(group.id)
            yield group

            # print("Enumerating shared groups for " + group.name + "," + str(group.id))
            # Get shared groups for this group
            for shared_group in self._get_shared_groups(
                    group.id, group.access.access_level, secret_enum=secrets_enum):
                if shared_group.id in processed_groups:
                    continue
                processed_groups.add(shared_group.id)
                yield shared_group

        return

    def enum_instance_secrets(self):
        return Secrets.list_secrets_for_instance(self.api)

    def enumerate_projects_v2(self,
                              secrets_enum,
                              runners_enum,
                              include_archived=False,
                              archived_only=False) -> Generator[Project,
                                                                None,
                                                                None]:
        """Enumerate all accessible projects through using the projects API.

        Yields:
            Project: Project objects containing project information and access levels
        """
        if not self.setup_complete:
            self._user_info = User.setup_user_info(self.api)
            self.setup_complete = True

        if self._user_info is None:
            print("Error: Unable to retrieve user information")
            return

        processed_projects = set()  # Track processed project IDs to avoid duplicates

        print("\nEnumerating Projects with Owner Privileges:")
        yield from self._enum_projects_from_access_level(processed_projects, 50, secrets_enum=secrets_enum, runners_enum=runners_enum, include_archived=include_archived, archived_only=archived_only)

        print("\nEnumerating Projects with Maintainer Privileges:")
        yield from self._enum_projects_from_access_level(processed_projects, 40, secrets_enum=secrets_enum, runners_enum=runners_enum, include_archived=include_archived, archived_only=archived_only)

        print("\nEnumerating Projects with Developer Privileges:")
        yield from self._enum_projects_from_access_level(processed_projects, 30, secrets_enum=secrets_enum, runners_enum=runners_enum, include_archived=include_archived, archived_only=archived_only)

        # Most permissions in GL are very similar for project members with Guest, Planner, or Reporter access.
        # For example, even project members with "Guest Access" can read source code, but none of the above roles can write.
        # Grouping these all into one to reduce the number of API calls we need to make.
        # This code doesn't account for access levels of "No Access" or "Minimal Access". Based on brief research, these roles are insignifigant from a security perspective, as if we can view projects details, we can read code.
        # We may be able to delete this line if we determine that having
        # read-only access to a project as a non-member is basically equivalent
        # to having guest access to a project.
        print("Enumerating Projects with Access level of Guest access, Planner access, or Reporter Access")
        yield from self._enum_projects_from_access_level(processed_projects, 10, secrets_enum=secrets_enum, runners_enum=runners_enum, include_archived=include_archived, archived_only=archived_only)

        if not self._is_gitlab_saas():
            print("Enumerating Projects that User is Not A Member Of")
            # We use 0 as a dummy value here to signal that we want to enum
            # projects the user is not a member of
            yield from self._enum_projects_from_access_level(processed_projects, 0, secrets_enum=secrets_enum, runners_enum=runners_enum, include_archived=include_archived, archived_only=archived_only)
        else:
            print(
                "Skipping enumeration of non-member public projects on GitLab SaaS to avoid performance issues")

    def fetch_runners(self, endpoint, type=None):
        """Enumerate all GitLab runners accessible using the API endpoint passed in to `endpoint`.

        Args:
            api: GitLab API instance
            endpoint: The API endpoint used for enumeration (should be the instance-level, project-level, or group-level runner API endpoint)
                Instance-level: /runners/all
                Project-level: /projects/:projectId:/runners
                    params: type=project_type
                Group-level: /groups/:groupID/runners
                    params: type=group_type

        Returns:
            List[Runner]: List of Runner objects
        """
        page = 1
        params = {
            'page': page,
            'per_page': 100
        }
        if type in ['project_type', 'group_type']:
            params['type'] = type
            print(f"Enumerating runners for the current project or group...")

        elif endpoint == "/runners/all":
            print("Enumerating all runners using the Global API...")
        else:
            print(
                f"\nEnumerating instance-level runners. These are accessible to all groups & projects.")

        # print(f'{endpoint}')
        while True:
            params['page'] = page
            # Get list of runners with pagination
            # print("Calling call get")
            res = self.api._call_get(endpoint, params)

            if not res or res.status_code != 200:
                print(
                    f"Error accessing runners API: {
                        res.status_code if res else 'No response'}")
                break

            runner_list = res.json()
            if not runner_list:
                print("0 runners discovered.")
                break

            # print("Prcessing runner large list")
            # Process each runner in this page
            for runner_data in runner_list:
                try:
                    runner = Runner.setup_runner_info(self.api, runner_data)
                    self.runners_list.append(runner)

                    # Track unique runners by type to avoid double counting
                    runner_type = getattr(runner, 'runner_type', 'unknown')
                    if runner_type in self.unique_runners:
                        self.unique_runners[runner_type][runner.id] = runner

                    runner.print_runner_info()
                except Exception as e:
                    print(
                        f"Error processing runner {
                            runner_data.get('id')}: {
                            str(e)}")
                    continue

            if len(runner_list) < 100:
                break

            page += 1

        return

    def fetch_project_runners(self, access_level, project_id):
        if access_level >= 40:
            # Skip instance-level runners on SaaS (GitLab.com) to avoid
            # enumerating thousands of shared runners
            if not self._is_gitlab_saas():
                # Only fetch instance-level runners on self-hosted GitLab
                if not self.instance_runner_enum_complete:
                    self.fetch_runners(
                        f'/projects/{project_id}/runners',
                        type="instance_type")
                    self.instance_runner_enum_complete = True

            # Fetch all project-level runners associated with this project
            # (self-hosted only)
            self.fetch_runners(
                f'/projects/{project_id}/runners',
                type="project_type")
            # Also fetch group-level runners that this project can access
            self.fetch_runners(
                f'/projects/{project_id}/runners',
                type="group_type")

        # Always analyze workflow files for runner tag requirements (regardless of access level)
        # This augments live runner data with workflow analysis and is
        # especially valuable on SaaS
        if access_level >= 30:  # Developer access or higher
            self._analyze_workflow_runner_requirements(project_id)

    def _analyze_workflow_runner_requirements(self, project_id: int):
        """Analyze workflow files to extract runner tag requirements and log usage

        Args:
            project_id: Project ID to analyze
        """
        try:
            # Track this project as analyzed
            self.projects_analyzed.add(project_id)

            workflow_parser = WorkflowSecretParser(self.api)

            print(
                f"\n[*] Analyzing GitLab CI workflows for runner requirements...")

            # Try to get the main workflow file
            workflow_files = ['.gitlab-ci.yml', '.gitlab-ci.yaml']
            workflow_content = None
            used_file = None

            for workflow_file in workflow_files:
                content = workflow_parser.get_workflow_file(
                    project_id, path=workflow_file)
                if content:
                    workflow_content = content
                    used_file = workflow_file
                    break

            if not workflow_content:
                print(
                    "[!] No GitLab CI workflow file found (.gitlab-ci.yml/.gitlab-ci.yaml)")
                return

            print(f"[+] Found workflow file: {used_file}")
            # Track workflow file found
            self.workflow_files_found += 1

            # Parse the workflow YAML
            parsed_yaml = workflow_parser.parse_workflow_yaml(workflow_content)
            if not parsed_yaml:
                print("[!] Failed to parse workflow YAML")
                return

            # Extract runner tags from YAML
            runner_tags = workflow_parser.extract_runner_tags(
                parsed_yaml, used_file)

            # Store runner tags for this project
            self.runner_tags_by_project[project_id] = runner_tags

            if runner_tags:
                print(f"\n[*] Runner Tags Required by Workflow:")
                print("-" * 40)

                # Group tags by job
                tags_by_job = {}
                for tag in runner_tags:
                    if tag.job_name not in tags_by_job:
                        tags_by_job[tag.job_name] = []
                    tags_by_job[tag.job_name].append(tag)

                for job_name, job_tags in tags_by_job.items():
                    print(f"Job: {job_name}")
                    for tag in job_tags:
                        context_info = f" ({
                            tag.context})" if tag.context != "job_tags" else ""
                        required_info = "" if tag.is_required else " [conditional]"
                        print(f"  - {tag.tag}{context_info}{required_info}")
                    print()

                # Summary of unique tags
                unique_tags = set(tag.tag for tag in runner_tags)
                print(
                    f"Unique Runner Tags Required: {
                        ', '.join(
                            sorted(unique_tags))}")
            else:
                print(
                    "[!] No specific runner tags found in workflow (may use default shared runners)")

            # Analyze pipeline logs for actual runner usage
            print(f"\n[*] Analyzing recent pipeline logs for runner usage...")
            runner_log_info = workflow_parser.extract_runner_info_from_logs(
                project_id)

            # Track pipeline analysis
            self.pipelines_analyzed += runner_log_info['pipeline_count']

            if runner_log_info['pipeline_count'] > 0:
                print(
                    f"[+] Analyzed {
                        runner_log_info['jobs_analyzed']} jobs from {
                        runner_log_info['pipeline_count']} recent pipelines")

                if runner_log_info['self_hosted_runners']:
                    print(f"[+] Self-hosted runners detected:")
                    for runner in runner_log_info['self_hosted_runners']:
                        print(f"    - {runner}")

                if runner_log_info['runner_tags_used']:
                    print(f"[+] Runner tags used in execution:")
                    for tag in runner_log_info['runner_tags_used']:
                        print(f"    - {tag}")

                if runner_log_info['shared_runners_used']:
                    print(f"[+] Shared/GitLab.com runners were also used")

                # Compare requirements vs actual usage
                if runner_tags and runner_log_info['runner_tags_used']:
                    required_tags = set(tag.tag for tag in runner_tags)
                    used_tags = set(runner_log_info['runner_tags_used'])

                    if required_tags != used_tags:
                        print(f"\n[!] Tag Mismatch Analysis:")
                        missing_tags = required_tags - used_tags
                        extra_tags = used_tags - required_tags

                        if missing_tags:
                            print(
                                f"    Required but not used: {
                                    ', '.join(missing_tags)}")
                        if extra_tags:
                            print(
                                f"    Used but not required: {
                                    ', '.join(extra_tags)}")
            else:
                print("[!] No recent pipeline execution found")

        except Exception as e:
            print(
                f"[!] Error analyzing workflow runner requirements: {
                    str(e)}")

    def print_runner_enumeration_summary(self):
        """Print a comprehensive summary of runner enumeration results"""
        print("\n" + "=" * 70)
        print("🎯 RUNNER ENUMERATION SUMMARY")
        print("=" * 70)

        # Live runners summary with unique counts by level
        total_unique_runners = sum(len(runners)
                                   for runners in self.unique_runners.values())

        if total_unique_runners > 0:
            print(
                f"\n📊 Live Self-Hosted Runners Discovered: {total_unique_runners} (unique)")

            # Show breakdown by level
            level_names = {
                'instance_type': 'Instance-level',
                'group_type': 'Group-level',
                'project_type': 'Project-level'
            }

            runner_tags_from_live = set()

            for runner_type, runners in self.unique_runners.items():
                if runners:
                    level_name = level_names.get(runner_type, runner_type)
                    print(f"  • {level_name}: {len(runners)} unique runners")

                    # Collect tags from live runners at this level
                    for runner in runners.values():
                        if hasattr(runner, 'tag_list') and runner.tag_list:
                            runner_tags_from_live.update(runner.tag_list)
                elif runner_type == 'instance_type' and self._is_gitlab_saas():
                    print(
                        f"  • Instance-level: Skipped on GitLab SaaS (avoiding shared runner noise)")

            if runner_tags_from_live:
                print(
                    f"\n🏷️  Live Runner Tags: {
                        ', '.join(
                            sorted(runner_tags_from_live))}")
        else:
            print(f"\n📊 Live Self-Hosted Runners:")
            if self._is_gitlab_saas():
                print(
                    f"  • Instance-level: Skipped on GitLab SaaS (avoiding shared runner noise)")
                print(f"  • Group-level: None found or insufficient permissions")
                print(f"  • Project-level: None found or insufficient permissions")
            else:
                print(f"  • None found or insufficient permissions")

        # Workflow analysis summary
        if self.projects_analyzed:
            print(f"\n📋 Workflow Analysis:")
            print(f"  • Projects analyzed: {len(self.projects_analyzed)}")
            print(f"  • Workflow files found: {self.workflow_files_found}")
            print(f"  • Pipelines analyzed: {self.pipelines_analyzed}")

            # Aggregate all runner tags from all projects
            all_runner_tags = set()
            variable_tags = set()
            conditional_tags = set()

            for project_id, runner_tags in self.runner_tags_by_project.items():
                for tag in runner_tags:
                    all_runner_tags.add(tag.tag)
                    if tag.context == 'variable_tags':
                        variable_tags.add(tag.tag)
                    elif not tag.is_required:
                        conditional_tags.add(tag.tag)

            if all_runner_tags:
                print(
                    f"\n🏷️  Required Runner Tags ({
                        len(all_runner_tags)} unique):")
                # Group tags by type
                static_tags = all_runner_tags - variable_tags - conditional_tags

                if static_tags:
                    print(f"  • Static tags: {', '.join(sorted(static_tags))}")
                if variable_tags:
                    print(
                        f"  • Variable tags: {
                            ', '.join(
                                sorted(variable_tags))}")
                if conditional_tags:
                    print(
                        f"  • Conditional tags: {
                            ', '.join(
                                sorted(conditional_tags))}")
            else:
                print(f"  • No runner tags found in workflows")
        else:
            print(f"\n📋 Workflow Analysis: No projects analyzed")

        # Security insights
        print(f"\n🔍 Security Assessment:")

        # Use unique runner counts for accurate security assessment
        instance_count = len(self.unique_runners['instance_type'])
        group_count = len(self.unique_runners['group_type'])
        project_count = len(self.unique_runners['project_type'])

        if instance_count > 0:
            print(
                f"  • {instance_count} unique instance-level self-hosted runners accessible")
        if group_count > 0:
            print(
                f"  • {group_count} unique group-level self-hosted runners accessible")
        if project_count > 0:
            print(
                f"  • {project_count} unique project-specific self-hosted runners accessible")

        if self.runner_tags_by_project:
            projects_with_tags = len(
                [tags for tags in self.runner_tags_by_project.values() if tags])
            print(
                f"  • {projects_with_tags}/{len(self.projects_analyzed)} projects require specific runner tags")

        if self._is_gitlab_saas():
            print(
                f"  • Focus on workflow analysis - primary intelligence source on GitLab SaaS")
        else:
            print(
                f"  • Complete runner landscape analyzed - live + workflow intelligence")

        print("=" * 70)

    def fetch_group_runners(self, access_level, group_id):
        if access_level >= 40:
            # Skip instance-level runners on SaaS (GitLab.com) to avoid
            # enumerating thousands of shared runners
            if not self._is_gitlab_saas():
                # Only fetch instance-level runners on self-hosted GitLab
                if not self.instance_runner_enum_complete:
                    self.fetch_runners(
                        f'/groups/{group_id}/runners',
                        type="instance_type")
                    self.instance_runner_enum_complete = True
            # Fetch group-level runners that this group can access
            self.fetch_runners(
                f'/groups/{group_id}/runners',
                type="group_type")
        return

    def _find_protection_for_branch(self, project_id, branch_name):
        # Return None if branch protection checking is not enabled
        if not self.check_branch_protection:
            return None

        page = 1
        per_page = 100
        while True:
            params = {
                'page': page,
                'per_page': per_page
            }

            endpoint = f'/projects/{project_id}/protected_branches'
            res = self.api._call_get(endpoint, params=params)

            if not res or res.status_code != 200:
                break

            protected_branches = res.json()

            for branch_data in protected_branches:
                if branch_data['name'] != branch_name:
                    continue

                risks = self._list_potential_risks(branch_data)
                return BranchProtection(
                    protected=True,
                    branch_name=branch_name,
                    risks=risks
                )

            if len(protected_branches) < per_page:
                break
            page += 1

        return BranchProtection(
            protected=False,
            branch_name=branch_name,
            risks=["Missing branch protection"]
        )

    def _list_potential_risks(self, branch_protection_data):
        access_levels_list = [
            ('merge_access_levels', 'Merge'),
            ('push_access_levels', 'Push'),
            ('unprotect_access_levels', 'Unprotect')
        ]
        risks = []
        for access_levels, action in access_levels_list:
            if access_levels not in branch_protection_data:
                continue
            potential_risks = self._access_potential_risks(
                branch_protection_data[access_levels])
            if potential_risks:
                descriptions = ', '.join(potential_risks)
                risks.append(f"{action} access to {descriptions}")
        return risks

    def _access_potential_risks(self, access_levels):
        return [access_level['access_level_description']
                for access_level in access_levels if access_level['access_level'] == 30]

    def _get_access_levels(self, access_levels):
        if not access_levels or not isinstance(access_levels, list):
            return []

        return [ProjectAccess(
            access_level['access_level'],
            access_level['access_level_description']
        ) for access_level in access_levels]

    def _get_project(self, project_path):
        encoded_path = project_path.replace('/', '%2F').lstrip('%2F')
        # print(f'Querying the project {project_path}')
        endpoint = f'/projects/{encoded_path}'
        response = self.api._call_get(endpoint, cache_response=False)
        # print(response.text)
        if response.status_code != 200:
            return None
        return response.json()

    def enum_single_project_secrets(self, project_path):
        project_id = self._get_project(project_path)['id']
        # try to exfil through project api
        print(
            f'\nAttempting to exfiltrate CICD variables for {project_path} through project API...')
        secure_files, variables = Secrets.list_secrets_for_project(
            project_id, 50, self.api)
        if variables is None:
            print(
                "User does not have sufficient privileges to retrieve project-level variables.")
            print(
                f'Attempting to identify potential CICD variables used in CICD pipelines by parsing workflow YML for {project_path}.')
            secure_files, variables = Secrets.list_secrets_for_project(
                project_id, 30, self.api)

        if secure_files is None or len(secure_files) < 1:
            print("No secure files identified")
        else:
            SecureFile.print_secure_files(secure_files, 50)
        if len(variables) < 1:
            print("No variables identified")
        else:
            CICDVariable.print_variables(variables, 50, "project")

    def check_sufficient_token_scopes(self, args):
        if args.enumerate_groups or args.enumerate_projects or args.check_branch_protections or args.self_enumeration or args.enumerate_projects or args.enumerate_secrets or args.enumerate_runners:
            if 'api' not in self._user_info.scopes and 'read_api' not in self.scopes:
                print("Error: api or read_api scope required.")
                return False
        if args.exfil_secrets_via_ppe:
            if 'api' not in self._user_info.scopes:
                print("Error: api scope required to commit code via the API.")
                return False

        return True

    def enumerate_branch_protections(
            self, project_path) -> Generator[BranchProtection, None, None]:
        project = self._get_project(project_path)
        if not project:
            print(f"[-] Please ensure the project {project_path} exists.")
            return

        project_id, default_branch = project['id'], project['default_branch']
        page = 1
        per_page = 100
        while True:
            params = {
                'page': page,
                'per_page': per_page
            }

            endpoint = f'/projects/{project_id}/protected_branches'
            res = self.api._call_get(endpoint, params=params)

            if not res or res.status_code != 200:
                break

            protected_branches = res.json()

            for branch_data in protected_branches:
                risks = self._list_potential_risks(branch_data)
                yield BranchProtection(
                    protected=True,
                    branch_name=branch_data['name'],
                    risks=risks,
                    default=default_branch == branch_data['name']
                )

            if len(protected_branches) < per_page:
                break
            page += 1

    def _enum_projects_from_access_level(self,
                                         processed_projects,
                                         access_level,
                                         secrets_enum=False,
                                         runners_enum=False,
                                         include_archived=False,
                                         archived_only=False) -> Generator[Project,
                                                                           None,
                                                                           None]:
        page = 1
        membership = True
        if access_level == 0:
            membership = False
        while True:
            params = {
                'page': page,
                'per_page': 100,
                'membership': membership,
                'with_custom_attributes': False,
                'statistics': False,
                'with_inherited_permissions': True
            }

            # Only use simple=True if we're not dealing with archived projects
            # because the simple response doesn't include the archived field
            if not include_archived and not archived_only:
                params['simple'] = True

            # Handle archived parameter correctly:
            # - archived_only=True: Add archived=true (only archived projects)
            # - include_archived=True: Don't add archived parameter (returns both)
            # - neither flag: Add archived=false (excludes archived projects)
            if archived_only:
                params['archived'] = True
            elif not include_archived:
                params['archived'] = False
            if access_level != 0:
                params['min_access_level'] = access_level

            res = self.api._call_get('/projects', params=params)
            if not res or res.status_code != 200:
                break

            projects = res.json()
            if not projects:
                break

            for project_data in projects:
                # Check if we already processed this project

                project_id = project_data.get('id')
                if project_id in processed_projects:
                    continue

                # Enum GitLab secrets
                if secrets_enum:
                    secure_files, variables = Secrets.list_secrets_for_project(
                        project_id, access_level, self.api)
                else:
                    secure_files = None
                    variables = None

                default_branch = project_data.get('default_branch', '')

                project = Project(
                    id=project_data['id'],
                    name=project_data.get('name', ''),
                    path_with_namespace=project_data.get('path_with_namespace', ''),
                    description=project_data.get('description'),
                    web_url=project_data.get('web_url', ''),
                    member=membership,
                    variables=variables,
                    secure_files=secure_files,
                    last_activity=project_data.get('last_activity_at'),
                    archived=project_data.get('archived', False),
                    archived_at=project_data.get('archived_at'),
                    access=ProjectAccess(
                        access_level=access_level,
                        access_level_description=self._get_access_level_description(access_level)
                    ),
                    default_branch=default_branch,
                    branch_protection=self._find_protection_for_branch(project_id, default_branch)
                )
                processed_projects.add(project_id)

                yield project

            if len(projects) < 100:
                break
            page += 1

    def _get_shared_groups(self,
                           group_id: int,
                           parent_access_level: int,
                           secret_enum: False) -> Generator[Tuple[Group,
                                                                  int],
                                                            None,
                                                            None]:
        """Get all groups shared with the specified group.

        Args:
            group_id: ID of the group to query shared groups for

        Yields:
            Tuple[Group, int]: Tuple of (shared Group object, access level granted to our parent group)
        """
        page = 1
        while True:
            params = {
                'page': page,
                'per_page': 100
            }

            # First get list of shared groups
            res = self.api._call_get(
                f'/groups/{group_id}/groups/shared', params=params)

            if not res or res.status_code != 200:
                break

            try:
                shared_groups = res.json()
            except Exception as e:
                print(
                    f"Error parsing shared groups response for group {group_id}: {
                        str(e)}")
                break

            if not shared_groups:
                break

            for shared_group_data in shared_groups:
                shared_group_id = shared_group_data['id']

                # Get full group details to find access level granted to our
                # parent group
                shared_group_details = self._get_group_details(shared_group_id)
                # print("Identified shared group with ID of " + str(shared_group_id))
                if not shared_group_details:
                    print("Can't get group details, this may be a bug")
                    continue

                # Find the sharing entry for our parent group
                granted_access_level = None
                for share in shared_group_details.get(
                        'shared_with_groups', []):
                    if share.get('group_id') == group_id:
                        granted_access_level = share.get('group_access_level')
                        # print("Access level assigned to group " + str(shared_group_id) + "is " + str(granted_access_level))

                        break

                if granted_access_level is None:
                    print(
                        "Can't identify shared group granted access level, this may be a bug")
                    continue  # Skip if we can't determine access level

                # Calculate effective access level as minimum of:
                # 1. Our access level to the parent group (group.access.access_level)
                # 2. Access level granted to parent group by shared group
                # (granted_access_level)
                effective_access = min(
                    parent_access_level, granted_access_level)
                if effective_access == 50 and secret_enum:
                    variables = Secrets.list_secrets_for_group(
                        group_id, self.api)
                else:
                    variables = None
                group = Group(
                    id=shared_group_id,
                    name=shared_group_data.get('name', ''),
                    path=shared_group_data.get('path', ''),
                    full_path=shared_group_data.get('full_path', ''),
                    description=shared_group_data.get('description'),
                    web_url=shared_group_data.get('web_url', ''),
                    shared=True,
                    variables=variables,
                    access=GroupAccess(
                        access_level=effective_access,
                        access_level_description=self._get_access_level_description(effective_access)
                    )
                )

                yield group

            if len(shared_groups) < 100:
                break

            page += 1

    def _get_group_details(self, group_id: int) -> Optional[Dict]:
        """Get detailed information about a group.

        Args:
            group_id: ID of the group to query

        Returns:
            Dict containing group details if successful, None otherwise
        """
        res = self.api._call_get(f'/groups/{group_id}')

        if res and res.status_code == 200:
            try:
                return res.json()
            except Exception as e:
                print(
                    f"Error parsing group details response for group {group_id}: {
                        str(e)}")
        return None

    def enumerate_token(self) -> bool:
        """Enumerate the GitLab token."""
        if not self.setup_complete:
            self._user_info = User.setup_user_info(self.api)
            if self._user_info is None:
                return False
            self.setup_complete = True

        self._user_info.print_user_token_info()
        return True

    def enumerate_direct_groups(
            self, secrets_enum=False) -> Generator[Group, None, None]:
        """Enumerate all accessible groups and their access levels.

        Yields:
            Group: Group objects containing group information and access levels
        """

        user_id = self._user_info.userid
        page = 1

        while True:
            groups = self.get_groups(page=page)

            if not groups:
                break

            for group_data in groups:
                group_id = group_data.get('id')
                if not group_id:
                    continue

                # Query member access level for this group
                member_info = self._get_group_member_access(group_id, user_id)

                if not member_info:
                    continue

                access_level = member_info.get('access_level', 10)
                access_description = self._get_access_level_description(
                    access_level)

                access = GroupAccess(
                    access_level=access_level,
                    access_level_description=access_description
                )

                if access_level == 50 and secrets_enum:
                    variables = Secrets.list_secrets_for_group(
                        group_id, self.api)
                else:
                    variables = None

                group = Group(
                    id=group_id,
                    name=group_data.get('name', ''),
                    path=group_data.get('path', ''),
                    full_path=group_data.get('full_path', ''),
                    description=group_data.get('description'),
                    shared=False,
                    variables=variables,
                    web_url=group_data.get('web_url', ''),
                    access=access
                )

                yield group

            if len(groups) < 100:
                break

            page += 1

    def _get_group_member_access(
            self,
            group_id: int,
            user_id: int) -> Optional[Dict]:
        """Get member access level for a specific group.

        Args:
            group_id: ID of the group to query
            user_id: ID of the user to check

        Returns:
            Dict containing member information if successful, None otherwise
        """
        res = self.api._call_get(f'/groups/{group_id}/members/{user_id}')

        if res and res.status_code == 200:
            try:
                return res.json()
            except Exception as e:
                print(
                    f"Error parsing member response for group {group_id}: {
                        str(e)}")
                return None
        return None

    def _get_access_level_description(self, access_level: int) -> str:
        """Convert numeric access level to human-readable description.

        Args:
            access_level: Numeric access level from API

        Returns:
            String description of access level
        """
        access_map = {
            50: 'Owner',
            40: 'Maintainer',
            30: 'Developer',
            20: 'Reporter',
            10: 'Guest, Planner, or Reporter (most likely read-only access).',
            0: 'Read Access'
        }

        return access_map.get(access_level, 'Unknown')

    def get_groups(self, page: int = 1,
                   per_page: int = 100) -> Optional[List[Dict]]:
        """Get all groups accessible to the authenticated user with membership info.

        Args:
            page: Page number for pagination
            per_page: Number of items per page

        Returns:
            List of group dictionaries if successful, None otherwise
        """
        params = {
            'page': page,
            'per_page': per_page,
            'min_access_level': 10,  # Guest access and above
            'with_custom_attributes': False,
            'include_parent_descendants': True,
            'top_level_only': False
        }
        res = self.api._call_get('/groups', params=params)

        if res and res.status_code == 200:
            return res.json()
        return None
