from django.db import models
from django.utils import timezone


class TenantManager(models.Manager):
    """
    Manager for the Tenant model with common query methods.
    """
    
    def active(self):
        """Return only active tenants."""
        return self.filter(status='active', is_active=True, deleted_at__isnull=True)
    
    def suspended(self):
        """Return only suspended tenants."""
        return self.filter(status='suspended')
    
    def trial_expired(self):
        """Return only tenants with expired trials."""
        return self.filter(status='trial_expired')
    
    def deleted(self):
        """Return only soft-deleted tenants."""
        return self.filter(status='deleted', deleted_at__isnull=False)
    
    def by_status(self, status):
        """Return tenants filtered by status."""
        return self.filter(status=status)
    
    def by_plan(self, plan):
        """Return tenants filtered by plan type."""
        return self.filter(plan=plan)
    
    def with_status(self):
        """Return all tenants with status information (including soft-deleted)."""
        return self.all()
    
    def available(self):
        """Return only tenants that are available for use (active or trial_expired that can be reactivated)."""
        return self.filter(status__in=['active', 'trial_expired'], deleted_at__isnull=True)
    
    def create_tenant(self, name, slug, plan='free', max_users=3, max_storage_mb=100, status='active'):
        """
        Create a new tenant with the given parameters.
        """
        return self.create(
            name=name,
            slug=slug,
            plan=plan,
            status=status,
            max_users=max_users,
            max_storage_mb=max_storage_mb,
            is_active=True
        )
    
    def soft_delete(self, tenant_id, reason="", changed_by=None):
        """
        Soft delete a tenant by setting the deleted_at timestamp.
        """
        tenant = self.get(pk=tenant_id)
        tenant.soft_delete(reason=reason, changed_by=changed_by)
        return tenant
    
    def restore(self, tenant_id, changed_by=None):
        """
        Restore a soft-deleted tenant.
        """
        tenant = self.get(pk=tenant_id)
        tenant.restore(changed_by=changed_by)
        return tenant
    
    def suspend(self, tenant_id, reason="", changed_by=None):
        """
        Suspend a tenant.
        """
        tenant = self.get(pk=tenant_id)
        tenant.suspend(reason=reason, changed_by=changed_by)
        return tenant
    
    def unsuspend(self, tenant_id, changed_by=None):
        """
        Unsuspend a tenant.
        """
        tenant = self.get(pk=tenant_id)
        tenant.unsuspend(changed_by=changed_by)
        return tenant
    
    def expire_trial(self, tenant_id, changed_by=None):
        """
        Mark a tenant's trial as expired.
        """
        tenant = self.get(pk=tenant_id)
        tenant.expire_trial(changed_by=changed_by)
        return tenant
    
    def bulk_soft_delete(self, tenant_ids, reason="", changed_by=None):
        """
        Bulk soft delete multiple tenants.
        """
        count = 0
        for tenant_id in tenant_ids:
            try:
                self.soft_delete(tenant_id, reason=reason, changed_by=changed_by)
                count += 1
            except self.model.DoesNotExist:
                continue
        return count
    
    def bulk_restore(self, tenant_ids, changed_by=None):
        """
        Bulk restore multiple tenants.
        """
        count = 0
        for tenant_id in tenant_ids:
            try:
                self.restore(tenant_id, changed_by=changed_by)
                count += 1
            except self.model.DoesNotExist:
                continue
        return count
    
    def bulk_suspend(self, tenant_ids, reason="", changed_by=None):
        """
        Bulk suspend multiple tenants.
        """
        count = 0
        for tenant_id in tenant_ids:
            try:
                self.suspend(tenant_id, reason=reason, changed_by=changed_by)
                count += 1
            except self.model.DoesNotExist:
                continue
        return count
    
    def bulk_unsuspend(self, tenant_ids, changed_by=None):
        """
        Bulk unsuspend multiple tenants.
        """
        count = 0
        for tenant_id in tenant_ids:
            try:
                self.unsuspend(tenant_id, changed_by=changed_by)
                count += 1
            except self.model.DoesNotExist:
                continue
        return count
    
    def get_by_slug_or_404(self, slug):
        """
        Get a tenant by slug or raise Http404.
        Excludes deleted tenants by default.
        """
        from django.http import Http404
        try:
            return self.active().get(slug=slug)
        except self.model.DoesNotExist:
            raise Http404(f"Tenant '{slug}' not found or is inactive")
    
    def get_by_slug_any_status(self, slug):
        """
        Get a tenant by slug regardless of status.
        """
        try:
            return self.get(slug=slug)
        except self.model.DoesNotExist:
            return None