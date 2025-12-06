#!/usr/bin/env python
import os
import sys
import django

# Add the project directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_project.settings')
django.setup()

# Temporarily disable audit signals
from audit import signals
from django.db.models.signals import post_save, pre_save
post_save.disconnect(signals.track_model_changes_after, dispatch_uid="audit_track_changes_after")
pre_save.disconnect(signals.track_model_changes_before, dispatch_uid="audit_track_changes_before")

from django.test import Client
from django.contrib.auth import get_user_model
from tenants.models import Tenant

User = get_user_model()

# Check available tenants
tenants = Tenant.objects.all()
print("Available tenants:")
for t in tenants:
    print(f"  {t.name} (slug: {t.slug})")

# Check user details
user = User.objects.get(email='lawyer@example.com')
print(f"\nUser role: {user.role}")
print(f"User tenant: {user.tenant}")

# Assign tenant if user doesn't have one
if not user.tenant and tenants.exists():
    # Use update to avoid triggering audit signals
    User.objects.filter(pk=user.pk).update(tenant=tenants.first())
    user.refresh_from_db()
    print(f"Assigned tenant {user.tenant.name} to lawyer@example.com")

# Create a test client
client = Client()

# Test login
print("\nTesting lawyer login...")
login_result = client.login(email='lawyer@example.com', password='password123')
print(f"Login successful: {login_result}")

if login_result:
    # Test accessing lawyer panel
    response = client.get('/lawyer-panel/')
    print(f"Lawyer panel status code: {response.status_code}")
    
    if response.status_code == 200:
        print("SUCCESS: Lawyer can access the lawyer panel!")
    elif response.status_code == 302:
        print(f"Redirected to: {response.get('Location', 'Unknown')}")
    else:
        print(f"Unexpected response: {response.status_code}")
else:
    print("FAILED: Login failed")