"""
Database router for multi-tenant application.

This router ensures that tenant-specific models are properly isolated
and that queries are correctly routed to the appropriate database.
"""

from django.conf import settings


class TenantRouter:
    """
    Database router for multi-tenant application.
    
    This router ensures that:
    1. Tenant-specific models are properly isolated
    2. Shared models are accessible across tenants
    3. Database connections are optimized for tenant queries
    """
    
    def db_for_read(self, model, **hints):
        """
        Suggest the database to read from.
        
        Args:
            model: The model class being queried
            **hints: Additional hints from the view
            
        Returns:
            The database alias to use for reading
        """
        # Get the tenant from hints if available
        tenant = hints.get('tenant')
        
        # If we have a tenant and the model is tenant-specific
        if tenant and hasattr(model, '_tenant_aware') and model._tenant_aware:
            # Use tenant-specific database if configured
            if hasattr(settings, 'TENANT_DATABASES') and tenant.slug in settings.TENANT_DATABASES:
                return f'tenant_{tenant.slug}'
        
        # Default to the default database
        return 'default'
    
    def db_for_write(self, model, **hints):
        """
        Suggest the database to write to.
        
        Args:
            model: The model class being written to
            **hints: Additional hints from the view
            
        Returns:
            The database alias to use for writing
        """
        # Get the tenant from hints if available
        tenant = hints.get('tenant')
        
        # If we have a tenant and the model is tenant-specific
        if tenant and hasattr(model, '_tenant_aware') and model._tenant_aware:
            # Use tenant-specific database if configured
            if hasattr(settings, 'TENANT_DATABASES') and tenant.slug in settings.TENANT_DATABASES:
                return f'tenant_{tenant.slug}'
        
        # Default to the default database
        return 'default'
    
    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations if models are in the same tenant or if one is shared.
        
        Args:
            obj1: The first object
            obj2: The second object
            **hints: Additional hints from the view
            
        Returns:
            True if the relation should be allowed, False otherwise
        """
        # Get the models
        model1 = obj1.__class__
        model2 = obj2.__class__
        
        # If both models are tenant-aware, they must be in the same tenant
        if (hasattr(model1, '_tenant_aware') and model1._tenant_aware and
            hasattr(model2, '_tenant_aware') and model2._tenant_aware):
            
            # Check if both objects have the same tenant
            if (hasattr(obj1, 'tenant') and hasattr(obj2, 'tenant') and
                obj1.tenant == obj2.tenant):
                return True
            
            # If we can't determine tenant, be safe and deny
            return False
        
        # If at least one model is not tenant-aware, allow the relation
        return True
    
    def allow_migrate(self, db, app_label, **hints):
        """
        Determine if migration should run on this database.
        
        Args:
            app_label: The app label
            model_name: The name of the model
            **hints: Additional hints from the view
            
        Returns:
            True if migration should run, False otherwise
        """
        # Get the database alias from hints
        database = hints.get('instance')
        
        # If this is a tenant-specific database
        if db and db.startswith('tenant_'):
            # Only allow tenant-aware models to migrate to tenant databases
            model = hints.get('model')
            if model and hasattr(model, '_tenant_aware') and model._tenant_aware:
                return True
            return False
        
        # Default to allowing migrations on the default database
        return True