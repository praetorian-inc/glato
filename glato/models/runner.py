from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime


@dataclass
class Runner:
    """Represents a GitLab Runner"""
    # Fields from /api/v4/runners/all endpoint
    id: int
    description: str
    ip_address: Optional[str]
    active: bool
    paused: bool
    is_shared: bool
    runner_type: str
    name: str
    online: bool
    status: str

    # Additional fields from /api/v4/runners/:id endpoint
    tag_list: Optional[List[str]] = None
    run_untagged: Optional[bool] = None
    locked: Optional[bool] = None
    maximum_timeout: Optional[int] = None
    access_level: Optional[str] = None
    version: Optional[str] = None
    revision: Optional[str] = None
    platform: Optional[str] = None
    architecture: Optional[str] = None
    contacted_at: Optional[datetime] = None
    maintenance_note: Optional[str] = None
    projects: Optional[List[dict]] = None
    groups: Optional[List[dict]] = None

    @staticmethod
    def setup_runner_info(api, runner_basic_info: dict) -> 'Runner':
        """Set up runner information using basic info from /runners/all and detailed info from /runners/:id

        Args:
            api: GitLab API instance
            runner_basic_info: Dictionary containing basic runner info from /runners/all endpoint

        Returns:
            Runner: Populated Runner instance
        """
        # Create initial runner with basic info
        runner = Runner(
            id=runner_basic_info['id'],
            description=runner_basic_info['description'],
            ip_address=runner_basic_info.get('ip_address'),
            active=runner_basic_info['active'],
            paused=runner_basic_info['paused'],
            is_shared=runner_basic_info['is_shared'],
            runner_type=runner_basic_info['runner_type'],
            name=runner_basic_info['name'],
            online=runner_basic_info['online'],
            status=runner_basic_info['status']
        )
        # print("Setting up runner info")
        # Get detailed information
        detailed_res = api._call_get(f'/runners/{runner.id}')
        if detailed_res and detailed_res.status_code == 200:
            detailed_data = detailed_res.json()

            # Parse contacted_at if it exists
            contacted_at = None
            if 'contacted_at' in detailed_data:
                try:
                    contacted_at = datetime.fromisoformat(
                        detailed_data['contacted_at'].replace('Z', '+00:00')
                    )
                except ValueError:
                    pass

            # Update runner with detailed information
            runner.tag_list = detailed_data.get('tag_list')
            runner.run_untagged = detailed_data.get('run_untagged')
            runner.locked = detailed_data.get('locked')
            runner.maximum_timeout = detailed_data.get('maximum_timeout')
            runner.access_level = detailed_data.get('access_level')
            runner.version = detailed_data.get('version')
            runner.revision = detailed_data.get('revision')
            runner.platform = detailed_data.get('platform')
            runner.architecture = detailed_data.get('architecture')
            runner.contacted_at = contacted_at
            runner.maintenance_note = detailed_data.get('maintenance_note')
            runner.projects = detailed_data.get('projects', [])
            runner.groups = detailed_data.get('groups', [])

        return runner

    def print_runner_info(self):
        """Print information about the GitLab runner."""
        print(f"\nRunner Information:")
        print("-----------------")
        print(f"Runner ID: {self.id}")
        print(f"Description: {self.description}")
        print(f"Type: {self.runner_type}")
        print(f"Status: {self.status}")
        print(f"Active: {self.active}")
        print(f"Online: {self.online}")
        print(f"Paused: {self.paused}")
        print(f"Shared: {self.is_shared}")

        if self.name:
            print(f"Name: {self.name}")
        if self.ip_address:
            print(f"IP Address: {self.ip_address}")

        # Print detailed information if available
        if self.tag_list:
            print(f"Tags: {', '.join(self.tag_list)}")
        if self.run_untagged is not None:
            print(f"Run Untagged: {self.run_untagged}")
        if self.locked is not None:
            print(f"Locked: {self.locked}")
        if self.maximum_timeout:
            print(f"Maximum Timeout: {self.maximum_timeout}")
        if self.access_level:
            print(f"Access Level: {self.access_level}")
        if self.version:
            print(f"Version: {self.version}")
            print(f"Revision: {self.revision}")
        if self.platform:
            print(f"Platform: {self.platform} ({self.architecture})")
        if self.contacted_at:
            print(f"Last Contact: {self.contacted_at}")
        if self.maintenance_note:
            print(f"Maintenance Note: {self.maintenance_note}")

        if self.groups:
            print("Associated Groups:")
            for group in self.groups:
                print(f"  - {group['name']} (ID: {group['id']})")

        if self.projects:
            print("Associated Projects:")
            for project in self.projects:
                print(
                    f"  - {project['path_with_namespace']} (ID: {project['id']})")
