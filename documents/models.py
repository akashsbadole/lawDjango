import os
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from .managers import DocumentManager

User = get_user_model()


def document_upload_path(instance, filename):
    """
    Generate a tenant-specific upload path for documents.
    Format: tenant_slug/documents/year/month/filename
    """
    tenant_slug = instance.tenant.slug if instance.tenant else 'unknown'
    now = timezone.now()
    return f"{tenant_slug}/documents/{now.year}/{now.month:02d}/{filename}"


class Document(models.Model):
    """
    Model representing a document in a law firm with tenant isolation.
    """
    CATEGORY_CHOICES = [
        ('contract', 'Contract'),
        ('evidence', 'Evidence'),
        ('correspondence', 'Correspondence'),
        ('court_filing', 'Court Filing'),
        ('discovery', 'Discovery'),
        ('motion', 'Motion'),
        ('brief', 'Brief'),
        ('research', 'Research'),
        ('note', 'Note'),
        ('other', 'Other'),
    ]
    
    DOCUMENT_TYPE_CHOICES = [
        ('pdf', 'PDF'),
        ('word', 'Word Document'),
        ('excel', 'Excel Spreadsheet'),
        ('powerpoint', 'PowerPoint Presentation'),
        ('image', 'Image'),
        ('text', 'Text File'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('other', 'Other'),
    ]
    
    ACCESS_LEVEL_CHOICES = [
        ('public', 'Public'),
        ('internal', 'Internal'),
        ('confidential', 'Confidential'),
        ('restricted', 'Restricted'),
    ]
    
    # Basic Document Information
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    
    # File Information
    file = models.FileField(
        upload_to=document_upload_path,
        max_length=500
    )
    file_name = models.CharField(max_length=255)  # Original filename
    file_size = models.BigIntegerField()  # File size in bytes
    file_type = models.CharField(
        max_length=20,
        choices=DOCUMENT_TYPE_CHOICES,
        default='other'
    )
    mime_type = models.CharField(max_length=100, blank=True, null=True)
    
    # Document Classification
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='other'
    )
    access_level = models.CharField(
        max_length=20,
        choices=ACCESS_LEVEL_CHOICES,
        default='internal'
    )
    
    # Relationships
    case = models.ForeignKey(
        'cases.Case',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documents'
    )
    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documents'
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_documents'
    )
    
    # Document Organization
    tags = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Comma-separated tags for categorization"
    )
    
    # Version Tracking
    version = models.PositiveIntegerField(default=1)
    parent_document = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='versions'
    )
    is_latest_version = models.BooleanField(default=True)
    
    # Tenant and Audit Fields
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='documents'
    )
    
    # Timestamps and Soft Delete
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    objects = DocumentManager()
    
    class Meta:
        db_table = 'documents'
        verbose_name = 'Document'
        verbose_name_plural = 'Documents'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'deleted_at']),
            models.Index(fields=['tenant', 'case']),
            models.Index(fields=['tenant', 'client']),
            models.Index(fields=['tenant', 'category']),
            models.Index(fields=['tenant', 'access_level']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.file_name})"
    
    @property
    def is_deleted(self):
        """Check if the document is soft-deleted."""
        return self.deleted_at is not None
    
    @property
    def file_extension(self):
        """Return the file extension."""
        return os.path.splitext(self.file_name)[1].lower()
    
    @property
    def file_size_mb(self):
        """Return file size in MB."""
        return round(self.file_size / (1024 * 1024), 2)
    
    @property
    def tag_list(self):
        """Return tags as a list."""
        if self.tags:
            return [tag.strip() for tag in self.tags.split(',')]
        return []
    
    def save(self, *args, **kwargs):
        # Set file metadata if file is provided
        if self.file and not self.file_name:
            self.file_name = os.path.basename(self.file.name)
            self.file_size = self.file.size
            
            # Determine MIME type and document type
            import mimetypes
            mime_type, _ = mimetypes.guess_type(self.file_name)
            self.mime_type = mime_type or 'application/octet-stream'
            
            # Determine document type based on MIME type or extension
            if mime_type:
                if 'pdf' in mime_type:
                    self.file_type = 'pdf'
                elif 'word' in mime_type or 'docx' in self.file_name or 'doc' in self.file_name:
                    self.file_type = 'word'
                elif 'excel' in mime_type or 'xlsx' in self.file_name or 'xls' in self.file_name:
                    self.file_type = 'excel'
                elif 'powerpoint' in mime_type or 'pptx' in self.file_name or 'ppt' in self.file_name:
                    self.file_type = 'powerpoint'
                elif 'image' in mime_type:
                    self.file_type = 'image'
                elif 'text' in mime_type:
                    self.file_type = 'text'
                elif 'video' in mime_type:
                    self.file_type = 'video'
                elif 'audio' in mime_type:
                    self.file_type = 'audio'
        
        super().save(*args, **kwargs)
    
    def soft_delete(self):
        """Mark the document as deleted without actually removing it from the database."""
        self.deleted_at = timezone.now()
        self.save()
    
    def restore(self):
        """Restore a soft-deleted document."""
        self.deleted_at = None
        self.save()
    
    def create_new_version(self, new_file, user=None):
        """
        Create a new version of this document.
        """
        # Mark current version as not latest
        self.is_latest_version = False
        self.save()
        
        # Create new version
        new_version = Document.objects.create(
            title=self.title,
            description=self.description,
            file=new_file,
            category=self.category,
            access_level=self.access_level,
            case=self.case,
            client=self.client,
            uploaded_by=user,
            tags=self.tags,
            version=self.version + 1,
            parent_document=self,
            is_latest_version=True,
            tenant=self.tenant
        )
        
        return new_version
    
    def get_absolute_url(self):
        """Return the absolute URL for this document."""
        from django.urls import reverse
        return reverse('documents:detail', kwargs={'pk': self.pk})
    
    def get_download_url(self):
        """Return the download URL for this document."""
        from django.urls import reverse
        return reverse('documents:download', kwargs={'pk': self.pk})
    
    def can_be_accessed_by(self, user):
        """
        Check if a user can access this document based on access level.
        """
        if user.is_superuser:
            return True
        
        # Users can always access their own uploaded documents
        if self.uploaded_by == user:
            return True
        
        # Check if user belongs to the same tenant
        if user.tenant != self.tenant:
            return False
        
        # Check access level
        if self.access_level == 'public':
            return True
        elif self.access_level == 'internal':
            return True  # All tenant members can access internal documents
        elif self.access_level == 'confidential':
            # Only lawyers and admins can access confidential documents
            return user.role in ['admin', 'lawyer']
        elif self.access_level == 'restricted':
            # Only admins and assigned lawyers can access restricted documents
            if user.role == 'admin':
                return True
            if user.role == 'lawyer' and self.case and self.case.assigned_lawyers.filter(pk=user.pk).exists():
                return True
        
        return False
    
    def check_storage_quota(self):
        """
        Check if uploading this document would exceed the tenant's storage quota.
        """
        tenant_storage_used = self.tenant.get_storage_used()
        available_storage = self.tenant.max_storage_mb * 1024 * 1024  # Convert MB to bytes
        
        return (tenant_storage_used + self.file_size) <= available_storage
