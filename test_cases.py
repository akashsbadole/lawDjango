import os
import django

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_project.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from tenants.models import Tenant

User = get_user_model()

def test_cases_module():
    print("Testing cases module...")
    
    # Check if tenant exists, create if not
    tenant, created = Tenant.objects.get_or_create(
        slug='test-law-firm',
        defaults={
            'name': 'Test Law Firm',
            'plan': 'basic',
            'max_users': 10
        }
    )
    if created:
        print(f"+ Created tenant: {tenant.name}")
    else:
        print(f"+ Found tenant: {tenant.name}")
    
    # Check if user exists, create if not
    user, created = User.objects.get_or_create(
        email='test@example.com',
        defaults={
            'first_name': 'Test',
            'last_name': 'User',
            'tenant': tenant,
            'is_active': True
        }
    )
    if created:
        print(f"+ Created user: {user.email}")
    else:
        print(f"+ Found user: {user.email}")
    
    # Test cases list view
    client = Client()
    client.force_login(user)
    
    try:
        response = client.get('/app/test-law-firm/cases/')
        print(f"+ Cases list view status: {response.status_code}")
        
        if response.status_code == 200:
            print("+ Cases list view is working!")
        else:
            print(f"- Cases list view failed with status {response.status_code}")
            try:
                print(f"Response content: {response.content.decode()[:500]}")
            except:
                print("Could not decode response content")
    except Exception as e:
        print(f"✗ Error testing cases list view: {e}")

if __name__ == '__main__':
    test_cases_module()