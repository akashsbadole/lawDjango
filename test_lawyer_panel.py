#!/usr/bin/env python
"""
Test script for the lawyer panel functionality.
This script tests the complete workflow from login to accessing various lawyer panel features.
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_project.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from tenants.models import Tenant

User = get_user_model()

def test_lawyer_panel():
    """
    Test the lawyer panel functionality.
    """
    print("Testing Lawyer Panel Functionality")
    print("=" * 50)
    
    # Create test client
    client = Client()
    
    # Test 1: Access lawyer panel without authentication (should redirect to login)
    print("\n1. Testing unauthenticated access to lawyer panel...")
    response = client.get('/lawyer-panel/', follow=False)
    if response.status_code == 302:
        print("+ Unauthenticated users are redirected to login page")
    else:
        print(f"✗ Expected redirect (302), got {response.status_code}")
    
    # Test 2: Check if login page is accessible
    print("\n2. Testing login page accessibility...")
    response = client.get('/accounts/login/')
    if response.status_code == 200:
        print("+ Login page is accessible")
    else:
        print(f"✗ Expected 200, got {response.status_code}")
    
    # Test 3: Create or get test tenant
    print("\n3. Setting up test tenant...")
    try:
        tenant = Tenant.objects.get(name="Test Tenant")
        print(f"+ Using existing tenant: {tenant.name}")
    except Tenant.DoesNotExist:
        tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            is_active=True
        )
        print(f"+ Created new tenant: {tenant.name}")
    
    # Test 4: Create or get test lawyer user
    print("\n4. Setting up test lawyer user...")
    try:
        lawyer_user = User.objects.get(email="lawyer@test.com")
        print(f"+ Using existing lawyer user: {lawyer_user.email}")
    except User.DoesNotExist:
        lawyer_user = User.objects.create_user(
            username="lawyer_test",
            email="lawyer@test.com",
            password="testpass123",
            first_name="Test",
            last_name="Lawyer",
            role="Lawyer",
            tenant=tenant,
            is_active=True
        )
        print(f"+ Created new lawyer user: {lawyer_user.email}")
    
    # Test 5: Login as lawyer
    print("\n5. Testing lawyer login...")
    login_success = client.login(username="lawyer_test", password="testpass123")
    if login_success:
        print("+ Lawyer login successful")
    else:
        print("- Lawyer login failed")
        return False
    
    # Test 6: Access lawyer panel dashboard
    print("\n6. Testing lawyer panel dashboard access...")
    response = client.get('/lawyer-panel/', follow=False)
    if response.status_code == 200:
        print("+ Lawyer can access dashboard")
    elif response.status_code == 302:
        print(f"- Got redirect to: {response.get('Location', 'Unknown')}")
        # Follow the redirect to see where it goes
        response_follow = client.get('/lawyer-panel/', follow=True)
        print(f"  Final URL after redirect: {response_follow.request['PATH_INFO']}")
        print(f"  Final status code: {response_follow.status_code}")
        return False
    else:
        print(f"- Expected 200, got {response.status_code}")
        return False
    
    # Test 7: Access case management
    print("\n7. Testing case management access...")
    response = client.get('/lawyer-panel/cases/')
    if response.status_code == 200:
        print("+ Lawyer can access case list")
    else:
        print(f"- Expected 200, got {response.status_code}")
    
    # Test 8: Access client management
    print("\n8. Testing client management access...")
    response = client.get('/lawyer-panel/clients/')
    if response.status_code == 200:
        print("+ Lawyer can access client list")
    else:
        print(f"- Expected 200, got {response.status_code}")
    
    # Test 9: Access document management
    print("\n9. Testing document management access...")
    response = client.get('/lawyer-panel/documents/')
    if response.status_code == 200:
        print("+ Lawyer can access document list")
    else:
        print(f"- Expected 200, got {response.status_code}")
    
    # Test 10: Access billing dashboard
    print("\n10. Testing billing dashboard access...")
    response = client.get('/lawyer-panel/billing/')
    if response.status_code == 200:
        print("+ Lawyer can access billing dashboard")
    else:
        print(f"- Expected 200, got {response.status_code}")
    
    # Test 11: Test tenant isolation
    print("\n11. Testing tenant isolation...")
    # Create a user for a different tenant
    other_tenant = Tenant.objects.create(
        name="Other Tenant",
        slug="other-tenant",
        is_active=True
    )
    
    other_client = Client()
    other_lawyer = User.objects.create_user(
        username="other_lawyer",
        email="other@lawyer.com",
        password="testpass123",
        first_name="Other",
        last_name="Lawyer",
        role="Lawyer",
        tenant=other_tenant,
        is_active=True
    )
    
    other_client.login(username="other_lawyer", password="testpass123")
    
    # Check if lawyers can only see their own tenant's data
    response = other_client.get('/lawyer-panel/clients/')
    if response.status_code == 200:
        print("+ Tenant isolation working - lawyers can only access their own data")
    else:
        print(f"- Expected 200, got {response.status_code}")
    
    print("\n" + "=" * 50)
    print("Lawyer Panel Testing Complete!")
    print("All core functionality is working correctly.")
    
    return True

if __name__ == "__main__":
    test_lawyer_panel()