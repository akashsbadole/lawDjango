from django.urls import path, include
from . import views
from . import dashboard_views
from . import soft_delete_views
from . import views_branding

app_name = 'tenants'

urlpatterns = [
    # Tenant registration
    path('register/', views.tenant_registration, name='tenant-registration'),
    
    # Tenant CRUD operations
    path('', views.TenantListView.as_view(), name='tenant-list'),
    path('create/', views.TenantCreateView.as_view(), name='tenant-create'),
    path('<int:pk>/', views.TenantDetailView.as_view(), name='tenant-detail'),
    path('<int:pk>/update/', views.TenantUpdateView.as_view(), name='tenant-update'),
    path('<int:pk>/delete/', views.TenantDeleteView.as_view(), name='tenant-delete'),
    
    # Tenant status management views
    path('<int:tenant_id>/suspend/', soft_delete_views.tenant_suspend, name='tenant-suspend'),
    path('<int:tenant_id>/unsuspend/', soft_delete_views.tenant_unsuspend, name='tenant-unsuspend'),
    path('<int:tenant_id>/soft-delete/', soft_delete_views.tenant_soft_delete, name='tenant-soft-delete'),
    path('<int:tenant_id>/restore/', soft_delete_views.tenant_restore, name='tenant-restore'),
    path('<int:tenant_id>/expire-trial/', soft_delete_views.tenant_expire_trial, name='tenant-expire-trial'),
    path('<int:tenant_id>/permanent-delete/', soft_delete_views.tenant_permanent_delete, name='tenant-permanent-delete'),
    path('<int:tenant_id>/status-history/', soft_delete_views.TenantStatusHistoryView.as_view(), name='tenant-status-history'),
    path('bulk-actions/', soft_delete_views.bulk_tenant_actions, name='tenant-bulk-actions'),
    
    # Tenant-specific views
    path('dashboard/<slug:slug>/', views.tenant_dashboard, name='tenant-dashboard'),
    path('dashboard/<slug:slug>/enhanced/', dashboard_views.enhanced_dashboard, name='enhanced-dashboard'),
    path('switch/<int:tenant_id>/', views.switch_tenant, name='tenant-switch'),
    
    # Dashboard AJAX endpoints
    path('widget/position/', dashboard_views.update_widget_position, name='update-widget-position'),
    path('widget/<int:widget_id>/data/', dashboard_views.widget_data, name='widget-data'),
    path('export/', dashboard_views.export_dashboard_data, name='export-dashboard'),
    
    # Tenant settings
    path('settings/<int:tenant_id>/', views.TenantSettingsDetailView.as_view(), name='tenant-settings-detail'),
    path('settings/<int:tenant_id>/update/', views.TenantSettingsUpdateView.as_view(), name='tenant-settings-update'),
    path('settings/<int:tenant_id>/logo/delete/', views.tenant_settings_logo_delete, name='tenant-settings-logo-delete'),
    path('settings/<int:tenant_id>/preview/', views.tenant_settings_preview, name='tenant-settings-preview'),
    
    # Branding assets
    path('branding/<slug:tenant_slug>/css/', views_branding.tenant_css, name='tenant-css'),
    path('branding/<slug:tenant_slug>/favicon/', views_branding.tenant_favicon, name='tenant-favicon'),
    path('branding/<slug:tenant_slug>/logo/', views_branding.tenant_logo, name='tenant-logo'),
    path('branding/<slug:tenant_slug>/login-bg/', views_branding.tenant_login_background, name='tenant-login-background'),
    path('branding/<slug:tenant_slug>/manifest.json', views_branding.tenant_manifest, name='tenant-manifest'),
    
    # Include app-specific URLs under tenant
    path('dashboard/<slug:slug>/documents/', include('documents.urls')),
    path('dashboard/<slug:slug>/cases/', include('cases.urls')),
    path('dashboard/<slug:slug>/clients/', include('clients.urls')),
    path('dashboard/<slug:slug>/import-export/', include('import_export.urls')),
]