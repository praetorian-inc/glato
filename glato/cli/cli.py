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

# glato/cli/cli.py

import argparse
import os
from glato.enumerate import Enumerator
from glato.attack import Attacker
from glato.util.cookie_config import CookieConfig
from ..models.secure_file import SecureFile
from ..models.variable import CICDVariable


def cli(args):
    """Main CLI function with improved error handling"""
    parser = argparse.ArgumentParser(
        description='GitLab Actions Token Operator (GLATO) - A tool for GitLab Actions enumeration and testing',
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument(
        '--cookie-auth',
        action='store_true',
        help='Use cookie-based authentication from config file')

    # Connection options
    parser.add_argument(
        '-u',
        '--url',
        default='https://gitlab.com',
        help='GitLab instance URL (default: https://gitlab.com)')
    parser.add_argument(
        '-p',
        '--proxy',
        help='Proxy to use for requests (e.g., http://127.0.0.1:8080)')
    parser.add_argument('--no-verify-ssl',
                        action='store_true',
                        help='Disable SSL certificate verification')
    parser.add_argument(
        '--config',
        help='Path to cookie config file (default: glato/config/cookies.json)')
    parser.add_argument(
        '--throttle',
        help='Number of seconds to wait in between API requests. Defaults to 0.')

    # Action options
    parser.add_argument('--enumerate-token',
                        action='store_true',
                        help='Enumerate token/cookie permissions and scope')
    # requires a token with api or read api or read_user scope to enum user
    # info

    parser.add_argument(
        '--enumerate-groups',
        action='store_true',
        help='Enumerate all accessible groups and access levels')
    # requires a token with api or read api scope
    parser.add_argument(
        '--check-branch-protections',
        action='store_true',
        help='Check branch protection and merge approval settings while enumerating projects. Requires --enumerate-projects or --project-path.')
    # requires a token with api or read api scope
    parser.add_argument(
        '--self-enumeration',
        action='store_true',
        help='Enumerate all accessible projects, groups, secrets, and runners according to the user\'s access levels.')
    # requires a token with api or read api scope
    parser.add_argument(
        '--enumerate-projects',
        action='store_true',
        help='Enumerate all accessible projects according to the user\'s access levels.')
    # requires a token with api or read api scope
    parser.add_argument(
        '--enumerate-secrets',
        action='store_true',
        help='Enumerates and exfiltrates secrets for all accessible project-level, group-level, and instance-level secrets where possible according to the user\'s access levels, or targets a specific project based on parameters. Performs WF YML analysis when secret API secret exfiltration is not possible. Requires --enumerate-projects/--enumerate-groups or --project-path')
    # requires a token with api or read api scope
    parser.add_argument(
        '--enumerate-runners',
        action='store_true',
        help='Enumerate self-hosted runners and analyze workflow runner requirements for all accessible projects and groups. Gets live runner data where permissions allow (Maintainer+) and always performs workflow tag analysis (Developer+). Requires --enumerate-projects and --enumerate-groups.')
    # Archive options
    parser.add_argument(
        '--include-archived',
        action='store_true',
        help='Include archived projects in enumeration (archived projects are excluded by default)')
    parser.add_argument('--archived-only',
                        action='store_true',
                        help='Enumerate only archived projects')

    # Attacker arguments
    parser.add_argument(
        '--exfil-secrets-via-ppe',
        action='store_true',
        help='Exfiltrate secrets with a Poisoned Pipeline Execution attack against a specific project. Requires --project-path and GL PAT.')
    # requires a token with api

    parser.add_argument(
        '--branch',
        help='Set the branch name for secrets exfiltration. It is strongly recommended to use a new branch name to avoid overwriting content, unless you need to target protected branches to retrieve protected variables. Defaults to "glato-test"')
    parser.add_argument('--project-path',
                        help='Set the project path')

    args = parser.parse_args(args)

    # Handle cookie authentication
    cookies = None
    if args.cookie_auth:
        cookie_config = CookieConfig(args.config)
        if not cookie_config.cookies_exist():
            cookie_config.wait_for_cookies()
        cookies = cookie_config.get_cookies()

    token = False
    if "GL_TOKEN" not in os.environ:
        token = input(
            "No 'GL_TOKEN' environment variable set. Please enter a GitLab"
            " PAT, or press Enter to proceed using Cookie Authentication.\n"
        )
        if token == "":
            token = False
    else:
        token = os.environ["GL_TOKEN"]

    if not _validate_args(args, token):
        return 1  # Return error code

    # Initialize the enumerator with branch protection option
    e = Enumerator(
        token=token if token else None,
        cookies=cookies,
        proxy=args.proxy,
        verify_ssl=not args.no_verify_ssl,
        gitlab_url=args.url,
        config_path=args.config,
        check_branch_protection=args.check_branch_protections,
        throttle=args.throttle
    )

    # Nomatter what, we need to enumerate the token and user privs
    valid_token = e.enumerate_token()
    if not valid_token:
        return 1

    # Ensure the token has sufficient scopes to perform the desired actions
    if token and e._user_info.scopes is not None and not e.check_sufficient_token_scopes(
            args):
        return 1

    if args.exfil_secrets_via_ppe:
        # Initialize the Attacker object
        a = Attacker(
            token=token,
            cookies=cookies,
            proxy=args.proxy,
            verify_ssl=not args.no_verify_ssl,
            gitlab_url=args.url,
            config_path=args.config,
            check_branch_protection=args.check_branch_protections,
            throttle=args.throttle
        )

        a.attack_project(
            args.project_path,
            args.branch if args.branch else 'praetorian-test'
        )

        return 0

    enum_specific_runners = args.enumerate_runners

    if args.enumerate_secrets and args.project_path:
        e.enum_single_project_secrets(args.project_path)

    if (args.enumerate_secrets or args.self_enumeration) and not args.project_path:
        if e._user_info.is_admin:
            print("\nUser is GitLab Instance Administrator")
            print("Enumerating Instance-level Secrets:")
            CICDVariable.print_variables(
                e.enum_instance_secrets(), 50, "instance")
        else:
            print(
                "\nUser is not a GitLab Instance Administrator. Unable to retrieve Instance-level secrets.")

    if args.check_branch_protections and args.project_path:
        _cli_enum_branch_protections(e, args.project_path)

    if args.self_enumeration or args.enumerate_runners:
        # If we are admin, use global APIs to get instance-level secrets and
        # all runners
        if e._user_info.is_admin:
            print("\nUser is GitLab Instance Administrator")
            if e._is_gitlab_saas():
                print(
                    "Skipping global runner enumeration on GitLab SaaS to avoid thousands of shared runners.")
                print(
                    "Will focus on project/group-specific runners and workflow analysis.")
            else:
                print("Enumerating Runners Using Admin API:")
                e.fetch_runners("/runners/all")
                e.full_runner_enum_complete = True
        else:
            print("\nUser is not a GitLab Instance Administrator. Will attempt to retrieve runners via projects and groups.")
        # Enum runners during project and group enumeration if they passed in the correct flag and we have not already enumerated them as an admin.
        # On SaaS, always do project/group enumeration even for admins since we
        # skip global enumeration
        enum_specific_runners = args.enumerate_runners and (
            not e._user_info.is_admin or e._is_gitlab_saas())

    if args.self_enumeration or args.enumerate_projects:
        _cli_enum_projects(e, args, enum_specific_runners)

    if args.self_enumeration or args.enumerate_groups:
        _cli_enum_groups(e, args, enum_specific_runners)

    # Print runner enumeration summary if runners were enumerated
    if args.enumerate_runners or args.self_enumeration:
        e.print_runner_enumeration_summary()

    return 0


def _validate_args(args, token):
    """Validate command line argument combinations and dependencies.

    Args:
        args: Parsed command line arguments

    Returns:
        bool: True if validation passes, False if validation fails
    """
    # Store error messages
    errors = []

    # Check auth
    if not args.cookie_auth and not token:
        errors.append(
            "Glato requires a Personal Access Token or Session Cookies (--cookie-auth) to authenticate.")

    # Check enumerate-runners dependencies
    if args.enumerate_runners and not (
            args.enumerate_projects and args.enumerate_groups):
        errors.append(
            "--enumerate-runners requires both --enumerate-projects and --enumerate-groups")

    # Check enumerate-secrets dependencies
    if args.enumerate_secrets and not (
            args.enumerate_projects or args.enumerate_groups or
            args.project_path or args.self_enumeration):
        errors.append(
            "--enumerate-secrets requires either --enumerate-projects and/or --enumerate-groups, --project-path, or --self-enumeration")

    # Check exfil-secrets-via-ppe dependencies
    if args.exfil_secrets_via_ppe:
        if not args.project_path:
            errors.append("--exfil-secrets-via-ppe requires --project-path")
        if not token:
            errors.append("--exfil-secrets-via-ppe requires a GL PAT")

    # Check branch protection dependencies
    if args.check_branch_protections and not (
            args.enumerate_projects or args.project_path):
        errors.append(
            "--check-branch-protections requires either --enumerate-projects or --project-path")

    # Check archive option dependencies
    if (args.include_archived or args.archived_only) and not (
            args.enumerate_projects or args.self_enumeration):
        errors.append(
            "Archive flags (--include-archived, --archived-only) require --enumerate-projects or --self-enumeration")

    if args.include_archived and args.archived_only:
        errors.append(
            "--include-archived and --archived-only are mutually exclusive")

    # If there are any errors, print them and return False
    if errors:
        print("\nError: Invalid argument combination(s):")
        for error in errors:
            print(f"  - {error}")
        return False

    return True


def _cli_enum_projects(e, args, runners_enum):
    if args.archived_only:
        print("\nEnumerating Archived Projects Only Using Projects API:")
    elif args.include_archived:
        print("\nEnumerating All Projects (Including Archived) Using Projects API:")
    else:
        print("\nEnumerating Active Projects Using Projects API:")
    print("-----------------")

    try:
        found_projects = False
        archived_count = 0
        active_count = 0

        for project in e.enumerate_projects_v2(
                secrets_enum=args.enumerate_secrets,
                runners_enum=runners_enum,
                include_archived=args.include_archived,
                archived_only=args.archived_only):
            found_projects = True
            if project.archived:
                archived_count += 1
            else:
                active_count += 1

            project.print_project(args, e, runners_enum)

        if not found_projects:
            print("\nNo projects found or authentication required.")
        else:
            # Print summary
            if args.include_archived and not args.archived_only:
                print(
                    f"\nProject Summary: {active_count} active, {archived_count} archived")
            elif args.archived_only:
                print(
                    f"\nProject Summary: {archived_count} archived projects found")
            else:
                print(
                    f"\nProject Summary: {active_count} active projects found")

    except Exception as err:
        print(f"Error enumerating projects: {str(err)}")


def _cli_enum_branch_protections(e, project_path):
    # Enumerate the branch protections of the project
    print("\nEnumerating Branch Protections Using API:")
    print("-----------------")
    for branch_protection in e.enumerate_branch_protections(project_path):
        # Print each branch protection details
        branch_protection.print_branch_protection()


def _cli_enum_groups(e, args, runners_enum):

    # Enumerate Group Info
    print("\nEnumerating Groups Using Groups API:")
    print("-----------------")
    for group in e.enumerate_groups(args.enumerate_secrets):
        group.print_group(args, e, runners_enum)

    return


def _cli_exfil_project_secrets(e, project_path):
    return
