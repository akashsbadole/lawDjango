from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from .managers import ClientRequestManager, RequestNoteManager

User = get_user_model()


class ClientRequest(models.Model):
    """
    Model representing a client request in a law firm with tenant isolation.
    """
    # Status choices
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('converted', 'Converted'),
    ]
    
    # Priority choices
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    # Request type choices
    REQUEST_TYPE_CHOICES = [
        ('consultation', 'Consultation'),
        ('representation', 'Representation'),
        ('advice', 'Legal Advice'),
        ('document_review', 'Document Review'),
        ('other', 'Other'),
    ]
    
    # Contact method choices
    CONTACT_METHOD_CHOICES = [
        ('email', 'Email'),
        ('phone', 'Phone'),
        ('video_call', 'Video Call'),
        ('in_person', 'In Person'),
    ]
    
    # Budget range choices
    BUDGET_CHOICES = [
        ('under_1000', 'Under $1,000'),
        ('1000_5000', '$1,000 - $5,000'),
        ('5000_10000', '$5,000 - $10,000'),
        ('10000_25000', '$10,000 - $25,000'),
        ('25000_50000', '$25,000 - $50,000'),
        ('over_50000', 'Over $50,000'),
        ('not_specified', 'Not Specified'),
    ]
    
    # Basic fields
    title = models.CharField(max_length=255)
    description = models.TextField()
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPE_CHOICES)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Client information
    client_name = models.CharField(max_length=255)
    client_email = models.EmailField()
    client_phone = models.CharField(max_length=20, blank=True, null=True)
    client_company = models.CharField(max_length=255, blank=True, null=True)
    
    # Request details
    preferred_contact_method = models.CharField(
        max_length=20, 
        choices=CONTACT_METHOD_CHOICES, 
        default='email'
    )
    preferred_contact_time = models.TextField(
        blank=True, 
        null=True,
        help_text="Preferred contact times (e.g., 'Weekdays 9-5', 'Evenings only')"
    )
    budget_range = models.CharField(
        max_length=20, 
        choices=BUDGET_CHOICES, 
        default='not_specified'
    )
    urgency_details = models.TextField(
        blank=True, 
        null=True,
        help_text="Details about urgency if applicable"
    )
    
    # Workflow fields
    assigned_lawyer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_requests',
        help_text="Lawyer assigned to handle this request"
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_requests',
        help_text="User who reviewed this request"
    )
    review_date = models.DateTimeField(null=True, blank=True)
    approval_date = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(
        blank=True, 
        null=True,
        help_text="Reason for rejection if applicable"
    )
    
    # Conversion tracking
    converted_to_client = models.ForeignKey(
        'clients.Client',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='converted_requests',
        help_text="Client record created from this request"
    )
    
    # Tenant and audit fields
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='client_requests'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_requests'
    )
    
    # Timestamps and Soft Delete
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    objects = ClientRequestManager()
    
    class Meta:
        db_table = 'client_requests'
        verbose_name = 'Client Request'
        verbose_name_plural = 'Client Requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'priority']),
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['client_email']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.client_name} ({self.get_status_display()})"
    
    @property
    def is_deleted(self):
        """Check if the request is soft-deleted."""
        return self.deleted_at is not None
    
    @property
    def is_pending(self):
        """Check if request is pending."""
        return self.status == 'pending'
    
    @property
    def is_under_review(self):
        """Check if request is under review."""
        return self.status == 'under_review'
    
    @property
    def is_approved(self):
        """Check if request is approved."""
        return self.status == 'approved'
    
    @property
    def is_rejected(self):
        """Check if request is rejected."""
        return self.status == 'rejected'
    
    @property
    def is_converted(self):
        """Check if request is converted to client."""
        return self.status == 'converted'
    
    @property
    def can_be_reviewed(self):
        """Check if request can be reviewed."""
        return self.status in ['pending']
    
    @property
    def can_be_approved(self):
        """Check if request can be approved."""
        return self.status in ['pending', 'under_review']
    
    @property
    def can_be_rejected(self):
        """Check if request can be rejected."""
        return self.status in ['pending', 'under_review']
    
    @property
    def can_be_converted(self):
        """Check if request can be converted to client."""
        return self.status == 'approved' and not self.converted_to_client
    
    def soft_delete(self):
        """Mark the request as deleted without actually removing it from the database."""
        self.deleted_at = timezone.now()
        self.save()
    
    def restore(self):
        """Restore a soft-deleted request."""
        self.deleted_at = None
        self.save()
    
    def submit_for_review(self, reviewed_by=None):
        """Submit request for review."""
        if self.can_be_reviewed:
            self.status = 'under_review'
            self.reviewed_by = reviewed_by
            self.review_date = timezone.now()
            self.save()
    
    def approve(self, reviewed_by=None):
        """Approve the request."""
        if self.can_be_approved:
            self.status = 'approved'
            self.reviewed_by = reviewed_by
            self.review_date = timezone.now()
            self.approval_date = timezone.now()
            self.save()
    
    def reject(self, reason="", reviewed_by=None):
        """Reject the request with a reason."""
        if self.can_be_rejected:
            self.status = 'rejected'
            self.rejection_reason = reason
            self.reviewed_by = reviewed_by
            self.review_date = timezone.now()
            self.save()
    
    def convert_to_client(self, client, converted_by=None):
        """Convert request to a client record."""
        if self.can_be_converted:
            self.status = 'converted'
            self.converted_to_client = client
            self.save()
    
    def get_priority_display_with_icon(self):
        """Get priority display with appropriate icon."""
        priority_icons = {
            'low': '<span class="badge bg-secondary">↓ Low</span>',
            'medium': '<span class="badge bg-info">→ Medium</span>',
            'high': '<span class="badge bg-warning">↑ High</span>',
            'urgent': '<span class="badge bg-danger">⚡ Urgent</span>',
        }
        return priority_icons.get(self.priority, self.priority)
    
    def get_status_display_with_icon(self):
        """Get status display with appropriate icon."""
        status_icons = {
            'pending': '<span class="badge bg-warning">⏳ Pending</span>',
            'under_review': '<span class="badge bg-info">👁️ Under Review</span>',
            'approved': '<span class="badge bg-success">✓ Approved</span>',
            'rejected': '<span class="badge bg-danger">✗ Rejected</span>',
            'converted': '<span class="badge bg-primary">👤 Converted</span>',
        }
        return status_icons.get(self.status, self.status)
    
    def get_absolute_url(self):
        """Return the absolute URL for this request."""
        from django.urls import reverse
        return reverse('client_requests:detail', kwargs={'pk': self.pk})


class RequestNote(models.Model):
    """
    Model representing notes attached to a client request.
    """
    request = models.ForeignKey(
        ClientRequest,
        on_delete=models.CASCADE,
        related_name='notes'
    )
    note = models.TextField()
    is_internal = models.BooleanField(
        default=True,
        help_text="Internal notes are only visible to staff, not to clients"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='request_notes'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='request_notes'
    )
    
    objects = RequestNoteManager()
    
    class Meta:
        db_table = 'request_notes'
        verbose_name = 'Request Note'
        verbose_name_plural = 'Request Notes'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['request', 'created_at']),
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['is_internal']),
        ]
    
    def __str__(self):
        return f"Note for {self.request.title} by {self.created_by or 'System'}"
    
    @property
    def is_recent(self):
        """Check if note was created in the last 24 hours."""
        return (timezone.now() - self.created_at).days == 0
    
    def get_created_by_display(self):
        """Get display name for creator."""
        if self.created_by:
            return f"{self.created_by.first_name} {self.created_by.last_name}".strip() or self.created_by.email
        return "System"
