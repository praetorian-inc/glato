# glato/util/cookie_config.py

import os
import json
from typing import Dict, Optional


class CookieConfig:
    """Handles cookie configuration loading and management"""

    # DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'cookies.json')
    DEFAULT_CONFIG_PATH = "glato/config/cookies.json"

    DEFAULT_CONFIG_TEMPLATE = {
        "azure_access": "",
        "gitlab_session": ""
    }

    def __init__(self, config_path: Optional[str] = None):
        """Initialize cookie configuration handler

        Args:
            config_path (str, optional): Path to cookie config file.
                                       Defaults to glato/config/cookies.json
        """
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self._ensure_config_exists()

    def _ensure_config_exists(self) -> None:
        """Create config directory and template file if they don't exist"""
        config_dir = os.path.dirname(self.config_path)
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)

        if not os.path.exists(self.config_path):
            self._save_config(self.DEFAULT_CONFIG_TEMPLATE)

    def _save_config(self, config: dict) -> None:
        """Save configuration to file

        Args:
            config (dict): Configuration to save
        """
        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=4)

    def _load_config(self) -> dict:
        """Load configuration from file

        Returns:
            dict: Loaded configuration
        """
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON in config file {self.config_path}")
            return self.DEFAULT_CONFIG_TEMPLATE

    def get_cookies(self) -> Dict[str, str]:
        """Get cookies from config file

        Returns:
            Dict[str, str]: Cookie dictionary for requests
        """
        config = self._load_config()
        azure_key, azure_cookies = config['azure_access'].split('#', 1)
        gitlab_key, gitlab_cookies = config['gitlab_session'].split('#', 1)

        return {
            azure_key: azure_cookies,
            gitlab_key: gitlab_cookies
        }

    def cookies_exist(self) -> bool:
        """Check if cookies exist and are non-empty

        Returns:
            bool: True if all required cookies exist and are non-empty
        """
        config = self._load_config()
        return all([
            config['azure_access'],
            config['gitlab_session']
        ])

    def update_cookies(self, azure_access: str, gitlab_session: str) -> None:
        """Update cookies in config file

        Args:
            azure_access (str): Azure access cookie value
            gitlab_session (str): GitLab session cookie value
        """
        config = self._load_config()
        config.update({
            "azure_access": azure_access,
            "gitlab_session": gitlab_session
        })
        self._save_config(config)

    def wait_for_cookies(self, check_interval: int = 30) -> None:
        """Wait for user to update cookies in config file

        Args:
            check_interval (int): How often to check for cookie updates in seconds
        """
        print(
            f"\nCookies expired or missing. Please update them in: {
                self.config_path}")
        print("Format:")
        print(json.dumps(self.DEFAULT_CONFIG_TEMPLATE, indent=4))
        print("\nPress Enter after updating the cookies file to continue...")

        while True:
            input()  # Wait for user to press Enter
            if self.cookies_exist():
                print("Cookies updated successfully, resuming operation...")
                break
            print(
                "Cookies still missing or invalid. Please update the file and press Enter again...")
