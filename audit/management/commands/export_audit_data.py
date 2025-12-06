import json
import csv
from io import StringIO
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from audit.models import AuditLog, ActivityLog, SecurityEvent, LoginLog


class Command(BaseCommand):
    help = 'Export audit data for compliance or analysis'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--log-type',
            choices=['audit', 'activity', 'security', 'login'],
            required=True,
            help='Type of log to export',
        )
        parser.add_argument(
            '--format',
            choices=['json', 'csv'],
            default='json',
            help='Export format (default: json)',
        )
        parser.add_argument(
            '--date-from',
            type=str,
            help='Start date (YYYY-MM-DD)',
        )
        parser.add_argument(
            '--date-to',
            type=str,
            help='End date (YYYY-MM-DD)',
        )
        parser.add_argument(
            '--days',
            type=int,
            help='Number of days to export (overrides date-from/date-to)',
        )
        parser.add_argument(
            '--output',
            type=str,
            required=True,
            help='Output file path',
        )
        parser.add_argument(
            '--tenant-id',
            type=int,
            help='Specific tenant ID to export (default: all tenants)',
        )
        parser.add_argument(
            '--include-sensitive',
            action='store_true',
            help='Include sensitive data like IP addresses and user agents',
        )
        parser.add_argument(
            '--compress',
            action='store_true',
            help='Compress output file (for JSON only)',
        )
    
    def handle(self, *args, **options):
        log_type = options['log_type']
        export_format = options['format']
        date_from = options['date_from']
        date_to = options['date_to']
        days = options['days']
        output_file = options['output']
        tenant_id = options['tenant_id']
        include_sensitive = options['include_sensitive']
        compress = options['compress']
        
        self.stdout.write(self.style.SUCCESS(f'Starting {log_type} log export...'))
        
        # Calculate date range
        now = timezone.now()
        if days:
            start_date = now - timedelta(days=days)
            end_date = now
        elif date_from and date_to:
            start_date = datetime.strptime(date_from, '%Y-%m-%d')
            end_date = datetime.strptime(date_to, '%Y-%m-%d')
        elif date_from:
            start_date = datetime.strptime(date_from, '%Y-%m-%d')
            end_date = now
        else:
            # Default to last 30 days
            start_date = now - timedelta(days=30)
            end_date = now
        
        # Build base queryset
        base_kwargs = {}
        if tenant_id:
            base_kwargs['tenant_id'] = tenant_id
        
        # Get data based on log type
        if log_type == 'audit':
            queryset = AuditLog.objects.filter(
                timestamp__gte=start_date,
                timestamp__lte=end_date,
                **base_kwargs
            ).select_related('user', 'content_type')
            data = self.format_audit_data(queryset, include_sensitive)
            
        elif log_type == 'activity':
            queryset = ActivityLog.objects.filter(
                timestamp__gte=start_date,
                timestamp__lte=end_date,
                **base_kwargs
            ).select_related('user', 'related_content_type')
            data = self.format_activity_data(queryset, include_sensitive)
            
        elif log_type == 'security':
            queryset = SecurityEvent.objects.filter(
                timestamp__gte=start_date,
                timestamp__lte=end_date,
                **base_kwargs
            ).select_related('user', 'resolved_by', 'related_content_type')
            data = self.format_security_data(queryset, include_sensitive)
            
        elif log_type == 'login':
            queryset = LoginLog.objects.filter(
                login_time__gte=start_date,
                login_time__lte=end_date,
                **base_kwargs
            ).select_related('user')
            data = self.format_login_data(queryset, include_sensitive)
        
        else:
            self.stdout.write(
                self.style.ERROR(f'Unknown log type: {log_type}')
            )
            return
        
        # Export data
        if export_format == 'json':
            self.export_json(data, output_file, compress)
        elif export_format == 'csv':
            self.export_csv(data, output_file, log_type, include_sensitive)
        
        self.stdout.write(
            self.style.SUCCESS(f'Exported {len(data)} {log_type} records to {output_file}')
        )
    
    def format_audit_data(self, queryset, include_sensitive):
        """Format audit log data for export."""
        data = []
        for obj in queryset:
            item = {
                'id': obj.id,
                'timestamp': obj.timestamp.isoformat(),
                'user': obj.user.email if obj.user else None,
                'action': obj.action,
                'model_name': obj.model_name,
                'object_id': obj.object_id,
                'object_repr': obj.object_repr,
                'changed_fields': obj.changed_fields,
                'old_values': obj.old_values,
                'new_values': obj.new_values,
            }
            
            if include_sensitive:
                item.update({
                    'ip_address': obj.ip_address,
                    'user_agent': obj.user_agent,
                    'session_key': obj.session_key,
                    'request_path': obj.request_path,
                    'request_method': obj.request_method,
                })
            
            data.append(item)
        return data
    
    def format_activity_data(self, queryset, include_sensitive):
        """Format activity log data for export."""
        data = []
        for obj in queryset:
            item = {
                'id': obj.id,
                'timestamp': obj.timestamp.isoformat(),
                'user': obj.user.email if obj.user else None,
                'activity_type': obj.activity_type,
                'description': obj.description,
                'metadata': obj.metadata,
            }
            
            if include_sensitive:
                item.update({
                    'ip_address': obj.ip_address,
                    'user_agent': obj.user_agent,
                    'request_path': obj.request_path,
                })
            
            data.append(item)
        return data
    
    def format_security_data(self, queryset, include_sensitive):
        """Format security event data for export."""
        data = []
        for obj in queryset:
            item = {
                'id': obj.id,
                'timestamp': obj.timestamp.isoformat(),
                'user': obj.user.email if obj.user else None,
                'event_type': obj.event_type,
                'severity': obj.severity,
                'description': obj.description,
                'resolved': obj.resolved,
                'resolved_by': obj.resolved_by.email if obj.resolved_by else None,
                'resolved_at': obj.resolved_at.isoformat() if obj.resolved_at else None,
                'resolution_notes': obj.resolution_notes,
                'event_data': obj.event_data,
            }
            
            if include_sensitive:
                item.update({
                    'source_ip': obj.source_ip,
                    'target_ip': obj.target_ip,
                    'user_agent': obj.user_agent,
                    'request_path': obj.request_path,
                    'request_method': obj.request_method,
                })
            
            data.append(item)
        return data
    
    def format_login_data(self, queryset, include_sensitive):
        """Format login log data for export."""
        data = []
        for obj in queryset:
            item = {
                'id': obj.id,
                'login_time': obj.login_time.isoformat(),
                'logout_time': obj.logout_time.isoformat() if obj.logout_time else None,
                'user': obj.user.email,
                'login_successful': obj.login_successful,
                'failure_reason': obj.failure_reason,
                'session_key': obj.session_key,
            }
            
            if include_sensitive:
                item.update({
                    'ip_address': obj.ip_address,
                    'user_agent': obj.user_agent,
                    'device_info': obj.device_info,
                    'location_info': obj.location_info,
                })
            
            data.append(item)
        return data
    
    def export_json(self, data, output_file, compress=False):
        """Export data as JSON."""
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        if compress:
            import gzip
            compressed_file = output_file + '.gz'
            with open(output_file, 'rb') as f_in:
                with gzip.open(compressed_file, 'wb') as f_out:
                    f_out.writelines(f_in)
            
            # Remove uncompressed file
            import os
            os.remove(output_file)
            self.stdout.write(
                self.style.SUCCESS(f'Compressed to {compressed_file}')
            )
    
    def export_csv(self, data, output_file, log_type, include_sensitive):
        """Export data as CSV."""
        with open(output_file, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Write headers based on log type
            if log_type == 'audit':
                headers = [
                    'ID', 'Timestamp', 'User', 'Action', 'Model', 'Object ID',
                    'Object Representation', 'Changed Fields', 'Old Values', 'New Values'
                ]
                if include_sensitive:
                    headers.extend([
                        'IP Address', 'User Agent', 'Session Key', 'Request Path', 'Request Method'
                    ])
                
            elif log_type == 'activity':
                headers = [
                    'ID', 'Timestamp', 'User', 'Activity Type', 'Description', 'Metadata'
                ]
                if include_sensitive:
                    headers.extend(['IP Address', 'User Agent', 'Request Path'])
                
            elif log_type == 'security':
                headers = [
                    'ID', 'Timestamp', 'User', 'Event Type', 'Severity', 'Description',
                    'Resolved', 'Resolved By', 'Resolved At', 'Resolution Notes', 'Event Data'
                ]
                if include_sensitive:
                    headers.extend([
                        'Source IP', 'Target IP', 'User Agent', 'Request Path', 'Request Method'
                    ])
                
            elif log_type == 'login':
                headers = [
                    'ID', 'Login Time', 'Logout Time', 'User', 'Successful',
                    'Failure Reason', 'Session Key'
                ]
                if include_sensitive:
                    headers.extend([
                        'IP Address', 'User Agent', 'Device Info', 'Location Info'
                    ])
            
            writer.writerow(headers)
            
            # Write data rows
            for item in data:
                row = []
                
                if log_type == 'audit':
                    row.extend([
                        item['id'], item['timestamp'], item['user'], item['action'],
                        item['model_name'], item['object_id'], item['object_repr'],
                        str(item['changed_fields']), str(item['old_values']), str(item['new_values'])
                    ])
                    if include_sensitive:
                        row.extend([
                            item['ip_address'], item['user_agent'], item['session_key'],
                            item['request_path'], item['request_method']
                        ])
                
                elif log_type == 'activity':
                    row.extend([
                        item['id'], item['timestamp'], item['user'], item['activity_type'],
                        item['description'], str(item['metadata'])
                    ])
                    if include_sensitive:
                        row.extend([
                            item['ip_address'], item['user_agent'], item['request_path']
                        ])
                
                elif log_type == 'security':
                    row.extend([
                        item['id'], item['timestamp'], item['user'], item['event_type'],
                        item['severity'], item['description'], item['resolved'],
                        item['resolved_by'], item['resolved_at'], item['resolution_notes'],
                        str(item['event_data'])
                    ])
                    if include_sensitive:
                        row.extend([
                            item['source_ip'], item['target_ip'], item['user_agent'],
                            item['request_path'], item['request_method']
                        ])
                
                elif log_type == 'login':
                    row.extend([
                        item['id'], item['login_time'], item['logout_time'], item['user'],
                        item['login_successful'], item['failure_reason'], item['session_key']
                    ])
                    if include_sensitive:
                        row.extend([
                            item['ip_address'], item['user_agent'],
                            str(item['device_info']), str(item['location_info'])
                        ])
                
                writer.writerow(row)