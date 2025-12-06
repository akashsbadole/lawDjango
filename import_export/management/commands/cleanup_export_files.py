import os
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from import_export.models import ExportJob, ImportJob


class Command(BaseCommand):
    help = 'Clean up old export and import files'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Delete files older than this many days (default: 30)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )
    
    def handle(self, *args, **options):
        days = options.get('days', 30)
        dry_run = options.get('dry_run', False)
        
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        
        self.stdout.write(
            f"Searching for files older than {days} days (created before {cutoff_date.date()})..."
        )
        
        # Clean up export files
        export_jobs = ExportJob.objects.filter(
            created_at__lt=cutoff_date,
            file__isnull=False
        )
        
        export_count = 0
        export_size = 0
        
        for job in export_jobs:
            if job.file and os.path.exists(job.file.path):
                file_size = os.path.getsize(job.file.path)
                export_size += file_size
                
                if dry_run:
                    self.stdout.write(f"Would delete export file: {job.file.path} ({file_size} bytes)")
                else:
                    self.stdout.write(f"Deleting export file: {job.file.path}")
                    job.file.delete()
                    job.file = None
                    job.save()
                
                export_count += 1
        
        # Clean up import files
        import_jobs = ImportJob.objects.filter(
            created_at__lt=cutoff_date,
            file__isnull=False
        )
        
        import_count = 0
        import_size = 0
        
        for job in import_jobs:
            if job.file and os.path.exists(job.file.path):
                file_size = os.path.getsize(job.file.path)
                import_size += file_size
                
                if dry_run:
                    self.stdout.write(f"Would delete import file: {job.file.path} ({file_size} bytes)")
                else:
                    self.stdout.write(f"Deleting import file: {job.file.path}")
                    job.file.delete()
                    job.file = None
                    job.save()
                
                import_count += 1
        
        # Clean up template sample files
        from import_export.models import ImportTemplate
        templates = ImportTemplate.objects.filter(
            created_at__lt=cutoff_date,
            sample_file__isnull=False
        )
        
        template_count = 0
        template_size = 0
        
        for template in templates:
            if template.sample_file and os.path.exists(template.sample_file.path):
                file_size = os.path.getsize(template.sample_file.path)
                template_size += file_size
                
                if dry_run:
                    self.stdout.write(f"Would delete template sample file: {template.sample_file.path} ({file_size} bytes)")
                else:
                    self.stdout.write(f"Deleting template sample file: {template.sample_file.path}")
                    template.sample_file.delete()
                    template.sample_file = None
                    template.save()
                
                template_count += 1
        
        # Summary
        total_files = export_count + import_count + template_count
        total_size = export_size + import_size + template_size
        
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"DRY RUN: Would delete {total_files} files ({total_size} bytes)"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully deleted {total_files} files ({total_size} bytes)"
                )
            )
            
            self.stdout.write(
                f"  - Export files: {export_count} ({export_size} bytes)"
            )
            self.stdout.write(
                f"  - Import files: {import_count} ({import_size} bytes)"
            )
            self.stdout.write(
                f"  - Template files: {template_count} ({template_size} bytes)"
            )