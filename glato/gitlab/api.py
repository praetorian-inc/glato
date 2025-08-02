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

import copy
import requests
import urllib3
from urllib.parse import urlparse
from ..util.cookie_config import CookieConfig
from typing import Optional, Dict, List
from bs4 import BeautifulSoup
import json
import time


class Api():
    """GitLab API client with integrated caching to reduce duplicate requests"""

    def __init__(
            self,
            pat: str = None,
            cookies: dict = None,
            proxy: str = None,
            verify_ssl: bool = True,
            gitlab_url: str = 'https://gitlab.com',
            api_version: int = 4,
            config_path: str = None,
            throttle=None):
        """Initialize the API client with caching"""
        self.verify_ssl = verify_ssl
        if not verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        self.gitlab_url = gitlab_url.rstrip('/') + f'/api/v{api_version}'

        self.cookie_config = CookieConfig(
            config_path) if cookies is None and pat is None else None
        self.cookies = cookies

        self.session = requests.Session()
        self._user_info = None
        if self.cookies is not None:
            self._load_session_cookies()
        self.throttle = throttle

        self.headers = {
            'Accept': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        self.pat = None
        if pat:
            self.headers['PRIVATE-TOKEN'] = pat
            self.pat = pat

        self.proxies = None
        if proxy:
            scheme = urlparse(proxy).scheme
            self.proxies = {scheme: proxy}

        # Initialize caches
        self._cache = {
            'responses': {},     # Cache raw successful GET responses
            'projects': {},      # Cache project metadata
            'projects_by_path': {},  # Cache project metadata by encoded path
            'files': {},        # Cache file contents
            'templates': {},     # Cache template contents
            'shared_groups': {},  # Cache shared group relationships
        }

    def _make_cache_key(self, cache_type: str, *args: any) -> str:
        """Create a consistent cache key for a given type and arguments"""
        return f"{cache_type}:" + ":".join(str(arg) for arg in args)

    def _load_session_cookies(self):
        """
        Loads the session cookies passed in the configuration file.
        """
        for domain in self.cookies.keys():
            if '<' not in self.cookies[domain]:
                for cookie in self.cookies[domain].split('; '):
                    self._load_domain_session_cookie(domain, cookie)

    def _load_domain_session_cookie(self, domain, cookie):
        """
        Load the session cookie for a specific domain.
        """
        if "=" in cookie:
            key, value = cookie.split('=', 1)
            # Remove any trailing slashes and protocol prefixes from domain
            clean_domain = domain.rstrip(
                '/').replace('https://', '').replace('http://', '')
            self.session.cookies.set(key, value, domain=clean_domain)

    def get_user_info(self) -> Optional[Dict]:
        """Get user info if user info is not already set.

        Returns:
            Dict containing user info if successful, None otherwise
        """

        res = self._call_get('/user')

        if res and res.status_code == 200:
            try:
                return res.json()
            except requests.exceptions.JSONDecodeError as e:
                print(f'Failed to parse JSON response: {str(e)}')
                return None
        else:
            return None

    def get_token_info(self) -> Optional[Dict]:
        """Get token info if user info is not already set.

        Returns:
            Dict containing user info if successful, None otherwise
        """

        res = self._call_get('/personal_access_tokens/self')

        if res and res.status_code == 200:
            try:
                return res.json()
            except requests.exceptions.JSONDecodeError as e:
                print(f'Failed to parse JSON response: {str(e)}')
                return None
        else:
            print("Cannot determine token scopes. API behavior may be undefined.")
            return None

    def get_project(self, project_id: int) -> Optional[Dict]:
        """Get cached project details or fetch if not cached"""
        cache_key = self._make_cache_key('project', project_id)

        if cache_key in self._cache['projects']:
            # print("Projects cache Hit for " + cache_key)
            return self._cache['projects'][cache_key]

        res = self._call_get(f'/projects/{project_id}')
        if res and res.status_code == 200:
            try:
                data = res.json()
                self._cache['projects'][cache_key] = data
                return data
            except Exception as e:
                print(f"Error parsing project response: {str(e)}")
        return None

    def get_project_by_encoded_path(self, encoded_path: int) -> Optional[Dict]:
        """Get cached project details by encoded path or fetch if not cached"""
        cache_key = self._make_cache_key('projects', encoded_path)

        if cache_key in self._cache['projects_by_path']:
            # print("Projects cache Hit for " + cache_key)
            return self._cache['projects_by_path'][cache_key]

        res = self._call_get(f'/projects/{encoded_path}')
        if res and res.status_code == 200:
            try:
                data = res.json()
                self._cache['projects_by_path'][cache_key] = data
                return data
            except Exception as e:
                print(f"Error parsing project response: {str(e)}")
        return None

    def get_file_content(self, project_id: int, path: str,
                         ref: str = 'main') -> Optional[str]:
        """Get cached file content or fetch if not cached"""
        cache_key = self._make_cache_key('file', project_id, path, ref)

        if cache_key in self._cache['files']:
            # print("File Cache Hit for " + cache_key)

            return self._cache['files'][cache_key]

        # URL encode the path
        encoded_path = path.replace('/', '%2F').lstrip('%2F')

        res = self._call_get(
            f'/projects/{project_id}/repository/files/{encoded_path}/raw',
            params={
                'ref': ref})

        if res and res.status_code == 200:
            content = res.text
            self._cache['files'][cache_key] = content
            return content
        return None

    def check_if_file_exists(self, project_id, path, branch_name):

        res = self._call_get(
            f'/projects/{project_id}/repository/files/{path}/raw',
            params={
                'ref': branch_name})

        if res and res.status_code == 200:
            return True
        elif res and res.status_code == 403:
            print(
                f'Potential Bug While Retrieving Pre-existing Yml for project ID: {
                    self.id} and branch {branch_name}')
            return False
        else:
            return False

    def _call_get(self, url: str, params: Optional[Dict] = None,
                  cache_response: bool = True, strip_auth: bool = False,
                  retry_count: int = 1) -> Optional[requests.Response]:
        """Make a GET request with caching"""

        # Sleep if there is a throttle
        if self.throttle:
            throttle = int(self.throttle)
            time.sleep(throttle)

        # Create cache key for this request
        cache_params = params.copy() if params else {}
        cache_key = self._make_cache_key(
            'response', url, json.dumps(
                cache_params, sort_keys=True))
        # Check cache first
        if cache_response and cache_key in self._cache['responses']:
            # print("Cache hit")
            # print(cache_key)
            return self._cache['responses'][cache_key]

        # Make the actual request
        request_url = self.gitlab_url + url
        headers = copy.deepcopy(self.headers)
        if strip_auth and 'Authorization' in headers:
            del headers['Authorization']

        # print(f"Sending GET request to {request_url} (logging does not include params)")
        try:
            resp = self.session.get(
                request_url,
                headers=headers,
                proxies=self.proxies,
                params=params,
                verify=self.verify_ssl,
                timeout=30
            )

            if resp.headers.get(
                    'Content-Type') != 'application/json' and 'text/plain' not in resp.headers.get('Content-Type', ''):
                # print(str(resp.headers.get('Content-Type')))
                print("[!] The session cookie expired. Let's try refreshing it...")
                resp = self._handle_auth_error(resp, headers)

            # Cache successful responses
            if cache_response and resp and resp.status_code == 200:
                self._cache['responses'][cache_key] = resp

            return resp

        except requests.exceptions.RequestException as e:
            print(f"Request failed: {str(e)}")
            return None

    def _call_post(self,
                   url: str,
                   json: Optional[Dict] = None,
                   strip_auth: bool = False,
                   retry_count: int = 1) -> Optional[requests.Response]:
        """Make a POST request"""

        # Sleep if there is a throttle
        if self.throttle:
            throttle = int(self.throttle)
            time.sleep(throttle)

        # Make the actual request
        request_url = self.gitlab_url + url
        headers = copy.deepcopy(self.headers)
        if strip_auth and 'Authorization' in headers:
            del headers['Authorization']

        # print(f"Sending request to {request_url} (logging does not include params)")
        try:
            resp = self.session.post(
                request_url,
                headers=headers,
                proxies=self.proxies,
                json=json,
                verify=self.verify_ssl,
                timeout=30
            )

            if resp.headers.get(
                    'Content-Type') != 'application/json' and 'text/plain' not in resp.headers.get('Content-Type', ''):
               # print(str(resp.headers.get('Content-Type')))
                print("[!] The session cookie expired. Let's try refreshing it...")
                resp = self._handle_auth_error(resp, headers)

            return resp

        except requests.exceptions.RequestException as e:
            print(f"Request failed: {str(e)}")
            return None

    def _call_delete(self, url: str, strip_auth: bool = False,
                     retry_count: int = 1) -> Optional[requests.Response]:
        """Make a DELETE request"""

        # Sleep if there is a throttle
        if self.throttle:
            throttle = int(self.throttle)
            time.sleep(throttle)

        # Make the actual request
        request_url = self.gitlab_url + url
        headers = copy.deepcopy(self.headers)
        if strip_auth and 'Authorization' in headers:
            del headers['Authorization']

        # print(f"Sending DELETE request to {request_url} (logging does not include params)")
        try:
            resp = self.session.delete(
                request_url,
                headers=headers,
                proxies=self.proxies,
                verify=self.verify_ssl,
                timeout=30
            )

            return resp

        except requests.exceptions.RequestException as e:
            print(f"Request failed: {str(e)}")
            return None

    def _handle_auth_error(
            self,
            response: requests.Response,
            headers: Optional[Dict] = None) -> requests.Response:
        """Handle authentication errors by waiting for cookie updates

        Args:
            response: Response object from request

        Returns:
            bool: True if auth error was handled, False otherwise
        """

        bs = BeautifulSoup(response.text, 'html.parser')
        form = bs.find('form')
        if form is None:
            raise Exception(
                "Please update the cookies in the config.json file")

        _input = form.find('input')

        tmp_url = form.attrs['action']
        key = _input.attrs['name']
        value = _input.attrs['value']
        # TODO: have this save the new cookies to a file
        return self.session.post(
            tmp_url,
            data={
                key: value},
            headers=headers,
            verify=self.verify_ssl,
        )
