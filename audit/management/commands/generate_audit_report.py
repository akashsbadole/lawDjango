import csv
import json
from io import StringIO
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.utils import timezone
from django.template.loader import render_to_string
from django.db.models import Count, Q
from audit.models import AuditLog, ActivityLog, SecurityEvent, LoginLog
from tenants.models import Tenant


class Command(BaseCommand):
    help = 'Generate audit reports for compliance and analysis'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--report-type',
            choices=['user_activity', 'security_summary', 'login_analytics', 'data_access', 'compliance'],
            required=True,
            help='Type of report to generate',
        )
        parser.add_argument(
            '--date-range',
            choices=['7', '30', '90', '365', 'custom'],
            default='30',
            help='Date range for the report (default: 30 days)',
        )
        parser.add_argument(
            '--date-from',
            type=str,
            help='Custom start date (YYYY-MM-DD)',
        )
        parser.add_argument(
            '--date-to',
            type=str,
            help='Custom end date (YYYY-MM-DD)',
        )
        parser.add_argument(
            '--tenant-id',
            type=int,
            help='Specific tenant ID (default: all tenants)',
        )
        parser.add_argument(
            '--format',
            choices=['json', 'csv', 'html'],
            default='json',
            help='Output format (default: json)',
        )
        parser.add_argument(
            '--output',
            type=str,
            help='Output file path (default: stdout)',
        )
        parser.add_argument(
            '--email',
            type=str,
            help='Email address to send report to',
        )
    
    def handle(self, *args, **options):
        report_type = options['report_type']
        date_range = options['date_range']
        date_from = options['date_from']
        date_to = options['date_to']
        tenant_id = options['tenant_id']
        output_format = options['format']
        output_file = options['output']
        email = options['email']
        
        # Calculate date range
        now = timezone.now()
        if date_range == 'custom':
            if not date_from or not date_to:
                self.stdout.write(
                    self.style.ERROR('Custom date range requires both --date-from and --date-to')
                )
                return
            start_date = datetime.strptime(date_from, '%Y-%m-%d')
            end_date = datetime.strptime(date_to, '%Y-%m-%d')
        else:
            days = int(date_range)
            start_date = now - timedelta(days=days)
            end_date = now
        
        # Build tenant filter
        tenant_filter = {}
        if tenant_id:
            tenant_filter['tenant_id'] = tenant_id
        
        # Generate report based on type
        if report_type == 'user_activity':
            report_data = self.generate_user_activity_report(start_date, end_date, tenant_filter)
        elif report_type == 'security_summary':
            report_data = self.generate_security_summary_report(start_date, end_date, tenant_filter)
        elif report_type == 'login_analytics':
            report_data = self.generate_login_analytics_report(start_date, end_date, tenant_filter)
        elif report_type == 'data_access':
            report_data = self.generate_data_access_report(start_date, end_date, tenant_filter)
        elif report_type == 'compliance':
            report_data = self.generate_compliance_report(start_date, end_date, tenant_filter)
        else:
            self.stdout.write(
                self.style.ERROR(f'Unknown report type: {report_type}')
            )
            return
        
        # Format output
        if output_format == 'json':
            output = json.dumps(report_data, indent=2, default=str)
        elif output_format == 'csv':
            output = self.format_as_csv(report_data, report_type)
        elif output_format == 'html':
            output = self.format_as_html(report_data, report_type, start_date, end_date)
        
        # Output or save to file
        if output_file:
            with open(output_file, 'w') as f:
                f.write(output)
            self.stdout.write(
                self.style.SUCCESS(f'Report saved to {output_file}')
            )
        else:
            self.stdout.write(output)
        
        # Email report if requested
        if email:
            self.email_report(email, report_type, output, start_date, end_date)
    
    def generate_user_activity_report(self, start_date, end_date, tenant_filter):
        """Generate user activity report."""
        # Get activity by user
        user_activity = ActivityLog.objects.filter(
            timestamp__gte=start_date,
            timestamp__lte=end_date,
            **tenant_filter
        ).values('user__email').annotate(
            activity_count=Count('id'),
            last_activity=models.Max('timestamp')
        ).order_by('-activity_count')
        
        # Get top activities
        top_activities = ActivityLog.objects.filter(
            timestamp__gte=start_date,
            timestamp__lte=end_date,
            **tenant_filter
        ).values('activity_type').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        return {
            'report_type': 'User Activity Report',
            'period': f'{start_date.date()} to {end_date.date()}',
            'generated_at': timezone.now().isoformat(),
            'user_activity': list(user_activity),
            'top_activities': list(top_activities),
            'total_activities': ActivityLog.objects.filter(
                timestamp__gte=start_date,
                timestamp__lte=end_date,
                **tenant_filter
            ).count(),
        }
    
    def generate_security_summary_report(self, start_date, end_date, tenant_filter):
        """Generate security summary report."""
        # Get security events by severity
        security_by_severity = SecurityEvent.objects.filter(
            timestamp__gte=start_date,
            timestamp__lte=end_date,
            **tenant_filter
        ).values('severity').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Get unresolved events
        unresolved_events = SecurityEvent.objects.filter(
            timestamp__gte=start_date,
            timestamp__lte=end_date,
            resolved=False,
            **tenant_filter
        ).order_by('-timestamp')[:20]
        
        # Get top event types
        top_event_types = SecurityEvent.objects.filter(
            timestamp__gte=start_date,
            timestamp__lte=end_date,
            **tenant_filter
        ).values('event_type').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        return {
            'report_type': 'Security Summary Report',
            'period': f'{start_date.date()} to {end_date.date()}',
            'generated_at': timezone.now().isoformat(),
            'security_by_severity': list(security_by_severity),
            'unresolved_events': [
                {
                    'id': event.id,
                    'event_type': event.event_type,
                    'description': event.description,
                    'severity': event.severity,
                    'timestamp': event.timestamp.isoformat(),
                }
                for event in unresolved_events
            ],
            'top_event_types': list(top_event_types),
            'total_events': SecurityEvent.objects.filter(
                timestamp__gte=start_date,
                timestamp__lte=end_date,
                **tenant_filter
            ).count(),
            'unresolved_count': SecurityEvent.objects.filter(
                timestamp__gte=start_date,
                timestamp__lte=end_date,
                resolved=False,
                **tenant_filter
            ).count(),
        }
    
    def generate_login_analytics_report(self, start_date, end_date, tenant_filter):
        """Generate login analytics report."""
        # Get login statistics
        total_logins = LoginLog.objects.filter(
            login_time__gte=start_date,
            login_time__lte=end_date,
            **tenant_filter
        ).count()
        
        successful_logins = LoginLog.objects.filter(
            login_time__gte=start_date,
            login_time__lte=end_date,
            login_successful=True,
            **tenant_filter
        ).count()
        
        failed_logins = LoginLog.objects.filter(
            login_time__gte=start_date,
            login_time__lte=end_date,
            login_successful=False,
            **tenant_filter
        ).count()
        
        # Get unique users
        unique_users = LoginLog.objects.filter(
            login_time__gte=start_date,
            login_time__lte=end_date,
            **tenant_filter
        ).values('user').distinct().count()
        
        # Get login by hour
        login_by_hour = LoginLog.objects.filter(
            login_time__gte=start_date,
            login_time__lte=end_date,
            login_successful=True,
            **tenant_filter
        ).extra(
            select={'hour': "strftime('%%H', login_time)"}
        ).values('hour').annotate(
            count=Count('id')
        ).order_by('hour')
        
        return {
            'report_type': 'Login Analytics Report',
            'period': f'{start_date.date()} to {end_date.date()}',
            'generated_at': timezone.now().isoformat(),
            'total_logins': total_logins,
            'successful_logins': successful_logins,
            'failed_logins': failed_logins,
            'success_rate': round((successful_logins / total_logins * 100) if total_logins > 0 else 0, 2),
            'unique_users': unique_users,
            'login_by_hour': list(login_by_hour),
        }
    
    def generate_data_access_report(self, start_date, end_date, tenant_filter):
        """Generate data access report."""
        # Get audit logs by model
        model_access = AuditLog.objects.filter(
            timestamp__gte=start_date,
            timestamp__lte=end_date,
            **tenant_filter
        ).values('model_name').annotate(
            access_count=Count('id'),
            create_count=Count('id', filter=Q(action='create')),
            update_count=Count('id', filter=Q(action='update')),
            delete_count=Count('id', filter=Q(action='delete')),
        ).order_by('-access_count')
        
        # Get export activities
        export_activities = ActivityLog.objects.filter(
            timestamp__gte=start_date,
            timestamp__lte=end_date,
            activity_type__in=['data_export', 'download', 'export'],
            **tenant_filter
        ).select_related('user').order_by('-timestamp')[:20]
        
        return {
            'report_type': 'Data Access Report',
            'period': f'{start_date.date()} to {end_date.date()}',
            'generated_at': timezone.now().isoformat(),
            'model_access': list(model_access),
            'export_activities': [
                {
                    'user': activity.user.email if activity.user else 'System',
                    'activity_type': activity.activity_type,
                    'description': activity.description,
                    'timestamp': activity.timestamp.isoformat(),
                }
                for activity in export_activities
            ],
        }
    
    def generate_compliance_report(self, start_date, end_date, tenant_filter):
        """Generate compliance report."""
        # Get all audit activities
        total_audit_logs = AuditLog.objects.filter(
            timestamp__gte=start_date,
            timestamp__lte=end_date,
            **tenant_filter
        ).count()
        
        # Get critical actions
        critical_actions = AuditLog.objects.filter(
            timestamp__gte=start_date,
            timestamp__lte=end_date,
            action__in=['delete', 'export', 'approve', 'reject'],
            **tenant_filter
        ).values('action').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Get security incidents
        security_incidents = SecurityEvent.objects.filter(
            timestamp__gte=start_date,
            timestamp__lte=end_date,
            severity__in=['high', 'critical'],
            **tenant_filter
        ).count()
        
        return {
            'report_type': 'Compliance Report',
            'period': f'{start_date.date()} to {end_date.date()}',
            'generated_at': timezone.now().isoformat(),
            'total_audit_logs': total_audit_logs,
            'critical_actions': list(critical_actions),
            'security_incidents': security_incidents,
            'compliance_score': self.calculate_compliance_score(
                total_audit_logs, security_incidents
            ),
        }
    
    def calculate_compliance_score(self, total_logs, incidents):
        """Calculate a simple compliance score."""
        if total_logs == 0:
            return 100
        
        # Base score starts at 100
        score = 100
        
        # Deduct points for security incidents
        score -= min(incidents * 5, 50)
        
        # Deduct points if too few logs (might indicate logging issues)
        if total_logs < 100:
            score -= 10
        
        return max(0, score)
    
    def format_as_csv(self, data, report_type):
        """Format report data as CSV."""
        output = StringIO()
        writer = csv.writer(output)
        
        if report_type == 'user_activity':
            writer.writerow(['User', 'Activity Count', 'Last Activity'])
            for row in data['user_activity']:
                writer.writerow([
                    row['user__email'], row['activity_count'], row['last_activity']
                ])
        
        elif report_type == 'security_summary':
            writer.writerow(['Severity', 'Count'])
            for row in data['security_by_severity']:
                writer.writerow([row['severity'], row['count']])
        
        return output.getvalue()
    
    def format_as_html(self, data, report_type, start_date, end_date):
        """Format report data as HTML."""
        context = {
            'data': data,
            'report_type': report_type,
            'start_date': start_date.date(),
            'end_date': end_date.date(),
        }
        return render_to_string(f'audit/reports/{report_type}.html', context)
    
    def email_report(self, email, report_type, content, start_date, end_date):
        """Email the report."""
        subject = f'Audit Report: {report_type.title()} - {start_date.date()} to {end_date.date()}'
        
        try:
            send_mail(
                subject=subject,
                message=content,
                from_email=None,  # Use default from email
                recipient_list=[email],
                html_message=content if '<html>' in content else None,
            )
            self.stdout.write(
                self.style.SUCCESS(f'Report emailed to {email}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to email report: {e}')
            )