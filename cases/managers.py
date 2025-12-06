from django.db import models
from django.utils import timezone


class CaseManager(models.Manager):
    """
    Manager for the Case model with tenant filtering and soft delete functionality.
    """
    
    def get_queryset(self):
        """
        Override the default queryset to exclude soft-deleted cases.
        """
        return super().get_queryset().filter(deleted_at__isnull=True)
    
    def all_with_deleted(self):
        """
        Return all cases including soft-deleted ones.
        """
        return super().get_queryset()
    
    def deleted(self):
        """
        Return only soft-deleted cases.
        """
        return super().get_queryset().filter(deleted_at__isnull=False)
    
    def for_tenant(self, tenant):
        """
        Filter cases by tenant.
        """
        return self.filter(tenant=tenant)
    
    def active_for_tenant(self, tenant):
        """
        Return active (non-deleted) cases for a specific tenant.
        """
        return self.filter(tenant=tenant, deleted_at__isnull=True)
    
    def open_for_tenant(self, tenant):
        """
        Return open cases for a specific tenant.
        """
        return self.filter(tenant=tenant, status='open', deleted_at__isnull=True)
    
    def closed_for_tenant(self, tenant):
        """
        Return closed cases for a specific tenant.
        """
        return self.filter(tenant=tenant, status='closed', deleted_at__isnull=True)
    
    def by_status(self, status, tenant=None):
        """
        Filter cases by status, optionally by tenant.
        """
        queryset = self.filter(status=status)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def by_case_type(self, case_type, tenant=None):
        """
        Filter cases by case type, optionally by tenant.
        """
        queryset = self.filter(case_type=case_type)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def by_client(self, client, tenant=None):
        """
        Filter cases by client, optionally by tenant.
        """
        queryset = self.filter(client=client)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def assigned_to(self, user, tenant=None):
        """
        Filter cases assigned to a specific user, optionally by tenant.
        """
        queryset = self.filter(assigned_lawyers=user)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def search(self, query, tenant=None):
        """
        Search cases by title, case number, or description.
        """
        queryset = self.all()
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        
        if query:
            queryset = queryset.filter(
                models.Q(title__icontains=query) |
                models.Q(case_number__icontains=query) |
                models.Q(description__icontains=query) |
                models.Q(client__first_name__icontains=query) |
                models.Q(client__last_name__icontains=query) |
                models.Q(client__email__icontains=query)
            )
        
        return queryset
    
    def create_case(self, tenant, user, **kwargs):
        """
        Create a new case with tenant and user information.
        """
        return self.create(
            tenant=tenant,
            created_by=user,
            **kwargs
        )
    
    def soft_delete(self, case_id):
        """
        Soft delete a case by setting the deleted_at timestamp.
        """
        case = self.get(pk=case_id)
        case.deleted_at = timezone.now()
        case.save()
        return case


class CaseEventManager(models.Manager):
    """
    Manager for the CaseEvent model with tenant filtering.
    """
    
    def for_tenant(self, tenant):
        """
        Filter case events by tenant.
        """
        return self.filter(tenant=tenant)
    
    def for_case(self, case, tenant=None):
        """
        Filter case events by case, optionally by tenant.
        """
        queryset = self.filter(case=case)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def by_event_type(self, event_type, tenant=None):
        """
        Filter case events by event type, optionally by tenant.
        """
        queryset = self.filter(event_type=event_type)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def upcoming(self, tenant=None):
        """
        Return upcoming case events (events with event_date in the future).
        """
        queryset = self.filter(event_date__gte=timezone.now())
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def past(self, tenant=None):
        """
        Return past case events (events with event_date in the past).
        """
        queryset = self.filter(event_date__lt=timezone.now())
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def today(self, tenant=None):
        """
        Return case events for today.
        """
        today = timezone.now().date()
        queryset = self.filter(event_date__date=today)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def this_week(self, tenant=None):
        """
        Return case events for this week.
        """
        today = timezone.now().date()
        start_of_week = today - timezone.timedelta(days=today.weekday())
        end_of_week = start_of_week + timezone.timedelta(days=6)
        queryset = self.filter(event_date__date__range=[start_of_week, end_of_week])
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def created_by(self, user, tenant=None):
        """
        Filter case events created by a specific user, optionally by tenant.
        """
        queryset = self.filter(created_by=user)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def search(self, query, tenant=None):
        """
        Search case events by title or description.
        """
        queryset = self.all()
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        
        if query:
            queryset = queryset.filter(
                models.Q(title__icontains=query) |
                models.Q(description__icontains=query) |
                models.Q(case__title__icontains=query) |
                models.Q(case__case_number__icontains=query)
            )
        
        return queryset
    
    def create_event(self, tenant, user, case, **kwargs):
        """
        Create a new case event with tenant and user information.
        """
        return self.create(
            tenant=tenant,
            created_by=user,
            case=case,
            **kwargs
        )