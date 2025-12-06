from django.db import models
from django.utils import timezone


class ClientRequestManager(models.Manager):
    """
    Custom manager for ClientRequest model with tenant-aware methods.
    """
    def get_queryset(self):
        """Override default queryset to exclude soft-deleted requests."""
        return super().get_queryset().filter(deleted_at__isnull=True)
    
    def all_with_deleted(self):
        """Get all requests including soft-deleted ones."""
        return super().get_queryset()
    
    def deleted(self):
        """Get only soft-deleted requests."""
        return super().get_queryset().filter(deleted_at__isnull=False)
    
    def for_tenant(self, tenant):
        """Get requests for a specific tenant."""
        return self.get_queryset().filter(tenant=tenant)
    
    def active_for_tenant(self, tenant):
        """Get active (non-deleted) requests for a specific tenant."""
        return self.for_tenant(tenant)
    
    def by_status(self, status, tenant=None):
        """Get requests by status."""
        queryset = self.get_queryset()
        if status:
            queryset = queryset.filter(status=status)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def by_priority(self, priority, tenant=None):
        """Get requests by priority."""
        queryset = self.get_queryset()
        if priority:
            queryset = queryset.filter(priority=priority)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def by_request_type(self, request_type, tenant=None):
        """Get requests by request type."""
        queryset = self.get_queryset()
        if request_type:
            queryset = queryset.filter(request_type=request_type)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def pending(self, tenant=None):
        """Get pending requests."""
        return self.by_status('pending', tenant)
    
    def under_review(self, tenant=None):
        """Get requests under review."""
        return self.by_status('under_review', tenant)
    
    def approved(self, tenant=None):
        """Get approved requests."""
        return self.by_status('approved', tenant)
    
    def rejected(self, tenant=None):
        """Get rejected requests."""
        return self.by_status('rejected', tenant)
    
    def converted(self, tenant=None):
        """Get converted requests."""
        return self.by_status('converted', tenant)
    
    def urgent(self, tenant=None):
        """Get urgent requests."""
        return self.by_priority('urgent', tenant)
    
    def high_priority(self, tenant=None):
        """Get high priority requests."""
        return self.by_priority('high', tenant)
    
    def assigned_to(self, user, tenant=None):
        """Get requests assigned to a specific user."""
        queryset = self.get_queryset().filter(assigned_lawyer=user)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def reviewed_by(self, user, tenant=None):
        """Get requests reviewed by a specific user."""
        queryset = self.get_queryset().filter(reviewed_by=user)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def created_by(self, user, tenant=None):
        """Get requests created by a specific user."""
        queryset = self.get_queryset().filter(created_by=user)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def can_be_reviewed(self, tenant=None):
        """Get requests that can be reviewed."""
        return self.by_status('pending', tenant)
    
    def can_be_approved(self, tenant=None):
        """Get requests that can be approved."""
        return self.get_queryset().filter(status__in=['pending', 'under_review'])
    
    def needs_action(self, tenant=None):
        """Get requests that need action (pending or under review)."""
        return self.get_queryset().filter(status__in=['pending', 'under_review'])
    
    def search(self, query, tenant=None):
        """Search requests by title, description, client name, or email."""
        queryset = self.get_queryset()
        if query:
            queryset = queryset.filter(
                models.Q(title__icontains=query) |
                models.Q(description__icontains=query) |
                models.Q(client_name__icontains=query) |
                models.Q(client_email__icontains=query) |
                models.Q(client_company__icontains=query)
            )
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset.distinct()
    
    def created_between(self, start_date, end_date, tenant=None):
        """Get requests created between two dates."""
        queryset = self.get_queryset()
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def get_statistics(self, tenant=None):
        """Get statistics for requests."""
        queryset = self.for_tenant(tenant) if tenant else self.get_queryset()
        
        return {
            'total': queryset.count(),
            'pending': queryset.filter(status='pending').count(),
            'under_review': queryset.filter(status='under_review').count(),
            'approved': queryset.filter(status='approved').count(),
            'rejected': queryset.filter(status='rejected').count(),
            'converted': queryset.filter(status='converted').count(),
            'urgent': queryset.filter(priority='urgent').count(),
            'high': queryset.filter(priority='high').count(),
            'medium': queryset.filter(priority='medium').count(),
            'low': queryset.filter(priority='low').count(),
        }


class RequestNoteManager(models.Manager):
    """
    Custom manager for RequestNote model with tenant-aware methods.
    """
    def get_queryset(self):
        """Override default queryset."""
        return super().get_queryset()
    
    def for_tenant(self, tenant):
        """Get notes for a specific tenant."""
        return self.get_queryset().filter(tenant=tenant)
    
    def for_request(self, request):
        """Get notes for a specific request."""
        return self.get_queryset().filter(request=request)
    
    def internal(self, tenant=None):
        """Get internal notes only."""
        queryset = self.get_queryset().filter(is_internal=True)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def public(self, tenant=None):
        """Get public notes only."""
        queryset = self.get_queryset().filter(is_internal=False)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def by_user(self, user, tenant=None):
        """Get notes created by a specific user."""
        queryset = self.get_queryset().filter(created_by=user)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def recent(self, days=7, tenant=None):
        """Get notes created in the last N days."""
        since_date = timezone.now() - timezone.timedelta(days=days)
        queryset = self.get_queryset().filter(created_at__gte=since_date)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def search(self, query, tenant=None):
        """Search notes by content."""
        queryset = self.get_queryset()
        if query:
            queryset = queryset.filter(note__icontains=query)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset