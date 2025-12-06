from django.core.management.base import BaseCommand
from django.utils import timezone
from import_export.models import ImportJob
from import_export.utils import process_import_job


class Command(BaseCommand):
    help = 'Process pending import jobs'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--job-id',
            type=int,
            help='Process a specific import job by ID',
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
                job = ImportJob.objects.get(id=job_id)
                self.stdout.write(f"Processing import job #{job.id}...")
                
                if job.status in ['completed', 'failed', 'cancelled']:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Job #{job.id} is already {job.status}. Skipping."
                        )
                    )
                    return
                
                process_import_job(job.id)
                self.stdout.write(
                    self.style.SUCCESS(f"Successfully processed import job #{job.id}")
                )
                
            except ImportJob.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"Import job with ID {job_id} does not exist")
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error processing import job #{job_id}: {str(e)}")
                )
        else:
            # Process multiple pending jobs
            pending_jobs = ImportJob.objects.filter(
                status__in=['pending', 'failed']
            ).order_by('created_at')[:limit]
            
            if not pending_jobs:
                self.stdout.write("No pending import jobs found.")
                return
            
            self.stdout.write(f"Found {len(pending_jobs)} pending import jobs...")
            
            for job in pending_jobs:
                try:
                    self.stdout.write(f"Processing import job #{job.id}...")
                    process_import_job(job.id)
                    self.stdout.write(
                        self.style.SUCCESS(f"Successfully processed import job #{job.id}")
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"Error processing import job #{job.id}: {str(e)}")
                    )
                    # Update job status to failed
                    job.status = 'failed'
                    job.errors = [{'message': str(e), 'row': 0}]
                    job.completed_at = timezone.now()
                    job.save()
            
            self.stdout.write(self.style.SUCCESS("Import job processing completed."))