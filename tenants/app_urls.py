from django.urls import path, include
from . import views

app_name = 'tenant_app'

# These URLs will be included under /app/{tenant_slug}/
# The TenantMiddleware will extract the tenant_slug and set request.tenant
urlpatterns = [
    # Tenant dashboard
    path('', views.tenant_dashboard, name='dashboard'),
    
    # Client URLs
    path('clients/', include('clients.urls')),
    
    # Cases URLs
    path('cases/', include('cases.urls')),
    
    # Documents URLs
    path('documents/', include('documents.urls')),
    
    # Billing URLs
    path('billing/', include('billing.urls')),
    
    # Permissions URLs
    path('permissions/', include('permissions.urls')),
    
    # Import/Export URLs
    path('import-export/', include('import_export.urls')),
]