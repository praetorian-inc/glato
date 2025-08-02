#!/bin/bash

# Script to run end-to-end tests for Glato against GitLab environments
# Usage: ./run_e2e_tests.sh

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Function to check if environment variable is set
check_env_var() {
    local var_name="$1"
    local var_value="${!var_name}"
    if [ -z "$var_value" ]; then
        return 1
    fi
    return 0
}

# Function to validate SaaS environment variables
validate_saas_env() {
    print_info "Validating SaaS environment variables..."
    
    local missing_vars=()
    
    # Check required SaaS variables
    if ! check_env_var "SAAS_ALICE_TOKEN"; then
        missing_vars+=("SAAS_ALICE_TOKEN")
    fi
    if ! check_env_var "SAAS_BOB_TOKEN"; then
        missing_vars+=("SAAS_BOB_TOKEN")
    fi
    if ! check_env_var "SAAS_IRENE_TOKEN"; then
        missing_vars+=("SAAS_IRENE_TOKEN")
    fi
    
    # Set default SaaS URL if not provided
    if ! check_env_var "SAAS_GITLAB_URL"; then
        export SAAS_GITLAB_URL="https://gitlab.com"
        print_info "Using default SaaS URL: $SAAS_GITLAB_URL"
    else
        print_info "Using SaaS URL: $SAAS_GITLAB_URL"
    fi
    
    if [ ${#missing_vars[@]} -ne 0 ]; then
        print_error "Missing required SaaS environment variables:"
        for var in "${missing_vars[@]}"; do
            echo "  - $var"
        done
        echo ""
        echo "Please set the following environment variables:"
        echo "export SAAS_GITLAB_URL=\"https://gitlab.com\"  # Optional - defaults to gitlab.com"
        echo "export SAAS_ALICE_TOKEN=\"glpat-your-alice-token\"    # Full API access"
        echo "export SAAS_BOB_TOKEN=\"glpat-your-bob-token\"        # Read-only access"
        echo "export SAAS_IRENE_TOKEN=\"glpat-your-irene-token\"    # Executive access"
        echo ""
        return 1
    fi
    
    print_success "SaaS environment variables validated"
    return 0
}

# Function to validate Self-hosted environment variables
validate_selfhosted_env() {
    print_info "Validating Self-hosted environment variables..."
    
    local missing_vars=()
    
    # Check required Self-hosted variables
    if ! check_env_var "SELF_HOSTED_GITLAB_URL"; then
        missing_vars+=("SELF_HOSTED_GITLAB_URL")
    fi
    if ! check_env_var "SELF_HOSTED_ALICE_TOKEN"; then
        missing_vars+=("SELF_HOSTED_ALICE_TOKEN")
    fi
    if ! check_env_var "SELF_HOSTED_BOB_TOKEN"; then
        missing_vars+=("SELF_HOSTED_BOB_TOKEN")
    fi
    if ! check_env_var "SELF_HOSTED_IRENE_TOKEN"; then
        missing_vars+=("SELF_HOSTED_IRENE_TOKEN")
    fi
    
    if [ ${#missing_vars[@]} -ne 0 ]; then
        print_error "Missing required Self-hosted environment variables:"
        for var in "${missing_vars[@]}"; do
            echo "  - $var"
        done
        echo ""
        echo "Please set the following environment variables:"
        echo "export SELF_HOSTED_GITLAB_URL=\"https://your-gitlab.com\"  # Required"
        echo "export SELF_HOSTED_ALICE_TOKEN=\"glpat-your-alice-token\"   # Full API access"
        echo "export SELF_HOSTED_BOB_TOKEN=\"glpat-your-bob-token\"       # Read-only access"
        echo "export SELF_HOSTED_IRENE_TOKEN=\"glpat-your-irene-token\"   # Executive access"
        echo ""
        echo "For complete setup instructions, see: docs/testing_e2e_guide.md"
        return 1
    fi
    
    print_success "Self-hosted environment variables validated"
    print_info "Using Self-hosted URL: $SELF_HOSTED_GITLAB_URL"
    return 0
}

# Function to run SaaS tests
run_saas_tests() {
    if ! validate_saas_env; then
        return 1
    fi
    
    print_info "Running GitLab SaaS E2E tests..."
    print_info "Target: $SAAS_GITLAB_URL"
    
    cd "$(dirname "$0")"
    export PYTHONPATH="$(pwd)"
    
    pytest -k "saas" -v
    local exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        print_success "SaaS tests completed successfully"
    else
        print_error "SaaS tests failed with exit code $exit_code"
    fi
    
    return $exit_code
}

# Function to run Self-hosted tests
run_selfhosted_tests() {
    if ! validate_selfhosted_env; then
        return 1
    fi
    
    print_info "Running Self-hosted GitLab E2E tests..."
    print_info "Target: $SELF_HOSTED_GITLAB_URL"
    
    cd "$(dirname "$0")"
    export PYTHONPATH="$(pwd)"
    
    pytest -k "selfhosted" -v
    local exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        print_success "Self-hosted tests completed successfully"
    else
        print_error "Self-hosted tests failed with exit code $exit_code"
    fi
    
    return $exit_code
}

# Function to run both test types
run_both_tests() {
    local saas_valid=true
    local selfhosted_valid=true
    
    # Validate both environments
    if ! validate_saas_env; then
        saas_valid=false
        print_warning "SaaS tests will be skipped due to missing environment variables"
    fi
    
    if ! validate_selfhosted_env; then
        selfhosted_valid=false
        print_warning "Self-hosted tests will be skipped due to missing environment variables"
    fi
    
    if [ "$saas_valid" = false ] && [ "$selfhosted_valid" = false ]; then
        print_error "Cannot run tests: both SaaS and Self-hosted environment variables are missing"
        return 1
    fi
    
    cd "$(dirname "$0")"
    export PYTHONPATH="$(pwd)"
    
    # Run tests based on available environments and test file naming convention
    if [ "$saas_valid" = true ] && [ "$selfhosted_valid" = true ]; then
        print_info "Running both GitLab SaaS and Self-hosted E2E tests..."
        print_info "SaaS Target: $SAAS_GITLAB_URL"
        print_info "Self-hosted Target: $SELF_HOSTED_GITLAB_URL"
        # Run all tests with saas or selfhosted in their filename
        pytest -k "saas or selfhosted" -v
    elif [ "$saas_valid" = true ]; then
        print_info "Running GitLab SaaS E2E tests only (Self-hosted environment not configured)..."
        print_info "SaaS Target: $SAAS_GITLAB_URL"
        pytest -k "saas" -v
    elif [ "$selfhosted_valid" = true ]; then
        print_info "Running Self-hosted GitLab E2E tests only (SaaS environment not configured)..."
        print_info "Self-hosted Target: $SELF_HOSTED_GITLAB_URL"
        pytest -k "selfhosted" -v
    fi
    
    local exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        print_success "All tests completed successfully"
    else
        print_error "Some tests failed with exit code $exit_code"
    fi
    
    return $exit_code
}

# Main script
echo "========================================"
echo "       Glato E2E Testing Suite"
echo "========================================"
echo ""

# Check if we're in the correct directory
if [ ! -d "e2e_test" ]; then
    print_error "e2e_test directory not found. Please run this script from the project root."
    exit 1
fi

# Display menu
echo "Please select which tests to run:"
echo ""
echo "1) GitLab SaaS tests only"
echo "2) Self-hosted GitLab tests only"
echo "3) Both SaaS and Self-hosted tests"
echo "4) Exit"
echo ""

# Get user input
while true; do
    read -p "Enter your choice (1-4): " choice
    
    case $choice in
        1)
            echo ""
            print_info "Selected: GitLab SaaS tests only"
            run_saas_tests
            exit_code=$?
            break
            ;;
        2)
            echo ""
            print_info "Selected: Self-hosted GitLab tests only"
            run_selfhosted_tests
            exit_code=$?
            break
            ;;
        3)
            echo ""
            print_info "Selected: Both SaaS and Self-hosted tests"
            run_both_tests
            exit_code=$?
            break
            ;;
        4)
            echo ""
            print_info "Exiting..."
            exit 0
            ;;
        *)
            print_error "Invalid choice. Please enter 1, 2, 3, or 4."
            ;;
    esac
done

echo ""
if [ $exit_code -eq 0 ]; then
    print_success "All selected tests completed successfully!"
else
    print_error "Some tests failed. Check the output above for details."
fi

exit $exit_code
