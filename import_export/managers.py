from django.db import models
from django.utils import timezone


class ImportJobManager(models.Manager):
    """
    Custom manager for ImportJob model with tenant filtering.
    """
    def get_queryset(self):
        """Filter by tenant if available."""
        queryset = super().get_queryset()
        return queryset
    
    def for_tenant(self, tenant):
        """Filter import jobs by tenant."""
        return self.get_queryset().filter(tenant=tenant)
    
    def active(self):
        """Get active (not completed) import jobs."""
        return self.get_queryset().filter(
            status__in=['pending', 'processing']
        )
    
    def completed(self):
        """Get completed import jobs."""
        return self.get_queryset().filter(
            status__in=['completed', 'failed', 'cancelled']
        )
    
    def by_model_type(self, model_type):
        """Filter import jobs by model type."""
        return self.get_queryset().filter(model_type=model_type)
    
    def recent(self, days=30):
        """Get import jobs from the last N days."""
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        return self.get_queryset().filter(created_at__gte=cutoff_date)


class ExportJobManager(models.Manager):
    """
    Custom manager for ExportJob model with tenant filtering.
    """
    def get_queryset(self):
        """Filter by tenant if available."""
        queryset = super().get_queryset()
        return queryset
    
    def for_tenant(self, tenant):
        """Filter export jobs by tenant."""
        return self.get_queryset().filter(tenant=tenant)
    
    def active(self):
        """Get active (not completed) export jobs."""
        return self.get_queryset().filter(
            status__in=['pending', 'processing']
        )
    
    def completed(self):
        """Get completed export jobs."""
        return self.get_queryset().filter(
            status__in=['completed', 'failed', 'cancelled']
        )
    
    def by_model_type(self, model_type):
        """Filter export jobs by model type."""
        return self.get_queryset().filter(model_type=model_type)
    
    def recent(self, days=30):
        """Get export jobs from the last N days."""
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        return self.get_queryset().filter(created_at__gte=cutoff_date)


class ImportTemplateManager(models.Manager):
    """
    Custom manager for ImportTemplate model with tenant filtering.
    """
    def get_queryset(self):
        """Filter by tenant if available."""
        queryset = super().get_queryset()
        return queryset
    
    def for_tenant(self, tenant):
        """Filter import templates by tenant."""
        return self.get_queryset().filter(tenant=tenant)
    
    def public(self):
        """Get public import templates."""
        return self.get_queryset().filter(is_public=True)
    
    def for_model_type(self, model_type):
        """Filter import templates by model type."""
        return self.get_queryset().filter(model_type=model_type)
    
    def available_to_tenant(self, tenant, model_type=None):
        """Get templates available to a tenant (tenant's own + public)."""
        queryset = self.get_queryset().filter(
            models.Q(tenant=tenant) | models.Q(is_public=True)
        )
        
        if model_type:
            queryset = queryset.filter(model_type=model_type)
            
        return queryset.distinct()