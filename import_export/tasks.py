"""
Background tasks for import/export functionality.
This module provides simple task processing without requiring Celery.
"""

import threading
import time
from django.utils import timezone
from .models import ImportJob, ExportJob
from .utils import process_import_job, process_export_job


class BackgroundTaskProcessor:
    """Simple background task processor using threading."""
    
    def __init__(self):
        self.running = False
        self.thread = None
    
    def start(self):
        """Start the background processor."""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._process_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        """Stop the background processor."""
        self.running = False
        if self.thread:
            self.thread.join()
    
    def _process_loop(self):
        """Main processing loop."""
        while self.running:
            try:
                # Process pending import jobs
                self._process_import_jobs()
                
                # Process pending export jobs
                self._process_export_jobs()
                
                # Sleep for 10 seconds before checking again
                time.sleep(10)
            except Exception as e:
                print(f"Error in background processor: {e}")
                time.sleep(30)  # Wait longer if there's an error
    
    def _process_import_jobs(self):
        """Process pending import jobs."""
        pending_jobs = ImportJob.objects.filter(
            status__in=['pending', 'failed']
        ).order_by('created_at')[:5]  # Process up to 5 jobs at a time
        
        for job in pending_jobs:
            try:
                print(f"Processing import job #{job.pk} in background...")
                process_import_job(job.pk)
                print(f"Successfully processed import job #{job.pk}")
            except Exception as e:
                print(f"Error processing import job #{job.pk}: {e}")
                job.status = 'failed'
                job.errors = [{'message': str(e), 'row': 0}]
                job.completed_at = timezone.now()
                job.save()
    
    def _process_export_jobs(self):
        """Process pending export jobs."""
        pending_jobs = ExportJob.objects.filter(
            status__in=['pending', 'failed']
        ).order_by('created_at')[:5]  # Process up to 5 jobs at a time
        
        for job in pending_jobs:
            try:
                print(f"Processing export job #{job.pk} in background...")
                process_export_job(job.pk)
                print(f"Successfully processed export job #{job.pk}")
            except Exception as e:
                print(f"Error processing export job #{job.pk}: {e}")
                job.status = 'failed'
                job.errors = [{'message': str(e)}]
                job.completed_at = timezone.now()
                job.save()


# Global instance
_processor = None


def start_background_processor():
    """Start the background task processor."""
    global _processor
    if _processor is None:
        _processor = BackgroundTaskProcessor()
        _processor.start()
        print("Background task processor started.")


def stop_background_processor():
    """Stop the background task processor."""
    global _processor
    if _processor is not None:
        _processor.stop()
        _processor = None
        print("Background task processor stopped.")


def process_import_job_async(job_id):
    """Process an import job asynchronously."""
    def _process():
        try:
            process_import_job(job_id)
        except Exception as e:
            print(f"Error in async import job processing: {e}")
    
    thread = threading.Thread(target=_process, daemon=True)
    thread.start()
    return thread


def process_export_job_async(job_id):
    """Process an export job asynchronously."""
    def _process():
        try:
            process_export_job(job_id)
        except Exception as e:
            print(f"Error in async export job processing: {e}")
    
    thread = threading.Thread(target=_process, daemon=True)
    thread.start()
    return thread


# Auto-start the background processor when the module is imported
# In production, you might want to start this from your management command
# or from a proper process manager like systemd
try:
    start_background_processor()
except Exception as e:
    print(f"Failed to start background processor: {e}")