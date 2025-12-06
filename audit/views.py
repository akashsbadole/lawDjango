import csv
import json
from datetime import datetime, timedelta
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg, Max, Min
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import ListView, DetailView, TemplateView, View
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.contrib.auth import get_user_model

from .models import AuditLog, ActivityLog, SecurityEvent, LoginLog
from .forms import AuditLogFilterForm, ActivityLogFilterForm, SecurityEventFilterForm, LoginLogFilterForm
from .utils import log_audit_event, log_activity

User = get_user_model()


class AuditLogListView(LoginRequiredMixin, ListView):
    """
    List view for audit logs with filtering and pagination.
    """
    model = AuditLog
    template_name = 'audit/audit_log_list.html'
    context_object_name = 'audit_logs'
    paginate_by = 50
    
    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return AuditLog.objects.none()
        
        queryset = AuditLog.objects.filter(tenant=tenant)
        
        # Apply filters
        form = AuditLogFilterForm(self.request.GET)
        if form.is_valid():
            cleaned_data = form.cleaned_data
            
            # Filter by action
            if cleaned_data.get('action'):
                queryset = queryset.filter(action=cleaned_data['action'])
            
            # Filter by model
            if cleaned_data.get('model_name'):
                queryset = queryset.filter(model_name__icontains=cleaned_data['model_name'])
            
            # Filter by user
            if cleaned_data.get('user'):
                queryset = queryset.filter(user=cleaned_data['user'])
            
            # Filter by date range
            if cleaned_data.get('date_from'):
                queryset = queryset.filter(timestamp__gte=cleaned_data['date_from'])
            
            if cleaned_data.get('date_to'):
                queryset = queryset.filter(timestamp__lte=cleaned_data['date_to'])
            
            # Filter by IP address
            if cleaned_data.get('ip_address'):
                queryset = queryset.filter(ip_address=cleaned_data['ip_address'])
        
        return queryset.select_related('user', 'content_type').order_by('-timestamp')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = AuditLogFilterForm(self.request.GET)
        context['title'] = 'Audit Logs'
        return context


class AuditLogDetailView(LoginRequiredMixin, DetailView):
    """
    Detail view for a single audit log entry.
    """
    model = AuditLog
    template_name = 'audit/audit_log_detail.html'
    context_object_name = 'audit_log'
    
    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return AuditLog.objects.none()
        
        return AuditLog.objects.filter(tenant=tenant).select_related('user', 'content_type')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Audit Log: {self.object.id}'
        return context


class ActivityLogListView(LoginRequiredMixin, ListView):
    """
    List view for activity logs with filtering and pagination.
    """
    model = ActivityLog
    template_name = 'audit/activity_log_list.html'
    context_object_name = 'activity_logs'
    paginate_by = 50
    
    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return ActivityLog.objects.none()
        
        queryset = ActivityLog.objects.filter(tenant=tenant)
        
        # Apply filters
        form = ActivityLogFilterForm(self.request.GET)
        if form.is_valid():
            cleaned_data = form.cleaned_data
            
            # Filter by activity type
            if cleaned_data.get('activity_type'):
                queryset = queryset.filter(activity_type=cleaned_data['activity_type'])
            
            # Filter by user
            if cleaned_data.get('user'):
                queryset = queryset.filter(user=cleaned_data['user'])
            
            # Filter by date range
            if cleaned_data.get('date_from'):
                queryset = queryset.filter(timestamp__gte=cleaned_data['date_from'])
            
            if cleaned_data.get('date_to'):
                queryset = queryset.filter(timestamp__lte=cleaned_data['date_to'])
            
            # Filter by description
            if cleaned_data.get('description'):
                queryset = queryset.filter(description__icontains=cleaned_data['description'])
        
        return queryset.select_related('user', 'related_content_type').order_by('-timestamp')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = ActivityLogFilterForm(self.request.GET)
        context['title'] = 'Activity Logs'
        return context


class SecurityEventListView(LoginRequiredMixin, ListView):
    """
    List view for security events with filtering and pagination.
    """
    model = SecurityEvent
    template_name = 'audit/security_event_list.html'
    context_object_name = 'security_events'
    paginate_by = 50
    
    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return SecurityEvent.objects.none()
        
        queryset = SecurityEvent.objects.filter(tenant=tenant)
        
        # Apply filters
        form = SecurityEventFilterForm(self.request.GET)
        if form.is_valid():
            cleaned_data = form.cleaned_data
            
            # Filter by event type
            if cleaned_data.get('event_type'):
                queryset = queryset.filter(event_type=cleaned_data['event_type'])
            
            # Filter by severity
            if cleaned_data.get('severity'):
                queryset = queryset.filter(severity=cleaned_data['severity'])
            
            # Filter by resolved status
            if cleaned_data.get('resolved') is not None:
                queryset = queryset.filter(resolved=cleaned_data['resolved'])
            
            # Filter by user
            if cleaned_data.get('user'):
                queryset = queryset.filter(user=cleaned_data['user'])
            
            # Filter by date range
            if cleaned_data.get('date_from'):
                queryset = queryset.filter(timestamp__gte=cleaned_data['date_from'])
            
            if cleaned_data.get('date_to'):
                queryset = queryset.filter(timestamp__lte=cleaned_data['date_to'])
        
        return queryset.select_related('user', 'resolved_by', 'related_content_type').order_by('-timestamp')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = SecurityEventFilterForm(self.request.GET)
        context['title'] = 'Security Events'
        return context


class SecurityEventDetailView(LoginRequiredMixin, DetailView):
    """
    Detail view for a single security event.
    """
    model = SecurityEvent
    template_name = 'audit/security_event_detail.html'
    context_object_name = 'security_event'
    
    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return SecurityEvent.objects.none()
        
        return SecurityEvent.objects.filter(tenant=tenant).select_related(
            'user', 'resolved_by', 'related_content_type'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Security Event: {self.object.id}'
        return context


class LoginLogListView(LoginRequiredMixin, ListView):
    """
    List view for login logs with filtering and pagination.
    """
    model = LoginLog
    template_name = 'audit/login_log_list.html'
    context_object_name = 'login_logs'
    paginate_by = 50
    
    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return LoginLog.objects.none()
        
        queryset = LoginLog.objects.filter(tenant=tenant)
        
        # Apply filters
        form = LoginLogFilterForm(self.request.GET)
        if form.is_valid():
            cleaned_data = form.cleaned_data
            
            # Filter by user
            if cleaned_data.get('user'):
                queryset = queryset.filter(user=cleaned_data['user'])
            
            # Filter by login success
            if cleaned_data.get('login_successful') is not None:
                queryset = queryset.filter(login_successful=cleaned_data['login_successful'])
            
            # Filter by date range
            if cleaned_data.get('date_from'):
                queryset = queryset.filter(login_time__gte=cleaned_data['date_from'])
            
            if cleaned_data.get('date_to'):
                queryset = queryset.filter(login_time__lte=cleaned_data['date_to'])
            
            # Filter by IP address
            if cleaned_data.get('ip_address'):
                queryset = queryset.filter(ip_address=cleaned_data['ip_address'])
        
        return queryset.select_related('user').order_by('-login_time')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = LoginLogFilterForm(self.request.GET)
        context['title'] = 'Login History'
        return context


class AuditDashboardView(LoginRequiredMixin, TemplateView):
    """
    Dashboard view showing audit statistics and recent activity.
    """
    template_name = 'audit/audit_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        
        if not tenant:
            return context
        
        # Time periods for statistics
        now = timezone.now()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)
        last_30d = now - timedelta(days=30)
        
        # Basic statistics
        context['total_audit_logs'] = AuditLog.objects.filter(tenant=tenant).count()
        context['total_activities'] = ActivityLog.objects.filter(tenant=tenant).count()
        context['total_security_events'] = SecurityEvent.objects.filter(tenant=tenant).count()
        context['unresolved_security_events'] = SecurityEvent.objects.filter(
            tenant=tenant, resolved=False
        ).count()
        
        # Recent statistics (last 24 hours)
        context['recent_audit_logs'] = AuditLog.objects.filter(
            tenant=tenant, timestamp__gte=last_24h
        ).count()
        context['recent_activities'] = ActivityLog.objects.filter(
            tenant=tenant, timestamp__gte=last_24h
        ).count()
        context['recent_security_events'] = SecurityEvent.objects.filter(
            tenant=tenant, timestamp__gte=last_24h
        ).count()
        
        # Security events by severity
        context['security_events_by_severity'] = SecurityEvent.objects.filter(
            tenant=tenant, timestamp__gte=last_7d
        ).values('severity').annotate(count=Count('id')).order_by('-count')
        
        # Top activities
        context['top_activities'] = ActivityLog.objects.filter(
            tenant=tenant, timestamp__gte=last_7d
        ).values('activity_type').annotate(count=Count('id')).order_by('-count')[:10]
        
        # Recent audit logs
        context['recent_audit_log_entries'] = AuditLog.objects.filter(
            tenant=tenant
        ).select_related('user').order_by('-timestamp')[:10]
        
        # Recent security events
        context['recent_security_event_entries'] = SecurityEvent.objects.filter(
            tenant=tenant, resolved=False
        ).select_related('user').order_by('-timestamp')[:10]
        
        # Failed login attempts (last 7 days)
        context['failed_logins'] = LoginLog.objects.filter(
            tenant=tenant, login_successful=False, login_time__gte=last_7d
        ).count()
        
        # Unique users active in last 7 days
        context['active_users'] = AuditLog.objects.filter(
            tenant=tenant, timestamp__gte=last_7d, user__isnull=False
        ).values('user').distinct().count()
        
        context['title'] = 'Audit Dashboard'
        return context


class AuditExportView(LoginRequiredMixin, View):
    """
    Export audit data to CSV or JSON.
    """
    
    def get(self, request):
        export_type = request.GET.get('type', 'csv')
        log_type = request.GET.get('log_type', 'audit')
        
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            messages.error(request, 'Tenant not found')
            return redirect('audit:dashboard')
        
        # Get filtered queryset
        if log_type == 'audit':
            queryset = self._get_filtered_audit_logs(request, tenant)
            filename = f'audit_logs_{timezone.now().strftime("%Y%m%d_%H%M%S")}'
        elif log_type == 'activity':
            queryset = self._get_filtered_activity_logs(request, tenant)
            filename = f'activity_logs_{timezone.now().strftime("%Y%m%d_%H%M%S")}'
        elif log_type == 'security':
            queryset = self._get_filtered_security_events(request, tenant)
            filename = f'security_events_{timezone.now().strftime("%Y%m%d_%H%M%S")}'
        elif log_type == 'login':
            queryset = self._get_filtered_login_logs(request, tenant)
            filename = f'login_logs_{timezone.now().strftime("%Y%m%d_%H%M%S")}'
        else:
            messages.error(request, 'Invalid log type')
            return redirect('audit:dashboard')
        
        # Export data
        if export_type == 'csv':
            return self._export_csv(queryset, filename)
        elif export_type == 'json':
            return self._export_json(queryset, filename)
        else:
            messages.error(request, 'Invalid export type')
            return redirect('audit:dashboard')
    
    def _get_filtered_audit_logs(self, request, tenant):
        queryset = AuditLog.objects.filter(tenant=tenant)
        form = AuditLogFilterForm(request.GET)
        if form.is_valid():
            # Apply same filters as in list view
            cleaned_data = form.cleaned_data
            if cleaned_data.get('action'):
                queryset = queryset.filter(action=cleaned_data['action'])
            if cleaned_data.get('model_name'):
                queryset = queryset.filter(model_name__icontains=cleaned_data['model_name'])
            if cleaned_data.get('user'):
                queryset = queryset.filter(user=cleaned_data['user'])
            if cleaned_data.get('date_from'):
                queryset = queryset.filter(timestamp__gte=cleaned_data['date_from'])
            if cleaned_data.get('date_to'):
                queryset = queryset.filter(timestamp__lte=cleaned_data['date_to'])
            if cleaned_data.get('ip_address'):
                queryset = queryset.filter(ip_address=cleaned_data['ip_address'])
        return queryset.select_related('user', 'content_type')
    
    def _get_filtered_activity_logs(self, request, tenant):
        queryset = ActivityLog.objects.filter(tenant=tenant)
        form = ActivityLogFilterForm(request.GET)
        if form.is_valid():
            cleaned_data = form.cleaned_data
            if cleaned_data.get('activity_type'):
                queryset = queryset.filter(activity_type=cleaned_data['activity_type'])
            if cleaned_data.get('user'):
                queryset = queryset.filter(user=cleaned_data['user'])
            if cleaned_data.get('date_from'):
                queryset = queryset.filter(timestamp__gte=cleaned_data['date_from'])
            if cleaned_data.get('date_to'):
                queryset = queryset.filter(timestamp__lte=cleaned_data['date_to'])
            if cleaned_data.get('description'):
                queryset = queryset.filter(description__icontains=cleaned_data['description'])
        return queryset.select_related('user', 'related_content_type')
    
    def _get_filtered_security_events(self, request, tenant):
        queryset = SecurityEvent.objects.filter(tenant=tenant)
        form = SecurityEventFilterForm(request.GET)
        if form.is_valid():
            cleaned_data = form.cleaned_data
            if cleaned_data.get('event_type'):
                queryset = queryset.filter(event_type=cleaned_data['event_type'])
            if cleaned_data.get('severity'):
                queryset = queryset.filter(severity=cleaned_data['severity'])
            if cleaned_data.get('resolved') is not None:
                queryset = queryset.filter(resolved=cleaned_data['resolved'])
            if cleaned_data.get('user'):
                queryset = queryset.filter(user=cleaned_data['user'])
            if cleaned_data.get('date_from'):
                queryset = queryset.filter(timestamp__gte=cleaned_data['date_from'])
            if cleaned_data.get('date_to'):
                queryset = queryset.filter(timestamp__lte=cleaned_data['date_to'])
        return queryset.select_related('user', 'resolved_by', 'related_content_type')
    
    def _get_filtered_login_logs(self, request, tenant):
        queryset = LoginLog.objects.filter(tenant=tenant)
        form = LoginLogFilterForm(request.GET)
        if form.is_valid():
            cleaned_data = form.cleaned_data
            if cleaned_data.get('user'):
                queryset = queryset.filter(user=cleaned_data['user'])
            if cleaned_data.get('login_successful') is not None:
                queryset = queryset.filter(login_successful=cleaned_data['login_successful'])
            if cleaned_data.get('date_from'):
                queryset = queryset.filter(login_time__gte=cleaned_data['date_from'])
            if cleaned_data.get('date_to'):
                queryset = queryset.filter(login_time__lte=cleaned_data['date_to'])
            if cleaned_data.get('ip_address'):
                queryset = queryset.filter(ip_address=cleaned_data['ip_address'])
        return queryset.select_related('user')
    
    def _export_csv(self, queryset, filename):
        """
        Export queryset to CSV format.
        """
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
        
        writer = csv.writer(response)
        
        # Write header based on model type
        if queryset.model == AuditLog:
            writer.writerow([
                'ID', 'Timestamp', 'User', 'Action', 'Model', 'Object ID', 
                'Object Repr', 'IP Address', 'User Agent', 'Changed Fields'
            ])
            for obj in queryset:
                writer.writerow([
                    obj.id, obj.timestamp, obj.user, obj.action, obj.model_name,
                    obj.object_id, obj.object_repr, obj.ip_address, 
                    obj.user_agent[:100] if obj.user_agent else '',  # Truncate long user agents
                    ', '.join(obj.changed_fields) if obj.changed_fields else ''
                ])
        
        elif queryset.model == ActivityLog:
            writer.writerow([
                'ID', 'Timestamp', 'User', 'Activity Type', 'Description', 
                'IP Address', 'Related Object'
            ])
            for obj in queryset:
                writer.writerow([
                    obj.id, obj.timestamp, obj.user, obj.activity_type,
                    obj.description, obj.ip_address, str(obj.related_object) if obj.related_object else ''
                ])
        
        elif queryset.model == SecurityEvent:
            writer.writerow([
                'ID', 'Timestamp', 'User', 'Event Type', 'Severity', 'Description',
                'Source IP', 'Resolved', 'Resolved By', 'Resolved At'
            ])
            for obj in queryset:
                writer.writerow([
                    obj.id, obj.timestamp, obj.user, obj.event_type, obj.severity,
                    obj.description, obj.source_ip, obj.resolved, obj.resolved_by, obj.resolved_at
                ])
        
        elif queryset.model == LoginLog:
            writer.writerow([
                'ID', 'Login Time', 'User', 'Successful', 'IP Address', 
                'User Agent', 'Logout Time', 'Session Duration'
            ])
            for obj in queryset:
                writer.writerow([
                    obj.id, obj.login_time, obj.user, obj.login_successful,
                    obj.ip_address, obj.user_agent[:100] if obj.user_agent else '',
                    obj.logout_time, obj.session_duration
                ])
        
        return response
    
    def _export_json(self, queryset, filename):
        """
        Export queryset to JSON format.
        """
        response = HttpResponse(content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename="{filename}.json"'
        
        data = []
        for obj in queryset:
            item = {
                'id': obj.id,
                'timestamp': obj.timestamp.isoformat(),
            }
            
            if queryset.model == AuditLog:
                item.update({
                    'user': obj.user.email if obj.user else None,
                    'action': obj.action,
                    'model_name': obj.model_name,
                    'object_id': obj.object_id,
                    'object_repr': obj.object_repr,
                    'ip_address': obj.ip_address,
                    'user_agent': obj.user_agent,
                    'changed_fields': obj.changed_fields,
                    'old_values': obj.old_values,
                    'new_values': obj.new_values,
                })
            
            elif queryset.model == ActivityLog:
                item.update({
                    'user': obj.user.email if obj.user else None,
                    'activity_type': obj.activity_type,
                    'description': obj.description,
                    'ip_address': obj.ip_address,
                    'metadata': obj.metadata,
                })
            
            elif queryset.model == SecurityEvent:
                item.update({
                    'user': obj.user.email if obj.user else None,
                    'event_type': obj.event_type,
                    'severity': obj.severity,
                    'description': obj.description,
                    'source_ip': obj.source_ip,
                    'resolved': obj.resolved,
                    'resolved_by': obj.resolved_by.email if obj.resolved_by else None,
                    'resolved_at': obj.resolved_at.isoformat() if obj.resolved_at else None,
                    'event_data': obj.event_data,
                })
            
            elif queryset.model == LoginLog:
                item.update({
                    'user': obj.user.email if obj.user else None,
                    'login_successful': obj.login_successful,
                    'failure_reason': obj.failure_reason,
                    'ip_address': obj.ip_address,
                    'user_agent': obj.user_agent,
                    'logout_time': obj.logout_time.isoformat() if obj.logout_time else None,
                    'session_duration': str(obj.session_duration) if obj.session_duration else None,
                })
            
            data.append(item)
        
        json.dump(data, response, indent=2)
        return response


@require_POST
@login_required
def resolve_security_event(request, event_id):
    """
    Resolve a security event.
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        messages.error(request, 'Tenant not found')
        return redirect('audit:security_events')
    
    event = get_object_or_404(SecurityEvent, id=event_id, tenant=tenant)
    resolution_notes = request.POST.get('resolution_notes', '')
    
    event.resolve(request.user, resolution_notes)
    
    # Log the resolution
    log_activity(
        tenant=tenant,
        user=request.user,
        activity_type='security_event',
        description=f"Resolved security event: {event.event_type}",
        related_object=event,
        request=request
    )
    
    messages.success(request, 'Security event resolved successfully')
    return redirect('audit:security_event_detail', pk=event_id)


@require_POST
@login_required
def bulk_resolve_security_events(request):
    """
    Bulk resolve multiple security events.
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        messages.error(request, 'Tenant not found')
        return redirect('audit:security_events')
    
    event_ids = request.POST.getlist('event_ids')
    resolution_notes = request.POST.get('resolution_notes', '')
    
    if not event_ids:
        messages.error(request, 'No events selected')
        return redirect('audit:security_events')
    
    events = SecurityEvent.objects.filter(id__in=event_ids, tenant=tenant, resolved=False)
    count = 0
    
    for event in events:
        event.resolve(request.user, resolution_notes)
        count += 1
    
    # Log the bulk resolution
    log_activity(
        tenant=tenant,
        user=request.user,
        activity_type='security_event',
        description=f"Bulk resolved {count} security events",
        request=request
    )
    
    messages.success(request, f'{count} security events resolved successfully')
    return redirect('audit:security_events')