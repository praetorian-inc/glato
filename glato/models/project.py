# glato/models/project.py

from dataclasses import dataclass, field
from typing import List, Optional
from .secure_file import SecureFile
from .variable import CICDVariable


@dataclass
class ProjectAccess:
    """Represents the access level a user has to a project"""
    access_level: int
    access_level_description: str


@dataclass
class BranchProtection:
    """Represents branch protection settings for a project"""
    protected: bool
    branch_name: str
    risks: List[str]
    default: bool = False

    def print_branch_protection(self):
        if len(self.risks) == 0:
            status = "Enabled"
        else:
            status = "Potential Risks"
        label = '[default]' if self.default else ''
        print(f"Branch Protection ({self.branch_name}){label}: {status}")
        for risk in self.risks:
            print(f" * {risk}")
        print("")


@dataclass
class Project:
    """Represents a GitLab project with relevant security information"""
    id: int
    name: str
    path_with_namespace: str
    description: Optional[str]
    web_url: str
    access: ProjectAccess
    default_branch: str
    member: bool
    variables: List[CICDVariable] = field(default_factory=list)
    secure_files: List[SecureFile] = field(default_factory=list)
    branch_protection: Optional[BranchProtection] = None
    last_activity: Optional[str] = None
    archived: bool = False
    archived_at: Optional[str] = None

    def print_project(self, args, e, runners_enum):
        archive_status = " [ARCHIVED]" if self.archived else ""
        print(f"\nProject: {self.path_with_namespace}{archive_status}")
        print(f"ID: {self.id}")
        if self.archived:
            print(f"Archive Status: Archived")
            if self.archived_at:
                print(f"Archived Date: {self.archived_at}")
        print(f"Member: {self.member}")
        print(f"Access Level: {self.access.access_level_description}")
        print(f"Default Branch: {self.default_branch}")
        if args.check_branch_protections:
            branch_protection_status = "Disabled"
            if self.branch_protection and self.branch_protection.protected:
                if len(self.branch_protection.risks) == 0:
                    branch_protection_status = "Enabled"
                else:
                    branch_protection_status = "Potential Risks"
            print(
                f"Branch Protection ({
                    self.branch_protection.branch_name}): {branch_protection_status}")
            for risk in self.branch_protection.risks:
                print(f" * {risk}")
        print(f"Web URL: {self.web_url}")
        print(f"Last Activity: {self.last_activity}")
        if args.enumerate_secrets:
            SecureFile.print_secure_files(
                self.secure_files, self.access.access_level)
            # In enumerate_projects_v2, modify the print_variables call:
            # print(f"Calling print_variables with {len(project.variables) if project.variables else 0} variables")
            CICDVariable.print_variables(
                self.variables, self.access.access_level, "project")
        if self.access.access_level >= 40 and not args.enumerate_secrets:
            print(
                "Re-run with --enumerate-secrets argument to dump project-level secrets.")
        if runners_enum and e.full_runner_enum_complete == False:
            e.fetch_project_runners(self.access.access_level, self.id)
