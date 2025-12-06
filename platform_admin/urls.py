from django.urls import path
from . import views

app_name = 'platform_admin'

urlpatterns = [
    # Dashboard
    path('', views.SuperAdminDashboardView.as_view(), name='dashboard'),
    
    # Tenant Management
    path('tenants/', views.TenantListView.as_view(), name='tenant_list'),
    path('tenants/<int:pk>/', views.TenantDetailView.as_view(), name='tenant_detail'),
    path('tenants/<int:pk>/edit/', views.TenantEditView.as_view(), name='tenant_edit'),
    path('tenants/bulk-action/', views.bulk_tenant_action, name='tenant_bulk_action'),
    
    # User Management
    path('users/', views.UserListView.as_view(), name='user_list'),
    
    # System Settings
    path('settings/', views.SystemSettingsView.as_view(), name='system_settings'),
    
    # Admin Notes
    path('notes/', views.AdminNoteListView.as_view(), name='note_list'),
    path('notes/create/', views.AdminNoteCreateView.as_view(), name='note_create'),
    
    # System Announcements
    path('announcements/', views.SystemAnnouncementListView.as_view(), name='announcement_list'),
    path('announcements/create/', views.SystemAnnouncementCreateView.as_view(), name='announcement_create'),
    
    # System Health
    path('health/', views.SystemHealthView.as_view(), name='system_health'),
    
    # Revenue Reports
    path('revenue/', views.RevenueReportView.as_view(), name='revenue_report'),
    
    # Activity Logs
    path('activity/', views.ActivityLogView.as_view(), name='activity_log'),
    
    # Data Export
    path('export/', views.export_data, name='export_data'),
    
    # API Endpoints
    path('api/system-status/', views.api_system_status, name='api_system_status'),
    path('api/tenant-metrics/', views.api_tenant_metrics, name='api_tenant_metrics'),
]