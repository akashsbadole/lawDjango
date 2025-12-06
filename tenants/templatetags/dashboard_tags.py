from django import template
from django.db.models import Count, Sum, Avg, F
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
from decimal import Decimal

from ..models import Tenant
from ..dashboard_models import DashboardWidget, UserDashboard, UserDashboardWidget
from cases.models import Case, CaseEvent
from clients.models import Client
from billing.models import Invoice, Payment, TimeEntry
from documents.models import Document

register = template.Library()


@register.simple_tag
def get_dashboard_widgets(user):
    """
    Get dashboard widgets for a user.
    """
    if hasattr(user, 'tenant') and user.tenant:
        dashboard = UserDashboard.objects.get_or_create_for_user(user)
        return UserDashboardWidget.objects.for_dashboard(dashboard).ordered()
    return []


@register.simple_tag
def get_widget_data(widget, tenant, user):
    """
    Get data for a specific widget.
    """
    cache_key = f"widget_data_{widget.id}_{tenant.id}_{user.role}"
    cached_data = cache.get(cache_key)
    
    if cached_data:
        return cached_data
    
    data = _get_widget_data_internal(widget, tenant, user)
    
    # Cache for 5 minutes
    cache.set(cache_key, data, 300)
    
    return data


def _get_widget_data_internal(widget, tenant, user):
    """
    Internal function to get widget data.
    """
    if widget.widget.widget_type == 'stats_card':
        return get_stats_card_data(widget.widget, tenant, user)
    elif widget.widget.widget_type == 'chart':
        return get_chart_data(widget.widget, tenant, user)
    elif widget.widget.widget_type == 'activity_feed':
        return get_activity_feed_data(tenant, user, widget.limit or 10)
    elif widget.widget.widget_type == 'upcoming_deadlines':
        return get_upcoming_deadlines_data(tenant, user, widget.limit or 10)
    elif widget.widget.widget_type == 'quick_actions':
        return get_quick_actions_data(user)
    elif widget.widget.widget_type == 'performance_metrics':
        return get_performance_metrics_data(tenant, user)
    
    return {}


@register.simple_tag
def get_stats_card_data(widget, tenant, user):
    """
    Get data for stats card widgets.
    """
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
        if user.role in ['admin', 'billing_manager']:
            return Invoice.objects.filter(
                tenant=tenant, 
                deleted_at__isnull=True, 
                status__in=['draft', 'sent']
            ).count()
        return 0
    elif widget.stat_type == 'monthly_revenue':
        if user.role in ['admin', 'billing_manager']:
            start_date = timezone.now().replace(day=1)
            revenue = Payment.objects.filter(
                tenant=tenant,
                payment_date__gte=start_date
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            return float(revenue)
        return 0
    elif widget.stat_type == 'storage_used':
        return tenant.get_storage_used()
    elif widget.stat_type == 'user_count':
        return tenant.get_current_user_count()
    
    return 0


@register.simple_tag
def get_chart_data(widget, tenant, user):
    """
    Get data for chart widgets.
    """
    end_date = timezone.now()
    start_date = end_date - timedelta(days=widget.date_range_days or 30)
    
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
    
    elif widget.data_source == 'revenue':
        # Monthly revenue trend
        if user.role in ['admin', 'billing_manager']:
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
            
            return {
                'labels': list(reversed(monthly_labels)),
                'data': list(reversed(monthly_revenue)),
                'type': widget.chart_type or 'line'
            }
    
    elif widget.data_source == 'documents':
        # Document uploads over time
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
    
    elif widget.data_source == 'clients':
        # Client acquisition
        client_acquisition = []
        client_labels = []
        
        for i in range(6):
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
        
        return {
            'labels': list(reversed(client_labels)),
            'data': list(reversed(client_acquisition)),
            'type': widget.chart_type or 'bar'
        }
    
    return {'labels': [], 'data': [], 'type': 'bar'}


@register.simple_tag
def get_activity_feed_data(tenant, user, limit=10):
    """
    Get data for activity feed widgets.
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
    
    return activities[:limit]


@register.simple_tag
def get_upcoming_deadlines_data(tenant, user, limit=10):
    """
    Get data for upcoming deadlines widgets.
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
    
    return deadlines[:limit]


@register.simple_tag
def get_quick_actions_data(user):
    """
    Get data for quick actions widgets.
    """
    actions = []
    
    # Common actions for all users
    actions.append({
        'title': 'Create Case',
        'url': '/cases/create/',
        'icon': 'fas fa-folder-plus',
        'color': 'primary'
    })
    
    actions.append({
        'title': 'Add Client',
        'url': '/clients/create/',
        'icon': 'fas fa-user-plus',
        'color': 'success'
    })
    
    actions.append({
        'title': 'Upload Document',
        'url': '/documents/upload/',
        'icon': 'fas fa-upload',
        'color': 'warning'
    })
    
    # Role-specific actions
    if user.role in ['admin', 'billing_manager']:
        actions.append({
            'title': 'Create Invoice',
            'url': '/billing/invoice/create/',
            'icon': 'fas fa-file-invoice',
            'color': 'info'
        })
        
        actions.append({
            'title': 'Log Time',
            'url': '/billing/time-entry/create/',
            'icon': 'fas fa-clock',
            'color': 'secondary'
        })
    
    return actions


@register.simple_tag
def get_performance_metrics_data(tenant, user):
    """
    Get data for performance metrics widgets.
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
            metrics['billing_efficiency'] = round((billable_time / total_time) * 100, 1)
        
        # Invoice collection rate
        total_invoiced = Invoice.objects.filter(
            tenant=tenant,
            deleted_at__isnull=True
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        
        total_collected = Payment.objects.filter(
            tenant=tenant
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        if total_invoiced > 0:
            metrics['collection_rate'] = round((total_collected / total_invoiced) * 100, 1)
    
    return metrics


@register.filter
def widget_size_class(size):
    """
    Convert widget size to Bootstrap grid class.
    """
    size_map = {
        'small': 'col-md-3',
        'medium': 'col-md-6',
        'large': 'col-md-8',
        'full': 'col-md-12',
    }
    return size_map.get(size, 'col-md-6')


@register.filter
def format_chart_data(data):
    """
    Format chart data for JavaScript consumption.
    """
    import json
    return json.dumps(data)


@register.filter
def get_stat_icon(stat_type):
    """
    Get icon for a stat type.
    """
    icon_map = {
        'total_clients': 'fas fa-user-tie',
        'total_cases': 'fas fa-folder-open',
        'total_documents': 'fas fa-file-alt',
        'total_invoices': 'fas fa-file-invoice',
        'active_cases': 'fas fa-folder',
        'unpaid_invoices': 'fas fa-file-invoice-dollar',
        'monthly_revenue': 'fas fa-chart-line',
        'storage_used': 'fas fa-database',
        'user_count': 'fas fa-users',
    }
    return icon_map.get(stat_type, 'fas fa-chart-bar')


@register.filter
def get_stat_color(stat_type):
    """
    Get color for a stat type.
    """
    color_map = {
        'total_clients': 'primary',
        'total_cases': 'success',
        'total_documents': 'info',
        'total_invoices': 'warning',
        'active_cases': 'success',
        'unpaid_invoices': 'danger',
        'monthly_revenue': 'success',
        'storage_used': 'warning',
        'user_count': 'primary',
    }
    return color_map.get(stat_type, 'secondary')