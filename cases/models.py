from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from .managers import CaseManager, CaseEventManager

User = get_user_model()


class Case(models.Model):
    """
    Model representing a legal case in a law firm with tenant isolation.
    """
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('closed', 'Closed'),
        ('pending', 'Pending'),
        ('suspended', 'Suspended'),
        ('appealed', 'Appealed'),
        ('settled', 'Settled'),
    ]
    
    CASE_TYPE_CHOICES = [
        ('civil', 'Civil'),
        ('criminal', 'Criminal'),
        ('corporate', 'Corporate'),
        ('family', 'Family'),
        ('real_estate', 'Real Estate'),
        ('intellectual_property', 'Intellectual Property'),
        ('tax', 'Tax'),
        ('bankruptcy', 'Bankruptcy'),
        ('immigration', 'Immigration'),
        ('personal_injury', 'Personal Injury'),
        ('employment', 'Employment'),
        ('other', 'Other'),
    ]
    
    # Basic Case Information
    title = models.CharField(max_length=255)
    case_number = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    
    # Case Classification
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    case_type = models.CharField(max_length=30, choices=CASE_TYPE_CHOICES, default='civil')
    
    # Relationships
    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.CASCADE,
        related_name='cases'
    )
    assigned_lawyers = models.ManyToManyField(
        User,
        related_name='assigned_cases',
        blank=True
    )
    
    # Important Dates
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True)
    
    # Case Outcome and Notes
    outcome = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    
    # Tenant and Audit Fields
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='cases'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_cases'
    )
    
    # Timestamps and Soft Delete
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    objects = CaseManager()
    
    class Meta:
        db_table = 'cases'
        verbose_name = 'Case'
        verbose_name_plural = 'Cases'
        ordering = ['-created_at']
        unique_together = [['case_number', 'tenant']]  # Case number should be unique per tenant
    
    def __str__(self):
        return f"{self.case_number} - {self.title}"
    
    @property
    def is_deleted(self):
        """Check if the case is soft-deleted."""
        return self.deleted_at is not None
    
    @property
    def is_active(self):
        """Check if the case is active (not closed or deleted)."""
        return self.status == 'open' and not self.is_deleted
    
    @property
    def duration_days(self):
        """Calculate the duration of the case in days."""
        end = self.end_date or timezone.now().date()
        return (end - self.start_date).days
    
    def soft_delete(self):
        """Mark the case as deleted without actually removing it from the database."""
        self.deleted_at = timezone.now()
        self.save()
    
    def restore(self):
        """Restore a soft-deleted case."""
        self.deleted_at = None
        self.save()
    
    def get_absolute_url(self):
        """Return the absolute URL for this case."""
        from django.urls import reverse
        return reverse('cases:detail', kwargs={'pk': self.pk})


class CaseEvent(models.Model):
    """
    Model representing events or activities related to a case.
    """
    EVENT_TYPE_CHOICES = [
        ('hearing', 'Hearing'),
        ('filing', 'Filing'),
        ('meeting', 'Meeting'),
        ('discovery', 'Discovery'),
        ('motion', 'Motion'),
        ('settlement', 'Settlement'),
        ('judgment', 'Judgment'),
        ('appeal', 'Appeal'),
        ('note', 'Note'),
        ('deadline', 'Deadline'),
        ('other', 'Other'),
    ]
    
    # Event Information
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES, default='note')
    title = models.CharField(max_length=255)
    description = models.TextField()
    event_date = models.DateTimeField()
    
    # Relationships
    case = models.ForeignKey(
        Case,
        on_delete=models.CASCADE,
        related_name='events'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_case_events'
    )
    
    # Tenant and Audit Fields
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='case_events'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = CaseEventManager()
    
    class Meta:
        db_table = 'case_events'
        verbose_name = 'Case Event'
        verbose_name_plural = 'Case Events'
        ordering = ['-event_date']
    
    def __str__(self):
        return f"{self.event_type.title()}: {self.title} ({self.case.case_number})"
    
    def get_absolute_url(self):
        """Return the absolute URL for this event's case."""
        return self.case.get_absolute_url()
