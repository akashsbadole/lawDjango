from django.db import models
from django.utils import timezone
from datetime import timedelta
from .dashboard_models import DashboardWidget, UserDashboard, UserDashboardWidget, DashboardActivity


class DashboardWidgetManager(models.Manager):
    """Manager for DashboardWidget model."""
    
    def active(self):
        """Get all active widgets."""
        return self.filter(is_active=True)
    
    def default(self):
        """Get all default widgets."""
        return self.filter(is_default=True)
    
    def for_role(self, role):
        """Get widgets visible to a specific role."""
        return self.filter(
            models.Q(visible_to_roles__contains=role) | 
            models.Q(visible_to_roles__len=0)
        ).distinct()
    
    def for_user(self, user):
        """Get widgets visible to a specific user."""
        return self.for_role(user.role).active()


class UserDashboardManager(models.Manager):
    """Manager for UserDashboard model."""
    
    def for_tenant(self, tenant):
        """Get dashboards for a specific tenant."""
        return self.filter(tenant=tenant)
    
    def get_or_create_for_user(self, user):
        """Get or create a dashboard for a user."""
        if hasattr(user, 'tenant') and user.tenant:
            dashboard, created = self.get_or_create(
                user=user,
                tenant=user.tenant
            )
            
            # If this is a new dashboard, add default widgets
            if created:
                self._add_default_widgets(dashboard, user)
            
            return dashboard
        return None
    
    def _add_default_widgets(self, dashboard, user):
        """Add default widgets to a new dashboard."""
        default_widgets = DashboardWidget.objects.default().active()
        
        for widget in default_widgets:
            # Check if widget is visible to user
            if widget.is_visible_to_user(user):
                UserDashboardWidget.objects.create(
                    dashboard=dashboard,
                    widget=widget,
                    position=widget.position,
                    size=widget.size
                )


class UserDashboardWidgetManager(models.Manager):
    """Manager for UserDashboardWidget model."""
    
    def active(self):
        """Get all active dashboard widgets."""
        return self.filter(is_active=True)
    
    def for_dashboard(self, dashboard):
        """Get widgets for a specific dashboard."""
        return self.active().filter(dashboard=dashboard)
    
    def ordered(self):
        """Get widgets ordered by position."""
        return self.order_by('position')


class DashboardActivityManager(models.Manager):
    """Manager for DashboardActivity model."""
    
    def for_tenant(self, tenant):
        """Get activities for a specific tenant."""
        return self.filter(tenant=tenant)
    
    def for_user(self, user):
        """Get activities for a specific user."""
        return self.filter(user=user)
    
    def recent(self, days=7):
        """Get recent activities within the specified number of days."""
        since_date = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=since_date)
    
    def by_action(self, action):
        """Get activities by action type."""
        return self.filter(action=action)
    
    def log_activity(self, user, action, tenant=None, widget_id=None, details=None):
        """Log a dashboard activity."""
        if not tenant and hasattr(user, 'tenant'):
            tenant = user.tenant
        
        return self.create(
            user=user,
            tenant=tenant,
            action=action,
            widget_id=widget_id,
            details=details or {}
        )