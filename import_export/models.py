import json
import os
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.core.validators import RegexValidator
from .managers import ImportJobManager, ExportJobManager, ImportTemplateManager

User = get_user_model()


def import_file_upload_path(instance, filename):
    """
    Generate a tenant-specific upload path for import files.
    Format: tenant_slug/imports/year/month/filename
    """
    tenant_slug = instance.tenant.slug if instance.tenant else 'unknown'
    now = timezone.now()
    return f"{tenant_slug}/imports/{now.year}/{now.month:02d}/{filename}"


def export_file_upload_path(instance, filename):
    """
    Generate a tenant-specific upload path for export files.
    Format: tenant_slug/exports/year/month/filename
    """
    tenant_slug = instance.tenant.slug if instance.tenant else 'unknown'
    now = timezone.now()
    return f"{tenant_slug}/exports/{now.year}/{now.month:02d}/{filename}"


class ImportJob(models.Model):
    """
    Model representing an import job for tenant data.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    MODEL_TYPE_CHOICES = [
        ('clients', 'Clients'),
        ('cases', 'Cases'),
        ('documents', 'Documents'),
        ('billing', 'Billing'),
        ('time_entries', 'Time Entries'),
        ('expenses', 'Expenses'),
        ('invoices', 'Invoices'),
        ('payments', 'Payments'),
    ]
    
    FILE_FORMAT_CHOICES = [
        ('csv', 'CSV'),
        ('xlsx', 'Excel'),
        ('json', 'JSON'),
    ]
    
    # Basic Information
    model_type = models.CharField(max_length=20, choices=MODEL_TYPE_CHOICES)
    file_format = models.CharField(max_length=10, choices=FILE_FORMAT_CHOICES, default='csv')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # File Information
    file = models.FileField(
        upload_to=import_file_upload_path,
        max_length=500
    )
    original_filename = models.CharField(max_length=255)
    file_size = models.BigIntegerField()  # File size in bytes
    
    # Progress Tracking
    total_records = models.IntegerField(default=0)
    processed_records = models.IntegerField(default=0)
    successful_records = models.IntegerField(default=0)
    failed_records = models.IntegerField(default=0)
    
    # Error Handling
    errors = models.JSONField(default=list, blank=True)
    error_summary = models.TextField(blank=True, null=True)
    
    # Configuration
    field_mappings = models.JSONField(default=dict, blank=True)
    skip_header = models.BooleanField(default=True)
    update_existing = models.BooleanField(default=False)
    dry_run = models.BooleanField(default=False)
    
    # Tenant and Audit Fields
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='import_jobs'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='import_jobs'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    objects = ImportJobManager()
    
    class Meta:
        db_table = 'import_jobs'
        verbose_name = 'Import Job'
        verbose_name_plural = 'Import Jobs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'model_type']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Import {self.model_type} - {self.get_status_display()}"
    
    @property
    def progress_percentage(self):
        """Calculate progress percentage."""
        if self.total_records == 0:
            return 0
        return int((self.processed_records / self.total_records) * 100)
    
    @property
    def is_completed(self):
        """Check if the import job is completed."""
        return self.status in ['completed', 'failed', 'cancelled']
    
    @property
    def is_running(self):
        """Check if the import job is currently running."""
        return self.status == 'processing'
    
    @property
    def file_size_mb(self):
        """Return file size in MB."""
        return round(self.file_size / (1024 * 1024), 2)
    
    def save(self, *args, **kwargs):
        # Set file metadata if file is provided
        if self.file and not self.original_filename:
            self.original_filename = os.path.basename(self.file.name)
            self.file_size = self.file.size
        
        super().save(*args, **kwargs)
    
    def start_processing(self):
        """Mark the job as processing and set start time."""
        self.status = 'processing'
        self.started_at = timezone.now()
        self.save()
    
    def complete_processing(self):
        """Mark the job as completed and set completion time."""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()
    
    def fail_processing(self, error_summary=None):
        """Mark the job as failed and set completion time."""
        self.status = 'failed'
        self.completed_at = timezone.now()
        if error_summary:
            self.error_summary = error_summary
        self.save()
    
    def cancel_processing(self):
        """Mark the job as cancelled and set completion time."""
        self.status = 'cancelled'
        self.completed_at = timezone.now()
        self.save()
    
    def add_error(self, row_number, error_message, record_data=None):
        """Add an error to the errors list."""
        error = {
            'row': row_number,
            'error': error_message,
            'timestamp': timezone.now().isoformat()
        }
        if record_data:
            error['data'] = record_data
        
        self.errors.append(error)
        self.failed_records += 1
        self.save()


class ExportJob(models.Model):
    """
    Model representing an export job for tenant data.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    MODEL_TYPE_CHOICES = [
        ('clients', 'Clients'),
        ('cases', 'Cases'),
        ('documents', 'Documents'),
        ('billing', 'Billing'),
        ('time_entries', 'Time Entries'),
        ('expenses', 'Expenses'),
        ('invoices', 'Invoices'),
        ('payments', 'Payments'),
    ]
    
    FILE_FORMAT_CHOICES = [
        ('csv', 'CSV'),
        ('xlsx', 'Excel'),
        ('json', 'JSON'),
    ]
    
    EXPORT_TYPE_CHOICES = [
        ('all', 'All Records'),
        ('filtered', 'Filtered Records'),
        ('selected', 'Selected Records'),
    ]
    
    # Basic Information
    model_type = models.CharField(max_length=20, choices=MODEL_TYPE_CHOICES)
    export_type = models.CharField(max_length=20, choices=EXPORT_TYPE_CHOICES, default='all')
    file_format = models.CharField(max_length=10, choices=FILE_FORMAT_CHOICES, default='csv')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # File Information
    file = models.FileField(
        upload_to=export_file_upload_path,
        max_length=500,
        null=True,
        blank=True
    )
    filename = models.CharField(max_length=255, blank=True, null=True)
    file_size = models.BigIntegerField(null=True, blank=True)  # File size in bytes
    
    # Progress Tracking
    total_records = models.IntegerField(default=0)
    processed_records = models.IntegerField(default=0)
    
    # Configuration
    filters = models.JSONField(default=dict, blank=True)
    selected_ids = models.JSONField(default=list, blank=True)
    field_selection = models.JSONField(default=list, blank=True)  # List of fields to include
    include_relations = models.BooleanField(default=False)
    
    # Error Handling
    errors = models.JSONField(default=list, blank=True)
    error_summary = models.TextField(blank=True, null=True)
    
    # Tenant and Audit Fields
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='export_jobs'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='export_jobs'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    objects = ExportJobManager()
    
    class Meta:
        db_table = 'export_jobs'
        verbose_name = 'Export Job'
        verbose_name_plural = 'Export Jobs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'model_type']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Export {self.model_type} - {self.get_status_display()}"
    
    @property
    def progress_percentage(self):
        """Calculate progress percentage."""
        if self.total_records == 0:
            return 0
        return int((self.processed_records / self.total_records) * 100)
    
    @property
    def is_completed(self):
        """Check if the export job is completed."""
        return self.status in ['completed', 'failed', 'cancelled']
    
    @property
    def is_running(self):
        """Check if the export job is currently running."""
        return self.status == 'processing'
    
    @property
    def file_size_mb(self):
        """Return file size in MB."""
        if self.file_size:
            return round(self.file_size / (1024 * 1024), 2)
        return 0
    
    @property
    def download_url(self):
        """Return the download URL for the export file."""
        if self.file:
            return self.file.url
        return None
    
    def start_processing(self):
        """Mark the job as processing and set start time."""
        self.status = 'processing'
        self.started_at = timezone.now()
        self.save()
    
    def complete_processing(self):
        """Mark the job as completed and set completion time."""
        self.status = 'completed'
        self.completed_at = timezone.now()
        if self.file:
            self.file_size = self.file.size
        self.save()
    
    def fail_processing(self, error_summary=None):
        """Mark the job as failed and set completion time."""
        self.status = 'failed'
        self.completed_at = timezone.now()
        if error_summary:
            self.error_summary = error_summary
        self.save()
    
    def cancel_processing(self):
        """Mark the job as cancelled and set completion time."""
        self.status = 'cancelled'
        self.completed_at = timezone.now()
        self.save()
    
    def add_error(self, error_message):
        """Add an error to the errors list."""
        error = {
            'error': error_message,
            'timestamp': timezone.now().isoformat()
        }
        self.errors.append(error)
        self.save()


class ImportTemplate(models.Model):
    """
    Model representing import templates for different data types.
    """
    MODEL_TYPE_CHOICES = [
        ('clients', 'Clients'),
        ('cases', 'Cases'),
        ('documents', 'Documents'),
        ('billing', 'Billing'),
        ('time_entries', 'Time Entries'),
        ('expenses', 'Expenses'),
        ('invoices', 'Invoices'),
        ('payments', 'Payments'),
    ]
    
    # Basic Information
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    model_type = models.CharField(max_length=20, choices=MODEL_TYPE_CHOICES)
    
    # Template Configuration
    field_mappings = models.JSONField(default=dict)  # Maps CSV columns to model fields
    required_fields = models.JSONField(default=list)  # List of required fields
    default_values = models.JSONField(default=dict)  # Default values for fields
    validation_rules = models.JSONField(default=dict)  # Validation rules for fields
    
    # Sample File
    sample_file = models.FileField(
        upload_to='import_templates/samples/',
        null=True,
        blank=True,
        help_text="Sample CSV/Excel file for this template"
    )
    
    # Template Options
    skip_header = models.BooleanField(default=True)
    encoding = models.CharField(max_length=20, default='utf-8')
    delimiter = models.CharField(max_length=5, default=',')
    update_existing = models.BooleanField(default=False)
    
    # Tenant and Audit Fields
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='import_templates'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_import_templates'
    )
    is_public = models.BooleanField(
        default=False,
        help_text="Make this template available to all tenants"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = ImportTemplateManager()
    
    class Meta:
        db_table = 'import_templates'
        verbose_name = 'Import Template'
        verbose_name_plural = 'Import Templates'
        ordering = ['model_type', 'name']
        unique_together = [['name', 'tenant']]
        indexes = [
            models.Index(fields=['tenant', 'model_type']),
            models.Index(fields=['is_public']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_model_type_display()})"
    
    def get_field_mapping_dict(self):
        """Return field mappings as a dictionary."""
        return self.field_mappings or {}
    
    def get_required_fields_list(self):
        """Return required fields as a list."""
        return self.required_fields or []
    
    def get_default_values_dict(self):
        """Return default values as a dictionary."""
        return self.default_values or {}
    
    def get_validation_rules_dict(self):
        """Return validation rules as a dictionary."""
        return self.validation_rules or {}
    
    def validate_record(self, record_data):
        """
        Validate a record against the template rules.
        Returns a tuple of (is_valid, errors).
        """
        errors = []
        
        # Check required fields
        for field in self.get_required_fields_list():
            if field not in record_data or not record_data[field]:
                errors.append(f"Field '{field}' is required")
        
        # Apply validation rules
        validation_rules = self.get_validation_rules_dict()
        for field, rules in validation_rules.items():
            if field in record_data:
                value = record_data[field]
                
                # Check data type
                if 'type' in rules:
                    expected_type = rules['type']
                    if expected_type == 'email' and '@' not in value:
                        errors.append(f"Field '{field}' must be a valid email address")
                    elif expected_type == 'number' and not value.replace('.', '').isdigit():
                        errors.append(f"Field '{field}' must be a number")
                    elif expected_type == 'date':
                        try:
                            from datetime import datetime
                            datetime.strptime(value, rules.get('date_format', '%Y-%m-%d'))
                        except ValueError:
                            errors.append(f"Field '{field}' must be a valid date")
                
                # Check min/max length
                if 'min_length' in rules and len(value) < rules['min_length']:
                    errors.append(f"Field '{field}' must be at least {rules['min_length']} characters")
                if 'max_length' in rules and len(value) > rules['max_length']:
                    errors.append(f"Field '{field}' must be no more than {rules['max_length']} characters")
                
                # Check allowed values
                if 'choices' in rules and value not in rules['choices']:
                    errors.append(f"Field '{field}' must be one of: {', '.join(rules['choices'])}")
        
        return len(errors) == 0, errors
