# glato/models/variable.py

from dataclasses import dataclass
from typing import List, Optional
from ..gitlab.api import *


@dataclass
class User:
    """Represents a GitLab User"""
    can_reach_user_api: bool
    can_reach_token_api: bool
    userid: int
    is_admin: bool = False
    username: Optional[str] = None
    token_name: Optional[str] = None
    email: Optional[str] = None
    token_created_at: Optional[str] = None
    is_bot: Optional[bool] = None
    organization: Optional[str] = None
    can_create_group: Optional[bool] = None
    can_create_project: Optional[bool] = None
    scopes: Optional[List[str]] = None

    @staticmethod
    def setup_user_info(api) -> bool:
        """Set up user information and token scopes."""

        token_info = None
        if api.pat:
            token_info = api.get_token_info()
        user_info = api.get_user_info()

        if token_info is None and user_info is not None:

            return User(
                userid=user_info.get('id'),
                username=user_info.get('username'),
                email=user_info.get('email'),
                is_bot=user_info.get('bot', False),
                organization=user_info.get('organization'),
                can_create_group=user_info.get('can_create_group', False),
                can_create_project=user_info.get('can_create_project', False),
                is_admin=user_info.get('is_admin', False),
                can_reach_user_api=True,
                can_reach_token_api=False
            )
        elif token_info is not None and user_info is None:
            return User(
                userid=token_info.get('user_id'),
                token_name=token_info.get('name'),
                token_created_at=token_info.get('created_at'),
                scopes=sorted(token_info.get('scopes')),
                is_admin='admin_mode' in sorted(token_info.get('scopes')),
                can_reach_user_api=False,
                can_reach_token_api=True
            )

        elif token_info is not None and user_info is not None:
            return User(
                userid=token_info.get('user_id'),
                username=user_info.get('username'),
                email=user_info.get('email'),
                is_bot=user_info.get('bot', False),
                organization=user_info.get('organization'),
                can_create_group=user_info.get('can_create_group', False),
                can_create_project=user_info.get('can_create_project', False),
                is_admin=user_info.get('is_admin', False),
                token_name=token_info.get('name'),
                token_created_at=token_info.get('created_at'),
                scopes=sorted(token_info.get('scopes')),
                can_reach_user_api=True,
                can_reach_token_api=True
            )
        else:
            print("\nToken is invalid, unauthorized, or expired.")
            return None

        # User(
        #         userid = token_info['user_id']
        #         username = str
        #         token_name = Optional[str]
        #         email =
        #         token_created_at = Optional[str]
        #         is_bot =
        #         organization = Optional[str]
        #         can_create_group = bool
        #         can_create_project = bool
        #         is_admin = ptional[bool] = False
        #         scopes = Optional[List[str]]
        #         can_reach_user_api = bool
        #         can_reach_token_api = bool
        # )

        # else:
        #      self.can_reach_token_api = True

        # if user_info == None:
        #      self.can_reach_user_api = False
        # else:
        #     self.can_reach_user_api = True

        # return bool(self._user_info)

    def print_user_token_info(self):
        """Print info associated with the GitLab user and token."""
        if self.can_reach_token_api and self.can_reach_user_api:
            print("User has the privileges to query token and user information.")
        elif self.can_reach_token_api and not self.can_reach_user_api:
            print("User has the privileges to query token information but not user information, likely due to missing scopes.")
        elif self.can_reach_user_api and not self.can_reach_token_api:
            print("User has the privileges to query user information but not token information, likely due to missing scopes")

        print("\nToken/User Information:")
        print("-----------------")
        print(f"User ID: {self.userid}")
        print(f"Is Admin: {self.is_admin}")

        if self.can_reach_user_api:
            print(f"Username: {self.username}")
            print(f"Email: {self.email}")
            print(f"Bot: {self.is_bot}")
            print(f"Organization: {self.organization}")
            print(f"Can Create Group: {self.can_create_group}")
            print(f"Can Create Project: {self.can_create_project}")
        if self.can_reach_token_api:
            print(f"Token Name: {self.token_name}")
            print(f"Token Created At: {self.token_created_at}")
            if self.scopes:
                print("\nScopes:")
                for scope in sorted(self.scopes):
                    print(f"  - {scope}")
