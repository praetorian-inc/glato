# GitLab Runners Implementation in Glato

This document describes the comprehensive GitLab runners implementation in the Glato project, featuring a three-tier runner hierarchy with proper token management and automated deployment.

## Overview

The Glato project implements a complete GitLab CI/CD infrastructure with three distinct runner levels:

1. **Instance Runner**: Global runner available to all projects in the GitLab instance
2. **Group Runner**: Scoped to the Product group and all its subgroups/projects  
3. **Project Runner**: Dedicated to the API Service project specifically

All runners are deployed as AWS EC2 instances using the "cattle-ops/gitlab-runner/aws" Terraform module (version 9.2.1) with Docker executor.

## Runner Hierarchy and Scope

### Instance Runner (`runner_docker_instance.tf`)
- **Scope**: Entire GitLab instance - can run jobs for ANY project
- **Description**: "Docker Runner for GitLab Instance - docker-runner"
- **Tags**: `["docker", "aws", "instance", "global", "docker-runner"]`
- **Runner Type**: `instance_type`
- **Shared**: `true` (available to all projects)
- **Use Case**: Global CI/CD tasks, system-wide operations

### Group Runner (`runner_docker_group.tf`)
- **Scope**: Product group and all its subgroups/projects
- **Description**: "Docker Runner for Product Group - docker-runner"
- **Tags**: `["docker", "aws", "product", "group", "docker-runner"]`
- **Runner Type**: `group_type`
- **Shared**: `false` (group-specific)
- **Use Case**: Product-wide testing, integration tests across multiple projects

### Project Runner (`runner_docker_project.tf`)
- **Scope**: API Service project only
- **Description**: "Docker Runner for API Service Project - docker-runner"
- **Tags**: `["docker", "aws", "project", "api", "docker-runner"]`
- **Runner Type**: `project_type`
- **Shared**: `false` (project-specific)
- **Use Case**: Project-specific builds, deployments, and testing

## Modern Runner Token Management

### Automated Token Generation
GitLab now uses the modern runner authentication system. Our implementation automatically creates runner tokens using the `gitlab_user_runner` resource:

```hcl
# Example: Instance runner token creation
resource "gitlab_user_runner" "instance_runner" {
  runner_type = "instance_type"
  description = "Docker Runner for GitLab Instance - ${var.environment}"
  tag_list    = ["docker", "aws", "instance", "global", var.environment]
  untagged    = true
  locked      = false
}
```

### Secure Token Storage
All runner tokens are automatically stored in AWS SSM Parameter Store:

- **Instance Runner**: `/gitlab/runner/instance/token`
- **Group Runner**: `/gitlab/runner/group/token`  
- **Project Runner**: `/gitlab/runner/project/token`

This ensures secure, encrypted storage and easy access by the runner instances.

### Token Dependency Chain
The implementation ensures proper resource creation order:
1. GitLab infrastructure (groups, projects, users)
2. GitLab runner tokens (`gitlab_user_runner`)
3. AWS SSM parameters (`aws_ssm_parameter`)
4. Runner EC2 instances (module instantiation)

## Runner Configuration Details

### Common Configuration
All runners share these settings:
- **Instance Type**: `t2.micro` (configurable via `var.runner_instance_type`)
- **Executor**: Docker
- **Default Image**: `alpine:latest`
- **Untagged Jobs**: `true` (can run jobs without specific tags)
- **EIP**: Each runner gets an Elastic IP for consistent access

### Network Configuration
- **VPC**: Uses default AWS VPC
- **Subnet**: Uses default subnet in the VPC
- **Security Groups**: Automatically created with appropriate rules
- **Private Address**: `false` (uses public addressing)

### Environment Customization
Runner descriptions include the environment suffix from `var.environment` (default: "docker-runner"), allowing multiple deployments in different environments.

## Required Environment Variables

### For Terraform Deployment
```bash
export TF_VAR_gitlab_token="glpat-your-admin-token-here"
export AWS_ACCESS_KEY_ID="your-aws-access-key"
export AWS_SECRET_ACCESS_KEY="your-aws-secret-key"
export AWS_DEFAULT_REGION="us-east-1"
```

### For E2E Testing
The e2e tests support multiple token sources (in priority order):
1. `TF_VAR_gitlab_token` (admin token - preferred)
2. `GITLAB_TOKEN` (general token)
3. Token file: `terraform-self-hosted/gitlab_tokens.env`
4. Individual user tokens (alice, bob, etc.)

## Deployment Workflow

### Initial Setup
```bash
cd terraform-self-hosted
terraform init
terraform validate
terraform plan
terraform apply
```

### Token File Generation
After `terraform apply`, the system automatically generates `gitlab_tokens.env` containing all user API tokens for testing.

### Verification
Check runner status:
```bash
# List all runners (requires admin token)
curl -H "PRIVATE-TOKEN: $TF_VAR_gitlab_token" \
  "https://your-gitlab-url/api/v4/runners/all"

# Check specific project runners
curl -H "PRIVATE-TOKEN: $TF_VAR_gitlab_token" \
  "https://your-gitlab-url/api/v4/projects/PROJECT_ID/runners"
```

## E2E Testing Integration

### Test Coverage
The e2e tests (`e2e_test/test_gitlab_runner.py`) validate:

1. **Runner Registration**: All three runners are properly registered and online
2. **Runner Configuration**: Correct tags, types, and permissions
3. **Pipeline Execution**: Ability to run actual CI/CD pipelines
4. **Token Permissions**: Proper access levels for different operations

### Test Features
- **Flexible Token Handling**: Supports file-based and environment variable tokens
- **Intelligent Runner Detection**: Uses proper descriptions and runner types
- **Permission Handling**: Gracefully handles admin vs. non-admin tokens
- **Detailed Debugging**: Comprehensive logging for troubleshooting

### Running Tests
```bash
# Run all runner tests
python -m pytest e2e_test/test_gitlab_runner.py -v

# Run specific test
python -m pytest e2e_test/test_gitlab_runner.py::TestGitLabRunner::test_instance_runner_is_registered -v -s
```

## Troubleshooting

### Common Issues

**403 Forbidden on Instance Runners**
- Cause: Token lacks admin privileges
- Solution: Ensure `TF_VAR_gitlab_token` is an admin token

**Runner Not Found**
- Cause: Description mismatch or wrong scope
- Solution: Check runner descriptions match expected patterns

**Token File Missing**
- Cause: Terraform hasn't been applied successfully
- Solution: Run `terraform apply` to generate token file

### Debug Commands
```bash
# Check current user permissions
curl -H "PRIVATE-TOKEN: $TF_VAR_gitlab_token" \
  "https://your-gitlab-url/api/v4/user"

# List runners by scope
curl -H "PRIVATE-TOKEN: $TF_VAR_gitlab_token" \
  "https://your-gitlab-url/api/v4/runners/all"

# Check runner details
curl -H "PRIVATE-TOKEN: $TF_VAR_gitlab_token" \
  "https://your-gitlab-url/api/v4/runners/RUNNER_ID"
```

## Security Considerations

### Token Management
- Admin tokens stored as environment variables (not in code)
- User tokens generated automatically and stored securely
- SSM parameters use encryption at rest
- Tokens have appropriate scopes and permissions

### Network Security
- Security groups limit access to necessary ports
- Elastic IPs provide consistent, trackable access
- VPC isolation where configured

### Access Control
- Runners scoped appropriately (instance/group/project)
- User permissions follow principle of least privilege
- Token rotation supported through Terraform re-application

## Future Enhancements

### Scalability
- Auto-scaling runner groups for high-demand periods
- Different instance types for different workload types
- Multi-region runner deployment for global teams

### Security
- Integration with AWS Secrets Manager
- Automated token rotation
- Enhanced network isolation with custom VPCs

### Functionality
- Support for additional executor types (shell, kubernetes)
- Custom Docker images for different project types
- Advanced caching strategies for faster builds

## Architecture Diagram

```
GitLab Instance
├── Instance Runner (Global)
│   └── Available to ALL projects
├── Product Group
│   ├── Group Runner (Product-wide)
│   │   └── Available to product group projects
│   └── API Group
│       └── API Service Project
│           └── Project Runner (Project-specific)
│               └── Available ONLY to API Service
```

This hierarchy ensures proper isolation while providing flexibility for different CI/CD needs across the organization.
