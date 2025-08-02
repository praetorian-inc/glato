from .api import Api
from ..models.secure_file import SecureFile
from ..models.variable import CICDVariable
from typing import List, Optional
from .workflow_parser import *
import requests


class Secrets():

    # Template categories for GitLab
    template_categories = [
        'gitlab-ci',      # CI/CD templates
        'Security',       # Security scanning templates
        'Managed-Cluster',  # Kubernetes templates
        'Pages',         # GitLab Pages templates
        'Auto-DevOps',   # Auto DevOps templates
        'Verify',        # Testing templates
        'Deploy'         # Deployment templates
    ]

    # Lists secrets for a proejct using various methods based on our access
    # level
    def list_secrets_for_project(project_id, access_level, api):
        # print("Listing Secrets for Project...")
        # Only list secrets if we have Developer+ access
        secure_files = None
        variables = None
        if access_level == 0 or access_level == 10 or access_level == 20:
            return secure_files, variables

        # List Secure Files
        secure_files = Secrets.list_secure_project_files(project_id, api)

        # Developer access
        if access_level == 30:
            variables = Secrets.list_secrets_from_workflow(project_id, api)

        if access_level == 40 or access_level == 50:
            variables = Secrets.list_secrets_from_api(
                project_id, "project", api)

        return secure_files, variables

    def list_secrets_for_group(group_id, api):
        return Secrets.list_secrets_from_api(group_id, "group", api)

    def list_secrets_for_instance(api):
        return Secrets.list_secrets_from_api(50, "instance", api)

    @staticmethod
    def get_template_content(
            api,
            template_path: str,
            category: str = None) -> Optional[str]:
        """Get template content based on template category.

        Args:
            template_path: Template path/name
            category: Optional specific category to try

        Returns:
            Template content if found, None otherwise
        """
        if not template_path.endswith('.yml'):
            template_path += '.yml'

        # If category specified, try only that one
        if category:
            categories_to_try = [category]
        else:
            categories_to_try = Secrets.template_categories

        # Try each category
        for cat in categories_to_try:
            res = api._call_get(f'/templates/{cat}/{template_path}')
            if res and res.status_code == 200:
                try:
                    return res.json().get('content')
                except BaseException:
                    continue

        # Fallback to repository API if template not found via template API
        try:
            # Try standard template location
            encoded_path = f"lib/gitlab/ci/templates/{template_path}".replace(
                '/', '%2F')
            res = api._call_get(
                '/projects/gitlab-org%2Fgitlab/repository/files/' +
                encoded_path +
                '/raw',
                params={
                    'ref': 'master'})
            if res and res.status_code == 200:
                return res.text

            # Try alternative location if standard failed
            encoded_path = template_path.replace('/', '%2F')
            res = api._call_get(
                '/projects/gitlab-org%2Fgitlab/repository/files/' +
                encoded_path +
                '/raw',
                params={
                    'ref': 'master'})
            if res and res.status_code == 200:
                return res.text

        except Exception as e:
            print(f"Error in template fallback for {template_path}: {str(e)}")

        print(f"Template {template_path} not found")
        return None

    def list_secrets_from_workflow(
            project_id: int, api) -> Optional[List[CICDVariable]]:
        """Retrieve potential CI/CD variables from all project workflow files including templates."""
        try:
            parser = WorkflowSecretParser(api)
            variables_by_source = {}  # Track variables and where they were found
            max_depth = 10  # Prevent infinite recursion
            processed_files = set()  # Track processed files to avoid cycles

            def process_workflow_file(
                    file_path: str,
                    current_project_id: int,
                    depth: int = 0,
                    is_template: bool = False,
                    is_downstream: bool = False) -> None:
                """Recursively process a workflow file and its includes."""
                if depth >= max_depth:
                    print(f"Maximum include depth reached at {file_path}")
                    return

                # Create a unique identifier for this file
                file_key = f"{current_project_id}:{file_path}"
                if file_key in processed_files:
                    return
                processed_files.add(file_key)

                # Get and parse the workflow file
                if is_template:
                    content = Secrets.get_template_content(api, file_path)
                else:
                    # For project files, use the repository files API
                    encoded_path = file_path.replace('/', '%2F')
                    encoded_path = encoded_path.lstrip("%2F")

                    # res = api._call_get(f'/projects/{current_project_id}/repository/files/{encoded_path}/raw',
                    #                params={'ref': 'HEAD'})
                    # print("Attempting file retrieval")
                    content = api.get_file_content(
                        current_project_id, encoded_path, 'HEAD')
                    # content = res.text if res and res.status_code == 200 else None

                if not content:
                    print(
                        f"Could not retrieve content for {file_path} likely due to insufficient permissions.")
                    return

                yaml_dict = parser.parse_workflow_yaml(content)
                if not yaml_dict:
                    return

                # Extract variables from current file
                variables = parser.extract_variables(yaml_dict, file_path)
              #  print(str(file_path) + ":" + str(project_id))
               # print("Variables: " + str(variables))

                # Group variables by their name for deduplication
                for var in variables:
                    if not var.is_predefined and not var.is_local:
                        key = var.name
                        if key not in variables_by_source:
                            variables_by_source[key] = {
                                'name': key,
                                'sources': set(),
                                'template_sources': set(),
                                'is_downstream': is_downstream
                            }
                        source = f"{file_path} ({var.context})"
                        if is_template:
                            variables_by_source[key]['template_sources'].add(
                                source)
                        else:
                            variables_by_source[key]['sources'].add(source)

                # Process includes
                includes = parser.extract_includes(yaml_dict)
                for include in includes:
                    if include.type == 'local':
                        if include.path.startswith('/'):
                            # Handle absolute paths
                            include_path = include.path.lstrip('/')
                        elif ('..' in include.path or not include.path.startswith('templates/')) and not include.path.startswith('.'):
                            # Handle relative paths and non-template paths
                            current_dir = os.path.dirname(file_path)
                            include_path = os.path.normpath(
                                os.path.join(current_dir, include.path))
                        else:
                            # Handle template-style paths (like the one in
                            # Kaniko.gitlab-ci.yml)
                            include_path = include.path
                        process_workflow_file(
                            include_path,
                            current_project_id,
                            depth + 1,
                            is_template,
                            is_downstream)

                    elif include.type == 'project' and include.project:
                        Secrets.process_project_include(
                            api,
                            include,
                            current_project_id,
                            process_workflow_file,
                            depth,
                            is_template,
                            is_downstream)

                    elif include.type == 'template':
                        process_workflow_file(
                            f"templates/{include.path}", current_project_id, depth + 1, True, is_downstream)

                # Process downstream pipelines
                for job_name, job_config in yaml_dict.items():
                    if isinstance(job_config, dict):
                        # Handle trigger keyword for downstream pipelines
                        # print(str(job_config))
                        # print("Starting downstream pipeline process")
                        if 'trigger' in job_config:
                            trigger = job_config['trigger']
                            # print(str(trigger))
                            if isinstance(trigger, dict):
                                # Handle direct project trigger
                                if 'project' in trigger:
                                    target_project = trigger['project']
                                    target_file = trigger.get(
                                        'file', '.gitlab-ci.yml')
                                    # Handle both project paths and IDs
                                    if target_project.isdigit():
                                        target_id = int(target_project)
                                    else:
                                        # Encode path for API
                                        json = api.get_project_by_encoded_path(
                                            encoded_path)
                                        target_id = json['id']
                                    encoded_path = target_project.replace(
                                        '/', '%2F')

                                    # Process downstream pipeline
                                    print("Processing downstream pipeline case 1")
                                    process_workflow_file(
                                        encoded_path, target_id, depth + 1, is_template, True)

                                # Handle include-based triggers
                                elif 'include' in trigger:
                                    # print("Parsing includes")
                                    include = trigger['include']
                                    if isinstance(include, str) and 1 == 2:
                                        # Handle simple string includes
                                        # print("String")
                                        if include.startswith('local:'):
                                            target_project = include.replace(
                                                'local:', '').strip()
                                        elif include.startswith('template:'):
                                            target_project = include.replace(
                                                'template:', '').strip()
                                        elif include.startswith('project:'):
                                            target_project = include.replace(
                                                'project:', '').strip()
                                        print(
                                            "Processing downstream pipeline case 2")
                                        process_workflow_file(
                                            include_path, current_project_id, depth + 1, is_template, True)

                                    else:
                                        # print("Dict")
                                        includes = parser.extract_includes(
                                            trigger)
                                        # print(includes)
                                        for include in includes:
                                            if isinstance(
                                                    include, IncludeFile):
                                                # Handle complex includes
                                                if include.type == 'local':
                                                    if include.path.startswith(
                                                            '/'):
                                                        # Handle absolute paths
                                                        include_path = include.path.lstrip(
                                                            '/')
                                                    elif ('..' in include.path or not include.path.startswith('templates/')) and not include.path.startswith('.'):
                                                        # Handle relative paths
                                                        # and non-template
                                                        # paths
                                                        current_dir = os.path.dirname(
                                                            file_path)
                                                        include_path = os.path.normpath(
                                                            os.path.join(current_dir, include.path))
                                                    else:
                                                        # Handle template-style
                                                        # paths
                                                        include_path = include.path
                                                    print(
                                                        "Processing downstream pipeline case 3")
                                                    process_workflow_file(
                                                        include_path, current_project_id, depth + 1, is_template, True)

                                                elif include.type == 'project' and include.project:
                                                    print(
                                                        "Processing downstream pipeline case 4")
                                                    Secrets.process_project_include(
                                                        api, include, current_project_id, process_workflow_file, depth, is_template, True)

                                                elif include.type == 'template':
                                                    print(
                                                        "Processing downstream pipeline case 5")
                                                    process_workflow_file(
                                                        f"templates/{include.path}", current_project_id, depth + 1, True, True)

            # Start processing from the main gitlab-ci.yml
            process_workflow_file('.gitlab-ci.yml', project_id)

            # Convert to CICDVariable format
            project_variables = []
            for var_info in variables_by_source.values():
                description_parts = []

                if var_info['sources']:
                    description_parts.append(
                        "Found in project files:\n" +
                        "\n".join(
                            f"      - {s}" for s in sorted(
                                var_info['sources'])))

                if var_info['template_sources']:
                    description_parts.append("Required by templates:\n" + "\n".join(
                        f"      - {s}" for s in sorted(var_info['template_sources'])))

              #  print(f"Creating CICDVariable for {var_info['name']}")

                # Check for OIDC indicators
                oidc_indicator = None

                if var_info['name'] in [
                    "VAULT_ID_TOKEN",
                    "VAULT_SERVER_URL",
                    "VAULT_AUTH_ROLE",
                        "vault"]:
                    oidc_indicator = "Vault"

                if var_info['name'] in [
                    "GCP_ID_TOKEN",
                    "GCP_WORKLOAD_IDENTITY_FEDERATION_PROVIDER_ID",
                    "GCP_WORKLOAD_IDENTITY_FEDERATION_POOL_ID",
                        "gcp_secret_manager"]:
                    oidc_indicator = "Google Cloud Secrets Manager"

                if var_info['name'] in ["AZURE_JWT", "azure_key_vault"]:
                    oidc_indicator = "Azure Key Vault"

                project_variables.append(
                    CICDVariable(
                        variable_type='env_var',
                        key=var_info['name'],
                        value='',
                        environment_scope='*',
                        description="\n\n".join(description_parts),
                        protected=False,
                        masked=False,
                        hidden=False,
                        raw=True,
                        is_downstream=var_info['is_downstream'],
                        oidc_indicator=oidc_indicator,
                        source_file=list(
                            var_info['sources'])[0].split(' (')[0] if var_info['sources'] else None,
                        source_context=list(
                            var_info['sources'])[0].split(' (')[1].rstrip(')') if var_info['sources'] else None,
                        is_workflow_variable=True))
            # print(f"Returning {len(project_variables)} CICDVariable objects")

            return project_variables

        except Exception as e:
            print(
                f"Error processing workflow files for project {project_id}: {
                    str(e)}")
            return None
            # 1. Retrieve the .gitlab-ci.yml file using the API
            # 2. Parse the yml and store it in a data structure
            # 3. Extract all env variables used in the yml (make sure to account for every possible way env vars can be referenced, like $<var>, %var%, etc., for every script type supported by GL)
            # 4. Make a list of "interesting env vars". These are env vars that could be project, group, or instance level CICD vars. To do this, we can filter out vars that are not any of the default GL env vars that every pipeline has, and they are not vars that are referenced in the "variable" section of the yml (vars from the variables section are local vars and won't include CICD secrets)
            # 5. List all workflows used by the .gitlab-ci.yml through "includes", except ones that are remotely included with http/https
            #       if the include is within a `trigger` tag, then it is a downstream pipeline. call this out any time it happens, and output these vars seperately
            # 6. Repeat the interesting env vars process for any workflows included by the .gitlab-ci.yml. Recursively do this for every workflow file we encounter, up to a maximum recursion depth of 5.
            # 7. '

    def process_project_include(
            api,
            include,
            current_project_id: int,
            process_workflow_file_func,
            depth: int,
            is_template: bool,
            is_downstream: bool) -> None:
        """Process a project include by resolving the project path and processing its workflow file.

        Args:
            api: GitLab API instance
            include: The include object containing project and path info
            current_project_id: ID of the current project being processed
            process_workflow_file_func: Function to process the workflow file
            depth: Current include depth
            is_template: Whether this is being processed as a template
        """
        try:
            project_ref = include.project

            # Handle direct project ID
            if project_ref.isdigit():
                target_project_id = project_ref
                process_workflow_file_func(
                    include.path,
                    target_project_id,
                    depth + 1,
                    is_template,
                    is_downstream)
                return

            # For path-based references, we need current project context
            current_project_data = api.get_project(current_project_id)
            if not current_project_data:
                return
            current_path = current_project_data['path_with_namespace']
            current_namespace = current_project_data['namespace']['full_path']

            # Handle relative path (starting with ../)
            if project_ref.startswith('../'):
                current_parts = current_path.split('/')
                ref_parts = project_ref.split('/')

                up_levels = ref_parts.count('..')
                if up_levels >= len(current_parts):
                    print(
                        f"Invalid relative path {project_ref} - tries to go above root")
                    return

                target_project_path = '/'.join(current_parts[:-up_levels] + [
                                               p for p in ref_parts if p != '..'])

            # Handle path without slash - relative to current namespace
            elif '/' not in project_ref:
                target_project_path = f"{current_namespace}/{project_ref}"

            # Already a full path
            else:
                target_project_path = project_ref

            # Look up project by path
            encoded_path = target_project_path.replace('/', '%2F')
            # project_res = api._call_get(f'/projects/{encoded_path}')

            # if not project_res or project_res.status_code != 200:
            #     print(f"Could not find project: {target_project_path}")
            #     if project_res:
            #         print(f"API response: {project_res.status_code}")
            #     return
            json = api.get_project_by_encoded_path(encoded_path)

            target_project_id = json['id']
            process_workflow_file_func(
                include.path,
                target_project_id,
                depth + 1,
                is_template,
                is_downstream)

        except Exception as e:
            print(
                f"Error processing project include {
                    include.project}: {
                    str(e)}")

    def list_secrets_from_api(
            id: int, type, api) -> Optional[List[CICDVariable]]:
        """Retrieve variables/secrets from a project's CI/CD variables.

        Args:
            project_id: The ID of the project to query

        Returns:
            Optional[List[CICDVariable]]: List of project variables if found, None if error or no access
        """

        page = 1
        params = {
            'page': page,
            'per_page': 100
        }
        complete = False
        variables = []
        is_project = False
        is_group = False

        while not complete:
            params['page'] = page

            if type == "project":
                res = api._call_get(f'/projects/{id}/variables', params=params)
                is_project = True
            elif type == "instance":
                res = api._call_get(f'/admin/ci/variables', params=params)
            elif type == "group":
                res = api._call_get(f'/groups/{id}/variables', params=params)
                is_group = True
            else:
                print("Error: Unknown variable type: " + type)
                return None

            if res.status_code == 404:
                return None

            if res.status_code != 200:
                print(
                    f"Error accessing {type} variables for {type} {id}: {
                        res.status_code}")
                return None

            try:
                variables_data = res.json()
                new_vars = [
                    CICDVariable.from_api_response(
                        var_data,
                        is_project,
                        is_group) for var_data in variables_data]

                if len(new_vars) < 100:
                    complete = True

                variables += new_vars
                page += 1

            except requests.exceptions.JSONDecodeError as e:
                print(f"Error parsing variables response for {id}: {str(e)}")
                return None
            except Exception as e:
                print(
                    f"Unexpected error processing variables for {id}: {
                        str(e)}")
                return None

        return variables

    def list_secure_project_files(project_id, api):
        # Return the list of secure files with metadata if it exists at
        # /api/v4/projects/<projectid>/secure_files
        """Retrieve secure files for a given project.

        Args:
            project_id: The ID of the project to query

        Returns:
            Optional[List[SecureFile]]: List of secure files if found, None if error or no access
        """
        # Use the existing API instance to make the request
        # print("Listing secure files")
        res = api._call_get(f'/projects/{project_id}/secure_files')

        if not res:
            return None

        if res.status_code == 404:
            # Project doesn't have secure files feature or no access
            return None

        if res.status_code != 200:
            print(
                f"Error accessing secure files for project {project_id}: {
                    res.status_code}")
            return None

        try:
            secure_files_data = res.json()
            secure_files = [SecureFile.from_api_response(file_data)
                            for file_data in secure_files_data]

            if secure_files:
                print(
                    f"Found {
                        len(secure_files)} secure file(s) in project {project_id}:")
                for sf in secure_files:
                    print(f"  - {sf.name} (Created: {sf.created_at.date()})")
                    if sf.metadata:
                        print(f"    Metadata present - check UI for details")

            return secure_files

        except requests.exceptions.JSONDecodeError as e:
            print(
                f"Error parsing secure files response for project {project_id}: {
                    str(e)}")
            return None
        except Exception as e:
            print(
                f"Unexpected error processing secure files for project {project_id}: {
                    str(e)}")
            return None
