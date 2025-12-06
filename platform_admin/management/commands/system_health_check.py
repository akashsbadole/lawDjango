from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import connection
from django.core.cache import cache
from django.conf import settings
from datetime import timedelta
import time
import psutil
import os

from platform_admin.models import SystemHealthCheck


class Command(BaseCommand):
    help = 'Run system health checks and record results'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--check-type',
            type=str,
            choices=[choice[0] for choice in SystemHealthCheck.CHECK_TYPES],
            help='Run specific type of health check'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Verbose output'
        )
    
    def handle(self, *args, **options):
        check_type = options.get('check_type')
        verbose = options.get('verbose', False)
        
        if check_type:
            # Run specific check
            if check_type == 'database':
                self.check_database(verbose)
            elif check_type == 'storage':
                self.check_storage(verbose)
            elif check_type == 'email':
                self.check_email_service(verbose)
            elif check_type == 'backup':
                self.check_backup_system(verbose)
            elif check_type == 'ssl':
                self.check_ssl_certificate(verbose)
            elif check_type == 'performance':
                self.check_performance(verbose)
            elif check_type == 'security':
                self.check_security(verbose)
            elif check_type == 'external_api':
                self.check_external_apis(verbose)
        else:
            # Run all checks
            self.stdout.write(self.style.SUCCESS('Running all system health checks...'))
            self.check_database(verbose)
            self.check_storage(verbose)
            self.check_email_service(verbose)
            self.check_backup_system(verbose)
            self.check_ssl_certificate(verbose)
            self.check_performance(verbose)
            self.check_security(verbose)
            self.check_external_apis(verbose)
            
            # Display summary
            self.display_health_summary()
    
    def check_database(self, verbose=False):
        """Check database connectivity and performance."""
        start_time = time.time()
        status = 'healthy'
        message = 'Database is operating normally'
        details = {}
        
        try:
            # Test database connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            
            # Check database size
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT pg_size_pretty(pg_database_size(current_database())) as size
                """ if 'postgresql' in settings.DATABASES['default']['ENGINE'] else """
                    SELECT 
                        ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS size_mb
                    FROM information_schema.tables 
                    WHERE table_schema = DATABASE()
                """)
                result = cursor.fetchone()
                details['database_size'] = result[0] if result else 'Unknown'
            
            # Check connection count
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT count(*) FROM pg_stat_activity 
                    WHERE state = 'active'
                """ if 'postgresql' in settings.DATABASES['default']['ENGINE'] else """
                    SHOW STATUS LIKE 'Threads_connected'
                """)
                result = cursor.fetchone()
                details['active_connections'] = result[0] if result else 0
            
            # Check slow queries (PostgreSQL specific)
            if 'postgresql' in settings.DATABASES['default']['ENGINE']:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT count(*) FROM pg_stat_statements 
                        WHERE mean_exec_time > 1000
                    """)
                    result = cursor.fetchone()
                    details['slow_queries'] = result[0] if result else 0
            
            if verbose:
                self.stdout.write(f"  Database: {message}")
                for key, value in details.items():
                    self.stdout.write(f"    {key}: {value}")
        
        except Exception as e:
            status = 'critical'
            message = f'Database error: {str(e)}'
            details['error'] = str(e)
            if verbose:
                self.stdout.write(self.style.ERROR(f"  Database: {message}"))
        
        # Record health check
        duration_ms = int((time.time() - start_time) * 1000)
        SystemHealthCheck.objects.create(
            check_type='database',
            status=status,
            message=message,
            details=details,
            check_duration_ms=duration_ms,
            next_check_due=timezone.now() + timedelta(minutes=15)
        )
    
    def check_storage(self, verbose=False):
        """Check disk space and storage systems."""
        start_time = time.time()
        status = 'healthy'
        message = 'Storage systems are operating normally'
        details = {}
        
        try:
            # Check disk space
            disk_usage = psutil.disk_usage('/')
            total_gb = disk_usage.total / (1024**3)
            used_gb = disk_usage.used / (1024**3)
            free_gb = disk_usage.free / (1024**3)
            usage_percent = (used_gb / total_gb) * 100
            
            details.update({
                'total_disk_gb': round(total_gb, 2),
                'used_disk_gb': round(used_gb, 2),
                'free_disk_gb': round(free_gb, 2),
                'disk_usage_percent': round(usage_percent, 2)
            })
            
            # Check if disk usage is critical
            if usage_percent > 90:
                status = 'critical'
                message = f'Critical: Disk usage is {usage_percent:.1f}%'
            elif usage_percent > 80:
                status = 'warning'
                message = f'Warning: Disk usage is {usage_percent:.1f}%'
            
            # Check memory usage
            memory = psutil.virtual_memory()
            details.update({
                'total_memory_gb': round(memory.total / (1024**3), 2),
                'used_memory_gb': round(memory.used / (1024**3), 2),
                'memory_usage_percent': memory.percent
            })
            
            if verbose:
                self.stdout.write(f"  Storage: {message}")
                for key, value in details.items():
                    self.stdout.write(f"    {key}: {value}")
        
        except Exception as e:
            status = 'critical'
            message = f'Storage check error: {str(e)}'
            details['error'] = str(e)
            if verbose:
                self.stdout.write(self.style.ERROR(f"  Storage: {message}"))
        
        # Record health check
        duration_ms = int((time.time() - start_time) * 1000)
        SystemHealthCheck.objects.create(
            check_type='storage',
            status=status,
            message=message,
            details=details,
            check_duration_ms=duration_ms,
            next_check_due=timezone.now() + timedelta(hours=1)
        )
    
    def check_email_service(self, verbose=False):
        """Check email service connectivity."""
        start_time = time.time()
        status = 'healthy'
        message = 'Email service is operating normally'
        details = {}
        
        try:
            from django.core.mail import send_mail
            
            # Send test email (to a test address or discard)
            test_result = send_mail(
                'System Health Check Test',
                'This is a test email to verify email service functionality.',
                settings.DEFAULT_FROM_EMAIL,
                ['test@example.com'],  # This would be configured to a real test address
                fail_silently=True
            )
            
            details['test_email_sent'] = True
            details['email_backend'] = settings.EMAIL_BACKEND
            
            if verbose:
                self.stdout.write(f"  Email: {message}")
                self.stdout.write(f"    Backend: {settings.EMAIL_BACKEND}")
        
        except Exception as e:
            status = 'critical'
            message = f'Email service error: {str(e)}'
            details['error'] = str(e)
            details['email_backend'] = getattr(settings, 'EMAIL_BACKEND', 'Not configured')
            if verbose:
                self.stdout.write(self.style.ERROR(f"  Email: {message}"))
        
        # Record health check
        duration_ms = int((time.time() - start_time) * 1000)
        SystemHealthCheck.objects.create(
            check_type='email',
            status=status,
            message=message,
            details=details,
            check_duration_ms=duration_ms,
            next_check_due=timezone.now() + timedelta(hours=6)
        )
    
    def check_backup_system(self, verbose=False):
        """Check backup system status."""
        start_time = time.time()
        status = 'healthy'
        message = 'Backup system is operating normally'
        details = {}
        
        try:
            # Check if backup directory exists and is writable
            backup_dir = getattr(settings, 'BACKUP_DIR', '/tmp/backups')
            
            if os.path.exists(backup_dir):
                if os.access(backup_dir, os.W_OK):
                    details['backup_dir_writable'] = True
                    
                    # Check last backup time (simplified check)
                    backup_files = [f for f in os.listdir(backup_dir) if f.endswith('.sql') or f.endswith('.dump')]
                    if backup_files:
                        latest_backup = max(
                            [os.path.getmtime(os.path.join(backup_dir, f)) for f in backup_files],
                            default=0
                        )
                        last_backup_time = timezone.datetime.fromtimestamp(latest_backup, tz=timezone.utc)
                        details['last_backup_time'] = last_backup_time.isoformat()
                        
                        # Check if backup is recent (within 24 hours)
                        if timezone.now() - last_backup_time > timedelta(hours=24):
                            status = 'warning'
                            message = 'Warning: Last backup is more than 24 hours old'
                    else:
                        status = 'warning'
                        message = 'Warning: No backup files found'
                        details['last_backup_time'] = None
                else:
                    status = 'critical'
                    message = 'Critical: Backup directory is not writable'
                    details['backup_dir_writable'] = False
            else:
                status = 'critical'
                message = 'Critical: Backup directory does not exist'
                details['backup_dir_exists'] = False
            
            if verbose:
                self.stdout.write(f"  Backup: {message}")
                for key, value in details.items():
                    self.stdout.write(f"    {key}: {value}")
        
        except Exception as e:
            status = 'critical'
            message = f'Backup system error: {str(e)}'
            details['error'] = str(e)
            if verbose:
                self.stdout.write(self.style.ERROR(f"  Backup: {message}"))
        
        # Record health check
        duration_ms = int((time.time() - start_time) * 1000)
        SystemHealthCheck.objects.create(
            check_type='backup',
            status=status,
            message=message,
            details=details,
            check_duration_ms=duration_ms,
            next_check_due=timezone.now() + timedelta(hours=12)
        )
    
    def check_ssl_certificate(self, verbose=False):
        """Check SSL certificate validity."""
        start_time = time.time()
        status = 'healthy'
        message = 'SSL certificates are valid'
        details = {}
        
        try:
            import ssl
            import socket
            from datetime import datetime
            
            # Get site domain from settings
            site_domain = getattr(settings, 'SITE_DOMAIN', 'localhost')
            port = 443
            
            if site_domain != 'localhost':
                # Check SSL certificate
                context = ssl.create_default_context()
                with socket.create_connection((site_domain, port), timeout=5) as sock:
                    with context.wrap_socket(sock, server_hostname=site_domain) as ssock:
                        cert = ssock.getpeercert()
                        
                        # Check expiration
                        expiry_date = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                        days_until_expiry = (expiry_date - datetime.now()).days
                        
                        details.update({
                            'domain': site_domain,
                            'issuer': cert['issuer'],
                            'expiry_date': cert['notAfter'],
                            'days_until_expiry': days_until_expiry
                        })
                        
                        if days_until_expiry < 7:
                            status = 'critical'
                            message = f'Critical: SSL certificate expires in {days_until_expiry} days'
                        elif days_until_expiry < 30:
                            status = 'warning'
                            message = f'Warning: SSL certificate expires in {days_until_expiry} days'
            else:
                details['domain'] = 'localhost'
                details['ssl_check_skipped'] = True
                message = 'SSL check skipped for localhost'
            
            if verbose:
                self.stdout.write(f"  SSL: {message}")
                for key, value in details.items():
                    self.stdout.write(f"    {key}: {value}")
        
        except Exception as e:
            status = 'critical'
            message = f'SSL certificate error: {str(e)}'
            details['error'] = str(e)
            if verbose:
                self.stdout.write(self.style.ERROR(f"  SSL: {message}"))
        
        # Record health check
        duration_ms = int((time.time() - start_time) * 1000)
        SystemHealthCheck.objects.create(
            check_type='ssl',
            status=status,
            message=message,
            details=details,
            check_duration_ms=duration_ms,
            next_check_due=timezone.now() + timedelta(days=1)
        )
    
    def check_performance(self, verbose=False):
        """Check system performance metrics."""
        start_time = time.time()
        status = 'healthy'
        message = 'System performance is normal'
        details = {}
        
        try:
            # Check CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            details['cpu_percent'] = cpu_percent
            
            # Check memory usage
            memory = psutil.virtual_memory()
            details['memory_percent'] = memory.percent
            
            # Check disk I/O (simplified)
            disk_io = psutil.disk_io_counters()
            if disk_io:
                details['disk_read_bytes'] = disk_io.read_bytes
                details['disk_write_bytes'] = disk_io.write_bytes
            
            # Check network I/O
            network_io = psutil.net_io_counters()
            if network_io:
                details['network_bytes_sent'] = network_io.bytes_sent
                details['network_bytes_recv'] = network_io.bytes_recv
            
            # Check load average (Unix systems)
            if hasattr(psutil, 'getloadavg'):
                load_avg = psutil.getloadavg()
                details['load_average'] = load_avg
                
                # Check if load is high
                if load_avg[0] > psutil.cpu_count() * 2:
                    status = 'warning'
                    message = 'Warning: High system load detected'
            
            # Check response time (simple database query)
            db_start = time.time()
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            db_response_time = (time.time() - db_start) * 1000
            details['db_response_time_ms'] = round(db_response_time, 2)
            
            if db_response_time > 1000:  # More than 1 second
                status = 'warning'
                message = 'Warning: Slow database response time'
            
            if verbose:
                self.stdout.write(f"  Performance: {message}")
                for key, value in details.items():
                    self.stdout.write(f"    {key}: {value}")
        
        except Exception as e:
            status = 'critical'
            message = f'Performance check error: {str(e)}'
            details['error'] = str(e)
            if verbose:
                self.stdout.write(self.style.ERROR(f"  Performance: {message}"))
        
        # Record health check
        duration_ms = int((time.time() - start_time) * 1000)
        SystemHealthCheck.objects.create(
            check_type='performance',
            status=status,
            message=message,
            details=details,
            check_duration_ms=duration_ms,
            next_check_due=timezone.now() + timedelta(minutes=30)
        )
    
    def check_security(self, verbose=False):
        """Check security settings."""
        start_time = time.time()
        status = 'healthy'
        message = 'Security settings are properly configured'
        details = {}
        
        try:
            # Check DEBUG setting
            debug_enabled = getattr(settings, 'DEBUG', False)
            details['debug_enabled'] = debug_enabled
            
            if debug_enabled:
                status = 'warning'
                message = 'Warning: DEBUG mode is enabled in production'
            
            # Check secret key
            secret_key = getattr(settings, 'SECRET_KEY', '')
            details['secret_key_configured'] = bool(secret_key)
            details['secret_key_length'] = len(secret_key)
            
            if len(secret_key) < 50:
                status = 'warning'
                message = 'Warning: Secret key appears to be weak'
            
            # Check allowed hosts
            allowed_hosts = getattr(settings, 'ALLOWED_HOSTS', [])
            details['allowed_hosts_configured'] = bool(allowed_hosts)
            details['allowed_hosts_count'] = len(allowed_hosts)
            
            if not allowed_hosts and not debug_enabled:
                status = 'warning'
                message = 'Warning: ALLOWED_HOSTS is not configured'
            
            # Check secure settings
            secure_settings = {
                'SESSION_COOKIE_SECURE': getattr(settings, 'SESSION_COOKIE_SECURE', False),
                'CSRF_COOKIE_SECURE': getattr(settings, 'CSRF_COOKIE_SECURE', False),
                'SECURE_SSL_REDIRECT': getattr(settings, 'SECURE_SSL_REDIRECT', False),
                'SECURE_HSTS_SECONDS': getattr(settings, 'SECURE_HSTS_SECONDS', 0),
            }
            details.update(secure_settings)
            
            secure_count = sum(1 for v in secure_settings.values() if v)
            if secure_count < 3 and not debug_enabled:
                status = 'warning'
                message = 'Warning: Some security settings are not enabled'
            
            if verbose:
                self.stdout.write(f"  Security: {message}")
                for key, value in details.items():
                    self.stdout.write(f"    {key}: {value}")
        
        except Exception as e:
            status = 'critical'
            message = f'Security check error: {str(e)}'
            details['error'] = str(e)
            if verbose:
                self.stdout.write(self.style.ERROR(f"  Security: {message}"))
        
        # Record health check
        duration_ms = int((time.time() - start_time) * 1000)
        SystemHealthCheck.objects.create(
            check_type='security',
            status=status,
            message=message,
            details=details,
            check_duration_ms=duration_ms,
            next_check_due=timezone.now() + timedelta(hours=6)
        )
    
    def check_external_apis(self, verbose=False):
        """Check external API connectivity."""
        start_time = time.time()
        status = 'healthy'
        message = 'External APIs are accessible'
        details = {}
        
        try:
            import requests
            
            # Check common external services
            services_to_check = [
                ('Google DNS', 'https://8.8.8.8'),
                ('Cloudflare DNS', 'https://1.1.1.1'),
                ('GitHub API', 'https://api.github.com'),
            ]
            
            for service_name, url in services_to_check:
                try:
                    response = requests.get(url, timeout=5)
                    details[f'{service_name.lower().replace(" ", "_")}_status'] = response.status_code
                    details[f'{service_name.lower().replace(" ", "_")}_response_time'] = round(response.elapsed.total_seconds() * 1000, 2)
                except Exception as e:
                    details[f'{service_name.lower().replace(" ", "_")}_error'] = str(e)
                    if status != 'critical':
                        status = 'warning'
                        message = f'Warning: Some external services are unreachable'
            
            if verbose:
                self.stdout.write(f"  External APIs: {message}")
                for key, value in details.items():
                    self.stdout.write(f"    {key}: {value}")
        
        except Exception as e:
            status = 'critical'
            message = f'External API check error: {str(e)}'
            details['error'] = str(e)
            if verbose:
                self.stdout.write(self.style.ERROR(f"  External APIs: {message}"))
        
        # Record health check
        duration_ms = int((time.time() - start_time) * 1000)
        SystemHealthCheck.objects.create(
            check_type='external_api',
            status=status,
            message=message,
            details=details,
            check_duration_ms=duration_ms,
            next_check_due=timezone.now() + timedelta(hours=3)
        )
    
    def display_health_summary(self):
        """Display a summary of the latest health checks."""
        latest_checks = {}
        
        for check_type in SystemHealthCheck.CHECK_TYPES:
            latest = SystemHealthCheck.objects.filter(
                check_type=check_type[0]
            ).order_by('-created_at').first()
            
            if latest:
                latest_checks[check_type[0]] = {
                    'status': latest.status,
                    'message': latest.message,
                    'last_check': latest.created_at
                }
        
        self.stdout.write(self.style.SUCCESS('\nHealth Check Summary:'))
        self.stdout.write('-' * 50)
        
        for check_type, check_data in latest_checks.items():
            status_color = {
                'healthy': self.style.SUCCESS,
                'warning': self.style.WARNING,
                'critical': self.style.ERROR
            }.get(check_data['status'], self.style.NOTICE)
            
            self.stdout.write(
                f"{check_type.title()}: {status_color(check_data['status'].upper())}"
            )
            self.stdout.write(f"  {check_data['message']}")
            self.stdout.write(f"  Last check: {check_data['last_check'].strftime('%Y-%m-%d %H:%M:%S')}")
            self.stdout.write('')