from django.core.management.base import BaseCommand
from django.db import transaction
from tenants.dashboard_models import DashboardWidget


class Command(BaseCommand):
    help = 'Create default dashboard widgets for all tenants'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset all widgets before creating defaults',
        )
    
    def handle(self, *args, **options):
        reset = options['reset']
        
        if reset:
            self.stdout.write('Resetting existing widgets...')
            DashboardWidget.objects.all().delete()
        
        with transaction.atomic():
            # Create default statistics widgets
            stats_widgets = [
                {
                    'widget_type': 'stats_card',
                    'title': 'Total Clients',
                    'description': 'Total number of clients in the system',
                    'stat_type': 'total_clients',
                    'is_default': True,
                    'position': 1,
                    'size': 'small',
                    'visible_to_roles': ['admin', 'lawyer', 'billing_manager', 'paralegal', 'staff'],
                },
                {
                    'widget_type': 'stats_card',
                    'title': 'Total Cases',
                    'description': 'Total number of cases in the system',
                    'stat_type': 'total_cases',
                    'is_default': True,
                    'position': 2,
                    'size': 'small',
                    'visible_to_roles': ['admin', 'lawyer', 'billing_manager', 'paralegal', 'staff'],
                },
                {
                    'widget_type': 'stats_card',
                    'title': 'Total Documents',
                    'description': 'Total number of documents in the system',
                    'stat_type': 'total_documents',
                    'is_default': True,
                    'position': 3,
                    'size': 'small',
                    'visible_to_roles': ['admin', 'lawyer', 'billing_manager', 'paralegal', 'staff'],
                },
                {
                    'widget_type': 'stats_card',
                    'title': 'Active Cases',
                    'description': 'Number of currently active cases',
                    'stat_type': 'active_cases',
                    'is_default': True,
                    'position': 4,
                    'size': 'small',
                    'visible_to_roles': ['admin', 'lawyer', 'billing_manager', 'paralegal', 'staff'],
                },
                {
                    'widget_type': 'stats_card',
                    'title': 'Monthly Revenue',
                    'description': 'Total revenue for the current month',
                    'stat_type': 'monthly_revenue',
                    'is_default': True,
                    'position': 5,
                    'size': 'small',
                    'visible_to_roles': ['admin', 'billing_manager'],
                },
                {
                    'widget_type': 'stats_card',
                    'title': 'Unpaid Invoices',
                    'description': 'Number of unpaid invoices',
                    'stat_type': 'unpaid_invoices',
                    'is_default': True,
                    'position': 6,
                    'size': 'small',
                    'visible_to_roles': ['admin', 'billing_manager'],
                },
                {
                    'widget_type': 'stats_card',
                    'title': 'Storage Used',
                    'description': 'Storage usage in MB',
                    'stat_type': 'storage_used',
                    'is_default': True,
                    'position': 7,
                    'size': 'small',
                    'visible_to_roles': ['admin', 'lawyer', 'billing_manager', 'paralegal', 'staff'],
                },
            ]
            
            # Create chart widgets
            chart_widgets = [
                {
                    'widget_type': 'chart',
                    'title': 'Cases by Type',
                    'description': 'Distribution of cases by type',
                    'chart_type': 'pie',
                    'data_source': 'cases',
                    'is_default': True,
                    'position': 8,
                    'size': 'medium',
                    'visible_to_roles': ['admin', 'lawyer', 'billing_manager', 'paralegal', 'staff'],
                },
                {
                    'widget_type': 'chart',
                    'title': 'Monthly Revenue Trend',
                    'description': 'Revenue trend over the last 6 months',
                    'chart_type': 'line',
                    'data_source': 'revenue',
                    'is_default': True,
                    'position': 9,
                    'size': 'medium',
                    'visible_to_roles': ['admin', 'billing_manager'],
                },
                {
                    'widget_type': 'chart',
                    'title': 'Document Uploads',
                    'description': 'Document uploads over the last 30 days',
                    'chart_type': 'bar',
                    'data_source': 'documents',
                    'is_default': True,
                    'position': 10,
                    'size': 'medium',
                    'visible_to_roles': ['admin', 'lawyer', 'billing_manager', 'paralegal', 'staff'],
                },
                {
                    'widget_type': 'chart',
                    'title': 'Client Acquisition',
                    'description': 'New clients acquired over the last 6 months',
                    'chart_type': 'bar',
                    'data_source': 'clients',
                    'is_default': True,
                    'position': 11,
                    'size': 'medium',
                    'visible_to_roles': ['admin', 'lawyer', 'billing_manager', 'paralegal', 'staff'],
                },
            ]
            
            # Create activity feed widget
            activity_widgets = [
                {
                    'widget_type': 'activity_feed',
                    'title': 'Recent Activities',
                    'description': 'Recent activities in the system',
                    'is_default': True,
                    'position': 12,
                    'size': 'large',
                    'limit': 10,
                    'visible_to_roles': ['admin', 'lawyer', 'billing_manager', 'paralegal', 'staff'],
                },
            ]
            
            # Create upcoming deadlines widget
            deadline_widgets = [
                {
                    'widget_type': 'upcoming_deadlines',
                    'title': 'Upcoming Deadlines',
                    'description': 'Upcoming deadlines and important dates',
                    'is_default': True,
                    'position': 13,
                    'size': 'medium',
                    'limit': 10,
                    'visible_to_roles': ['admin', 'lawyer', 'billing_manager', 'paralegal', 'staff'],
                },
            ]
            
            # Create quick actions widget
            quick_actions_widgets = [
                {
                    'widget_type': 'quick_actions',
                    'title': 'Quick Actions',
                    'description': 'Common actions and shortcuts',
                    'is_default': True,
                    'position': 14,
                    'size': 'medium',
                    'visible_to_roles': ['admin', 'lawyer', 'billing_manager', 'paralegal', 'staff'],
                },
            ]
            
            # Create performance metrics widget
            performance_widgets = [
                {
                    'widget_type': 'performance_metrics',
                    'title': 'Performance Metrics',
                    'description': 'Key performance indicators',
                    'is_default': True,
                    'position': 15,
                    'size': 'medium',
                    'visible_to_roles': ['admin', 'billing_manager'],
                },
            ]
            
            # Combine all widgets
            all_widgets = (
                stats_widgets + 
                chart_widgets + 
                activity_widgets + 
                deadline_widgets + 
                quick_actions_widgets + 
                performance_widgets
            )
            
            # Create widgets
            created_count = 0
            for widget_data in all_widgets:
                widget, created = DashboardWidget.objects.get_or_create(
                    title=widget_data['title'],
                    defaults=widget_data
                )
                if created:
                    created_count += 1
                    self.stdout.write(f'Created widget: {widget.title}')
                else:
                    self.stdout.write(f'Widget already exists: {widget.title}')
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully created {created_count} new dashboard widgets. '
                    f'Total widgets: {DashboardWidget.objects.count()}'
                )
            )