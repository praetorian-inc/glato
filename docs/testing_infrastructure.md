# GitLab Infrastructure Setup for E2E Testing

This document covers the infrastructure setup required for comprehensive Glato E2E testing.

## 🏗️ **Infrastructure Overview**

The Glato test suite requires a GitLab environment with:
- **Users**: Test users with different permission levels (Alice, Bob, Irene, etc.)
- **Groups**: Multi-tier group hierarchy for testing access patterns
- **Projects**: Test projects with CI/CD variables and branch protections
- **Runners**: GitLab runners for pipeline execution testing (optional)

## 🚀 **Quick Setup Options**

### **Option 1: Use Existing GitLab Instance**
If you have an existing GitLab instance, you can run tests with minimal setup:

```bash
# Set environment variables for your existing instance
export SELF_HOSTED_GITLAB_URL="https://your-gitlab.com"
export SELF_HOSTED_ALICE_TOKEN="glpat-your-admin-token"
export SELF_HOSTED_BOB_TOKEN="glpat-your-read-only-token"
export SELF_HOSTED_IRENE_TOKEN="glpat-your-executive-token"

# Run tests (will use existing projects and groups)
cd e2e_test
pytest -k "selfhosted" -v
```

### **Option 2: Automated Setup with Terraform**
For comprehensive testing with full infrastructure:

```bash
# Set up complete test environment
cd terraform-self-hosted
terraform init
terraform apply

# This creates:
# - GitLab users (alice, bob, carol, dave, eve, frank, grace, henry)
# - Multi-tier group structure (acme-corporation, engineering, product, etc.)
# - Test projects with CI/CD variables and branch protections
# - GitLab runners (project, group, instance level)
# - AWS infrastructure for runners
```

## 🔧 **Manual Setup Requirements**

If setting up manually, ensure your GitLab instance has:

### **Required Users**
| User | Role | Token Scope | Purpose |
|------|------|-------------|---------|
| **Alice** | Developer/Maintainer | `api` | Full access testing |
| **Bob** | Reporter/Guest | `read_api` | Limited access testing |
| **Irene** | Owner/Admin | `api` | Executive access testing |

### **Required Groups (Recommended)**
```
acme-corporation-glato/
├── engineering-glato/
│   ├── backend-glato/
│   └── frontend-glato/
├── product-glato/
│   └── api-glato/
└── security-glato/
```

### **Required Projects (Minimum)**
- At least one project with CI/CD variables
- At least one project with branch protections
- Projects accessible by different users with different permission levels

### **Optional: GitLab Runners**
For runner testing, set up:
- Project-level runners
- Group-level runners  
- Instance-level runners

## 🔐 **Token Configuration**

### **Core Tokens (Required)**
```bash
export SELF_HOSTED_ALICE_TOKEN="glpat-alice-full-access"
export SELF_HOSTED_BOB_TOKEN="glpat-bob-read-only"
export SELF_HOSTED_IRENE_TOKEN="glpat-irene-executive"
export SELF_HOSTED_ADMIN_TOKEN="glpat-admin-fallback"
```

### **Organizational Tokens (Optional)**
```bash
export SELF_HOSTED_CAROL_TOKEN="glpat-carol-limited"
export SELF_HOSTED_DAVE_TOKEN="glpat-dave-developer"
export SELF_HOSTED_EVE_TOKEN="glpat-eve-product-manager"
export SELF_HOSTED_FRANK_TOKEN="glpat-frank-devops"
export SELF_HOSTED_GRACE_TOKEN="glpat-grace-security"
export SELF_HOSTED_HENRY_TOKEN="glpat-henry-finance"
```

### **Token Scope Requirements**
| Token Type | Required Scopes | Notes |
|------------|----------------|-------|
| **Alice (Full)** | `api` | Full API access for comprehensive testing |
| **Bob (Limited)** | `read_api` | Read-only for permission boundary testing |
| **Irene (Executive)** | `api` | Executive-level access patterns |
| **Admin (Fallback)** | `api` | Administrative access for infrastructure tests |

## 🏗️ **Terraform Infrastructure Details**

### **Prerequisites for Terraform Setup**
- GitLab CE/EE instance with admin access
- AWS account (for runner infrastructure)
- Terraform v1.0+ installed

### **Environment Variables for Terraform**
```bash
# GitLab configuration
export TF_VAR_gitlab_url="https://your-gitlab.com"
export TF_VAR_gitlab_token="your-admin-token"

# AWS configuration (for runners)
export AWS_ACCESS_KEY_ID="your-aws-access-key"
export AWS_SECRET_ACCESS_KEY="your-aws-secret-key"
export AWS_DEFAULT_REGION="us-east-1"
```

### **Terraform Setup Commands**
```bash
cd terraform-self-hosted

# Initialize Terraform
terraform init

# Review planned changes
terraform plan

# Apply configuration
terraform apply

# Verify setup
terraform output
```

### **Created Infrastructure**
The Terraform setup creates:

#### **GitLab Resources**
- **Users**: alice, bob, carol, dave, eve, frank, grace, henry, irene
- **Groups**: Multi-tier hierarchy with proper access controls
- **Projects**: Test projects with CI/CD variables and branch protections
- **Runners**: Registered GitLab runners at different levels

#### **AWS Resources**
- **EC2 Instances**: Runner instances with Docker executor
- **Security Groups**: Proper network access controls
- **IAM Roles**: Runner permissions and access policies
- **SSM Parameters**: Secure storage for runner tokens

## 🧪 **Testing Infrastructure Validation**

### **Verify Setup**
```bash
# Test token access
glato -u $SELF_HOSTED_GITLAB_URL --enumerate-token

# Test group enumeration
glato -u $SELF_HOSTED_GITLAB_URL --enumerate-groups

# Test project enumeration
glato -u $SELF_HOSTED_GITLAB_URL --enumerate-projects

# Test runner enumeration
glato -u $SELF_HOSTED_GITLAB_URL --enumerate-runners
```

### **Run Infrastructure Tests**
```bash
# Test infrastructure components
pytest test_selfhosted_token_enumeration.py -v
pytest test_selfhosted_group_secrets.py -v
pytest test_selfhosted_hierarchical_access.py -v

# Test runner infrastructure (requires AWS setup)
pytest test_selfhosted_runners.py -v
```

## 🔍 **Troubleshooting**

### **Common Issues**

#### **Token Permission Errors**
```bash
# Error: 403 Forbidden
# Solution: Verify token scopes and user permissions
glato -u $SELF_HOSTED_GITLAB_URL --enumerate-token
```

#### **Missing Groups/Projects**
```bash
# Error: No projects found
# Solution: Create test projects or use existing ones
export SELF_HOSTED_PROJECT_PATH="your-existing-project"
```

#### **Runner Registration Issues**
```bash
# Error: No runners found
# Solution: Verify runner registration and AWS infrastructure
gitlab-runner list
```

### **Validation Commands**
```bash
# Check GitLab connectivity
curl -H "Authorization: Bearer $SELF_HOSTED_ALICE_TOKEN" \
     "$SELF_HOSTED_GITLAB_URL/api/v4/user"

# Check group access
curl -H "Authorization: Bearer $SELF_HOSTED_ALICE_TOKEN" \
     "$SELF_HOSTED_GITLAB_URL/api/v4/groups"

# Check project access
curl -H "Authorization: Bearer $SELF_HOSTED_ALICE_TOKEN" \
     "$SELF_HOSTED_GITLAB_URL/api/v4/projects"
```

## 🧹 **Cleanup**

### **Terraform Cleanup**
```bash
cd terraform-self-hosted
terraform destroy
```

### **Manual Cleanup**
If you set up infrastructure manually:
1. Remove test users and their tokens
2. Delete test groups and projects
3. Unregister GitLab runners
4. Clean up AWS resources (if used)

## 📚 **Related Documentation**

- **[E2E Testing Guide](testing_e2e_guide.md)** - Complete testing documentation
- **[Quick Reference](testing_e2e_overview.md)** - Quick start commands
- **[GitLab Runners Implementation](gitlab_runners_implementation.md)** - Runner architecture details

## 🎯 **Best Practices**

1. **Use Dedicated Test Environment**: Don't run tests against production GitLab
2. **Separate Tokens**: Use different tokens for different test users
3. **Infrastructure as Code**: Use Terraform for reproducible setups
4. **Regular Cleanup**: Clean up test resources to avoid clutter
5. **Security**: Never commit tokens or credentials to version control
6. **Monitoring**: Monitor test infrastructure for performance and costs 