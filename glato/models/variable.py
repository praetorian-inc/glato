# glato/models/variable.py

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class CICDVariable:
    """Represents a GitLab project variable"""
    variable_type: str
    key: str
    value: str
    environment_scope: str
    description: Optional[str]
    protected: bool
    masked: bool
    hidden: bool
    raw: bool
    # Add new fields for workflow variables
    source_file: Optional[str] = None
    source_context: Optional[str] = None
    oidc_indicator: Optional[str] = None
    is_workflow_variable: bool = False
    is_group_variable: bool = False
    is_instance_variable: bool = False
    is_downstream: bool = False

    @staticmethod
    def from_api_response(
            data: dict,
            is_project=False,
            is_group=False) -> 'CICDVariable':
        """Create a CICDVariable instance from API response data"""
        return CICDVariable(
            variable_type=data['variable_type'],
            key=data['key'],
            value=data['value'],
            environment_scope=data.get('environment_scope', None),
            description=data.get('description'),
            protected=data['protected'],
            masked=data['masked'],
            hidden=data.get('hidden', None),
            raw=data['raw'],
            is_group_variable=is_group
        )

    @staticmethod
    def print_variables(variables, role, type):

        # If it's a project-level var and we are below a Dev, return bc we
        # can't access any secrets.
        if type == 'project' and role < 30:
            return

        # If it's a group-level var and we are below Owner, return bc we can't
        # access any secrets.
        if type == 'group' and role < 50:
            return

        if variables is None or len(variables) == 0:
            print("Found 0 variable(s).")
            return

        # Separate workflow variables from regular variables
        workflow_vars = [v for v in variables if v.is_workflow_variable]
        regular_vars = [v for v in variables if not v.is_workflow_variable]

        # Print regular variables
        if regular_vars:

            print(f"Found {len(regular_vars)} {type} variable(s):")

            for var in regular_vars:
                desc = f" - {var.description}" if var.description else ""
                scope = f" (scope: {
                    var.environment_scope})" if var.environment_scope != "*" else ""
                print(f"  - {var.key}{scope}{desc}")
                print(f"    Value: {var.value}")
                print(f"    Type: {var.variable_type}")

                security_attrs = []
                if var.protected:
                    security_attrs.append("protected")
                if var.masked:
                    security_attrs.append("masked")
                if var.hidden:
                    security_attrs.append("hidden")
                if security_attrs:
                    print(f"    Security: {', '.join(security_attrs)}")

        # Print workflow variables
        if workflow_vars:
            print(f"Found {len(workflow_vars)} variable(s) referenced in workflow files. These could potentially be CICD variables. If you have Developer access, you can attempt to exfiltrate CICD variables available to this project through a Poisoned Pipeline Execution (PPE) attack with the --exfil-secrets-via-ppe flag:")
            for var in workflow_vars:

                print(f"  - {var.key}")

                if var.oidc_indicator is not None:
                    print(
                        f"    Possible Indcator that Pipeline Uses " +
                        var.oidc_indicator +
                        " via OIDC Authentication")

                if var.source_file:
                    print(f"    Source File: {var.source_file}")
                if var.source_context:
                    print(f"    Context: {var.source_context}")
                if var.is_downstream:
                    print(f"    Variable Discovered in Downstream Pipeline")
                if var.description:  # Description contains template usage info
                    print(f"    {var.description}")
