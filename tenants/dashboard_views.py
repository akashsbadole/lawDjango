from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q, F
from django.core.cache import cache
from django.core.serializers.json import DjangoJSONEncoder
import json
from datetime import datetime, timedelta
from decimal import Decimal

from .models import Tenant
from .dashboard_models import DashboardWidget, UserDashboard, UserDashboardWidget, DashboardActivity
from .dashboard_managers import DashboardActivityManager

# Import models from other apps
from cases.models import Case, CaseEvent
from clients.models import Client
from billing.models import Invoice, Payment, TimeEntry
from documents.models import Document

User = get_user_model()


@login_required
def enhanced_dashboard(request, slug=None):
    """
    Enhanced dashboard view with comprehensive statistics and widgets.
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
    
    # Get or create user dashboard
    dashboard = UserDashboard.objects.get_or_create_for_user(request.user)
    
    # Get dashboard widgets for this user
    dashboard_widgets = UserDashboardWidget.objects.for_dashboard(dashboard).ordered()
    
    # Log dashboard view activity
    DashboardActivity.objects.log_activity(
        user=request.user,
        action='view',
        tenant=tenant,
        details={'widgets_count': len(dashboard_widgets)}
    )
    
    # Get dashboard data with caching
    cache_key = f"dashboard_data_{tenant.id}_{request.user.role}"
    dashboard_data = cache.get(cache_key)
    
    if not dashboard_data:
        dashboard_data = get_dashboard_data(tenant, request.user)
        # Cache for 5 minutes
        cache.set(cache_key, dashboard_data, 300)
    
    context = {
        'tenant': tenant,
        'user_count': tenant.get_current_user_count(),
        'storage_used': tenant.get_storage_used(),
        'can_add_user': tenant.can_add_user(),
        'dashboard': dashboard,
        'dashboard_widgets': dashboard_widgets,
        'dashboard_data': dashboard_data,
    }
    
    return render(request, 'tenants/enhanced_dashboard.html', context)


def get_dashboard_data(tenant, user):
    """
    Get comprehensive dashboard data based on user role and permissions.
    """
    # Base date range for data (last 30 days by default)
    end_date = timezone.now()
    start_date = end_date - timedelta(days=30)
    
    data = {
        'stats': get_statistics(tenant, user, start_date, end_date),
        'charts': get_chart_data(tenant, user, start_date, end_date),
        'activities': get_recent_activities(tenant, user),
        'deadlines': get_upcoming_deadlines(tenant, user),
        'performance': get_performance_metrics(tenant, user),
    }
    
    return data


def get_statistics(tenant, user, start_date, end_date):
    """
    Get dashboard statistics based on user role.
    """
    stats = {}
    
    # Basic stats (visible to all roles)
    stats['total_clients'] = Client.objects.filter(tenant=tenant, deleted_at__isnull=True).count()
    stats['total_cases'] = Case.objects.filter(tenant=tenant, deleted_at__isnull=True).count()
    stats['total_documents'] = Document.objects.filter(tenant=tenant, deleted_at__isnull=True).count()
    stats['total_invoices'] = Invoice.objects.filter(tenant=tenant, deleted_at__isnull=True).count()
    
    # Active cases by status
    cases_by_status = Case.objects.filter(
        tenant=tenant, 
        deleted_at__isnull=True
    ).values('status').annotate(count=Count('id'))
    stats['cases_by_status'] = {item['status']: item['count'] for item in cases_by_status}
    
    # Recent activities count
    stats['new_clients_this_month'] = Client.objects.filter(
        tenant=tenant,
        deleted_at__isnull=True,
        created_at__gte=start_date
    ).count()
    
    stats['new_cases_this_month'] = Case.objects.filter(
        tenant=tenant,
        deleted_at__isnull=True,
        created_at__gte=start_date
    ).count()
    
    stats['new_documents_this_month'] = Document.objects.filter(
        tenant=tenant,
        deleted_at__isnull=True,
        created_at__gte=start_date
    ).count()
    
    # Role-specific stats
    if user.role in ['admin', 'billing_manager']:
        # Financial stats
        stats['unpaid_invoices'] = Invoice.objects.filter(
            tenant=tenant,
            deleted_at__isnull=True,
            status__in=['draft', 'sent']
        ).count()
        
        stats['monthly_revenue'] = Payment.objects.filter(
            tenant=tenant,
            payment_date__gte=start_date
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        stats['total_outstanding'] = Invoice.objects.filter(
            tenant=tenant,
            deleted_at__isnull=True,
            status__in=['draft', 'sent']
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        
        stats['unbilled_time_entries'] = TimeEntry.objects.filter(
            tenant=tenant,
            deleted_at__isnull=True,
            is_billable=True
        ).exclude(
            invoice_items__isnull=False
        ).count()
    
    if user.role in ['admin', 'lawyer']:
        # Case-related stats
        stats['assigned_cases'] = Case.objects.filter(
            tenant=tenant,
            deleted_at__isnull=True,
            assigned_lawyers=user
        ).count()
        
        # Average case resolution time
        resolved_cases = Case.objects.filter(
            tenant=tenant,
            deleted_at__isnull=True,
            status__in=['closed', 'settled'],
            end_date__isnull=False
        )
        if resolved_cases.exists():
            avg_duration = resolved_cases.aggregate(
                avg_duration=Avg(F('end_date') - F('start_date'))
            )['avg_duration']
            if avg_duration:
                stats['avg_case_resolution_days'] = avg_duration.days
    
    # Storage usage
    stats['storage_used'] = tenant.get_storage_used()
    stats['storage_percentage'] = (stats['storage_used'] / tenant.max_storage_mb) * 100 if tenant.max_storage_mb > 0 else 0
    
    return stats


def get_chart_data(tenant, user, start_date, end_date):
    """
    Get data for dashboard charts.
    """
    charts = {}
    
    # Cases by type pie chart
    cases_by_type = Case.objects.filter(
        tenant=tenant,
        deleted_at__isnull=True
    ).values('case_type').annotate(count=Count('id'))
    
    charts['cases_by_type'] = {
        'labels': [item['case_type'].replace('_', ' ').title() for item in cases_by_type],
        'data': [item['count'] for item in cases_by_type],
        'type': 'pie'
    }
    
    # Monthly revenue trend (for admin and billing managers)
    if user.role in ['admin', 'billing_manager']:
        # Get last 6 months of revenue data
        monthly_revenue = []
        monthly_labels = []
        
        for i in range(6):
            month_start = (end_date - timedelta(days=30*i)).replace(day=1)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            revenue = Payment.objects.filter(
                tenant=tenant,
                payment_date__gte=month_start,
                payment_date__lte=month_end
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            monthly_revenue.append(float(revenue))
            monthly_labels.append(month_start.strftime('%b %Y'))
        
        charts['monthly_revenue'] = {
            'labels': list(reversed(monthly_labels)),
            'data': list(reversed(monthly_revenue)),
            'type': 'line'
        }
    
    # Document uploads over time
    document_uploads = []
    document_labels = []
    
    for i in range(30):  # Last 30 days
        day = end_date - timedelta(days=i)
        count = Document.objects.filter(
            tenant=tenant,
            deleted_at__isnull=True,
            created_at__date=day.date()
        ).count()
        
        document_uploads.append(count)
        document_labels.append(day.strftime('%m/%d'))
    
    charts['document_uploads'] = {
        'labels': list(reversed(document_labels)),
        'data': list(reversed(document_uploads)),
        'type': 'bar'
    }
    
    # Client acquisition chart
    client_acquisition = []
    client_labels = []
    
    for i in range(6):  # Last 6 months
        month_start = (end_date - timedelta(days=30*i)).replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        count = Client.objects.filter(
            tenant=tenant,
            deleted_at__isnull=True,
            created_at__gte=month_start,
            created_at__lte=month_end
        ).count()
        
        client_acquisition.append(count)
        client_labels.append(month_start.strftime('%b %Y'))
    
    charts['client_acquisition'] = {
        'labels': list(reversed(client_labels)),
        'data': list(reversed(client_acquisition)),
        'type': 'bar'
    }
    
    return charts


def get_recent_activities(tenant, user):
    """
    Get recent activities for the activity feed.
    """
    activities = []
    
    # Recent case updates
    recent_cases = Case.objects.filter(
        tenant=tenant,
        deleted_at__isnull=True,
        updated_at__gte=timezone.now() - timedelta(days=7)
    ).order_by('-updated_at')[:5]
    
    for case in recent_cases:
        activities.append({
            'type': 'case_update',
            'title': f'Case "{case.title}" updated',
            'description': f'Status: {case.get_status_display()}',
            'timestamp': case.updated_at,
            'url': case.get_absolute_url(),
            'icon': 'fas fa-folder-open'
        })
    
    # New documents
    recent_docs = Document.objects.filter(
        tenant=tenant,
        deleted_at__isnull=True,
        created_at__gte=timezone.now() - timedelta(days=7)
    ).order_by('-created_at')[:5]
    
    for doc in recent_docs:
        activities.append({
            'type': 'document_upload',
            'title': f'Document "{doc.title}" uploaded',
            'description': f'Category: {doc.get_category_display()}',
            'timestamp': doc.created_at,
            'url': doc.get_absolute_url(),
            'icon': 'fas fa-file-alt'
        })
    
    # Invoice status changes
    recent_invoices = Invoice.objects.filter(
        tenant=tenant,
        deleted_at__isnull=True,
        updated_at__gte=timezone.now() - timedelta(days=7)
    ).order_by('-updated_at')[:5]
    
    for invoice in recent_invoices:
        activities.append({
            'type': 'invoice_update',
            'title': f'Invoice {invoice.invoice_number} updated',
            'description': f'Status: {invoice.get_status_display()}',
            'timestamp': invoice.updated_at,
            'url': invoice.get_absolute_url(),
            'icon': 'fas fa-file-invoice-dollar'
        })
    
    # Sort all activities by timestamp
    activities.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return activities[:10]  # Return only the 10 most recent activities


def get_upcoming_deadlines(tenant, user):
    """
    Get upcoming deadlines and important dates.
    """
    deadlines = []
    now = timezone.now()
    
    # Upcoming hearings and events
    upcoming_events = CaseEvent.objects.filter(
        tenant=tenant,
        event_date__gte=now,
        event_date__lte=now + timedelta(days=30)
    ).order_by('event_date')[:10]
    
    for event in upcoming_events:
        deadlines.append({
            'type': 'event',
            'title': event.title,
            'description': f'{event.get_event_type_display()} - {event.case.title}',
            'date': event.event_date,
            'url': event.get_absolute_url(),
            'icon': 'fas fa-calendar-alt'
        })
    
    # Invoice due dates (for admin and billing managers)
    if user.role in ['admin', 'billing_manager']:
        due_invoices = Invoice.objects.filter(
            tenant=tenant,
            deleted_at__isnull=True,
            status__in=['draft', 'sent'],
            due_date__gte=now,
            due_date__lte=now + timedelta(days=30)
        ).order_by('due_date')[:10]
        
        for invoice in due_invoices:
            deadlines.append({
                'type': 'invoice_due',
                'title': f'Invoice {invoice.invoice_number} due',
                'description': f'Client: {invoice.client.full_name} - Amount: ${invoice.total_amount}',
                'date': invoice.due_date,
                'url': invoice.get_absolute_url(),
                'icon': 'fas fa-file-invoice-dollar'
            })
    
    # Sort all deadlines by date
    deadlines.sort(key=lambda x: x['date'])
    
    return deadlines[:10]  # Return only the 10 upcoming deadlines


def get_performance_metrics(tenant, user):
    """
    Get performance metrics for the dashboard.
    """
    metrics = {}
    
    # Case resolution time
    resolved_cases = Case.objects.filter(
        tenant=tenant,
        deleted_at__isnull=True,
        status__in=['closed', 'settled'],
        end_date__isnull=False
    )
    
    if resolved_cases.exists():
        avg_duration = resolved_cases.aggregate(
            avg_duration=Avg(F('end_date') - F('start_date'))
        )['avg_duration']
        if avg_duration:
            metrics['avg_case_resolution_days'] = avg_duration.days
    
    # Billing efficiency (for admin and billing managers)
    if user.role in ['admin', 'billing_manager']:
        # Calculate billable vs non-billable time
        total_time = TimeEntry.objects.filter(
            tenant=tenant,
            deleted_at__isnull=True
        ).aggregate(total_hours=Sum('hours'))['total_hours'] or Decimal('0.00')
        
        billable_time = TimeEntry.objects.filter(
            tenant=tenant,
            deleted_at__isnull=True,
            is_billable=True
        ).aggregate(billable_hours=Sum('hours'))['billable_hours'] or Decimal('0.00')
        
        if total_time > 0:
            metrics['billing_efficiency'] = (billable_time / total_time) * 100
        
        # Invoice collection rate
        total_invoiced = Invoice.objects.filter(
            tenant=tenant,
            deleted_at__isnull=True
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        
        total_collected = Payment.objects.filter(
            tenant=tenant
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        if total_invoiced > 0:
            metrics['collection_rate'] = (total_collected / total_invoiced) * 100
    
    return metrics


@login_required
@require_POST
def update_widget_position(request):
    """
    Update widget position and size via AJAX.
    """
    try:
        data = json.loads(request.body)
        widget_id = data.get('widget_id')
        position = data.get('position')
        size = data.get('size')
        
        if not all([widget_id, position is not None]):
            return JsonResponse({'success': False, 'error': 'Missing required data'})
        
        # Get user dashboard
        dashboard = UserDashboard.objects.get_or_create_for_user(request.user)
        
        # Update widget position
        widget = UserDashboardWidget.objects.get(
            dashboard=dashboard,
            widget_id=widget_id
        )
        widget.position = position
        if size:
            widget.size = size
        widget.save()
        
        # Log activity
        DashboardActivity.objects.log_activity(
            user=request.user,
            action='customize',
            tenant=request.user.tenant,
            widget_id=widget_id,
            details={'action': 'update_position', 'position': position, 'size': size}
        )
        
        return JsonResponse({'success': True})
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def export_dashboard_data(request):
    """
    Export dashboard data as JSON or CSV.
    """
    export_format = request.GET.get('format', 'json')
    
    # Get tenant
    if hasattr(request, 'tenant') and request.tenant:
        tenant = request.tenant
    else:
        return JsonResponse({'error': 'No tenant specified'}, status=400)
    
    # Get dashboard data
    dashboard_data = get_dashboard_data(tenant, request.user)
    
    # Log export activity
    DashboardActivity.objects.log_activity(
        user=request.user,
        action='export',
        tenant=tenant,
        details={'format': export_format}
    )
    
    if export_format == 'json':
        response = HttpResponse(
            json.dumps(dashboard_data, cls=DjangoJSONEncoder),
            content_type='application/json'
        )
        response['Content-Disposition'] = f'attachment; filename="dashboard_data_{tenant.slug}_{timezone.now().strftime("%Y%m%d")}.json"'
        return response
    
    elif export_format == 'csv':
        # Create CSV response for stats
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Metric', 'Value'])
        
        # Write stats
        for key, value in dashboard_data['stats'].items():
            writer.writerow([key, value])
        
        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="dashboard_stats_{tenant.slug}_{timezone.now().strftime("%Y%m%d")}.csv"'
        return response
    
    return JsonResponse({'error': 'Invalid export format'}, status=400)


@login_required
def widget_data(request, widget_id):
    """
    Get data for a specific widget via AJAX.
    """
    try:
        # Get widget
        widget = get_object_or_404(DashboardWidget, id=widget_id)
        
        # Check if user can view this widget
        if not widget.is_visible_to_user(request.user):
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        # Get tenant
        if hasattr(request, 'tenant') and request.tenant:
            tenant = request.tenant
        else:
            return JsonResponse({'error': 'No tenant specified'}, status=400)
        
        # Get widget-specific data
        data = get_widget_data(widget, tenant, request.user)
        
        # Log widget click activity
        DashboardActivity.objects.log_activity(
            user=request.user,
            action='widget_click',
            tenant=tenant,
            widget_id=widget_id,
            details={'widget_type': widget.widget_type}
        )
        
        return JsonResponse({'success': True, 'data': data})
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def get_widget_data(widget, tenant, user):
    """
    Get data for a specific widget based on its type and configuration.
    """
    if widget.widget_type == 'stats_card':
        if widget.stat_type == 'total_clients':
            return Client.objects.filter(tenant=tenant, deleted_at__isnull=True).count()
        elif widget.stat_type == 'total_cases':
            return Case.objects.filter(tenant=tenant, deleted_at__isnull=True).count()
        elif widget.stat_type == 'total_documents':
            return Document.objects.filter(tenant=tenant, deleted_at__isnull=True).count()
        elif widget.stat_type == 'total_invoices':
            return Invoice.objects.filter(tenant=tenant, deleted_at__isnull=True).count()
        elif widget.stat_type == 'active_cases':
            return Case.objects.filter(tenant=tenant, deleted_at__isnull=True, status='open').count()
        elif widget.stat_type == 'unpaid_invoices':
            return Invoice.objects.filter(
                tenant=tenant, 
                deleted_at__isnull=True, 
                status__in=['draft', 'sent']
            ).count()
        elif widget.stat_type == 'monthly_revenue':
            start_date = timezone.now().replace(day=1)
            return Payment.objects.filter(
                tenant=tenant,
                payment_date__gte=start_date
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        elif widget.stat_type == 'storage_used':
            return tenant.get_storage_used()
        elif widget.stat_type == 'user_count':
            return tenant.get_current_user_count()
    
    elif widget.widget_type == 'chart':
        # Return chart data based on widget configuration
        if widget.data_source == 'cases':
            # Cases by type
            cases_by_type = Case.objects.filter(
                tenant=tenant,
                deleted_at__isnull=True
            ).values('case_type').annotate(count=Count('id'))
            
            return {
                'labels': [item['case_type'].replace('_', ' ').title() for item in cases_by_type],
                'data': [item['count'] for item in cases_by_type],
                'type': widget.chart_type or 'pie'
            }
        
        elif widget.data_source == 'documents':
            # Document uploads over time
            end_date = timezone.now()
            start_date = end_date - timedelta(days=widget.date_range_days)
            
            document_uploads = []
            document_labels = []
            
            current_date = start_date
            while current_date <= end_date:
                count = Document.objects.filter(
                    tenant=tenant,
                    deleted_at__isnull=True,
                    created_at__date=current_date.date()
                ).count()
                
                document_uploads.append(count)
                document_labels.append(current_date.strftime('%m/%d'))
                current_date += timedelta(days=1)
            
            return {
                'labels': document_labels,
                'data': document_uploads,
                'type': widget.chart_type or 'line'
            }
    
    elif widget.widget_type == 'activity_feed':
        # Return recent activities
        return get_recent_activities(tenant, user)[:widget.limit]
    
    elif widget.widget_type == 'upcoming_deadlines':
        # Return upcoming deadlines
        return get_upcoming_deadlines(tenant, user)[:widget.limit]
    
    return {}