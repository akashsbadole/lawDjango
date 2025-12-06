#!/usr/bin/env python
"""
Test runner script for multi-tenant functionality.

This script provides utilities to run specific test suites for the
multi-tenant lawyer management system.
"""

import os
import sys
import argparse
import subprocess
import django
from django.conf import settings
from django.test.utils import get_runner
from django.core.management import execute_from_command_line


def run_test_suite(test_labels, verbosity=2, keepdb=False, parallel=0):
    """
    Run a specific test suite.
    
    Args:
        test_labels: List of test labels to run
        verbosity: Verbosity level
        keepdb: Whether to keep the test database
        parallel: Number of parallel processes
        
    Returns:
        int: Exit code
    """
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_project.settings')
    
    django.setup()
    
    TestRunner = get_runner(settings)
    test_runner = TestRunner(
        verbosity=verbosity,
        keepdb=keepdb,
        parallel=parallel
    )
    
    failures = test_runner.run_tests(test_labels)
    return failures


def run_all_tenant_tests(verbosity=2, keepdb=False, parallel=0):
    """
    Run all multi-tenant related tests.
    
    Args:
        verbosity: Verbosity level
        keepdb: Whether to keep the test database
        parallel: Number of parallel processes
        
    Returns:
        int: Exit code
    """
    test_labels = [
        'tests.test_tenants',
        'tests.test_users',
        'tests.test_permissions',
        'tests.test_clients',
        'tests.test_cases',
        'tests.test_documents',
        'tests.test_billing',
        'tests.test_subscriptions',
        'tests.test_audit',
        'tests.test_import_export',
        'tests.test_backup_restore',
        'tests.test_platform_admin',
        'tests.test_integration'
    ]
    
    return run_test_suite(test_labels, verbosity, keepdb, parallel)


def run_module_tests(module_name, verbosity=2, keepdb=False, parallel=0):
    """
    Run tests for a specific module.
    
    Args:
        module_name: Name of the module
        verbosity: Verbosity level
        keepdb: Whether to keep the test database
        parallel: Number of parallel processes
        
    Returns:
        int: Exit code
    """
    test_label = f'tests.test_{module_name}'
    return run_test_suite([test_label], verbosity, keepdb, parallel)


def run_isolation_tests(verbosity=2, keepdb=False, parallel=0):
    """
    Run tenant isolation tests.
    
    Args:
        verbosity: Verbosity level
        keepdb: Whether to keep the test database
        parallel: Number of parallel processes
        
    Returns:
        int: Exit code
    """
    test_labels = [
        'tests.test_integration.TenantIsolationTests',
        'tests.test_integration.UserIsolationTests',
        'tests.test_integration.PermissionIsolationTests',
        'tests.test_integration.DataIsolationTests',
        'tests.test_integration.CrossTenantAccessTests'
    ]
    
    return run_test_suite(test_labels, verbosity, keepdb, parallel)


def run_performance_tests(verbosity=2, keepdb=False, parallel=0):
    """
    Run performance tests.
    
    Args:
        verbosity: Verbosity level
        keepdb: Whether to keep the test database
        parallel: Number of parallel processes
        
    Returns:
        int: Exit code
    """
    test_labels = [
        'tests.test_integration.PerformanceTests'
    ]
    
    return run_test_suite(test_labels, verbosity, keepdb, parallel)


def run_security_tests(verbosity=2, keepdb=False, parallel=0):
    """
    Run security tests.
    
    Args:
        verbosity: Verbosity level
        keepdb: Whether to keep the test database
        parallel: Number of parallel processes
        
    Returns:
        int: Exit code
    """
    test_labels = [
        'tests.test_integration.SecurityTests'
    ]
    
    return run_test_suite(test_labels, verbosity, keepdb, parallel)


def run_browser_tests(verbosity=2, keepdb=False, parallel=0):
    """
    Run browser-based tests.
    
    Args:
        verbosity: Verbosity level
        keepdb: Whether to keep the test database
        parallel: Number of parallel processes
        
    Returns:
        int: Exit code
    """
    test_labels = [
        'tests.test_integration.BrowserTests'
    ]
    
    return run_test_suite(test_labels, verbosity, keepdb, parallel)


def run_api_tests(verbosity=2, keepdb=False, parallel=0):
    """
    Run API tests.
    
    Args:
        verbosity: Verbosity level
        keepdb: Whether to keep the test database
        parallel: Number of parallel processes
        
    Returns:
        int: Exit code
    """
    test_labels = [
        'tests.test_integration.APITests'
    ]
    
    return run_test_suite(test_labels, verbosity, keepdb, parallel)


def run_coverage_report(test_labels=None):
    """
    Run tests with coverage reporting.
    
    Args:
        test_labels: List of test labels to run
        
    Returns:
        int: Exit code
    """
    if test_labels is None:
        test_labels = [
            'tests.test_tenants',
            'tests.test_users',
            'tests.test_permissions',
            'tests.test_clients',
            'tests.test_cases',
            'tests.test_documents',
            'tests.test_billing',
            'tests.test_subscriptions',
            'tests.test_audit',
            'tests.test_import_export',
            'tests.test_backup_restore',
            'tests.test_platform_admin',
            'tests.test_integration'
        ]
    
    cmd = [
        sys.executable, '-m', 'coverage', 'run',
        '--source=.',
        '--omit=*/migrations/*,*/tests/*,*/venv/*,*/env/*,*/__pycache__/*',
        'manage.py', 'test'
    ] + test_labels
    
    try:
        result = subprocess.run(cmd, check=True)
        
        # Generate coverage report
        subprocess.run([
            sys.executable, '-m', 'coverage', 'report',
            '--show-missing'
        ], check=True)
        
        # Generate HTML coverage report
        subprocess.run([
            sys.executable, '-m', 'coverage', 'html'
        ], check=True)
        
        return result.returncode
    except subprocess.CalledProcessError as e:
        return e.returncode


def create_test_data():
    """
    Create test data for manual testing.
    
    Returns:
        int: Exit code
    """
    from tests.fixtures import (
        create_sample_tenant_data,
        create_multi_tenant_scenario,
        create_security_test_data
    )
    
    print("Creating sample tenant data...")
    sample_data = create_sample_tenant_data()
    print(f"Created sample tenant: {sample_data['tenant'].name}")
    
    print("\nCreating multi-tenant scenario...")
    multi_data = create_multi_tenant_scenario()
    print(f"Created {len(multi_data)} multi-tenant objects")
    
    print("\nCreating security test data...")
    security_data = create_security_test_data()
    print(f"Created security tenant: {security_data['tenant'].name}")
    
    print("\nTest data created successfully!")
    return 0


def main():
    """
    Main entry point for the test runner.
    """
    parser = argparse.ArgumentParser(description='Run multi-tenant tests')
    
    parser.add_argument(
        'command',
        choices=[
            'all', 'tenants', 'users', 'permissions', 'clients', 'cases',
            'documents', 'billing', 'subscriptions', 'audit', 'import_export',
            'backup_restore', 'platform_admin', 'integration', 'isolation',
            'performance', 'security', 'browser', 'api', 'coverage',
            'create_data'
        ],
        help='Command to run'
    )
    
    parser.add_argument(
        '--verbosity', '-v',
        type=int,
        default=2,
        help='Verbosity level (0-3)'
    )
    
    parser.add_argument(
        '--keepdb', '-k',
        action='store_true',
        help='Keep the test database'
    )
    
    parser.add_argument(
        '--parallel', '-p',
        type=int,
        default=0,
        help='Number of parallel processes'
    )
    
    parser.add_argument(
        '--labels', '-l',
        nargs='*',
        help='Additional test labels'
    )
    
    args = parser.parse_args()
    
    # Run the appropriate command
    if args.command == 'all':
        exit_code = run_all_tenant_tests(
            args.verbosity, args.keepdb, args.parallel
        )
    elif args.command == 'tenants':
        exit_code = run_module_tests(
            'tenants', args.verbosity, args.keepdb, args.parallel
        )
    elif args.command == 'users':
        exit_code = run_module_tests(
            'users', args.verbosity, args.keepdb, args.parallel
        )
    elif args.command == 'permissions':
        exit_code = run_module_tests(
            'permissions', args.verbosity, args.keepdb, args.parallel
        )
    elif args.command == 'clients':
        exit_code = run_module_tests(
            'clients', args.verbosity, args.keepdb, args.parallel
        )
    elif args.command == 'cases':
        exit_code = run_module_tests(
            'cases', args.verbosity, args.keepdb, args.parallel
        )
    elif args.command == 'documents':
        exit_code = run_module_tests(
            'documents', args.verbosity, args.keepdb, args.parallel
        )
    elif args.command == 'billing':
        exit_code = run_module_tests(
            'billing', args.verbosity, args.keepdb, args.parallel
        )
    elif args.command == 'subscriptions':
        exit_code = run_module_tests(
            'subscriptions', args.verbosity, args.keepdb, args.parallel
        )
    elif args.command == 'audit':
        exit_code = run_module_tests(
            'audit', args.verbosity, args.keepdb, args.parallel
        )
    elif args.command == 'import_export':
        exit_code = run_module_tests(
            'import_export', args.verbosity, args.keepdb, args.parallel
        )
    elif args.command == 'backup_restore':
        exit_code = run_module_tests(
            'backup_restore', args.verbosity, args.keepdb, args.parallel
        )
    elif args.command == 'platform_admin':
        exit_code = run_module_tests(
            'platform_admin', args.verbosity, args.keepdb, args.parallel
        )
    elif args.command == 'integration':
        exit_code = run_module_tests(
            'integration', args.verbosity, args.keepdb, args.parallel
        )
    elif args.command == 'isolation':
        exit_code = run_isolation_tests(
            args.verbosity, args.keepdb, args.parallel
        )
    elif args.command == 'performance':
        exit_code = run_performance_tests(
            args.verbosity, args.keepdb, args.parallel
        )
    elif args.command == 'security':
        exit_code = run_security_tests(
            args.verbosity, args.keepdb, args.parallel
        )
    elif args.command == 'browser':
        exit_code = run_browser_tests(
            args.verbosity, args.keepdb, args.parallel
        )
    elif args.command == 'api':
        exit_code = run_api_tests(
            args.verbosity, args.keepdb, args.parallel
        )
    elif args.command == 'coverage':
        exit_code = run_coverage_report(args.labels)
    elif args.command == 'create_data':
        exit_code = create_test_data()
    else:
        parser.print_help()
        exit_code = 1
    
    sys.exit(exit_code)


if __name__ == '__main__':
    main()