from django.core.management.base import BaseCommand
from django.utils import timezone
from import_export.models import ExportJob
from import_export.utils import process_export_job


class Command(BaseCommand):
    help = 'Process pending export jobs'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--job-id',
            type=int,
            help='Process a specific export job by ID',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Maximum number of jobs to process (default: 10)',
        )
    
    def handle(self, *args, **options):
        job_id = options.get('job_id')
        limit = options.get('limit', 10)
        
        if job_id:
            # Process a specific job
            try:
                job = ExportJob.objects.get(id=job_id)
                self.stdout.write(f"Processing export job #{job.pk}...")
                
                if job.status in ['completed', 'failed', 'cancelled']:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Job #{job.pk} is already {job.status}. Skipping."
                        )
                    )
                    return
                
                process_export_job(job.pk)
                self.stdout.write(
                    self.style.SUCCESS(f"Successfully processed export job #{job.pk}")
                )
                
            except ExportJob.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"Export job with ID {job_id} does not exist")
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error processing export job #{job_id}: {str(e)}")
                )
        else:
            # Process multiple pending jobs
            pending_jobs = ExportJob.objects.filter(
                status__in=['pending', 'failed']
            ).order_by('created_at')[:limit]
            
            if not pending_jobs:
                self.stdout.write("No pending export jobs found.")
                return
            
            self.stdout.write(f"Found {len(pending_jobs)} pending export jobs...")
            
            for job in pending_jobs:
                try:
                    self.stdout.write(f"Processing export job #{job.pk}...")
                    process_export_job(job.pk)
                    self.stdout.write(
                        self.style.SUCCESS(f"Successfully processed export job #{job.pk}")
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"Error processing export job #{job.pk}: {str(e)}")
                    )
                    # Update job status to failed
                    job.status = 'failed'
                    job.errors = [{'message': str(e)}]
                    job.completed_at = timezone.now()
                    job.save()
            
            self.stdout.write(self.style.SUCCESS("Export job processing completed."))