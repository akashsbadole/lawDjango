from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from .models import Tenant

User = get_user_model()


class DashboardWidget(models.Model):
    """
    Model representing a dashboard widget configuration.
    """
    WIDGET_TYPES = [
        ('stats_card', 'Statistics Card'),
        ('chart', 'Chart'),
        ('activity_feed', 'Activity Feed'),
        ('quick_actions', 'Quick Actions'),
        ('upcoming_deadlines', 'Upcoming Deadlines'),
        ('performance_metrics', 'Performance Metrics'),
    ]
    
    CHART_TYPES = [
        ('pie', 'Pie Chart'),
        ('bar', 'Bar Chart'),
        ('line', 'Line Chart'),
        ('doughnut', 'Doughnut Chart'),
    ]
    
    STAT_TYPES = [
        ('total_clients', 'Total Clients'),
        ('total_cases', 'Total Cases'),
        ('total_documents', 'Total Documents'),
        ('total_invoices', 'Total Invoices'),
        ('active_cases', 'Active Cases'),
        ('unpaid_invoices', 'Unpaid Invoices'),
        ('monthly_revenue', 'Monthly Revenue'),
        ('storage_used', 'Storage Used'),
        ('user_count', 'User Count'),
    ]
    
    # Widget identification
    widget_type = models.CharField(max_length=20, choices=WIDGET_TYPES)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    
    # Widget configuration
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    position = models.IntegerField(default=0, help_text="Position order on dashboard")
    size = models.CharField(
        max_length=10,
        choices=[
            ('small', 'Small (1x1)'),
            ('medium', 'Medium (2x1)'),
            ('large', 'Large (2x2)'),
            ('full', 'Full Width (3x2)'),
        ],
        default='medium'
    )
    
    # Chart-specific configuration
    chart_type = models.CharField(max_length=20, choices=CHART_TYPES, blank=True, null=True)
    stat_type = models.CharField(max_length=30, choices=STAT_TYPES, blank=True, null=True)
    
    # Data configuration
    data_source = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Data source for the widget (e.g., 'cases', 'invoices', 'documents')"
    )
    date_range_days = models.IntegerField(
        default=30,
        validators=[MinValueValidator(1), MaxValueValidator(365)],
        help_text="Number of days to look back for data"
    )
    limit = models.IntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Maximum number of items to display"
    )
    
    # Filter configuration (JSON field for flexibility)
    filters = models.JSONField(
        default=dict,
        blank=True,
        help_text="Filters to apply to the widget data (JSON format)"
    )
    
    # Role-based visibility
    visible_to_roles = models.JSONField(
        default=list,
        blank=True,
        help_text="List of roles that can see this widget (empty = all roles)"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Managers will be assigned after model definition to avoid circular imports
    
    class Meta:
        db_table = 'dashboard_widgets'
        verbose_name = 'Dashboard Widget'
        verbose_name_plural = 'Dashboard Widgets'
        ordering = ['position', 'title']
    
    def __str__(self):
        return f"{self.title} ({self.get_widget_type_display()})"
    
    def is_visible_to_user(self, user):
        """Check if this widget is visible to a specific user based on their role."""
        if not self.is_active:
            return False
        
        # If no roles specified, visible to all
        if not self.visible_to_roles:
            return True
        
        # Check if user's role is in the visible roles list
        return user.role in self.visible_to_roles


class UserDashboard(models.Model):
    """
    Model representing a user's personalized dashboard configuration.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='dashboard'
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='user_dashboards'
    )
    
    # Dashboard configuration
    widgets = models.ManyToManyField(
        DashboardWidget,
        through='UserDashboardWidget',
        related_name='user_dashboards'
    )
    
    # Layout preferences
    layout = models.JSONField(
        default=dict,
        blank=True,
        help_text="Layout configuration for widgets (JSON format)"
    )
    
    # Date range preferences
    default_date_range_days = models.IntegerField(
        default=30,
        validators=[MinValueValidator(1), MaxValueValidator(365)],
        help_text="Default date range for dashboard widgets"
    )
    
    # Auto-refresh settings
    auto_refresh_enabled = models.BooleanField(default=True)
    auto_refresh_interval = models.IntegerField(
        default=300,  # 5 minutes
        validators=[MinValueValidator(30), MaxValueValidator(3600)],
        help_text="Auto-refresh interval in seconds"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_dashboards'
        verbose_name = 'User Dashboard'
        verbose_name_plural = 'User Dashboards'
        unique_together = [['user', 'tenant']]
    
    def __str__(self):
        return f"{self.user.email} - {self.tenant.name} Dashboard"


class UserDashboardWidget(models.Model):
    """
    Model representing the relationship between a user dashboard and a widget.
    """
    dashboard = models.ForeignKey(
        UserDashboard,
        on_delete=models.CASCADE,
        related_name='dashboard_widgets'
    )
    widget = models.ForeignKey(
        DashboardWidget,
        on_delete=models.CASCADE,
        related_name='dashboard_users'
    )
    
    # Widget configuration for this user
    is_active = models.BooleanField(default=True)
    position = models.IntegerField(default=0)
    size = models.CharField(
        max_length=10,
        choices=[
            ('small', 'Small (1x1)'),
            ('medium', 'Medium (2x1)'),
            ('large', 'Large (2x2)'),
            ('full', 'Full Width (3x2)'),
        ],
        default='medium'
    )
    
    # User-specific filters
    filters = models.JSONField(
        default=dict,
        blank=True,
        help_text="User-specific filters for this widget (JSON format)"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_dashboard_widgets'
        verbose_name = 'User Dashboard Widget'
        verbose_name_plural = 'User Dashboard Widgets'
        unique_together = [['dashboard', 'widget']]
        ordering = ['position']
    
    def __str__(self):
        return f"{self.dashboard} - {self.widget}"


class DashboardActivity(models.Model):
    """
    Model representing dashboard activity logs for tracking user interactions.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='dashboard_activities'
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='dashboard_activities'
    )
    
    # Activity details
    action = models.CharField(
        max_length=50,
        choices=[
            ('view', 'View Dashboard'),
            ('widget_click', 'Widget Click'),
            ('export', 'Export Data'),
            ('filter', 'Apply Filter'),
            ('customize', 'Customize Layout'),
        ]
    )
    widget_id = models.IntegerField(null=True, blank=True)
    details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional details about the activity (JSON format)"
    )
    
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'dashboard_activities'
        verbose_name = 'Dashboard Activity'
        verbose_name_plural = 'Dashboard Activities'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['action', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.action} - {self.created_at}"


# Import and assign managers after model definition to avoid circular imports
from .dashboard_managers import (
    DashboardWidgetManager, UserDashboardManager,
    UserDashboardWidgetManager, DashboardActivityManager
)

# Assign managers to models
DashboardWidget.objects = DashboardWidgetManager()
UserDashboard.objects = UserDashboardManager()
UserDashboardWidget.objects = UserDashboardWidgetManager()
DashboardActivity.objects = DashboardActivityManager()