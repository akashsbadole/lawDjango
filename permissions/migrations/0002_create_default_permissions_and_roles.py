from django.db import migrations

def create_default_permissions_and_roles(apps, schema_editor):
    """
    Create default permissions and roles for the system.
    """
    TenantPermission = apps.get_model('permissions', 'TenantPermission')
    Role = apps.get_model('permissions', 'Role')
    Tenant = apps.get_model('tenants', 'Tenant')
    
    # Create default permissions
    default_permissions = [
        # Client permissions
        {'name': 'View Clients', 'codename': 'clients.view_client', 'module': 'clients'},
        {'name': 'Add Client', 'codename': 'clients.add_client', 'module': 'clients'},
        {'name': 'Change Client', 'codename': 'clients.change_client', 'module': 'clients'},
        {'name': 'Delete Client', 'codename': 'clients.delete_client', 'module': 'clients'},
        
        # Case permissions
        {'name': 'View Cases', 'codename': 'cases.view_case', 'module': 'cases'},
        {'name': 'Add Case', 'codename': 'cases.add_case', 'module': 'cases'},
        {'name': 'Change Case', 'codename': 'cases.change_case', 'module': 'cases'},
        {'name': 'Delete Case', 'codename': 'cases.delete_case', 'module': 'cases'},
        
        # Document permissions
        {'name': 'View Documents', 'codename': 'documents.view_document', 'module': 'documents'},
        {'name': 'Add Document', 'codename': 'documents.add_document', 'module': 'documents'},
        {'name': 'Change Document', 'codename': 'documents.change_document', 'module': 'documents'},
        {'name': 'Delete Document', 'codename': 'documents.delete_document', 'module': 'documents'},
        
        # Invoice permissions
        {'name': 'View Invoices', 'codename': 'billing.view_invoice', 'module': 'billing'},
        {'name': 'Add Invoice', 'codename': 'billing.add_invoice', 'module': 'billing'},
        {'name': 'Change Invoice', 'codename': 'billing.change_invoice', 'module': 'billing'},
        {'name': 'Delete Invoice', 'codename': 'billing.delete_invoice', 'module': 'billing'},
        
        # Payment permissions
        {'name': 'View Payments', 'codename': 'billing.view_payment', 'module': 'billing'},
        {'name': 'Add Payment', 'codename': 'billing.add_payment', 'module': 'billing'},
        {'name': 'Change Payment', 'codename': 'billing.change_payment', 'module': 'billing'},
        {'name': 'Delete Payment', 'codename': 'billing.delete_payment', 'module': 'billing'},
        
        # Time entry permissions
        {'name': 'View Time Entries', 'codename': 'billing.view_time_entry', 'module': 'billing'},
        {'name': 'Add Time Entry', 'codename': 'billing.add_time_entry', 'module': 'billing'},
        {'name': 'Change Time Entry', 'codename': 'billing.change_time_entry', 'module': 'billing'},
        {'name': 'Delete Time Entry', 'codename': 'billing.delete_time_entry', 'module': 'billing'},
        
        # Expense permissions
        {'name': 'View Expenses', 'codename': 'billing.view_expense', 'module': 'billing'},
        {'name': 'Add Expense', 'codename': 'billing.add_expense', 'module': 'billing'},
        {'name': 'Change Expense', 'codename': 'billing.change_expense', 'module': 'billing'},
        {'name': 'Delete Expense', 'codename': 'billing.delete_expense', 'module': 'billing'},
        
        # User management permissions
        {'name': 'View Users', 'codename': 'users.view_user', 'module': 'users'},
        {'name': 'Add User', 'codename': 'users.add_user', 'module': 'users'},
        {'name': 'Change User', 'codename': 'users.change_user', 'module': 'users'},
        {'name': 'Delete User', 'codename': 'users.delete_user', 'module': 'users'},
        
        # Role management permissions
        {'name': 'View Roles', 'codename': 'roles.view_role', 'module': 'roles'},
        {'name': 'Add Role', 'codename': 'roles.add_role', 'module': 'roles'},
        {'name': 'Change Role', 'codename': 'roles.change_role', 'module': 'roles'},
        {'name': 'Delete Role', 'codename': 'roles.delete_role', 'module': 'roles'},
        {'name': 'Assign Roles', 'codename': 'roles.assign_role', 'module': 'roles'},
    ]
    
    # Create permissions
    permission_objects = {}
    for perm_data in default_permissions:
        permission, created = TenantPermission.objects.get_or_create(
            codename=perm_data['codename'],
            defaults=perm_data
        )
        permission_objects[permission.codename] = permission
    
    # Get all tenants
    tenants = Tenant.objects.all()
    
    # Create default roles for each tenant
    for tenant in tenants:
        # Admin role - gets all permissions
        admin_role, created = Role.objects.get_or_create(
            name='Admin',
            tenant=tenant,
            defaults={
                'description': 'Full access to all system features and settings',
                'is_system_role': True,
            }
        )
        if created:
            admin_role.permissions.set(TenantPermission.objects.all())
        
        # Lawyer role
        lawyer_permissions = [
            'clients.view_client', 'clients.add_client', 'clients.change_client',
            'cases.view_case', 'cases.add_case', 'cases.change_case',
            'documents.view_document', 'documents.add_document', 'documents.change_document',
            'billing.view_invoice', 'billing.add_invoice', 'billing.change_invoice',
        ]
        
        lawyer_role, created = Role.objects.get_or_create(
            name='Lawyer',
            tenant=tenant,
            defaults={
                'description': 'Can manage cases, clients, and documents',
                'is_system_role': True,
            }
        )
        if created:
            lawyer_role.permissions.set([
                permission_objects[perm] for perm in lawyer_permissions
                if perm in permission_objects
            ])
        
        # Paralegal role
        paralegal_permissions = [
            'clients.view_client', 'clients.add_client', 'clients.change_client',
            'cases.view_case', 'cases.add_case', 'cases.change_case',
            'documents.view_document', 'documents.add_document', 'documents.change_document',
            'billing.view_invoice',
        ]
        
        paralegal_role, created = Role.objects.get_or_create(
            name='Paralegal',
            tenant=tenant,
            defaults={
                'description': 'Can view and edit cases, clients, and documents but cannot delete',
                'is_system_role': True,
            }
        )
        if created:
            paralegal_role.permissions.set([
                permission_objects[perm] for perm in paralegal_permissions
                if perm in permission_objects
            ])
        
        # Billing Manager role
        billing_manager_permissions = [
            'clients.view_client',
            'cases.view_case',
            'documents.view_document',
            'billing.view_invoice', 'billing.add_invoice', 'billing.change_invoice', 'billing.delete_invoice',
            'billing.view_payment', 'billing.add_payment', 'billing.change_payment',
            'billing.view_time_entry', 'billing.add_time_entry', 'billing.change_time_entry',
            'billing.view_expense', 'billing.add_expense', 'billing.change_expense',
        ]
        
        billing_manager_role, created = Role.objects.get_or_create(
            name='Billing Manager',
            tenant=tenant,
            defaults={
                'description': 'Can manage all billing and financial operations',
                'is_system_role': True,
            }
        )
        if created:
            billing_manager_role.permissions.set([
                permission_objects[perm] for perm in billing_manager_permissions
                if perm in permission_objects
            ])
        
        # Read-only Staff role
        readonly_permissions = [
            'clients.view_client',
            'cases.view_case',
            'documents.view_document',
            'billing.view_invoice',
            'billing.view_payment',
            'billing.view_time_entry',
            'billing.view_expense',
        ]
        
        readonly_role, created = Role.objects.get_or_create(
            name='Read-only Staff',
            tenant=tenant,
            defaults={
                'description': 'Can view all information but cannot make changes',
                'is_system_role': True,
            }
        )
        if created:
            readonly_role.permissions.set([
                permission_objects[perm] for perm in readonly_permissions
                if perm in permission_objects
            ])


class Migration(migrations.Migration):
    dependencies = [
        ('tenants', '0001_initial'),
        ('permissions', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            create_default_permissions_and_roles,
            reverse_code=migrations.RunPython.noop
        ),
    ]