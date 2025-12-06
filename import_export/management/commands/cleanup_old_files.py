import os
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
from import_export.models import ImportJob, ExportJob


class Command(BaseCommand):
    help = 'Clean up old import/export files'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Delete files older than this many days (default: 30)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )
    
    def handle(self, *args, **options):
        days = options.get('days')
        dry_run = options.get('dry_run')
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Clean up import files
        import_jobs = ImportJob.objects.filter(
            completed_at__lt=cutoff_date,
            status__in=['completed', 'failed', 'cancelled']
        )
        
        import_count = 0
        import_size = 0
        
        for job in import_jobs:
            if job.file and os.path.exists(job.file.path):
                file_size = os.path.getsize(job.file.path)
                import_size += file_size
                
                if dry_run:
                    self.stdout.write(
                        f"Would delete import file: {job.file.path} ({file_size / 1024 / 1024:.2f} MB)"
                    )
                else:
                    job.file.delete()
                    import_count += 1
                    self.stdout.write(
                        f"Deleted import file: {job.file.path} ({file_size / 1024 / 1024:.2f} MB)"
                    )
        
        # Clean up export files
        export_jobs = ExportJob.objects.filter(
            completed_at__lt=cutoff_date,
            status__in=['completed', 'failed', 'cancelled']
        )
        
        export_count = 0
        export_size = 0
        
        for job in export_jobs:
            if job.file and os.path.exists(job.file.path):
                file_size = os.path.getsize(job.file.path)
                export_size += file_size
                
                if dry_run:
                    self.stdout.write(
                        f"Would delete export file: {job.file.path} ({file_size / 1024 / 1024:.2f} MB)"
                    )
                else:
                    job.file.delete()
                    export_count += 1
                    self.stdout.write(
                        f"Deleted export file: {job.file.path} ({file_size / 1024 / 1024:.2f} MB)"
                    )
        
        total_size = import_size + export_size
        total_count = import_count + export_count
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: Would delete {total_count} files "
                    f"({total_size / 1024 / 1024:.2f} MB) older than {days} days"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Deleted {total_count} files "
                    f"({total_size / 1024 / 1024:.2f} MB) older than {days} days"
                )
            )