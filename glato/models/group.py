
from dataclasses import dataclass, field
from typing import Optional, List
from .variable import CICDVariable


@dataclass
class GroupAccess:
    """Represents the access level a user has to a group"""
    access_level: int
    access_level_description: str


@dataclass
class Group:
    """Represents a GitLab group with relevant information"""
    id: int
    name: str
    path: str
    full_path: str
    description: Optional[str]
    web_url: str
    shared: bool
    access: GroupAccess
    variables: List[CICDVariable] = field(default_factory=list)

    def print_group(self, args, e, runners_enum):
        print(f"\nGroup: {self.name}")
        print(f"ID: {self.id}")
        print(f"Access Level: {self.access.access_level_description}")
        if self.shared:
            print(f"  - Group Access Granted via Shared Group")
        print(f"Full Path: {self.full_path}")
        print(f"Web URL: {self.web_url}")
        print(f"Description: {self.description}")
        if args.enumerate_secrets:
            CICDVariable.print_variables(
                self.variables, self.access.access_level, "group")
        if self.access.access_level == 50 and not args.enumerate_secrets:
            print("Re-run with --enumerate-secrets argument to dump group-level secrets.")
        if runners_enum and e.full_runner_enum_complete == False:
            e.fetch_group_runners(self.access.access_level, self.id)
