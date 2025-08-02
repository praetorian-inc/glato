# Glato E2E Testing Guide

This comprehensive guide covers end-to-end testing for Glato across both GitLab SaaS and self-hosted environments.

## 🎯 **Quick Start**

### **GitLab SaaS Testing**
```bash
# Set environment variables
export SAAS_GITLAB_URL="https://gitlab.com"
export SAAS_ALICE_TOKEN="glpat-your-alice-token"
export SAAS_BOB_TOKEN="glpat-your-bob-token"
export SAAS_IRENE_TOKEN="glpat-your-irene-token"

# Run all SaaS tests
cd e2e_test
pytest -k "saas" -v
```

### **Self-Hosted GitLab Testing**
```bash
# Set environment variables
export SELF_HOSTED_GITLAB_URL="https://your-gitlab.com"
export SELF_HOSTED_ALICE_TOKEN="glpat-your-alice-token"
export SELF_HOSTED_BOB_TOKEN="glpat-your-bob-token"
export SELF_HOSTED_IRENE_TOKEN="glpat-your-irene-token"

# Run all self-hosted tests
cd e2e_test
pytest -k "selfhosted" -v
```

## 📊 **Test Coverage Summary**

| Feature Category | GitLab SaaS | Self-Hosted | Total Tests |
|------------------|-------------|-------------|-------------|
| **Token Enumeration** | ✅ 6 tests | ✅ 15 tests | 21 tests |
| **Project Enumeration** | ✅ 9 tests | ✅ 3 tests | 12 tests |
| **Group Enumeration** | ✅ Included | ✅ 8 tests | 8+ tests |
| **Secret Enumeration** | ✅ Included | ✅ 8 tests | 8+ tests |
| **Infrastructure Validation** | ✅ 13 tests | ✅ Included | 13+ tests |
| **PPE Testing** | ✅ 7 tests | ✅ Included | 7+ tests |
| **Runner Testing** | ✅ 4 tests | ✅ 13 tests | 17 tests |
| **Hierarchical Access** | ✅ Included | ✅ 4 tests | 4+ tests |
| **Archived Projects** | ✅ 8 tests | ✅ 9 tests | 17 tests |
| **Total** | **54 tests** | **50 tests** | **104 tests** |

### **Test Results**
- **GitLab SaaS**: 54 passed, 0 failed, ~5-6 min
- **Self-Hosted**: 50 passed, 0 failed, ~3-5 min

## 🔧 **Environment Setup**

### **Required Environment Variables**

#### **For GitLab SaaS Testing**
```bash
# GitLab SaaS URL (optional - defaults to gitlab.com)
export SAAS_GITLAB_URL="https://gitlab.com"

# Core test users with different permission levels
export SAAS_ALICE_TOKEN="glpat-your-alice-token"    # Full API access
export SAAS_BOB_TOKEN="glpat-your-bob-token"        # Read-only access
export SAAS_IRENE_TOKEN="glpat-your-irene-token"    # Executive access
export SAAS_ADMIN_TOKEN="glpat-your-admin-token"    # Admin access
```

#### **For Self-Hosted GitLab Testing**
```bash
# Self-hosted GitLab URL (required)
export SELF_HOSTED_GITLAB_URL="https://your-gitlab.com"

# Core test users
export SELF_HOSTED_ALICE_TOKEN="glpat-alice-token"
export SELF_HOSTED_BOB_TOKEN="glpat-bob-token"
export SELF_HOSTED_IRENE_TOKEN="glpat-irene-token"
export SELF_HOSTED_ADMIN_TOKEN="glpat-admin-token"

# Optional: Organizational role tokens for advanced testing
export SELF_HOSTED_CAROL_TOKEN="glpat-carol-token"   # Limited access
export SELF_HOSTED_DAVE_TOKEN="glpat-dave-token"     # Developer
export SELF_HOSTED_EVE_TOKEN="glpat-eve-token"       # Product manager
export SELF_HOSTED_FRANK_TOKEN="glpat-frank-token"   # DevOps engineer
export SELF_HOSTED_GRACE_TOKEN="glpat-grace-token"   # Security analyst
export SELF_HOSTED_HENRY_TOKEN="glpat-henry-token"   # Finance manager
```

### **Token Requirements**
| User | Required Scopes | Purpose |
|------|----------------|---------|
| **Alice** | `api` (full access) | PPE attacks, project creation, full enumeration |
| **Bob** | `read_api` only | Permission boundary testing (should fail gracefully) |
| **Irene** | `api` (executive level) | Executive access pattern testing |
| **Admin** | `api` (admin level) | Infrastructure validation, fallback testing |

> **⚠️ Important**: Use different tokens with different permission levels for proper permission boundary testing. Using the same token for all users will cause false test results.

### **Legacy Environment Variables (Still Supported)**
```bash
# Legacy variables that still work
export GITLAB_URL="https://your-gitlab.com"
export GITLAB_TOKEN="your-token"
export TF_VAR_gitlab_token="your-token"
export ALICE_GLATO_TOKEN="alice-token"
export BOB_GLATO_TOKEN="bob-token"
export IRENE_GLATO_TOKEN="irene-token"
```

## 🚀 **Running Tests**

### **All Tests**
```bash
# Run all SaaS tests
pytest -k "saas" -v

# Run all self-hosted tests  
pytest -k "selfhosted" -v

# Run all tests (both environments)
pytest -v
```

### **Specific Test Categories**
```bash
# Token enumeration
pytest test_saas_token_enumeration.py -v
pytest test_selfhosted_token_enumeration.py -v

# Infrastructure validation
pytest test_saas_infrastructure.py -v

# PPE (Poisoned Pipeline Execution) testing
pytest test_saas_ppe.py -v

# Project enumeration
pytest test_saas_project_enumeration.py -v
pytest test_selfhosted_project_detection.py -v

# Runner testing
pytest test_saas_runners.py -v
pytest test_selfhosted_runners.py -v

# Group and secret enumeration
pytest test_selfhosted_group_secrets.py -v

# Hierarchical access testing
pytest test_selfhosted_hierarchical_access.py -v

# Archived projects testing
pytest test_saas_archived_projects.py -v
pytest test_selfhosted_archived_projects.py -v
```

### **Feature-Specific Testing**
```bash
# Test specific features across environments
pytest -k "token" -v          # Token-related tests
pytest -k "group" -v          # Group enumeration tests
pytest -k "secret" -v         # Secret enumeration tests
pytest -k "ppe" -v            # PPE attack tests
pytest -k "runner" -v         # Runner infrastructure tests
pytest -k "branch" -v         # Branch protection tests
pytest -k "archived" -v       # Archived projects tests
```

## 🔍 **Test Details by Environment**

### **GitLab SaaS Tests (54 tests)**

#### **Infrastructure Validation (13 tests)**
- Group management and hierarchy validation
- User verification (Alice, Bob, Irene)
- Permission testing across different access levels
- Project settings validation (CI/CD variables, branch protections)
- Environment stability and rate limiting handling

#### **PPE Testing (7 tests)**
- Secret exfiltration with actual secret validation
- Permission boundary testing (Alice vs Bob access)
- Error handling for invalid projects/parameters
- Branch parameter specification testing
- Output validation and decrypted content parsing
- Pipeline lifecycle and cleanup verification

#### **Token Enumeration (6 tests)**
- Token validation and scope verification
- User information retrieval
- Permission verification
- Timeout handling (30s protection)

#### **Project Enumeration (9 tests)**
- SaaS optimization validation
- Timeout protection for large project sets
- Performance analysis and scaling limitations
- Member vs non-member project analysis
- SaaS detection and skip message validation

#### **Runner Testing (4 tests)**
- SaaS shared runner validation
- Pipeline execution testing
- Parallel execution coordination
- Runner status verification

#### **Archived Projects Testing (8 tests)**
- Default exclusion of archived projects for security
- `--include-archived` flag functionality validation
- `--archived-only` flag behavior testing
- CLI argument validation (mutually exclusive flags)
- Integration with other enumeration features
- Archive display formatting and project summaries
- Performance characteristics on SaaS environment

### **Self-Hosted Tests (50 tests)**

#### **Token Enumeration (15 tests)**
- Comprehensive token scope validation
- Rate limiting boundary testing
- Multi-user token verification
- Permission inheritance testing

#### **Runner Infrastructure (13 tests)**
- Custom runner testing and validation
- AWS integration testing
- Three-tier runner architecture (project, group, instance)
- Runner registration and execution testing

#### **Group Secrets (8 tests)**
- Group-level CI/CD variable enumeration
- Hierarchical secret inheritance
- Department-level access validation
- Secret scope and visibility testing

#### **Hierarchical Access (4 tests)**
- Group hierarchy permission validation
- Organizational role testing
- Department isolation verification
- Branch protection security analysis

#### **Project Detection (3 tests)**
- Self-hosted project access validation
- Non-SaaS behavior verification
- Public project inclusion testing

#### **Archived Projects Testing (9 tests)**
- Comprehensive archived project enumeration
- PPE attack prevention on archived projects
- Integration with secrets, branch protection, and runner enumeration
- Archive status display and detailed information
- Access level consistency validation
- Self-hosted specific features (non-member project inclusion)

## 🔐 **Permission Boundary Testing**

The test suite validates permission boundaries using different user roles:

### **Core Test Users**
| User | Token Scope | Expected Behavior | Test Purpose |
|------|-------------|-------------------|--------------|
| **Alice** | `api` (full) | ✅ Should succeed with all operations | Full access validation |
| **Bob** | `read_api` only | ⚠️ Should fail gracefully with permission errors | Limited access validation |
| **Irene** | `api` (executive) | 🔑 Different access patterns | Executive role validation |

### **Organizational Users (Self-Hosted)**
| User | Department | Role | Test Focus |
|------|------------|------|------------|
| **Carol** | General | Limited User | Basic access patterns |
| **Dave** | Engineering | Developer | Development workflow testing |
| **Eve** | Product | Product Manager | Department-level access |
| **Frank** | DevOps | DevOps Engineer | Infrastructure secrets testing |
| **Grace** | Security | Security Analyst | Security scanning, branch protection |
| **Henry** | Finance | Finance Manager | Department isolation testing |

## 📈 **Expected Results**

### **Successful Test Run**
```bash
# GitLab SaaS
========================= 54 passed, 0 skipped, 0 failed =========================

# Self-Hosted
========================= 50 passed, 0 skipped, 0 failed =========================
```

### **Common Skipped Tests (Acceptable)**
```bash
# Token not configured (organizational roles)
SKIPPED (Token SELF_HOSTED_EVE_TOKEN not found)

# Infrastructure dependencies
SKIPPED (No projects found for CI variables test)

# Environment-specific tests
SKIPPED (This test is only applicable for GitLab SaaS)

# Permission-related skips
SKIPPED (Runner enumeration failed due to insufficient permissions)
```

## 🐛 **Troubleshooting**

### **Common Issues**

#### **Environment Variables**
```bash
# Verify your configuration
echo "SaaS URL: ${SAAS_GITLAB_URL}"
echo "Self-hosted URL: ${SELF_HOSTED_GITLAB_URL}"
echo "Alice token: ${SAAS_ALICE_TOKEN:0:10}..."
echo "Bob token: ${SAAS_BOB_TOKEN:0:10}..."

# Quick token validation
glato -u ${SAAS_GITLAB_URL:-https://gitlab.com} --enumerate-token
glato -u ${SELF_HOSTED_GITLAB_URL} --enumerate-token
```

#### **Permission Errors**
- **403 Forbidden**: Check token scopes and validity
- **Token not found**: Verify environment variable names
- **Rate limiting**: Use different tokens or add delays

#### **Test Failures**
- **Timeout issues**: Expected on SaaS for large enumerations
- **Missing projects**: Ensure test projects exist or use existing ones
- **Runner failures**: Verify AWS infrastructure for self-hosted

### **Debug Commands**
```bash
# Verbose output with debug information
pytest -v -s --gitlab-url https://gitlab.com

# Run specific test with maximum verbosity
pytest test_saas_infrastructure.py::TestSaaSInfrastructure::test_required_groups_exist -v -s

# Check test discovery
pytest --collect-only -k "saas"
```

## 🏗️ **Infrastructure Setup**

### **For Self-Hosted Testing**

If you need to set up a complete test environment:

```bash
# Using Terraform (recommended)
cd terraform-self-hosted
terraform init
terraform apply

# This creates:
# - GitLab users (alice, bob, carol, etc.)
# - Multi-tier group structure  
# - Test projects with different permissions
# - GitLab runners (project, group, instance)
# - AWS infrastructure for runners
```

### **Manual Setup Requirements**
- GitLab instance with admin access
- Test users with appropriate token scopes
- Test groups and projects
- (Optional) AWS infrastructure for runner testing

## 📚 **Test File Reference**

### **GitLab SaaS Test Files**
- `test_saas_infrastructure.py` - Infrastructure validation (13 tests)
- `test_saas_ppe.py` - PPE attack testing (7 tests)
- `test_saas_project_enumeration.py` - Project enumeration (9 tests)
- `test_saas_token_enumeration.py` - Token validation (6 tests)
- `test_saas_runners.py` - Runner testing (4 tests)
- `test_saas_archived_projects.py` - Archived projects testing (8 tests)

### **Self-Hosted Test Files**
- `test_selfhosted_token_enumeration.py` - Token validation (15 tests)
- `test_selfhosted_runners.py` - Runner infrastructure (13 tests)
- `test_selfhosted_group_secrets.py` - Group secrets (8 tests)
- `test_selfhosted_hierarchical_access.py` - Access control (4 tests)
- `test_selfhosted_project_detection.py` - Project detection (3 tests)
- `test_selfhosted_archived_projects.py` - Archived projects testing (9 tests)

### **Shared Test Files**
- `conftest.py` - Test fixtures and configuration
- `test_runner_e2e_verification.py` - Cross-environment runner validation

## 🎯 **Best Practices**

1. **Use Different Tokens**: Don't use the same token for Alice, Bob, and Irene
2. **Environment Isolation**: Keep SaaS and self-hosted configurations separate
3. **Timeout Awareness**: SaaS tests include timeout protection for large datasets
4. **Permission Testing**: Validate both success and failure scenarios
5. **Infrastructure Dependencies**: Ensure required groups, projects, and users exist
6. **Rate Limiting**: Be mindful of API rate limits, especially on SaaS
7. **Security**: Never commit tokens to version control

## 📞 **Support**

For issues with the test suite:
1. Check environment variable configuration
2. Verify token permissions and scopes
3. Ensure required infrastructure exists
4. Review test output for specific error messages
5. Use debug commands for detailed troubleshooting 