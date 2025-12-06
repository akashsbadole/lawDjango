from django.db import models
from django.utils import timezone


class ClientManager(models.Manager):
    """
    Manager for the Client model with tenant filtering and soft delete functionality.
    """
    
    def get_queryset(self):
        """
        Override the default queryset to exclude soft-deleted clients.
        """
        return super().get_queryset().filter(deleted_at__isnull=True)
    
    def all_with_deleted(self):
        """
        Return all clients including soft-deleted ones.
        """
        return super().get_queryset()
    
    def deleted(self):
        """
        Return only soft-deleted clients.
        """
        return super().get_queryset().filter(deleted_at__isnull=False)
    
    def for_tenant(self, tenant):
        """
        Filter clients by tenant.
        """
        return self.filter(tenant=tenant)
    
    def active_for_tenant(self, tenant):
        """
        Return active (non-deleted) clients for a specific tenant.
        """
        return self.filter(tenant=tenant, deleted_at__isnull=True)
    
    def search(self, query, tenant=None):
        """
        Search clients by name, email, or company.
        """
        queryset = self.all()
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        
        if query:
            queryset = queryset.filter(
                models.Q(first_name__icontains=query) |
                models.Q(last_name__icontains=query) |
                models.Q(email__icontains=query) |
                models.Q(company__icontains=query)
            )
        
        return queryset
    
    def create_client(self, tenant, user, **kwargs):
        """
        Create a new client with tenant and user information.
        """
        return self.create(
            tenant=tenant,
            created_by=user,
            **kwargs
        )
    
    def soft_delete(self, client_id):
        """
        Soft delete a client by setting the deleted_at timestamp.
        """
        client = self.get(pk=client_id)
        client.deleted_at = timezone.now()
        client.save()
        return client