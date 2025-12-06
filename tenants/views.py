from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.db import transaction
from .models import Tenant
from .forms import TenantForm, TenantUpdateForm, TenantRegistrationForm, TenantSettingsForm, TenantSettingsReadOnlyForm
from .models import TenantSettings


class TenantListView(LoginRequiredMixin, ListView):
    """
    View to list all tenants (for superadmin).
    """
    model = Tenant
    template_name = 'tenants/tenant_list.html'
    context_object_name = 'tenants'
    paginate_by = 10
    
    def get_queryset(self):
        # Only show active tenants by default
        queryset = Tenant.objects.active()
        # Allow filtering by plan
        plan_filter = self.request.GET.get('plan')
        if plan_filter:
            queryset = queryset.filter(plan=plan_filter)
        return queryset


class TenantDetailView(LoginRequiredMixin, DetailView):
    """
    View to show details of a specific tenant.
    """
    model = Tenant
    template_name = 'tenants/tenant_detail.html'
    context_object_name = 'tenant'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.get_object()
        context['user_count'] = tenant.get_current_user_count()
        context['storage_used'] = tenant.get_storage_used()
        return context


class TenantCreateView(LoginRequiredMixin, CreateView):
    """
    View to create a new tenant.
    """
    model = Tenant
    form_class = TenantForm
    template_name = 'tenants/tenant_form.html'
    success_url = reverse_lazy('tenant-list')
    
    def form_valid(self, form):
        messages.success(self.request, f'Tenant "{form.instance.name}" has been created successfully.')
        return super().form_valid(form)


class TenantUpdateView(LoginRequiredMixin, UpdateView):
    """
    View to update an existing tenant.
    """
    model = Tenant
    form_class = TenantUpdateForm
    template_name = 'tenants/tenant_form.html'
    success_url = reverse_lazy('tenant-list')
    
    def form_valid(self, form):
        messages.success(self.request, f'Tenant "{form.instance.name}" has been updated successfully.')
        return super().form_valid(form)


class TenantDeleteView(LoginRequiredMixin, DeleteView):
    """
    View to soft delete a tenant.
    """
    model = Tenant
    template_name = 'tenants/tenant_confirm_delete.html'
    success_url = reverse_lazy('tenant-list')
    
    def delete(self, request, *args, **kwargs):
        tenant = self.get_object()
        tenant.soft_delete()
        messages.success(request, f'Tenant "{tenant.name}" has been deleted successfully.')
        return redirect(self.success_url)


@login_required
def tenant_dashboard(request, slug=None):
    """
    Dashboard view for a specific tenant.
    
    If slug is provided, it's used for backward compatibility with direct URL access.
    Otherwise, the tenant is obtained from the middleware (request.tenant).
    """
    # Get tenant from middleware if available, otherwise from slug parameter
    if hasattr(request, 'tenant') and request.tenant:
        tenant = request.tenant
    elif slug:
        tenant = get_object_or_404(Tenant, slug=slug)
    else:
        messages.error(request, "No tenant specified.")
        return redirect('home')
    
    # Check if user belongs to this tenant or is superadmin
    if not request.user.is_superuser and (not hasattr(request.user, 'tenant') or request.user.tenant != tenant):
        messages.error(request, "You don't have permission to access this tenant's dashboard.")
        return redirect('home')
    
    context = {
        'tenant': tenant,
        'user_count': tenant.get_current_user_count(),
        'storage_used': tenant.get_storage_used(),
        'can_add_user': tenant.can_add_user(),
    }
    
    return render(request, 'tenants/tenant_dashboard.html', context)


@login_required
def switch_tenant(request, tenant_id):
    """
    View to switch between tenants for users with access to multiple tenants.
    """
    tenant = get_object_or_404(Tenant, pk=tenant_id)
    
    # Check if user belongs to this tenant or is superadmin
    if not request.user.is_superuser and (not hasattr(request.user, 'tenant') or request.user.tenant != tenant):
        messages.error(request, "You don't have permission to access this tenant.")
        return redirect('home')
    
    # Store tenant in session
    request.session['current_tenant_id'] = tenant.pk
    messages.success(request, f"Switched to tenant: {tenant.name}")
    
    # Redirect to tenant dashboard or previous page
    next_url = request.GET.get('next', reverse_lazy('tenant-dashboard', kwargs={'slug': tenant.slug}))
    return redirect(next_url)


def tenant_registration(request):
    """
    View for tenant registration that creates both tenant and admin user.
    """
    if request.user.is_authenticated:
        messages.info(request, "You're already logged in. Please log out to register a new tenant.")
        return redirect('home')
    
    if request.method == 'POST':
        form = TenantRegistrationForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Create tenant and admin user
                    tenant = form.save()
                    
                    # Get the created admin user
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    admin_user = User.objects.get(email=form.cleaned_data['admin_email'])
                    
                    # Log in the admin user
                    login(request, admin_user)
                    
                    # Store tenant in session
                    request.session['current_tenant_id'] = tenant.pk
                    
                    messages.success(
                        request,
                        f"Welcome! Your law firm '{tenant.name}' has been successfully registered. "
                        f"You are now logged in as the admin user."
                    )
                    
                    # Redirect to tenant dashboard
                    return redirect(reverse_lazy('tenant-dashboard', kwargs={'slug': tenant.slug}))
                    
            except Exception as e:
                messages.error(request, f"An error occurred during registration: {str(e)}")
                return render(request, 'tenants/tenant_registration.html', {'form': form})
    else:
        form = TenantRegistrationForm()
    
    return render(request, 'tenants/tenant_registration.html', {'form': form})


class TenantSettingsDetailView(LoginRequiredMixin, DetailView):
    """
    View to display tenant settings (read-only for non-admins).
    """
    model = TenantSettings
    template_name = 'tenants/tenant_settings_detail.html'
    context_object_name = 'settings'
    
    def get_object(self, queryset=None):
        # Get tenant from middleware or from URL parameter
        if hasattr(self.request, 'tenant') and self.request.tenant:
            tenant = self.request.tenant
        else:
            tenant_id = self.kwargs.get('tenant_id')
            tenant = get_object_or_404(Tenant, pk=tenant_id)
        
        # Get or create tenant settings
        return tenant.get_settings()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        settings = self.get_object()
        context['tenant'] = settings.tenant
        context['form'] = TenantSettingsReadOnlyForm(instance=settings)
        
        # Check if user can edit settings (admin only)
        context['can_edit'] = (
            self.request.user.is_superuser or
            (hasattr(self.request.user, 'role') and self.request.user.role == 'admin')
        )
        
        return context


class TenantSettingsUpdateView(LoginRequiredMixin, UpdateView):
    """
    View to update tenant settings (admin only).
    """
    model = TenantSettings
    form_class = TenantSettingsForm
    template_name = 'tenants/tenant_settings_form.html'
    success_url = None  # Will be set dynamically
    
    def dispatch(self, request, *args, **kwargs):
        # Only allow admins to update settings
        if not request.user.is_superuser and (not hasattr(request.user, 'role') or request.user.role != 'admin'):
            messages.error(request, "You don't have permission to update tenant settings.")
            return redirect('tenant-settings-detail')
        return super().dispatch(request, *args, **kwargs)
    
    def get_object(self, queryset=None):
        # Get tenant from middleware or from URL parameter
        if hasattr(self.request, 'tenant') and self.request.tenant:
            tenant = self.request.tenant
        else:
            tenant_id = self.kwargs.get('tenant_id')
            tenant = get_object_or_404(Tenant, pk=tenant_id)
        
        # Get or create tenant settings
        return tenant.get_settings()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        settings = self.get_object()
        context['tenant'] = settings.tenant
        return context
    
    def get_success_url(self):
        # Redirect to settings detail page after successful update
        settings = self.get_object()
        return reverse_lazy('tenant-settings-detail', kwargs={'tenant_id': settings.tenant.pk})
    
    def form_valid(self, form):
        messages.success(self.request, 'Settings have been updated successfully.')
        return super().form_valid(form)


@login_required
def tenant_settings_logo_delete(request, tenant_id=None):
    """
    View to delete tenant logo (admin only).
    """
    # Get tenant from middleware or from URL parameter
    if hasattr(request, 'tenant') and request.tenant:
        tenant = request.tenant
    elif tenant_id:
        tenant = get_object_or_404(Tenant, pk=tenant_id)
    else:
        messages.error(request, "No tenant specified.")
        return redirect('home')
    
    # Check if user can edit settings (admin only)
    if not request.user.is_superuser and (not hasattr(request.user, 'role') or request.user.role != 'admin'):
        messages.error(request, "You don't have permission to update tenant settings.")
        return redirect('tenant-settings-detail')
    
    # Get tenant settings
    settings = tenant.get_settings()
    
    if request.method == 'POST':
        # Delete logo
        if settings.logo:
            settings.logo.delete()
            settings.logo = None
            settings.save()
            messages.success(request, 'Logo has been deleted successfully.')
        else:
            messages.info(request, 'No logo to delete.')
        
        return redirect('tenant-settings-update', tenant_id=tenant.pk)
    
    return redirect('tenant-settings-detail', tenant_id=tenant.pk)


@login_required
def tenant_settings_preview(request, tenant_id=None):
    """
    View to preview tenant settings with branding applied.
    """
    # Get tenant from middleware or from URL parameter
    if hasattr(request, 'tenant') and request.tenant:
        tenant = request.tenant
    elif tenant_id:
        tenant = get_object_or_404(Tenant, pk=tenant_id)
    else:
        messages.error(request, "No tenant specified.")
        return redirect('home')
    
    # Get tenant settings
    settings = tenant.get_settings()
    
    # Check if user can view settings
    if not request.user.is_superuser and (not hasattr(request.user, 'tenant') or request.user.tenant != tenant):
        messages.error(request, "You don't have permission to view these settings.")
        return redirect('home')
    
    # Clear branding cache to ensure latest settings are used
    from .branding_utils import clear_branding_cache
    clear_branding_cache(tenant)
    
    # Get branding context
    from .branding_utils import get_tenant_branding_context
    branding_context = get_tenant_branding_context(tenant)
    
    context = {
        'tenant': tenant,
        'settings': settings,
        'preview_mode': True,
    }
    
    # Add branding context to template context
    context.update(branding_context)
    
    return render(request, 'tenants/tenant_settings_preview.html', context)