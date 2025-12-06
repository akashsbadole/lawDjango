from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Permission
from django.utils.translation import gettext_lazy as _


class TenantPermission(models.Model):
    """
    Custom permission model that extends Django's built-in Permission model
    but is scoped to a specific tenant.
    """
    name = models.CharField(_("name"), max_length=255)
    codename = models.CharField(_("codename"), max_length=100, unique=True)
    description = models.TextField(_("description"), blank=True)
    module = models.CharField(_("module"), max_length=100, help_text=_("e.g., clients, cases, billing"))
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _("Tenant Permission")
        verbose_name_plural = _("Tenant Permissions")
        ordering = ['module', 'name']
    
    def __str__(self):
        return f"{self.module}.{self.name}"


class Role(models.Model):
    """
    Role model that represents a collection of permissions within a tenant.
    """
    name = models.CharField(_("name"), max_length=100)
    description = models.TextField(_("description"), blank=True)
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='roles'
    )
    permissions = models.ManyToManyField(
        TenantPermission,
        blank=True,
        related_name='roles'
    )
    is_system_role = models.BooleanField(
        default=False,
        help_text=_("System roles cannot be deleted and are available to all tenants")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _("Role")
        verbose_name_plural = _("Roles")
        unique_together = ['name', 'tenant']
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.tenant.name})"
    
    def has_permission(self, permission_codename):
        """Check if this role has a specific permission."""
        return self.permissions.filter(codename=permission_codename).exists()


class UserRole(models.Model):
    """
    Model to link users to roles within a tenant.
    """
    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name='user_roles'
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='role_users'
    )
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='user_roles'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_roles'
    )
    
    class Meta:
        verbose_name = _("User Role")
        verbose_name_plural = _("User Roles")
        unique_together = ['user', 'role', 'tenant']
    
    def __str__(self):
        return f"{self.user.email} - {self.role.name} ({self.tenant.name})"


# System-wide predefined roles that will be created for each tenant
SYSTEM_ROLES = [
    {
        'name': 'Admin',
        'description': 'Full access to all system features and settings',
        'permissions': '*',  # Will be handled in migration to give all permissions
    },
    {
        'name': 'Lawyer',
        'description': 'Can manage cases, clients, and documents',
        'permissions': [
            'clients.view_client',
            'clients.add_client',
            'clients.change_client',
            'cases.view_case',
            'cases.add_case',
            'cases.change_case',
            'documents.view_document',
            'documents.add_document',
            'documents.change_document',
            'billing.view_invoice',
            'billing.add_invoice',
            'billing.change_invoice',
        ]
    },
    {
        'name': 'Paralegal',
        'description': 'Can view and edit cases, clients, and documents but cannot delete',
        'permissions': [
            'clients.view_client',
            'clients.add_client',
            'clients.change_client',
            'cases.view_case',
            'cases.add_case',
            'cases.change_case',
            'documents.view_document',
            'documents.add_document',
            'documents.change_document',
            'billing.view_invoice',
        ]
    },
    {
        'name': 'Billing Manager',
        'description': 'Can manage all billing and financial operations',
        'permissions': [
            'clients.view_client',
            'cases.view_case',
            'documents.view_document',
            'billing.view_invoice',
            'billing.add_invoice',
            'billing.change_invoice',
            'billing.delete_invoice',
            'billing.view_payment',
            'billing.add_payment',
            'billing.change_payment',
            'billing.view_time_entry',
            'billing.add_time_entry',
            'billing.change_time_entry',
            'billing.view_expense',
            'billing.add_expense',
            'billing.change_expense',
        ]
    },
    {
        'name': 'Read-only Staff',
        'description': 'Can view all information but cannot make changes',
        'permissions': [
            'clients.view_client',
            'cases.view_case',
            'documents.view_document',
            'billing.view_invoice',
            'billing.view_payment',
            'billing.view_time_entry',
            'billing.view_expense',
        ]
    },
]

# System-wide permissions that will be created
SYSTEM_PERMISSIONS = [
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
