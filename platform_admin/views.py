from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.db.models import Count, Sum, Q, Avg
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db import transaction
from django.urls import reverse
from django.template.loader import render_to_string
from django.contrib.auth.mixins import UserPassesTestMixin
from django.views.generic import ListView, DetailView, UpdateView, CreateView, DeleteView
from django.contrib.auth.views import LoginView, LogoutView
from django.utils.decorators import method_decorator
from django.views.generic.edit import FormMixin
from django.contrib.auth.forms import AuthenticationForm
from django.core.cache import cache
from django.conf import settings
from decimal import Decimal
import json
import csv
from datetime import datetime, timedelta

from tenants.models import Tenant, TenantSettings
from subscriptions.models import TenantSubscription, SubscriptionPlan, Invoice, Payment
from accounts.models import CustomUser
from clients.models import Client
from cases.models import Case
from documents.models import Document
from billing.models import Invoice as BillingInvoice
from .models import (
    SystemSettings, PlatformMetrics, AdminNote, SystemAnnouncement,
    SystemHealthCheck, AdminActivityLog
)
from .forms import (
    SystemSettingsForm, AdminNoteForm, SystemAnnouncementForm,
    TenantEditForm, BulkTenantForm
)

User = get_user_model()


def is_super_admin(user):
    """Check if user is a super admin."""
    return user.is_authenticated and user.is_superuser


class SuperAdminRequiredMixin(UserPassesTestMixin):
    """Mixin to ensure user is a super admin."""
    
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superuser
    
    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            messages.error(self.request, "You don't have permission to access the super admin panel.")
            return redirect('admin:login')
        return redirect('admin:login')


@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(is_super_admin), name='dispatch')
class SuperAdminDashboardView(SuperAdminRequiredMixin, ListView):
    """Super Admin Dashboard with system-wide statistics."""
    template_name = 'platform_admin/dashboard.html'
    context_object_name = 'metrics'
    
    def get_queryset(self):
        return PlatformMetrics.objects.filter(
            metric_type='daily'
        ).order_by('-date')[:30]
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get current system settings
        context['system_settings'] = SystemSettings.get_settings()
        
        # Calculate current statistics
        now = timezone.now()
        
        # Tenant statistics
        context['total_tenants'] = Tenant.objects.count()
        context['active_tenants'] = Tenant.objects.filter(is_active=True).count()
        context['new_tenants_month'] = Tenant.objects.filter(
            created_at__gte=now - timedelta(days=30)
        ).count()
        
        # User statistics
        context['total_users'] = CustomUser.objects.count()
        context['active_users'] = CustomUser.objects.filter(
            last_login__gte=now - timedelta(days=30)
        ).count()
        context['new_users_month'] = CustomUser.objects.filter(
            date_joined__gte=now - timedelta(days=30)
        ).count()
        
        # Subscription statistics
        context['total_subscriptions'] = TenantSubscription.objects.count()
        context['active_subscriptions'] = TenantSubscription.objects.filter(
            status='active'
        ).count()
        context['trial_subscriptions'] = TenantSubscription.objects.filter(
            status='trial'
        ).count()
        
        # Revenue statistics
        monthly_revenue = Payment.objects.filter(
            payment_date__gte=now - timedelta(days=30),
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        context['monthly_revenue'] = monthly_revenue
        
        # Recent activity
        context['recent_activity'] = AdminActivityLog.objects.select_related(
            'admin_user', 'tenant'
        ).order_by('-created_at')[:10]
        
        # System health
        context['health_checks'] = SystemHealthCheck.objects.order_by('-created_at')[:10]
        
        # Pending admin notes
        context['pending_notes'] = AdminNote.objects.filter(
            requires_follow_up=True,
            is_resolved=False
        ).count()
        
        # Active announcements
        context['active_announcements'] = SystemAnnouncement.objects.filter(
            is_active=True,
            start_date__lte=now
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=now)
        ).count()
        
        # Storage usage
        context['total_storage_mb'] = Document.objects.aggregate(
            total=Sum('file_size')
        )['total'] or 0
        
        return context


@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(is_super_admin), name='dispatch')
class TenantListView(SuperAdminRequiredMixin, ListView):
    """List all tenants with filtering and search capabilities."""
    model = Tenant
    template_name = 'platform_admin/tenant_list.html'
    context_object_name = 'tenants'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Tenant.objects.all()
        
        # Search functionality
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(slug__icontains=search_query)
            )
        
        # Filter by status
        status_filter = self.request.GET.get('status', '')
        if status_filter == 'active':
            queryset = queryset.filter(is_active=True)
        elif status_filter == 'inactive':
            queryset = queryset.filter(is_active=False)
        
        # Filter by plan
        plan_filter = self.request.GET.get('plan', '')
        if plan_filter:
            queryset = queryset.filter(plan=plan_filter)
        
        # Order by
        order_by = self.request.GET.get('order_by', '-created_at')
        if order_by:
            queryset = queryset.order_by(order_by)
        
        return queryset.select_related('settings').prefetch_related('users')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter context
        context['search_query'] = self.request.GET.get('search', '')
        context['status_filter'] = self.request.GET.get('status', '')
        context['plan_filter'] = self.request.GET.get('plan', '')
        context['order_by'] = self.request.GET.get('order_by', '-created_at')
        
        # Plan choices for filter
        context['plan_choices'] = Tenant.PLAN_CHOICES
        
        return context


@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(is_super_admin), name='dispatch')
class TenantDetailView(SuperAdminRequiredMixin, DetailView):
    """Detailed view of a specific tenant."""
    model = Tenant
    template_name = 'platform_admin/tenant_detail.html'
    context_object_name = 'tenant'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.get_object()
        
        # Get tenant settings
        context['tenant_settings'] = tenant.get_settings()
        
        # Get subscription information
        context['subscription'] = tenant.get_current_subscription()
        
        # Get user count
        context['user_count'] = tenant.get_current_user_count()
        
        # Get recent users
        context['recent_users'] = tenant.users.order_by('-date_joined')[:10]
        
        # Get admin notes for this tenant
        context['admin_notes'] = AdminNote.objects.filter(
            tenant=tenant
        ).order_by('-created_at')[:10]
        
        # Get storage usage
        context['storage_used'] = tenant.get_storage_used()
        context['storage_limit'] = tenant.get_storage_limit()
        
        return context


@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(is_super_admin), name='dispatch')
class TenantEditView(SuperAdminRequiredMixin, UpdateView):
    """Edit tenant information."""
    model = Tenant
    form_class = TenantEditForm
    template_name = 'platform_admin/tenant_edit.html'
    context_object_name = 'tenant'
    
    def get_success_url(self):
        return reverse('platform_admin:tenant_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        messages.success(self.request, f"Tenant '{form.instance.name}' has been updated successfully.")
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(is_super_admin), name='dispatch')
class UserListView(SuperAdminRequiredMixin, ListView):
    """List all users across all tenants."""
    model = CustomUser
    template_name = 'platform_admin/user_list.html'
    context_object_name = 'users'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = CustomUser.objects.all().select_related('tenant')
        
        # Search functionality
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(email__icontains=search_query) |
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(tenant__name__icontains=search_query)
            )
        
        # Filter by role
        role_filter = self.request.GET.get('role', '')
        if role_filter:
            queryset = queryset.filter(role=role_filter)
        
        # Filter by tenant
        tenant_filter = self.request.GET.get('tenant', '')
        if tenant_filter:
            queryset = queryset.filter(tenant_id=tenant_filter)
        
        # Filter by status
        status_filter = self.request.GET.get('status', '')
        if status_filter == 'active':
            queryset = queryset.filter(is_active=True)
        elif status_filter == 'inactive':
            queryset = queryset.filter(is_active=False)
        
        # Order by
        order_by = self.request.GET.get('order_by', '-date_joined')
        if order_by:
            queryset = queryset.order_by(order_by)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter context
        context['search_query'] = self.request.GET.get('search', '')
        context['role_filter'] = self.request.GET.get('role', '')
        context['tenant_filter'] = self.request.GET.get('tenant', '')
        context['status_filter'] = self.request.GET.get('status', '')
        context['order_by'] = self.request.GET.get('order_by', '-date_joined')
        
        # Role choices for filter
        context['role_choices'] = CustomUser._meta.get_field('role').choices
        
        # Tenant choices for filter
        context['tenant_choices'] = Tenant.objects.all()
        
        return context


@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(is_super_admin), name='dispatch')
class SystemSettingsView(SuperAdminRequiredMixin, UpdateView):
    """View and edit system-wide settings."""
    model = SystemSettings
    form_class = SystemSettingsForm
    template_name = 'platform_admin/system_settings.html'
    
    def get_object(self, queryset=None):
        return SystemSettings.get_settings()
    
    def get_success_url(self):
        return reverse('platform_admin:system_settings')
    
    def form_valid(self, form):
        messages.success(self.request, "System settings have been updated successfully.")
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(is_super_admin), name='dispatch')
class AdminNoteListView(SuperAdminRequiredMixin, ListView):
    """List all admin notes."""
    model = AdminNote
    template_name = 'platform_admin/note_list.html'
    context_object_name = 'notes'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = AdminNote.objects.all().select_related(
            'admin_user', 'tenant', 'related_user'
        )
        
        # Filter by tenant
        tenant_filter = self.request.GET.get('tenant', '')
        if tenant_filter:
            queryset = queryset.filter(tenant_id=tenant_filter)
        
        # Filter by note type
        note_type_filter = self.request.GET.get('note_type', '')
        if note_type_filter:
            queryset = queryset.filter(note_type=note_type_filter)
        
        # Filter by status
        status_filter = self.request.GET.get('status', '')
        if status_filter == 'resolved':
            queryset = queryset.filter(is_resolved=True)
        elif status_filter == 'unresolved':
            queryset = queryset.filter(is_resolved=False)
        elif status_filter == 'follow_up':
            queryset = queryset.filter(requires_follow_up=True, is_resolved=False)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter context
        context['tenant_filter'] = self.request.GET.get('tenant', '')
        context['note_type_filter'] = self.request.GET.get('note_type', '')
        context['status_filter'] = self.request.GET.get('status', '')
        
        # Filter choices
        context['note_type_choices'] = AdminNote.NOTE_TYPES
        context['tenant_choices'] = Tenant.objects.all()
        
        return context


@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(is_super_admin), name='dispatch')
class AdminNoteCreateView(SuperAdminRequiredMixin, CreateView):
    """Create a new admin note."""
    model = AdminNote
    form_class = AdminNoteForm
    template_name = 'platform_admin/note_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        form.instance.admin_user = self.request.user
        messages.success(self.request, "Admin note has been created successfully.")
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('platform_admin:note_list')


@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(is_super_admin), name='dispatch')
class SystemAnnouncementListView(SuperAdminRequiredMixin, ListView):
    """List all system announcements."""
    model = SystemAnnouncement
    template_name = 'platform_admin/announcement_list.html'
    context_object_name = 'announcements'
    paginate_by = 20
    
    def get_queryset(self):
        return SystemAnnouncement.objects.all().select_related(
            'created_by'
        ).order_by('-priority', '-created_at')


@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(is_super_admin), name='dispatch')
class SystemAnnouncementCreateView(SuperAdminRequiredMixin, CreateView):
    """Create a new system announcement."""
    model = SystemAnnouncement
    form_class = SystemAnnouncementForm
    template_name = 'platform_admin/announcement_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "System announcement has been created successfully.")
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('platform_admin:announcement_list')


@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(is_super_admin), name='dispatch')
class SystemHealthView(SuperAdminRequiredMixin, ListView):
    """View system health checks."""
    model = SystemHealthCheck
    template_name = 'platform_admin/system_health.html'
    context_object_name = 'health_checks'
    
    def get_queryset(self):
        return SystemHealthCheck.objects.all().order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Group health checks by type
        health_by_type = {}
        for check in self.get_queryset():
            if check.check_type not in health_by_type:
                health_by_type[check.check_type] = []
            health_by_type[check.check_type].append(check)
        
        context['health_by_type'] = health_by_type
        
        # Get latest check for each type
        latest_checks = {}
        for check_type in SystemHealthCheck.CHECK_TYPES:
            latest = SystemHealthCheck.objects.filter(
                check_type=check_type[0]
            ).order_by('-created_at').first()
            if latest:
                latest_checks[check_type[0]] = latest
        
        context['latest_checks'] = latest_checks
        
        return context


@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(is_super_admin), name='dispatch')
class RevenueReportView(SuperAdminRequiredMixin, ListView):
    """View revenue reports."""
    model = Payment
    template_name = 'platform_admin/revenue_report.html'
    context_object_name = 'payments'
    
    def get_queryset(self):
        queryset = Payment.objects.filter(status='completed').select_related(
            'invoice__tenant'
        )
        
        # Filter by date range
        date_from = self.request.GET.get('date_from', '')
        date_to = self.request.GET.get('date_to', '')
        
        if date_from:
            try:
                date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
                queryset = queryset.filter(payment_date__date__gte=date_from)
            except ValueError:
                pass
        
        if date_to:
            try:
                date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
                queryset = queryset.filter(payment_date__date__lte=date_to)
            except ValueError:
                pass
        
        return queryset.order_by('-payment_date')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Calculate revenue statistics
        payments = self.get_queryset()
        
        context['total_revenue'] = payments.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        context['monthly_revenue'] = payments.filter(
            payment_date__gte=timezone.now() - timedelta(days=30)
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Revenue by tenant
        context['revenue_by_tenant'] = payments.values(
            'invoice__tenant__name'
        ).annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('-total')[:10]
        
        # Revenue by month
        context['revenue_by_month'] = payments.extra(
            select={'month': 'strftime("%%Y-%%m", payment_date)'}
        ).values('month').annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('-month')[:12]
        
        return context


@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(is_super_admin), name='dispatch')
class ActivityLogView(SuperAdminRequiredMixin, ListView):
    """View admin activity logs."""
    model = AdminActivityLog
    template_name = 'platform_admin/activity_log.html'
    context_object_name = 'logs'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = AdminActivityLog.objects.all().select_related(
            'admin_user', 'tenant', 'target_user'
        )
        
        # Filter by admin user
        admin_filter = self.request.GET.get('admin', '')
        if admin_filter:
            queryset = queryset.filter(admin_user_id=admin_filter)
        
        # Filter by action type
        action_filter = self.request.GET.get('action', '')
        if action_filter:
            queryset = queryset.filter(action_type=action_filter)
        
        # Filter by tenant
        tenant_filter = self.request.GET.get('tenant', '')
        if tenant_filter:
            queryset = queryset.filter(tenant_id=tenant_filter)
        
        # Filter by date range
        date_from = self.request.GET.get('date_from', '')
        date_to = self.request.GET.get('date_to', '')
        
        if date_from:
            try:
                date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
                queryset = queryset.filter(created_at__date__gte=date_from)
            except ValueError:
                pass
        
        if date_to:
            try:
                date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
                queryset = queryset.filter(created_at__date__lte=date_to)
            except ValueError:
                pass
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter context
        context['admin_filter'] = self.request.GET.get('admin', '')
        context['action_filter'] = self.request.GET.get('action', '')
        context['tenant_filter'] = self.request.GET.get('tenant', '')
        context['date_from'] = self.request.GET.get('date_from', '')
        context['date_to'] = self.request.GET.get('date_to', '')
        
        # Filter choices
        context['action_choices'] = AdminActivityLog.ACTION_TYPES
        context['admin_choices'] = User.objects.filter(is_superuser=True)
        context['tenant_choices'] = Tenant.objects.all()
        
        return context


# Bulk operations views
@login_required
@user_passes_test(is_super_admin)
@require_POST
def bulk_tenant_action(request):
    """Perform bulk actions on tenants."""
    tenant_ids = request.POST.getlist('tenant_ids')
    action = request.POST.get('action')
    
    if not tenant_ids or not action:
        messages.error(request, "No tenants selected or action specified.")
        return redirect('platform_admin:tenant_list')
    
    tenants = Tenant.objects.filter(id__in=tenant_ids)
    count = 0
    
    with transaction.atomic():
        for tenant in tenants:
            if action == 'enable':
                tenant.is_active = True
                tenant.save()
                count += 1
            elif action == 'disable':
                tenant.is_active = False
                tenant.save()
                count += 1
            elif action == 'delete':
                tenant.soft_delete()
                count += 1
    
    action_name = {
        'enable': 'enabled',
        'disable': 'disabled',
        'delete': 'deleted'
    }.get(action, action)
    
    messages.success(request, f"{count} tenants have been {action_name}.")
    
    # Log the action
    AdminActivityLog.objects.create(
        admin_user=request.user,
        action_type='bulk_operation',
        action_description=f"Bulk {action_name} {count} tenants",
        details={'tenant_ids': tenant_ids, 'action': action}
    )
    
    return redirect('platform_admin:tenant_list')


@login_required
@user_passes_test(is_super_admin)
def export_data(request):
    """Export data in various formats."""
    export_type = request.GET.get('type', 'tenants')
    format_type = request.GET.get('format', 'csv')
    
    if export_type == 'tenants':
        queryset = Tenant.objects.all()
        
        if format_type == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="tenants.csv"'
            
            writer = csv.writer(response)
            writer.writerow(['Name', 'Slug', 'Plan', 'Status', 'Created At', 'User Count'])
            
            for tenant in queryset:
                writer.writerow([
                    tenant.name,
                    tenant.slug,
                    tenant.plan,
                    'Active' if tenant.is_active else 'Inactive',
                    tenant.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    tenant.get_current_user_count()
                ])
            
            return response
    
    elif export_type == 'users':
        queryset = CustomUser.objects.all().select_related('tenant')
        
        if format_type == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="users.csv"'
            
            writer = csv.writer(response)
            writer.writerow(['Email', 'First Name', 'Last Name', 'Role', 'Tenant', 'Status', 'Joined'])
            
            for user in queryset:
                writer.writerow([
                    user.email,
                    user.first_name,
                    user.last_name,
                    user.role,
                    user.tenant.name if user.tenant else 'None',
                    'Active' if user.is_active else 'Inactive',
                    user.date_joined.strftime('%Y-%m-%d %H:%M:%S')
                ])
            
            return response
    
    messages.error(request, "Invalid export type or format.")
    return redirect('platform_admin:dashboard')


# API endpoints for system monitoring
@login_required
@user_passes_test(is_super_admin)
def api_system_status(request):
    """API endpoint for system status."""
    cache_key = 'system_status'
    status_data = cache.get(cache_key)
    
    if not status_data:
        now = timezone.now()
        
        # Get basic system stats
        status_data = {
            'timestamp': now.isoformat(),
            'tenants': {
                'total': Tenant.objects.count(),
                'active': Tenant.objects.filter(is_active=True).count(),
                'new_this_month': Tenant.objects.filter(
                    created_at__gte=now - timedelta(days=30)
                ).count()
            },
            'users': {
                'total': CustomUser.objects.count(),
                'active': CustomUser.objects.filter(
                    last_login__gte=now - timedelta(days=30)
                ).count(),
                'new_this_month': CustomUser.objects.filter(
                    date_joined__gte=now - timedelta(days=30)
                ).count()
            },
            'subscriptions': {
                'total': TenantSubscription.objects.count(),
                'active': TenantSubscription.objects.filter(status='active').count(),
                'trial': TenantSubscription.objects.filter(status='trial').count()
            },
            'health': {}
        }
        
        # Add health check data
        for check_type in SystemHealthCheck.CHECK_TYPES:
            latest = SystemHealthCheck.objects.filter(
                check_type=check_type[0]
            ).order_by('-created_at').first()
            
            if latest:
                status_data['health'][check_type[0]] = {
                    'status': latest.status,
                    'message': latest.message,
                    'last_check': latest.created_at.isoformat()
                }
        
        # Cache for 5 minutes
        cache.set(cache_key, status_data, 300)
    
    return JsonResponse(status_data)


@login_required
@user_passes_test(is_super_admin)
def api_tenant_metrics(request):
    """API endpoint for tenant metrics."""
    tenant_id = request.GET.get('tenant_id')
    
    if not tenant_id:
        return JsonResponse({'error': 'Tenant ID required'}, status=400)
    
    try:
        tenant = Tenant.objects.get(id=tenant_id)
    except Tenant.DoesNotExist:
        return JsonResponse({'error': 'Tenant not found'}, status=404)
    
    # Get tenant metrics
    metrics = {
        'tenant': {
            'id': tenant.id,
            'name': tenant.name,
            'plan': tenant.plan,
            'is_active': tenant.is_active,
            'created_at': tenant.created_at.isoformat()
        },
        'users': {
            'total': tenant.get_current_user_count(),
            'max_allowed': tenant.get_storage_limit()
        },
        'storage': {
            'used_mb': tenant.get_storage_used(),
            'limit_mb': tenant.get_storage_limit(),
            'usage_percentage': (tenant.get_storage_used() / tenant.get_storage_limit() * 100) if tenant.get_storage_limit() > 0 else 0
        },
        'subscription': None
    }
    
    # Add subscription data if available
    subscription = tenant.get_current_subscription()
    if subscription:
        metrics['subscription'] = {
            'status': subscription.status,
            'plan': subscription.plan.name if subscription.plan else None,
            'start_date': subscription.start_date.isoformat(),
            'end_date': subscription.end_date.isoformat() if subscription.end_date else None,
            'is_active': subscription.is_active,
            'is_trial': subscription.is_trial,
            'days_until_expiry': subscription.days_until_expiry
        }
    
    return JsonResponse(metrics)
