from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from .managers import ClientManager

User = get_user_model()


class Client(models.Model):
    """
    Model representing a client in a law firm with tenant isolation.
    """
    # Basic Information
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    
    # Professional Information
    company = models.CharField(max_length=255, blank=True, null=True)
    occupation = models.CharField(max_length=255, blank=True, null=True)
    
    # Legal-specific Fields
    case_history = models.TextField(blank=True, null=True, help_text="Brief history of legal cases")
    notes = models.TextField(blank=True, null=True, help_text="Additional notes about the client")
    
    # Tenant and Audit Fields
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='clients'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_clients'
    )
    
    # Timestamps and Soft Delete
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    objects = ClientManager()
    
    class Meta:
        db_table = 'clients'
        verbose_name = 'Client'
        verbose_name_plural = 'Clients'
        ordering = ['-created_at']
        unique_together = [['email', 'tenant']]  # Email should be unique per tenant
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"
    
    @property
    def full_name(self):
        """Return the full name of the client."""
        return f"{self.first_name} {self.last_name}"
    
    @property
    def is_deleted(self):
        """Check if the client is soft-deleted."""
        return self.deleted_at is not None
    
    def soft_delete(self):
        """Mark the client as deleted without actually removing it from the database."""
        self.deleted_at = timezone.now()
        self.save()
    
    def restore(self):
        """Restore a soft-deleted client."""
        self.deleted_at = None
        self.save()
    
    def get_absolute_url(self):
        """Return the absolute URL for this client."""
        from django.urls import reverse
        return reverse('clients:detail', kwargs={'pk': self.pk})
