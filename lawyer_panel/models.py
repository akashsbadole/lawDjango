from typing import TYPE_CHECKING
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.contrib.auth import get_user_model
from django.urls import reverse
from decimal import Decimal
import os

if TYPE_CHECKING:
    from django.db.models.manager import Manager

User = get_user_model()


class PracticeArea(models.Model):
    """
    Model representing practice areas for lawyers.
    Tenant-aware to ensure multi-tenant isolation.
    """
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='practice_areas'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'lawyer_practice_areas'
        unique_together = ['name', 'tenant']
        verbose_name = 'Practice Area'
        verbose_name_plural = 'Practice Areas'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.tenant.name})"


class LawyerQualification(models.Model):
    """
    Model representing lawyer qualifications and certifications.
    """
    QUALIFICATION_TYPES = [
        ('degree', 'Law Degree'),
        ('masters', 'Master\'s Degree'),
        ('phd', 'PhD/Doctorate'),
        ('certificate', 'Professional Certificate'),
        ('license', 'License'),
        ('accreditation', 'Accreditation'),
        ('other', 'Other'),
    ]
    
    lawyer_profile = models.ForeignKey(
        'LawyerProfile',
        on_delete=models.CASCADE,
        related_name='qualifications'
    )
    qualification_type = models.CharField(
        max_length=20,
        choices=QUALIFICATION_TYPES
    )
    title = models.CharField(max_length=200)
    institution = models.CharField(max_length=200)
    year_obtained = models.IntegerField(
        validators=[
            MinValueValidator(1900),
            MaxValueValidator(timezone.now().year + 10)
        ]
    )
    description = models.TextField(blank=True)
    certificate_file = models.FileField(
        upload_to='lawyer_qualifications/',
        blank=True,
        null=True
    )
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='lawyer_qualifications'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'lawyer_qualifications'
        verbose_name = 'Lawyer Qualification'
        verbose_name_plural = 'Lawyer Qualifications'
        ordering = ['-year_obtained', 'title']
    
    def __str__(self):
        return f"{self.title} - {self.lawyer_profile.user.get_full_name()}"
    
    def get_certificate_filename(self):
        """Get the filename of the certificate file."""
        if self.certificate_file:
            return os.path.basename(self.certificate_file.name)
        return None


class LawyerProfile(models.Model):
    """
    Comprehensive lawyer profile model with professional information,
    billing details, and availability management.
    """
    EXPERIENCE_LEVELS = [
        ('junior', 'Junior (0-3 years)'),
        ('associate', 'Associate (3-7 years)'),
        ('senior', 'Senior (7-12 years)'),
        ('partner', 'Partner (12+ years)'),
        ('of_counsel', 'Of Counsel'),
    ]
    
    BILLING_METHODS = [
        ('hourly', 'Hourly Rate'),
        ('fixed', 'Fixed Fee'),
        ('contingency', 'Contingency'),
        ('retainer', 'Retainer'),
        ('hybrid', 'Hybrid'),
    ]
    
    # Link to CustomUser
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='lawyer_profile'
    )
    
    # Professional Information
    bar_number = models.CharField(
        max_length=50,
        blank=True,
        help_text="State bar registration number"
    )
    law_school = models.CharField(
        max_length=200,
        blank=True,
        help_text="Law school attended"
    )
    graduation_year = models.IntegerField(
        null=True,
        blank=True,
        validators=[
            MinValueValidator(1900),
            MaxValueValidator(timezone.now().year + 10)
        ]
    )
    experience_level = models.CharField(
        max_length=20,
        choices=EXPERIENCE_LEVELS,
        blank=True
    )
    years_of_experience = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )
    
    # Specialization
    practice_areas = models.ManyToManyField(
        PracticeArea,
        blank=True,
        related_name='lawyers'
    )
    specializations = models.TextField(
        blank=True,
        help_text="Comma-separated list of specializations"
    )
    
    # Billing Information
    billing_method = models.CharField(
        max_length=20,
        choices=BILLING_METHODS,
        blank=True
    )
    hourly_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    consultation_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    retainer_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    contingency_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal('0.00')),
            MaxValueValidator(Decimal('100.00'))
        ]
    )
    
    # Professional Details
    bio = models.TextField(
        blank=True,
        help_text="Professional biography"
    )
    languages = models.CharField(
        max_length=500,
        blank=True,
        help_text="Languages spoken (comma-separated)"
    )
    website = models.URLField(blank=True)
    linkedin_profile = models.URLField(blank=True)
    
    # Availability Management
    is_available = models.BooleanField(default=True)
    max_cases = models.IntegerField(
        default=20,
        validators=[MinValueValidator(1)]
    )
    current_case_load = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)]
    )
    
    # Tenant and Audit Fields
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='lawyer_profiles'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'lawyer_profiles'
        verbose_name = 'Lawyer Profile'
        verbose_name_plural = 'Lawyer Profiles'
        ordering = ['user__last_name', 'user__first_name']
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.email} - {self.tenant.name}"
    
    def save(self, *args, **kwargs):
        # Set tenant from user if not provided
        if not self.tenant and hasattr(self.user, 'tenant') and self.user.tenant:
            self.tenant = self.user.tenant
        
        # Auto-calculate years of experience if graduation year is set
        if self.graduation_year and not self.years_of_experience:
            current_year = timezone.now().year
            self.years_of_experience = max(0, current_year - self.graduation_year)
        
        super().save(*args, **kwargs)
    
    def soft_delete(self):
        """Soft delete the lawyer profile."""
        self.deleted_at = timezone.now()
        self.is_available = False
        self.save()
    
    def restore(self):
        """Restore a soft-deleted lawyer profile."""
        self.deleted_at = None
        self.save()
    
    @property
    def is_deleted(self):
        """Check if the profile is soft-deleted."""
        return self.deleted_at is not None
    
    @property
    def full_name(self):
        """Get the full name of the lawyer."""
        return self.user.get_full_name() or self.user.email
    
    @property
    def availability_percentage(self):
        """Calculate availability as a percentage."""
        if self.max_cases == 0:
            return 0
        return max(0, min(100, (1 - self.current_case_load / self.max_cases) * 100))
    
    @property
    def is_at_capacity(self):
        """Check if the lawyer is at maximum case capacity."""
        return self.current_case_load >= self.max_cases
    
    def get_languages_list(self):
        """Get languages as a list."""
        if self.languages:
            return [lang.strip() for lang in self.languages.split(',') if lang.strip()]
        return []
    
    def get_specializations_list(self):
        """Get specializations as a list."""
        if self.specializations:
            return [spec.strip() for spec in self.specializations.split(',') if spec.strip()]
        return []
    
    def get_profile_completion_percentage(self):
        """Calculate profile completion percentage."""
        fields_to_check = [
            'bar_number', 'law_school', 'graduation_year', 'experience_level',
            'years_of_experience', 'billing_method', 'hourly_rate', 'bio',
            'languages', 'website', 'linkedin_profile'
        ]
        
        completed_fields = 0
        for field in fields_to_check:
            value = getattr(self, field)
            if value:
                if isinstance(value, str) and value.strip():
                    completed_fields += 1
                elif not isinstance(value, str):
                    completed_fields += 1
        
        # Check for practice areas
        if self.practice_areas.exists():
            completed_fields += 1
        
        # Check for qualifications
        if hasattr(self, 'qualifications') and self.qualifications.exists():
            completed_fields += 1
        
        # Total fields to check (including practice_areas and qualifications)
        total_fields = len(fields_to_check) + 2
        
        return round((completed_fields / total_fields) * 100, 1)
    
    def update_case_load(self):
        """Update current case load based on assigned cases."""
        from cases.models import Case
        active_cases = Case.objects.filter(
            assigned_lawyers=self.user,
            tenant=self.tenant,
            deleted_at__isnull=True,
            status__in=['open', 'active', 'in_progress']
        ).count()
        
        self.current_case_load = active_cases
        self.save(update_fields=['current_case_load'])
    
    def validate_billing_fields(self):
        """Validate that appropriate billing fields are filled based on billing method."""
        errors = []
        
        if self.billing_method == 'hourly' and not self.hourly_rate:
            errors.append("Hourly rate is required for hourly billing method.")
        
        if self.billing_method == 'fixed' and not self.hourly_rate:
            errors.append("Base rate is required for fixed fee billing method.")
        
        if self.billing_method == 'contingency' and not self.contingency_percentage:
            errors.append("Contingency percentage is required for contingency billing method.")
        
        if self.billing_method == 'retainer' and not self.retainer_fee:
            errors.append("Retainer fee is required for retainer billing method.")
        
        if self.billing_method == 'hybrid':
            if not self.hourly_rate:
                errors.append("Hourly rate is required for hybrid billing method.")
            if not self.retainer_fee:
                errors.append("Retainer fee is required for hybrid billing method.")
        
        return errors
    
    def get_absolute_url(self):
        """Get the absolute URL for the lawyer profile."""
        return reverse('lawyer_panel:lawyer_profile_detail', kwargs={'pk': self.pk})
    
    def can_accept_new_case(self):
        """Check if the lawyer can accept a new case."""
        return self.is_available and not self.is_at_capacity
