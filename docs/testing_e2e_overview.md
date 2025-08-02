# E2E Testing Quick Reference

This document provides a quick reference for Glato's end-to-end testing capabilities. For comprehensive documentation, see [E2E Testing Guide](testing_e2e_guide.md).

## 🎯 **Quick Start**

### **GitLab SaaS Testing**
```bash
export SAAS_GITLAB_URL="https://gitlab.com"
export SAAS_ALICE_TOKEN="glpat-your-alice-token"
export SAAS_BOB_TOKEN="glpat-your-bob-token"
export SAAS_IRENE_TOKEN="glpat-your-irene-token"

cd e2e_test
pytest -k "saas" -v
```

### **Self-Hosted GitLab Testing**
```bash
export SELF_HOSTED_GITLAB_URL="https://your-gitlab.com"
export SELF_HOSTED_ALICE_TOKEN="glpat-your-alice-token"
export SELF_HOSTED_BOB_TOKEN="glpat-your-bob-token"
export SELF_HOSTED_IRENE_TOKEN="glpat-your-irene-token"

cd e2e_test
pytest -k "selfhosted" -v
```

### **Quick Run Script**

```bash
./run_e2e_tests.sh
```

## 📊 **Test Coverage Summary**

| Feature Category | GitLab SaaS | Self-Hosted |
|------------------|-------------|-------------|
| **Token Enumeration** | ✅ 6 tests | ✅ 15 tests |
| **Project Enumeration** | ✅ 9 tests | ✅ 3 tests |
| **Group Enumeration** | ✅ Included | ✅ 8 tests |
| **Secret Enumeration** | ✅ Included | ✅ 8 tests |
| **Infrastructure Validation** | ✅ 13 tests | ✅ Included |
| **PPE Testing** | ✅ 7 tests | ✅ Included |
| **Runner Testing** | ✅ 4 tests | ✅ 13 tests |
| **Hierarchical Access** | ✅ Included | ✅ 4 tests |

### **Test Results**
- **GitLab SaaS**: 46 passed, 0 failed, ~5-6 min
- **Self-Hosted**: 41 passed, 0 failed, ~3-5 min

## 🔧 **Environment Variables**

### **Required for SaaS Testing**
```bash
export SAAS_GITLAB_URL="https://gitlab.com"  # Optional - defaults to gitlab.com
export SAAS_ALICE_TOKEN="glpat-your-alice-token"    # Full API access
export SAAS_BOB_TOKEN="glpat-your-bob-token"        # Read-only access
export SAAS_IRENE_TOKEN="glpat-your-irene-token"    # Executive access
export SAAS_ADMIN_TOKEN="glpat-your-admin-token"    # Admin access
```

### **Required for Self-Hosted Testing**
```bash
export SELF_HOSTED_GITLAB_URL="https://your-gitlab.com"  # Required
export SELF_HOSTED_ALICE_TOKEN="glpat-alice-token"
export SELF_HOSTED_BOB_TOKEN="glpat-bob-token"
export SELF_HOSTED_IRENE_TOKEN="glpat-irene-token"
export SELF_HOSTED_ADMIN_TOKEN="glpat-admin-token"

# Optional: Organizational role tokens for advanced testing
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

> **⚠️ Important**: Use different tokens with different permission levels for proper permission boundary testing.

## 🚀 **Common Test Commands**

### **Run All Tests**
```bash
pytest -k "saas" -v                    # All SaaS tests
pytest -k "selfhosted" -v              # All self-hosted tests
pytest -v                              # All tests (both environments)
```

### **Run Specific Categories**
```bash
pytest test_saas_infrastructure.py -v          # Infrastructure validation
pytest test_saas_ppe.py -v                     # PPE testing
pytest test_saas_token_enumeration.py -v       # Token enumeration
pytest test_selfhosted_runners.py -v           # Runner testing
pytest test_selfhosted_group_secrets.py -v     # Group secrets
```

### **Feature-Specific Testing**
```bash
pytest -k "token" -v          # Token-related tests
pytest -k "group" -v          # Group enumeration tests
pytest -k "secret" -v         # Secret enumeration tests
pytest -k "ppe" -v            # PPE attack tests
pytest -k "runner" -v         # Runner infrastructure tests
```

## 📈 **Expected Results**

### **Successful Test Run**
```bash
# GitLab SaaS
========================= 46 passed, 0 skipped, 0 failed =========================

# Self-Hosted
========================= 41 passed, 0 skipped, 0 failed =========================
```

### **Common Skipped Tests (Acceptable)**
- Token not configured (organizational roles)
- Infrastructure dependencies missing
- Environment-specific tests
- Permission-related skips

## 🐛 **Quick Troubleshooting**

### **Environment Validation**
```bash
# Check configuration
echo "SaaS URL: ${SAAS_GITLAB_URL}"
echo "Self-hosted URL: ${SELF_HOSTED_GITLAB_URL}"
echo "Alice token: ${SAAS_ALICE_TOKEN:0:10}..."

# Quick token validation
glato -u ${SAAS_GITLAB_URL:-https://gitlab.com} --enumerate-token
glato -u ${SELF_HOSTED_GITLAB_URL} --enumerate-token
```

### **Debug Commands**
```bash
# Verbose output
pytest -v -s --gitlab-url https://gitlab.com

# Specific test with maximum verbosity
pytest test_saas_infrastructure.py::TestSaaSInfrastructure::test_required_groups_exist -v -s

# Check test discovery
pytest --collect-only -k "saas"
```

## 📚 **Documentation**

- **[Complete E2E Testing Guide](testing_e2e_guide.md)** - Comprehensive documentation
- **[Infrastructure Setup](testing_infrastructure.md)** - GitLab environment setup
- **[GitLab Runners Implementation](gitlab_runners_implementation.md)** - Runner architecture details

## 🎯 **Test File Reference**

### **GitLab SaaS Test Files**
- `test_saas_infrastructure.py` - Infrastructure validation (13 tests)
- `test_saas_ppe.py` - PPE attack testing (7 tests)
- `test_saas_project_enumeration.py` - Project enumeration (9 tests)
- `test_saas_token_enumeration.py` - Token validation (6 tests)
- `test_saas_runners.py` - Runner testing (4 tests)

### **Self-Hosted Test Files**
- `test_selfhosted_token_enumeration.py` - Token validation (15 tests)
- `test_selfhosted_runners.py` - Runner infrastructure (13 tests)
- `test_selfhosted_group_secrets.py` - Group secrets (8 tests)
- `test_selfhosted_hierarchical_access.py` - Access control (4 tests)
- `test_selfhosted_project_detection.py` - Project detection (3 tests)

---

## 📋 **Complete Test Case Documentation**

The following table documents all 82 test cases in the Glato E2E testing suite:

| # | Test Case Name | File | Environment | Hypothesis | Testing Logic | Expected Outcome |
|---|---|---|---|---|---|---|
| 1 | `test_temp` | `unit_test/test_saas_selfhosted_main.py` | Both | Entry point function handles missing arguments gracefully | Calls `main.entry()` without arguments | `SystemExit` exception raised |
| 2 | `test_required_groups_exist` | `test_saas_infrastructure.py` | SaaS | Required organizational groups exist with proper access | Run `--enumerate-groups`, check for acme-corporation-glato, engineering-glato, product-glato | String matches for group names and access levels (owner/maintainer) |
| 3 | `test_optional_security_group` | `test_saas_infrastructure.py` | SaaS | Optional security group exists with appropriate access | Check for security-glato group in enumeration output | Optional: security group with maintainer/owner access |
| 4 | `test_subgroups_exist` | `test_saas_infrastructure.py` | SaaS | Subgroups exist within correct parent hierarchy | Enumerate groups, verify web-glato under product-glato | String match for "full path: product-glato/web-glato" |
| 5 | `test_group_hierarchy_structure` | `test_saas_infrastructure.py` | SaaS | Group hierarchy is logically consistent | Parse all groups and their paths, validate parent-child relationships | All subgroups have existing parent groups |
| 6 | `test_expected_users_exist` | `test_saas_infrastructure.py` | SaaS | Required users exist with proper token configuration | Run `--enumerate-token`, check user information | String matches for username, user ID, email, api scope |
| 7 | `test_test_project_exists` | `test_saas_infrastructure.py` | SaaS | Test project exists and is accessible | Run `--enumerate-projects` with project path filter | Project found in enumeration output |
| 8 | `test_alice_maintainer_access` | `test_saas_infrastructure.py` | SaaS | Alice has maintainer-level access to groups | Token enumeration shows appropriate access levels | Access level verification in output |
| 9 | `test_bob_developer_access` | `test_saas_infrastructure.py` | SaaS | Bob has developer-level access (read-only) | Token enumeration with Bob's token | Limited scope verification (read_api) |
| 10 | `test_irene_executive_access` | `test_saas_infrastructure.py` | SaaS | Irene has executive-level access | Token enumeration shows executive permissions | Executive access level detected |
| 11 | `test_project_ci_variables_exist` | `test_saas_infrastructure.py` | SaaS | Test project has required CI/CD variables | Project enumeration includes CI variable information | CI variables found in project details |
| 12 | `test_branch_protections_exist` | `test_saas_infrastructure.py` | SaaS | Test project has branch protection rules | Project enumeration shows branch protection data | Branch protection rules detected |
| 13 | `test_environment_stability` | `test_saas_infrastructure.py` | SaaS | SaaS environment remains stable during testing | Multiple consecutive token enumerations | All requests succeed without degradation |
| 14 | `test_rate_limiting_handling` | `test_saas_infrastructure.py` | SaaS | Rate limiting is handled gracefully | Rapid successive API calls | No rate limit errors or graceful handling |

| 15 | `test_admin_token_enumeration` | `test_saas_infrastructure.py` | SaaS | Admin token provides enhanced enumeration capabilities | Use admin token for group enumeration | Enhanced access and data retrieval |
| 16 | `test_admin_project_access` | `test_saas_infrastructure.py` | SaaS | Admin token provides access to admin-level projects | Project enumeration with admin privileges | Access to administrative projects |
| 17 | `test_admin_group_enumeration` | `test_saas_infrastructure.py` | SaaS | Admin token enables comprehensive group enumeration | Group enumeration with admin token | Complete group hierarchy access |
| 18 | `test_ppe_successful_exfiltration` | `test_saas_ppe.py` | SaaS | PPE (Post-Pwn Enumeration) extracts data successfully | Run PPE with valid project, verify output files | Files created with expected content |
| 19 | `test_ppe_with_branch_parameter` | `test_saas_ppe.py` | SaaS | PPE works with specific branch targeting | Run PPE with branch parameter | Branch-specific data extraction |
| 20 | `test_ppe_error_handling_invalid_project` | `test_saas_ppe.py` | SaaS | PPE handles invalid project gracefully | Run PPE with non-existent project | Appropriate error message, no crash |
| 21 | `test_ppe_error_handling_insufficient_permissions` | `test_saas_ppe.py` | SaaS | PPE handles permission errors appropriately | Run PPE with limited-access token | Permission error detected and handled |
| 22 | `test_ppe_missing_project_path_error` | `test_saas_ppe.py` | SaaS | PPE requires project path parameter | Run PPE without project path | Error indicating missing required parameter |
| 23 | `test_ppe_cleanup_verification` | `test_saas_ppe.py` | SaaS | PPE cleanup removes temporary artifacts | Run PPE, verify cleanup of temp files | No temporary files remain after execution |
| 24 | `test_ppe_output_validation` | `test_saas_ppe.py` | SaaS | PPE output format is valid and complete | Run PPE, validate output file structure | Valid JSON/format in output files |
| 25 | `test_saas_basic_enumeration_with_timeout` | `test_saas_project_enumeration.py` | SaaS | Basic project enumeration completes within timeout | Run project enumeration with timeout | Completes successfully within time limit |
| 26 | `test_saas_performance_characteristics` | `test_saas_project_enumeration.py` | SaaS | Project enumeration has acceptable performance | Measure enumeration execution time | Response time within acceptable bounds |
| 27 | `test_saas_member_project_filtering` | `test_saas_project_enumeration.py` | SaaS | Enumeration correctly filters member projects | Run with member filter, verify results | Only member projects returned |
| 28 | `test_saas_access_level_validation` | `test_saas_project_enumeration.py` | SaaS | Access levels are correctly identified | Check access levels in project enumeration | Accurate access level reporting |
| 29 | `test_saas_limited_token_access` | `test_saas_project_enumeration.py` | SaaS | Limited tokens have restricted project access | Use Bob's read-only token | Limited project visibility |
| 30 | `test_saas_executive_token_access` | `test_saas_project_enumeration.py` | SaaS | Executive tokens have enhanced project access | Use Irene's executive token | Enhanced project visibility |
| 31 | `test_saas_branch_protection_enumeration` | `test_saas_project_enumeration.py` | SaaS | Branch protection rules are enumerated correctly | Check branch protection in projects | Branch protection data included |
| 32 | `test_saas_environment_detection` | `test_saas_project_enumeration.py` | SaaS | SaaS environment is correctly detected | Environment detection in enumeration | SaaS environment identified |
| 33 | `test_runners_are_online` | `test_saas_runners.py` | SaaS | Required GitLab runners are online and available | Check runner status via API | Runners show "online" status |
| 34 | `test_project_runner_execution` | `test_saas_runners.py` | SaaS | Project runners can execute CI/CD jobs | Create pipeline with project runner job | Pipeline succeeds, job executes |
| 35 | `test_group_runner_execution` | `test_saas_runners.py` | SaaS | Group runners can execute CI/CD jobs | Create pipeline with group runner job | Pipeline succeeds, job executes |
| 36 | `test_parallel_runner_execution` | `test_saas_runners.py` | SaaS | Multiple runners can execute parallel jobs | Create pipeline with parallel jobs | All parallel jobs execute successfully |
| 37 | `test_admin_token_enumeration` | `test_saas_token_enumeration.py` | SaaS | Admin tokens enumerate correctly | Run token enumeration with admin token | Complete token information returned |
| 38 | `test_limited_token_enumeration` | `test_saas_token_enumeration.py` | SaaS | Limited tokens enumerate correctly | Run token enumeration with Bob's token | Limited scope information returned |
| 39 | `test_executive_token_enumeration` | `test_saas_token_enumeration.py` | SaaS | Executive tokens enumerate correctly | Run token enumeration with Irene's token | Executive level information returned |
| 40 | `test_token_scope_limitations` | `test_saas_token_enumeration.py` | SaaS | Token scope limitations are properly identified | Test operations beyond token scope | Appropriate scope limitation errors |
| 41 | `test_comprehensive_token_information` | `test_saas_token_enumeration.py` | SaaS | Token enumeration returns complete information | Check all token information fields | Username, ID, email, scopes present |
| 42 | `test_rate_limiting_behavior` | `test_saas_token_enumeration.py` | SaaS | Rate limiting is handled during token operations | Multiple rapid token enumeration calls | No rate limit failures or graceful handling |
| 43 | `test_invalid_token_handling` | `test_saas_token_enumeration.py` | SaaS | Invalid tokens are handled gracefully | Use invalid/expired token | Appropriate authentication error |
| 44 | `test_token_enumeration_output_format` | `test_saas_token_enumeration.py` | SaaS | Token enumeration output format is consistent | Validate output structure and format | Consistent, readable output format |
| 45 | `test_saas_environment_detection` | `test_saas_token_enumeration.py` | SaaS | SaaS environment is detected in token enumeration | Environment detection in token info | SaaS environment correctly identified |
| 46 | `test_enumerate_groups_full_access` | `test_selfhosted_group_secrets.py` | Self-Hosted | Full access token can enumerate all groups | Run group enumeration with Alice token | Complete group listing returned |
| 47 | `test_enumerate_groups_with_limited_access` | `test_selfhosted_group_secrets.py` | Self-Hosted | Limited tokens have restricted group access | Run group enumeration with Bob token | Limited group visibility |
| 48 | `test_enumerate_secrets_with_full_access` | `test_selfhosted_group_secrets.py` | Self-Hosted | Full access enables secret enumeration | Enumerate secrets with full privileges | Secrets discovered and listed |
| 49 | `test_secret_formats_and_protection` | `test_selfhosted_group_secrets.py` | Self-Hosted | Different secret formats are handled correctly | Check various secret types and protection | Multiple secret formats detected |
| 50 | `test_limited_access_secret_enumeration` | `test_selfhosted_group_secrets.py` | Self-Hosted | Limited access restricts secret enumeration | Attempt secret enumeration with Bob token | Limited or no secret access |
| 51 | `test_departmental_secrets_access` | `test_selfhosted_group_secrets.py` | Self-Hosted | Departmental boundaries limit secret access | Check cross-department secret access | Secrets limited to appropriate departments |
| 52 | `test_self_enumeration_with_full_access` | `test_selfhosted_group_secrets.py` | Self-Hosted | Self-enumeration works with full access | Enumerate own user/group information | Complete self-information returned |
| 53 | `test_company_level_access` | `test_selfhosted_hierarchical_access.py` | Self-Hosted | Company-level access provides broad visibility | Test access at company level | Wide access across organizational units |
| 54 | `test_department_access` | `test_selfhosted_hierarchical_access.py` | Self-Hosted | Department access is limited to department scope | Test access at department level | Access limited to department resources |
| 55 | `test_team_access` | `test_selfhosted_hierarchical_access.py` | Self-Hosted | Team access is limited to team scope | Test access at team level | Access limited to team resources |
| 56 | `test_secrets_across_hierarchy` | `test_selfhosted_hierarchical_access.py` | Self-Hosted | Secrets respect hierarchical boundaries | Test secret access across hierarchy levels | Secrets accessible based on hierarchy position |
| 57 | `test_limited_developer_access` | `test_selfhosted_hierarchical_access.py` | Self-Hosted | Developers have limited hierarchical access | Test developer-level permissions | Limited access to higher-level resources |
| 58 | `test_department_isolation` | `test_selfhosted_hierarchical_access.py` | Self-Hosted | Departments are properly isolated | Test cross-department access restrictions | No unauthorized cross-department access |
| 59 | `test_branch_protection_security_analysis` | `test_selfhosted_hierarchical_access.py` | Self-Hosted | Branch protections are analyzed for security | Analyze branch protection configurations | Security analysis of protection rules |
| 60 | `test_company_wide_branch_protection_analysis` | `test_selfhosted_hierarchical_access.py` | Self-Hosted | Company-wide branch protections are consistent | Check branch protections across organization | Consistent protection policies |
| 61 | `test_security_secrets_and_branch_protection` | `test_selfhosted_hierarchical_access.py` | Self-Hosted | Security secrets and branch protections correlate | Check relationship between secrets and protections | Proper security correlation |
| 62 | `test_selfhosted_basic_enumeration` | `test_selfhosted_project_enumeration.py` | Self-Hosted | Basic project enumeration works on self-hosted | Run project enumeration | Projects successfully enumerated |
| 63 | `test_selfhosted_includes_non_member_projects` | `test_selfhosted_project_enumeration.py` | Self-Hosted | Enumeration includes projects where user is not a member | Check non-member project visibility | Non-member projects included in results |
| 64 | `test_selfhosted_environment_detection` | `test_selfhosted_project_enumeration.py` | Self-Hosted | Self-hosted environment is correctly detected | Environment detection in enumeration | Self-hosted environment identified |
| 65 | `test_selfhosted_performance_characteristics` | `test_selfhosted_project_enumeration.py` | Self-Hosted | Project enumeration has acceptable performance | Measure enumeration performance | Performance within acceptable bounds |
| 66 | `test_selfhosted_access_level_validation` | `test_selfhosted_project_enumeration.py` | Self-Hosted | Access levels are correctly reported | Validate access levels in results | Accurate access level information |
| 67 | `test_selfhosted_limited_token_access` | `test_selfhosted_project_enumeration.py` | Self-Hosted | Limited tokens have restricted access | Use limited token for enumeration | Restricted project visibility |
| 68 | `test_selfhosted_comprehensive_enumeration` | `test_selfhosted_project_enumeration.py` | Self-Hosted | Comprehensive enumeration captures all data | Full enumeration with all options | Complete project information captured |
| 69 | `test_selfhosted_branch_protection_enumeration` | `test_selfhosted_project_enumeration.py` | Self-Hosted | Branch protections are included in enumeration | Check branch protection data | Branch protection information included |
| 70 | `test_runners_are_online` | `test_selfhosted_runners.py` | Self-Hosted | Self-hosted runners are online and available | Check runner status | Runners show "online" status |
| 71 | `test_project_runner_execution` | `test_selfhosted_runners.py` | Self-Hosted | Project runners execute jobs successfully | Create and run pipeline job | Job executes successfully |
| 72 | `test_group_runner_execution` | `test_selfhosted_runners.py` | Self-Hosted | Group runners execute jobs successfully | Create and run group runner job | Job executes successfully |
| 73 | `test_parallel_runner_execution` | `test_selfhosted_runners.py` | Self-Hosted | Parallel jobs execute on multiple runners | Create parallel pipeline jobs | All parallel jobs execute successfully |
| 74 | `test_instance_runner_availability` | `test_selfhosted_runners.py` | Self-Hosted | Instance runners are available (admin required) | Check instance runner status | Instance runners available or admin access required |
| 75 | `test_admin_token_enumeration` | `test_selfhosted_token_enumeration.py` | Self-Hosted | Admin tokens enumerate correctly on self-hosted | Token enumeration with admin token | Complete token information returned |
| 76 | `test_limited_token_enumeration` | `test_selfhosted_token_enumeration.py` | Self-Hosted | Limited tokens enumerate correctly on self-hosted | Token enumeration with limited token | Limited scope information returned |
| 77 | `test_token_scope_limitations` | `test_selfhosted_token_enumeration.py` | Self-Hosted | Token scope limitations are identified | Test operations beyond token scope | Appropriate scope limitation handling |
| 78 | `test_comprehensive_token_information` | `test_selfhosted_token_enumeration.py` | Self-Hosted | Complete token information is returned | Check all token information fields | Username, ID, email, scopes present |
| 79 | `test_rate_limiting_behavior` | `test_selfhosted_token_enumeration.py` | Self-Hosted | Rate limiting is handled appropriately | Multiple rapid token operations | No rate limit failures |
| 80 | `test_invalid_token_handling` | `test_selfhosted_token_enumeration.py` | Self-Hosted | Invalid tokens are handled gracefully | Use invalid token | Appropriate authentication error |
| 81 | `test_token_enumeration_output_format` | `test_selfhosted_token_enumeration.py` | Self-Hosted | Output format is consistent | Validate output structure | Consistent, readable output format |
| 82 | `test_selfhosted_environment_behavior` | `test_selfhosted_token_enumeration.py` | Self-Hosted | Self-hosted specific behaviors work correctly | Test self-hosted specific features | Self-hosted features function properly |

### **Test Categories Summary**

- **🔧 Unit Tests**: 1 test (core functionality)
- **🏗️ Infrastructure**: 17 tests (environment setup and validation)
- **🔑 Token Enumeration**: 14 tests (authentication and authorization)
- **📂 Project Enumeration**: 16 tests (project discovery and access)
- **👥 Group/Secret Management**: 7 tests (organizational structure)
- **🏃 Runner Testing**: 9 tests (CI/CD infrastructure)
- **🔐 Hierarchical Access**: 9 tests (permission boundaries)
- **⚡ PPE (Post-Pwn Enumeration)**: 7 tests (attack simulation)
- **🔄 Performance & Reliability**: 3 tests (system stability)
