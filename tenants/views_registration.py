"""
Tenant Registration and Onboarding Views
Implements Feature #1 from todo.md: Tenant Creation & Onboarding
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, get_user_model
from django.contrib import messages
from django.views.generic import CreateView, TemplateView, UpdateView
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.utils.text import slugify
from django.db import transaction

from .models import Tenant, TenantSettings
from .forms import TenantRegistrationForm, TenantOnboardingForm
from permissions.models import Role

User = get_user_model()


class TenantRegistrationView(CreateView):
    """
    Public registration page for new tenants (law firms).
    Creates tenant, first admin user, and default settings.
    """
    model = Tenant
    form_class = TenantRegistrationForm
    template_name = 'tenants/registration/register.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Register Your Law Firm'
        return context
    
    @transaction.atomic
    def form_valid(self, form):
        # Create tenant
        tenant = form.save(commit=False)
        tenant.slug = slugify(tenant.name)
        
        # Ensure unique slug
        base_slug = tenant.slug
        counter = 1
        while Tenant.objects.filter(slug=tenant.slug).exists():
            tenant.slug = f"{base_slug}-{counter}"
            counter += 1
        
        tenant.save()
        
        # Create admin user
        user = User.objects.create_user(
            email=form.cleaned_data['admin_email'],
            password=form.cleaned_data['admin_password'],
            first_name=form.cleaned_data['admin_first_name'],
            last_name=form.cleaned_data['admin_last_name'],
            tenant=tenant,
            role='admin'
        )
        
        # Create default tenant settings
        TenantSettings.objects.create(tenant=tenant)
        
        # Create default roles for tenant
        self._create_default_roles(tenant)
        
        # Log in the new admin user
        login(self.request, user, backend='django.contrib.auth.backends.ModelBackend')
        
        messages.success(
            self.request,
            f'Welcome to {tenant.name}! Your law firm has been registered successfully.'
        )
        
        return redirect('tenants:onboarding', tenant_id=tenant.pk)
    
    def _create_default_roles(self, tenant):
        """Create default roles for a new tenant."""
        default_roles = [
            {'name': 'Admin', 'description': 'Full access to all features'},
            {'name': 'Lawyer', 'description': 'Access to cases, clients, and billing'},
            {'name': 'Paralegal', 'description': 'Limited access to cases and documents'},
            {'name': 'Billing Manager', 'description': 'Access to billing and invoices'},
            {'name': 'Read-only Staff', 'description': 'View-only access'},
        ]
        
        for role_data in default_roles:
            Role.objects.get_or_create(
                name=role_data['name'],
                tenant=tenant,
                defaults={'description': role_data['description']}
            )


class TenantOnboardingView(TemplateView):
    """
    Multi-step onboarding wizard for new tenants.
    """
    template_name = 'tenants/registration/onboarding.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = get_object_or_404(Tenant, pk=self.kwargs['tenant_id'])
        
        # Calculate onboarding progress
        steps = [
            {
                'name': 'Company Info',
                'complete': bool(tenant.name and tenant.slug),
                'icon': 'fa-building',
                'url': reverse('tenants:onboarding_company', kwargs={'tenant_id': tenant.pk})
            },
            {
                'name': 'Billing Setup',
                'complete': hasattr(tenant, 'subscription') and tenant.subscription is not None,
                'icon': 'fa-credit-card',
                'url': reverse('tenants:onboarding_billing', kwargs={'tenant_id': tenant.pk})
            },
            {
                'name': 'Team Members',
                'complete': tenant.users.count() > 1,
                'icon': 'fa-users',
                'url': reverse('tenants:onboarding_team', kwargs={'tenant_id': tenant.pk})
            },
            {
                'name': 'Practice Areas',
                'complete': tenant.practice_areas.exists() if hasattr(tenant, 'practice_areas') else False,
                'icon': 'fa-balance-scale',
                'url': reverse('tenants:onboarding_practice', kwargs={'tenant_id': tenant.pk})
            },
        ]
        
        completed_steps = sum(1 for step in steps if step['complete'])
        progress_percentage = (completed_steps / len(steps)) * 100
        
        context.update({
            'tenant': tenant,
            'steps': steps,
            'completed_steps': completed_steps,
            'total_steps': len(steps),
            'progress_percentage': progress_percentage,
            'title': 'Complete Your Setup'
        })
        
        return context


class TenantOnboardingCompanyView(UpdateView):
    """Onboarding step: Company information."""
    model = Tenant
    template_name = 'tenants/registration/onboarding_company.html'
    fields = ['name', 'phone', 'address', 'website']
    pk_url_kwarg = 'tenant_id'
    
    def get_success_url(self):
        return reverse('tenants:onboarding', kwargs={'tenant_id': self.object.pk})
    
    def form_valid(self, form):
        messages.success(self.request, 'Company information updated!')
        return super().form_valid(form)


class TenantOnboardingBillingView(TemplateView):
    """Onboarding step: Billing setup."""
    template_name = 'tenants/registration/onboarding_billing.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = get_object_or_404(Tenant, pk=self.kwargs['tenant_id'])
        
        # Get available plans
        from subscriptions.models import SubscriptionPlan
        plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price')
        
        context.update({
            'tenant': tenant,
            'plans': plans,
            'title': 'Choose Your Plan'
        })
        
        return context


class TenantOnboardingTeamView(TemplateView):
    """Onboarding step: Team members."""
    template_name = 'tenants/registration/onboarding_team.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = get_object_or_404(Tenant, pk=self.kwargs['tenant_id'])
        
        context.update({
            'tenant': tenant,
            'team_members': tenant.users.all(),
            'title': 'Invite Team Members'
        })
        
        return context


class TenantOnboardingPracticeView(TemplateView):
    """Onboarding step: Practice areas."""
    template_name = 'tenants/registration/onboarding_practice.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = get_object_or_404(Tenant, pk=self.kwargs['tenant_id'])
        
        # Default practice areas
        default_areas = [
            'Civil Litigation', 'Criminal Defense', 'Corporate Law',
            'Family Law', 'Real Estate', 'Intellectual Property',
            'Tax Law', 'Bankruptcy', 'Immigration', 'Personal Injury',
            'Employment Law', 'Estate Planning'
        ]
        
        context.update({
            'tenant': tenant,
            'default_areas': default_areas,
            'title': 'Select Practice Areas'
        })
        
        return context


@require_GET
def check_slug_availability(request):
    """AJAX endpoint to check if a tenant slug is available."""
    slug = request.GET.get('slug', '')
    
    if len(slug) < 3:
        return JsonResponse({'available': False, 'message': 'Slug must be at least 3 characters'})
    
    slug = slugify(slug)
    available = not Tenant.objects.filter(slug=slug).exists()
    
    return JsonResponse({
        'available': available,
        'slug': slug,
        'message': 'Available' if available else 'Already taken'
    })


@require_GET
def check_email_availability(request):
    """AJAX endpoint to check if an email is available."""
    email = request.GET.get('email', '')
    
    if not email:
        return JsonResponse({'available': False, 'message': 'Email is required'})
    
    available = not User.objects.filter(email=email).exists()
    
    return JsonResponse({
        'available': available,
        'message': 'Available' if available else 'Email already registered'
    })
