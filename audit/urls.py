from django.urls import path
from . import views

app_name = 'audit'

urlpatterns = [
    # Dashboard
    path('', views.AuditDashboardView.as_view(), name='dashboard'),
    
    # Audit Logs
    path('audit-logs/', views.AuditLogListView.as_view(), name='audit_logs'),
    path('audit-logs/<int:pk>/', views.AuditLogDetailView.as_view(), name='audit_log_detail'),
    
    # Activity Logs
    path('activity-logs/', views.ActivityLogListView.as_view(), name='activity_logs'),
    
    # Security Events
    path('security-events/', views.SecurityEventListView.as_view(), name='security_events'),
    path('security-events/<int:pk>/', views.SecurityEventDetailView.as_view(), name='security_event_detail'),
    path('security-events/<int:event_id>/resolve/', views.resolve_security_event, name='resolve_security_event'),
    path('security-events/bulk-resolve/', views.bulk_resolve_security_events, name='bulk_resolve_security_events'),
    
    # Login Logs
    path('login-logs/', views.LoginLogListView.as_view(), name='login_logs'),
    
    # Export
    path('export/', views.AuditExportView.as_view(), name='export'),
]