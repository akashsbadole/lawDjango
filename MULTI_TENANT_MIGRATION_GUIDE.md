# Multi-Tenant Migration Guide

This guide provides instructions for migrating an existing single-tenant Django application to use the multi-tenant configuration.

## Overview

The multi-tenant system allows multiple law firms (tenants) to use the same application while keeping their data completely isolated. This migration guide will help you update your existing application to support multiple tenants.

## Prerequisites

1. **Backup Your Data**: Before starting the migration, create a complete backup of your database and media files.
2. **Install Dependencies**: Ensure all required dependencies are installed:
   ```
   pip install python-decouple django-redis
   ```
3. **Environment Configuration**: Set up environment variables for your deployment environment.

## Migration Steps

### 1. Update Settings

1. Replace your existing `settings.py` with the new multi-tenant settings
2. Configure environment variables for your deployment:
   ```bash
   # Database configuration
   DB_ENGINE=django.db.backends.postgresql
   DB_NAME=your_database_name
   DB_USER=your_database_user
   DB_PASSWORD=your_database_password
   DB_HOST=your_database_host
   DB_PORT=5432
   
   # Redis configuration (recommended for production)
   REDIS_URL=redis://localhost:6379/1
   USE_REDIS_CACHE=True
   
   # Email configuration
   EMAIL_HOST=your_smtp_host
   EMAIL_PORT=587
   EMAIL_USE_TLS=True
   EMAIL_HOST_USER=your_smtp_username
   EMAIL_HOST_PASSWORD=your_smtp_password
   
   # Environment
   ENVIRONMENT=production
   SECRET_KEY=your_secret_key
   DEBUG=False
   ```

### 2. Database Migration

1. **Create a Default Tenant**:
   ```python
   from tenants.models import Tenant, TenantSettings
   
   # Create the default tenant
   default_tenant = Tenant.objects.create(
       name="Default Law Firm",
       slug="default",
       plan="professional",
       max_users=50,
       max_storage_mb=10240,  # 10GB
       is_active=True,
       status='active'
   )
   
   # Create default tenant settings
   TenantSettings.objects.create(tenant=default_tenant)
   ```

2. **Update Existing Users**:
   ```python
   from accounts.models import CustomUser
   
   # Assign existing users to the default tenant
   CustomUser.objects.all().update(tenant=default_tenant)
   ```

3. **Run Migrations**:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

### 3. Update Models

1. **Add Tenant Field to Models**:
   ```python
   from django.db import models
   from tenants.models import Tenant
   
   class YourModel(models.Model):
       tenant = models.ForeignKey(
           Tenant,
           on_delete=models.CASCADE,
           related_name='yourmodel_set'
       )
       
       # Add _tenant_aware attribute for router
       _tenant_aware = True
       
       # Other fields...
       name = models.CharField(max_length=100)
       created_at = models.DateTimeField(auto_now_add=True)
   ```

2. **Update Model Managers**:
   ```python
   from django.db import models
   from tenants.models import Tenant
   
   class YourModelManager(models.Manager):
       def get_queryset(self):
           # Filter by current tenant if available
           from tenants.utils import get_current_tenant
           tenant = get_current_tenant()
           if tenant:
               return super().get_queryset().filter(tenant=tenant)
           return super().get_queryset()
   
   class YourModel(models.Model):
       tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
       _tenant_aware = True
       
       objects = YourModelManager()
   ```

### 4. Update URLs

1. **Update URL Configuration**:
   ```python
   # In your main urls.py
   from django.urls import path, include
   
   urlpatterns = [
       # Tenant-specific URLs
       path('app/<slug:tenant_slug>/', include('your_app.urls')),
       
       # Admin URLs
       path('admin/', admin.site.urls),
       
       # Authentication URLs
       path('accounts/', include('allauth.urls')),
   ]
   ```

2. **Update App URLs**:
   ```python
   # In your app urls.py
   from django.urls import path
   
   urlpatterns = [
       path('', views.dashboard, name='dashboard'),
       path('clients/', views.client_list, name='client_list'),
       # Other URLs...
   ]
   ```

### 5. Update Views

1. **Add Tenant Context to Views**:
   ```python
   from django.shortcuts import get_object_or_404
   from tenants.models import Tenant
   
   def your_view(request, tenant_slug):
       # Get the tenant
       tenant = get_object_or_404(Tenant, slug=tenant_slug)
       
       # Set the tenant on the request
       request.tenant = tenant
       
       # Your view logic...
       return render(request, 'template.html', context)
   ```

2. **Update Class-Based Views**:
   ```python
   from django.views.generic import TemplateView
   from tenants.mixins import TenantMixin
   
   class YourView(TenantMixin, TemplateView):
       template_name = 'template.html'
       
       def get_context_data(self, **kwargs):
           context = super().get_context_data(**kwargs)
           # Tenant is automatically available as self.tenant
           context['tenant'] = self.tenant
           return context
   ```

### 6. Update Templates

1. **Create Tenant-Specific Templates**:
   ```html
   <!-- templates/tenants/default/dashboard.html -->
   {% extends "base.html" %}
   
   {% block branding %}
       <img src="{{ logo_url }}" alt="{{ company_name }}">
       <style>
           :root {
               --brand-primary: {{ brand_colors.primary }};
               --brand-secondary: {{ brand_colors.secondary }};
           }
       </style>
   {% endblock %}
   
   {% block content %}
       <h1>Welcome to {{ company_name }}</h1>
       <p>{{ dashboard_welcome_message }}</p>
   {% endblock %}
   ```

2. **Update Base Template**:
   ```html
   <!-- templates/base.html -->
   {% load static %}
   
   <html>
   <head>
       <title>{% block title %}{{ company_name }}{% endblock %}</title>
       
       <!-- Tenant-specific CSS -->
       {% if css_url %}
       <link rel="stylesheet" href="{{ css_url }}">
       {% endif %}
       
       <!-- Custom CSS -->
       {% if custom_css %}
       <style>{{ custom_css|safe }}</style>
       {% endif %}
   </head>
   <body>
       {% block content %}{% endblock %}
   </body>
   </html>
   ```

### 7. Update Forms

1. **Use Tenant Context in Forms**:
   ```python
   from django import forms
   from tenants.models import Tenant
   
   class YourForm(forms.ModelForm):
       def __init__(self, *args, **kwargs):
           # Get the tenant from kwargs
           self.tenant = kwargs.pop('tenant', None)
           super().__init__(*args, **kwargs)
           
           # Customize form based on tenant
           if self.tenant:
               self.fields['some_field'].widget.attrs.update({
                   'placeholder': self.tenant.settings.get_custom_placeholder()
               })
   ```

### 8. Update Static Files

1. **Organize Static Files by Tenant**:
   ```
   static/
   ├── tenants/
   │   ├── default/
   │   │   ├── css/
   │   │   ├── js/
   │   │   └── images/
   │   └── tenant2/
   │       ├── css/
   │       ├── js/
   │       └── images/
   └── global/
       ├── css/
       ├── js/
       └── images/
   ```

2. **Update Static File References**:
   ```html
   {% load static %}
   
   <!-- Tenant-specific static file -->
   <link rel="stylesheet" href="{% static 'tenants/'|add:tenant.slug|add:'/css/style.css' %}">
   
   <!-- Global static file -->
   <script src="{% static 'global/js/app.js' %}"></script>
   ```

## Post-Migration Steps

### 1. Test the Migration

1. **Verify Tenant Isolation**:
   - Check that users can only access their own data
   - Verify that cross-tenant data access is prevented
   - Test tenant-specific branding and settings

2. **Test Authentication**:
   - Verify users can log in with tenant-specific URLs
   - Test that sessions are properly isolated
   - Check that password reset works correctly

3. **Test Email Functionality**:
   - Verify emails use tenant-specific branding
   - Check that email headers include tenant information
   - Test unsubscribe functionality

### 2. Configure Monitoring

1. **Set Up Logging**:
   ```bash
   # Create log directories
   mkdir -p logs/tenants
   
   # Configure log rotation
   # Add to your cron or systemd timer
   ```

2. **Monitor Performance**:
   - Track database query performance
   - Monitor cache hit rates
   - Watch for memory leaks

### 3. Deploy to Production

1. **Environment Configuration**:
   ```bash
   # Production environment variables
   ENVIRONMENT=production
   DEBUG=False
   SECURE_SSL_REDIRECT=True
   SESSION_COOKIE_SECURE=True
   CSRF_COOKIE_SECURE=True
   ```

2. **Database Configuration**:
   ```bash
   # Production database settings
   DB_ENGINE=django.db.backends.postgresql
   DB_NAME=production_db
   DB_USER=production_user
   DB_PASSWORD=secure_password
   DB_HOST=production-db.example.com
   DB_PORT=5432
   
   # Connection pooling
   DATABASE_CONNECTION_POOL_SIZE=20
   DATABASE_CONNECTION_POOL_MAX_OVERFLOW=30
   ```

3. **Cache Configuration**:
   ```bash
   # Production cache settings
   USE_REDIS_CACHE=True
   REDIS_URL=redis://redis.example.com:6379/1
   REDIS_PASSWORD=redis_password
   REDIS_DB=1
   ```

## Troubleshooting

### Common Issues

1. **Tenant Not Found**:
   - Check that the tenant slug is correct
   - Verify the tenant is active
   - Ensure the URL pattern matches the tenant detection method

2. **Cross-Tenant Data Access**:
   - Verify that all models have the tenant field
   - Check that model managers filter by tenant
   - Ensure the database router is properly configured

3. **Static Files Not Loading**:
   - Check that static files are organized by tenant
   - Verify the static file configuration
   - Run `collectstatic` with the correct settings

4. **Email Issues**:
   - Check email configuration for the tenant
   - Verify email templates exist
   - Check email headers and formatting

### Debug Mode

To enable debug mode for specific tenants:

1. **Set Environment Variable**:
   ```bash
   TENANT_DEBUG_OVERRIDE=True
   TENANT_DEBUG_ALLOWED_SLUGS=tenant1,tenant2
   ```

2. **Or Update Settings**:
   ```python
   # In settings.py
   TENANT_DEBUG_OVERRIDE = True
   TENANT_DEBUG_ALLOWED_SLUGS = ['tenant1', 'tenant2']
   ```

## Best Practices

1. **Security**:
   - Always validate tenant access
   - Use HTTPS in production
   - Implement rate limiting for tenant APIs
   - Regularly review tenant permissions

2. **Performance**:
   - Use Redis for caching in production
   - Implement database connection pooling
   - Optimize queries with select_related and prefetch_related
   - Monitor and tune database performance

3. **Maintenance**:
   - Regularly backup tenant data
   - Implement log rotation
   - Monitor resource usage per tenant
   - Plan for tenant data migration

4. **Scalability**:
   - Design for horizontal scaling
   - Use CDN for static files
   - Implement queue-based task processing
   - Consider database sharding for large deployments

## Support

If you encounter issues during migration:

1. Check the logs for detailed error messages
2. Verify all environment variables are set correctly
3. Ensure all dependencies are installed
4. Test with a small dataset before migrating all data

For additional support, refer to the documentation or contact the development team.