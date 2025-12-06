# Multi-Tenant Test Suite

This directory contains comprehensive tests for the multi-tenant lawyer management system. The test suite covers all aspects of the multi-tenant functionality including tenant isolation, user management, permissions, and all application modules.

## Test Structure

### Test Files

- `utils.py` - Base test classes and utilities for multi-tenant testing
- `fixtures.py` - Factory functions and test data creation utilities
- `run_tests.py` - Test runner script with various options
- `test_tenants.py` - Tenant model tests
- `test_users.py` - User model tests
- `test_permissions.py` - Permission system tests
- `test_clients.py` - Client module tests
- `test_cases.py` - Case module tests
- `test_documents.py` - Document module tests
- `test_billing.py` - Billing module tests
- `test_subscriptions.py` - Subscription tests
- `test_audit.py` - Audit system tests
- `test_import_export.py` - Import/export tests
- `test_backup_restore.py` - Backup/restore tests
- `test_platform_admin.py` - Super admin tests
- `test_integration.py` - Integration tests
- `test_tenant_middleware.py` - Tenant middleware tests

### Test Base Classes

The `utils.py` file provides several base classes for testing:

- `TenantTestCase` - Base class for tenant-related tests
- `MultiTenantTestCase` - For testing multi-tenant scenarios
- `TenantAwareTestCase` - For tenant context testing
- `TenantMixinTestMixin` - For tenant isolation testing
- `FileTestCase` - For file-related testing
- `PerformanceTestCase` - For performance testing
- `APITestCase` - For API testing

## Running Tests

### Using the Test Runner Script

The `run_tests.py` script provides convenient options for running tests:

```bash
# Run all multi-tenant tests
python tests/run_tests.py all

# Run tests for a specific module
python tests/run_tests.py tenants
python tests/run_tests.py users
python tests/run_tests.py clients
python tests/run_tests.py cases
python tests/run_tests.py documents
python tests/run_tests.py billing
python tests/run_tests.py subscriptions
python tests/run_tests.py audit
python tests/run_tests.py import_export
python tests/run_tests.py backup_restore
python tests/run_tests.py platform_admin
python tests/run_tests.py integration

# Run specific test categories
python tests/run_tests.py isolation    # Tenant isolation tests
python tests/run_tests.py performance  # Performance tests
python tests/run_tests.py security     # Security tests
python tests/run_tests.py browser      # Browser-based tests
python tests/run_tests.py api          # API tests

# Run with coverage
python tests/run_tests.py coverage

# Create test data
python tests/run_tests.py create_data
```

### Test Runner Options

- `--verbosity, -v` - Verbosity level (0-3, default: 2)
- `--keepdb, -k` - Keep the test database
- `--parallel, -p` - Number of parallel processes
- `--labels, -l` - Additional test labels

Example:
```bash
python tests/run_tests.py all -v 3 -k -p 4
```

### Using Django's Test Command

You can also use Django's built-in test command:

```bash
# Run all tests
python manage.py test tests

# Run specific test file
python manage.py test tests.test_tenants

# Run specific test class
python manage.py test tests.test_tenants.TenantModelTests

# Run specific test method
python manage.py test tests.test_tenants.TenantModelTests.test_create_tenant
```

## Test Fixtures

The `fixtures.py` file provides factory functions to create test data:

### Basic Fixtures

- `create_test_tenant()` - Create a test tenant
- `create_test_user()` - Create a test user
- `create_test_admin_user()` - Create a test admin user
- `create_test_superuser()` - Create a test superuser
- `create_test_permission()` - Create a test permission
- `create_test_role()` - Create a test role
- `create_test_user_role()` - Create a user role assignment

### Module-Specific Fixtures

- `create_test_client()` - Create a test client
- `create_test_case()` - Create a test case
- `create_test_document()` - Create a test document
- `create_test_invoice()` - Create a test invoice
- `create_test_payment()` - Create a test payment
- `create_test_time_entry()` - Create a test time entry
- `create_test_billing_rate()` - Create a test billing rate
- `create_test_subscription_plan()` - Create a test subscription plan
- `create_test_tenant_subscription()` - Create a test tenant subscription
- `create_test_audit_log()` - Create a test audit log
- `create_test_backup_job()` - Create a test backup job
- `create_test_restore_job()` - Create a test restore job
- `create_test_backup_schedule()` - Create a test backup schedule

### Comprehensive Fixtures

- `create_sample_tenant_data()` - Create a complete sample tenant with all related data
- `create_multi_tenant_scenario()` - Create a multi-tenant scenario with multiple tenants
- `create_performance_test_data()` - Create a large dataset for performance testing
- `create_security_test_data()` - Create data for security testing
- `create_test_data_for_module()` - Create test data for a specific module

## Test Categories

### Unit Tests

Unit tests focus on individual components:

- Model tests for all models
- Manager method tests
- Form validation tests
- View function tests
- Utility function tests

### Integration Tests

Integration tests test how components work together:

- Tenant isolation tests
- User authentication tests
- Permission system tests
- Cross-tenant data access tests
- End-to-end workflow tests

### Performance Tests

Performance tests ensure the system performs well with large datasets:

- Large dataset queries
- Concurrent user tests
- File upload performance
- Report generation performance

### Security Tests

Security tests verify the system is secure:

- Cross-tenant data access prevention
- Permission bypass attempts
- SQL injection prevention
- XSS prevention
- CSRF protection

### Browser Tests

Browser tests verify the user interface works correctly:

- Form submissions
- Navigation flows
- JavaScript functionality
- Responsive design

## Test Coverage

The test suite aims for comprehensive coverage of:

### Tenant Isolation

- Data isolation between tenants
- User access restrictions
- Permission enforcement
- Middleware functionality

### Core Functionality

- CRUD operations for all models
- Form validation
- View rendering
- URL routing

### Business Logic

- Case management workflows
- Document versioning
- Invoice calculations
- Subscription management
- Audit logging

### Error Handling

- Invalid input handling
- Edge cases
- Exception handling
- User feedback

## Best Practices

### Writing Tests

1. Use descriptive test method names
2. Follow the Arrange-Act-Assert pattern
3. Test both success and failure cases
4. Use fixtures for consistent test data
5. Keep tests independent and isolated

### Test Data

1. Use factory functions instead of fixtures
2. Create minimal test data
3. Clean up after tests
4. Use transactions where appropriate

### Performance

1. Use `@override_settings` to disable expensive operations
2. Use `@mock.patch` for external services
3. Use `bulk_create` for large datasets
4. Use `parallel` option for faster test runs

## Continuous Integration

The test suite is designed to run in CI/CD environments:

```yaml
# Example GitHub Actions workflow
- name: Run tests
  run: |
    python tests/run_tests.py all --keepdb --parallel 4

- name: Generate coverage report
  run: |
    python tests/run_tests.py coverage
```

## Troubleshooting

### Common Issues

1. **Database errors**: Make sure migrations are up to date
2. **Import errors**: Check PYTHONPATH includes the project directory
3. **Permission errors**: Ensure test database has correct permissions
4. **Timeout errors**: Increase timeout or use parallel execution

### Debugging Tests

1. Use `--verbosity 3` for detailed output
2. Use `pdb.set_trace()` in test methods
3. Use `--keepdb` to inspect test database
4. Use `--debug-mode` for Django debug output

## Contributing

When adding new tests:

1. Follow existing test patterns
2. Add appropriate fixtures
3. Update documentation
4. Ensure coverage is maintained
5. Run the full test suite before submitting

## Test Data Management

### Test Database

The test suite uses a separate test database:

- Default: `test_lawyer`
- Can be customized in settings
- Use `--keepdb` to preserve between runs
- Use `--parallel` for faster execution

### Test Files

Test files are stored in the `tests/` directory:

- Unit tests in `test_*.py` files
- Integration tests in `test_integration.py`
- Fixtures in `fixtures.py`
- Utilities in `utils.py`

### Test Media

Test media files are handled separately:

- Use `SimpleUploadedFile` for file uploads
- Clean up after tests
- Use temporary directories for large files