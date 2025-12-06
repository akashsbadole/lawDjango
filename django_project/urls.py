from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

def lawyer_redirect(request):
    """Redirect /lawyer/ to /lawyer-panel/"""
    return redirect('lawyer_panel:dashboard')

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("accounts/", include("accounts.urls")),
    path("", include("pages.urls")),
    path("tenants/", include("tenants.urls")),
    # App URLs with tenant pattern: /app/{tenant_slug}/
    # This will be caught by the TenantMiddleware
    path("app/", include("tenants.app_urls")),
    path("subscriptions/", include("subscriptions.urls")),
    path("platform-admin/", include("platform_admin.urls")),
    path("backup-restore/", include("backup_restore.urls")),
    path("audit/", include("audit.urls")),
    path("lawyer/", lawyer_redirect, name='lawyer_redirect'),
    path("lawyer-panel/", include("lawyer_panel.urls")),
    path("legal-research/", include("legal_research.urls")),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [
        path("__debug__/", include(debug_toolbar.urls)),
    ] + urlpatterns
