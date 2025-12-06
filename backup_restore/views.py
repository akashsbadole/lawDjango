import json
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.db import transaction
from django.http import Http404, JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone
from .models import BackupJob, RestoreJob, BackupSchedule
from .forms import (
    BackupJobForm, RestoreJobForm, BackupScheduleForm,
    BackupJobWizardForm, RestoreJobWizardForm
)
from .utils import BackupUtility, RestoreUtility, verify_backup_integrity, cleanup_old_backups
from permissions.utils import TenantPermissionRequiredMixin
from audit.utils import log_activity


class TenantRequiredMixin:
    """
    Mixin to ensure tenant is available and user has access.
    """
    def dispatch(self, request, *args, **kwargs):
        # Check if tenant is available in request
        if not hasattr(request, 'tenant') or not request.tenant:
            messages.error(request, "No tenant specified.")
            return redirect('home')
        
        # Check if user belongs to this tenant or is superadmin
        if not request.user.is_superuser and (not hasattr(request.user, 'tenant') or request.user.tenant != request.tenant):
            messages.error(request, "You don't have permission to access this tenant's data.")
            return redirect('home')
        
        return super(TenantRequiredMixin, self).dispatch(request, *args, **kwargs)


class BackupJobListView(TenantPermissionRequiredMixin, LoginRequiredMixin, ListView):
    """
    View to list all backup jobs for the current tenant.
    """
    model = BackupJob
    template_name = 'backup_restore/backup_list.html'
    context_object_name = 'backups'
    paginate_by = 10
    permission_required = 'backup_restore.view_backupjob'
    
    def get_queryset(self):
        # Filter backup jobs by current tenant
        queryset = BackupJob.objects.for_tenant(self.request.tenant)
        
        # Handle filtering by status
        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Handle filtering by backup type
        type_filter = self.request.GET.get('backup_type')
        if type_filter:
            queryset = queryset.filter(backup_type=type_filter)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = self.request.tenant
        context['status_choices'] = BackupJob.STATUS_CHOICES
        context['backup_type_choices'] = BackupJob.BACKUP_TYPE_CHOICES
        context['current_status'] = self.request.GET.get('status', '')
        context['current_type'] = self.request.GET.get('backup_type', '')
        return context


class BackupJobDetailView(TenantPermissionRequiredMixin, LoginRequiredMixin, DetailView):
    """
    View to show details of a specific backup job.
    """
    model = BackupJob
    template_name = 'backup_restore/backup_detail.html'
    context_object_name = 'backup'
    permission_required = 'backup_restore.view_backupjob'
    
    def get_object(self):
        # Get backup job by ID and ensure it belongs to current tenant
        backup = get_object_or_404(BackupJob, pk=self.kwargs['pk'])
        
        # Check if backup belongs to current tenant
        if backup.tenant != self.request.tenant:
            raise Http404("Backup not found or you don't have permission to view it.")
        
        return backup
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = self.request.tenant
        context['can_download'] = self.object.is_completed and self.object.file_path
        return context


class BackupJobCreateView(TenantPermissionRequiredMixin, LoginRequiredMixin, CreateView):
    """
    View to create a new backup job.
    """
    model = BackupJob
    form_class = BackupJobWizardForm
    template_name = 'backup_restore/backup_wizard.html'
    permission_required = 'backup_restore.add_backupjob'
    
    def get_success_url(self):
        return reverse_lazy('backup_restore:backup_detail', kwargs={'pk': self.object.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = self.request.tenant
        context['title'] = 'Create New Backup'
        context['backup_type_choices'] = BackupJob.BACKUP_TYPE_CHOICES
        return context
    
    def form_valid(self, form):
        with transaction.atomic():
            # Create backup job with tenant and user information
            backup = form.save(commit=False)
            backup.tenant = self.request.tenant
            backup.created_by = self.request.user
            backup.save()
            
            # Log activity
            log_activity(
                tenant=self.request.tenant,
                user=self.request.user,
                activity_type='BACKUP_CREATED',
                description=f'Created new backup job: {backup.name}',
                related_object=backup
            )
            
            messages.success(
                self.request,
                f'Backup job "{backup.name}" has been created successfully.'
            )
        
        return super().form_valid(form)


class BackupJobUpdateView(TenantPermissionRequiredMixin, LoginRequiredMixin, UpdateView):
    """
    View to update an existing backup job.
    """
    model = BackupJob
    form_class = BackupJobForm
    template_name = 'backup_restore/backup_form.html'
    permission_required = 'backup_restore.change_backupjob'
    
    def get_object(self):
        # Get backup job by ID and ensure it belongs to current tenant
        backup = get_object_or_404(BackupJob, pk=self.kwargs['pk'])
        
        # Check if backup belongs to current tenant
        if backup.tenant != self.request.tenant:
            raise Http404("Backup not found or you don't have permission to edit it.")
        
        return backup
    
    def get_success_url(self):
        return reverse_lazy('backup_restore:backup_detail', kwargs={'pk': self.object.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = self.request.tenant
        context['title'] = f'Edit Backup: {self.object.name}'
        return context
    
    def form_valid(self, form):
        with transaction.atomic():
            backup = form.save()
            
            # Log activity
            log_activity(
                tenant=self.request.tenant,
                user=self.request.user,
                activity_type='BACKUP_UPDATED',
                description=f'Updated backup job: {backup.name}',
                related_object=backup
            )
            
            messages.success(
                self.request,
                f'Backup job "{backup.name}" has been updated successfully.'
            )
        
        return super().form_valid(form)


class BackupJobDeleteView(TenantPermissionRequiredMixin, LoginRequiredMixin, DeleteView):
    """
    View to delete a backup job.
    """
    model = BackupJob
    template_name = 'backup_restore/backup_confirm_delete.html'
    success_url = reverse_lazy('backup_restore:backup_list')
    permission_required = 'backup_restore.delete_backupjob'
    
    def get_object(self):
        # Get backup job by ID and ensure it belongs to current tenant
        backup = get_object_or_404(BackupJob, pk=self.kwargs['pk'])
        
        # Check if backup belongs to current tenant
        if backup.tenant != self.request.tenant:
            raise Http404("Backup not found or you don't have permission to delete it.")
        
        return backup
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = self.request.tenant
        return context
    
    def delete(self, request, *args, **kwargs):
        backup = self.get_object()
        
        # Delete backup file if it exists
        if backup.file_path:
            try:
                from django.core.files.storage import default_storage
                if default_storage.exists(backup.file_path):
                    default_storage.delete(backup.file_path)
            except Exception as e:
                messages.warning(request, f'Failed to delete backup file: {str(e)}')
        
        # Log activity
        log_activity(
            tenant=request.tenant,
            user=request.user,
            activity_type='BACKUP_DELETED',
            description=f'Deleted backup job: {backup.name}',
            related_object=backup
        )
        
        messages.success(
            request,
            f'Backup job "{backup.name}" has been deleted successfully.'
        )
        return redirect(self.success_url)


class RestoreJobListView(TenantPermissionRequiredMixin, LoginRequiredMixin, ListView):
    """
    View to list all restore jobs for the current tenant.
    """
    model = RestoreJob
    template_name = 'backup_restore/restore_list.html'
    context_object_name = 'restores'
    paginate_by = 10
    permission_required = 'backup_restore.view_restorejob'
    
    def get_queryset(self):
        # Filter restore jobs by current tenant
        queryset = RestoreJob.objects.for_tenant(self.request.tenant)
        
        # Handle filtering by status
        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = self.request.tenant
        context['status_choices'] = RestoreJob.STATUS_CHOICES
        context['current_status'] = self.request.GET.get('status', '')
        return context


class RestoreJobDetailView(TenantPermissionRequiredMixin, LoginRequiredMixin, DetailView):
    """
    View to show details of a specific restore job.
    """
    model = RestoreJob
    template_name = 'backup_restore/restore_detail.html'
    context_object_name = 'restore'
    permission_required = 'backup_restore.view_restorejob'
    
    def get_object(self):
        # Get restore job by ID and ensure it belongs to current tenant
        restore = get_object_or_404(RestoreJob, pk=self.kwargs['pk'])
        
        # Check if restore belongs to current tenant
        if restore.tenant != self.request.tenant:
            raise Http404("Restore not found or you don't have permission to view it.")
        
        return restore
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = self.request.tenant
        return context


class RestoreJobCreateView(TenantPermissionRequiredMixin, LoginRequiredMixin, CreateView):
    """
    View to create a new restore job.
    """
    model = RestoreJob
    form_class = RestoreJobWizardForm
    template_name = 'backup_restore/restore_wizard.html'
    permission_required = 'backup_restore.add_restorejob'
    
    def get_success_url(self):
        return reverse_lazy('backup_restore:restore_detail', kwargs={'pk': self.object.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = self.request.tenant
        context['title'] = 'Create New Restore'
        context['conflict_resolution_choices'] = RestoreJob.CONFLICT_RESOLUTION_CHOICES
        return context
    
    def form_valid(self, form):
        with transaction.atomic():
            # Create restore job with tenant and user information
            restore = form.save(commit=False)
            restore.tenant = self.request.tenant
            restore.created_by = self.request.user
            restore.save()
            
            # Log activity
            log_activity(
                tenant=self.request.tenant,
                user=self.request.user,
                activity_type='RESTORE_CREATED',
                description=f'Created new restore job: {restore.name}',
                related_object=restore
            )
            
            messages.success(
                self.request,
                f'Restore job "{restore.name}" has been created successfully.'
            )
        
        return super().form_valid(form)


class RestoreJobUpdateView(TenantPermissionRequiredMixin, LoginRequiredMixin, UpdateView):
    """
    View to update an existing restore job.
    """
    model = RestoreJob
    form_class = RestoreJobForm
    template_name = 'backup_restore/restore_form.html'
    permission_required = 'backup_restore.change_restorejob'
    
    def get_object(self):
        # Get restore job by ID and ensure it belongs to current tenant
        restore = get_object_or_404(RestoreJob, pk=self.kwargs['pk'])
        
        # Check if restore belongs to current tenant
        if restore.tenant != self.request.tenant:
            raise Http404("Restore not found or you don't have permission to edit it.")
        
        return restore
    
    def get_success_url(self):
        return reverse_lazy('backup_restore:restore_detail', kwargs={'pk': self.object.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = self.request.tenant
        context['title'] = f'Edit Restore: {self.object.name}'
        return context
    
    def form_valid(self, form):
        with transaction.atomic():
            restore = form.save()
            
            # Log activity
            log_activity(
                tenant=self.request.tenant,
                user=self.request.user,
                activity_type='RESTORE_UPDATED',
                description=f'Updated restore job: {restore.name}',
                related_object=restore
            )
            
            messages.success(
                self.request,
                f'Restore job "{restore.name}" has been updated successfully.'
            )
        
        return super().form_valid(form)


class RestoreJobDeleteView(TenantPermissionRequiredMixin, LoginRequiredMixin, DeleteView):
    """
    View to delete a restore job.
    """
    model = RestoreJob
    template_name = 'backup_restore/restore_confirm_delete.html'
    success_url = reverse_lazy('backup_restore:restore_list')
    permission_required = 'backup_restore.delete_restorejob'
    
    def get_object(self):
        # Get restore job by ID and ensure it belongs to current tenant
        restore = get_object_or_404(RestoreJob, pk=self.kwargs['pk'])
        
        # Check if restore belongs to current tenant
        if restore.tenant != self.request.tenant:
            raise Http404("Restore not found or you don't have permission to delete it.")
        
        return restore
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = self.request.tenant
        return context
    
    def delete(self, request, *args, **kwargs):
        restore = self.get_object()
        
        # Delete restore file if it exists
        if restore.backup_file:
            try:
                restore.backup_file.delete()
            except Exception as e:
                messages.warning(request, f'Failed to delete restore file: {str(e)}')
        
        # Log activity
        log_activity(
            tenant=request.tenant,
            user=request.user,
            activity_type='RESTORE_DELETED',
            description=f'Deleted restore job: {restore.name}',
            related_object=restore
        )
        
        messages.success(
            request,
            f'Restore job "{restore.name}" has been deleted successfully.'
        )
        return redirect(self.success_url)


class BackupScheduleListView(TenantPermissionRequiredMixin, LoginRequiredMixin, ListView):
    """
    View to list all backup schedules for the current tenant.
    """
    model = BackupSchedule
    template_name = 'backup_restore/schedule_list.html'
    context_object_name = 'schedules'
    paginate_by = 10
    permission_required = 'backup_restore.view_backupschedule'
    
    def get_queryset(self):
        # Filter backup schedules by current tenant
        queryset = BackupSchedule.objects.for_tenant(self.request.tenant)
        
        # Handle filtering by status
        active_filter = self.request.GET.get('is_active')
        if active_filter is not None:
            queryset = queryset.filter(is_active=active_filter == 'true')
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = self.request.tenant
        context['frequency_choices'] = BackupSchedule.FREQUENCY_CHOICES
        context['current_active'] = self.request.GET.get('is_active', '')
        return context


class BackupScheduleDetailView(TenantPermissionRequiredMixin, LoginRequiredMixin, DetailView):
    """
    View to show details of a specific backup schedule.
    """
    model = BackupSchedule
    template_name = 'backup_restore/schedule_detail.html'
    context_object_name = 'schedule'
    permission_required = 'backup_restore.view_backupschedule'
    
    def get_object(self):
        # Get backup schedule by ID and ensure it belongs to current tenant
        schedule = get_object_or_404(BackupSchedule, pk=self.kwargs['pk'])
        
        # Check if schedule belongs to current tenant
        if schedule.tenant != self.request.tenant:
            raise Http404("Backup schedule not found or you don't have permission to view it.")
        
        return schedule
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = self.request.tenant
        context['next_run'] = self.object.next_run
        return context


class BackupScheduleCreateView(TenantPermissionRequiredMixin, LoginRequiredMixin, CreateView):
    """
    View to create a new backup schedule.
    """
    model = BackupSchedule
    form_class = BackupScheduleForm
    template_name = 'backup_restore/schedule_form.html'
    permission_required = 'backup_restore.add_backupschedule'
    
    def get_success_url(self):
        return reverse_lazy('backup_restore:schedule_detail', kwargs={'pk': self.object.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = self.request.tenant
        context['title'] = 'Create New Backup Schedule'
        context['frequency_choices'] = BackupSchedule.FREQUENCY_CHOICES
        context['backup_type_choices'] = BackupSchedule.BACKUP_TYPE_CHOICES
        return context
    
    def form_valid(self, form):
        with transaction.atomic():
            # Create backup schedule with tenant and user information
            schedule = form.save(commit=False)
            schedule.tenant = self.request.tenant
            schedule.created_by = self.request.user
            schedule.save()
            
            # Calculate next run time
            schedule.calculate_next_run()
            
            # Log activity
            log_activity(
                tenant=self.request.tenant,
                user=self.request.user,
                activity_type='SCHEDULE_CREATED',
                description=f'Created new backup schedule: {schedule.name}',
                related_object=schedule
            )
            
            messages.success(
                self.request,
                f'Backup schedule "{schedule.name}" has been created successfully.'
            )
        
        return super().form_valid(form)


class BackupScheduleUpdateView(TenantPermissionRequiredMixin, LoginRequiredMixin, UpdateView):
    """
    View to update an existing backup schedule.
    """
    model = BackupSchedule
    form_class = BackupScheduleForm
    template_name = 'backup_restore/schedule_form.html'
    permission_required = 'backup_restore.change_backupschedule'
    
    def get_object(self):
        # Get backup schedule by ID and ensure it belongs to current tenant
        schedule = get_object_or_404(BackupSchedule, pk=self.kwargs['pk'])
        
        # Check if schedule belongs to current tenant
        if schedule.tenant != self.request.tenant:
            raise Http404("Backup schedule not found or you don't have permission to edit it.")
        
        return schedule
    
    def get_success_url(self):
        return reverse_lazy('backup_restore:schedule_detail', kwargs={'pk': self.object.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = self.request.tenant
        context['title'] = f'Edit Backup Schedule: {self.object.name}'
        context['frequency_choices'] = BackupSchedule.FREQUENCY_CHOICES
        context['backup_type_choices'] = BackupSchedule.BACKUP_TYPE_CHOICES
        return context
    
    def form_valid(self, form):
        with transaction.atomic():
            schedule = form.save()
            
            # Recalculate next run time
            schedule.calculate_next_run()
            
            # Log activity
            log_activity(
                tenant=self.request.tenant,
                user=self.request.user,
                activity_type='SCHEDULE_UPDATED',
                description=f'Updated backup schedule: {schedule.name}',
                related_object=schedule
            )
            
            messages.success(
                self.request,
                f'Backup schedule "{schedule.name}" has been updated successfully.'
            )
        
        return super().form_valid(form)


class BackupScheduleDeleteView(TenantPermissionRequiredMixin, LoginRequiredMixin, DeleteView):
    """
    View to delete a backup schedule.
    """
    model = BackupSchedule
    template_name = 'backup_restore/schedule_confirm_delete.html'
    success_url = reverse_lazy('backup_restore:schedule_list')
    permission_required = 'backup_restore.delete_backupschedule'
    
    def get_object(self):
        # Get backup schedule by ID and ensure it belongs to current tenant
        schedule = get_object_or_404(BackupSchedule, pk=self.kwargs['pk'])
        
        # Check if schedule belongs to current tenant
        if schedule.tenant != self.request.tenant:
            raise Http404("Backup schedule not found or you don't have permission to delete it.")
        
        return schedule
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = self.request.tenant
        return context
    
    def delete(self, request, *args, **kwargs):
        schedule = self.get_object()
        
        # Log activity
        log_activity(
            tenant=request.tenant,
            user=request.user,
            activity_type='SCHEDULE_DELETED',
            description=f'Deleted backup schedule: {schedule.name}',
            related_object=schedule
        )
        
        messages.success(
            request,
            f'Backup schedule "{schedule.name}" has been deleted successfully.'
        )
        return redirect(self.success_url)


@login_required
@require_POST
def execute_backup_job(request, pk):
    """
    Execute a backup job immediately.
    """
    backup = get_object_or_404(BackupJob, pk=pk)
    
    # Check if user has permission
    if not request.user.is_superuser and backup.tenant != request.tenant:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    # Check if backup can be executed
    if backup.status not in ['pending', 'failed']:
        return JsonResponse({'error': 'Backup cannot be executed in current status'}, status=400)
    
    try:
        # Execute backup in background
        from .tasks import execute_backup_task
        execute_backup_task.delay(backup.pk)
        
        return JsonResponse({'success': True, 'message': 'Backup execution started'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def execute_restore_job(request, pk):
    """
    Execute a restore job immediately.
    """
    restore = get_object_or_404(RestoreJob, pk=pk)
    
    # Check if user has permission
    if not request.user.is_superuser and restore.tenant != request.tenant:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    # Check if restore can be executed
    if restore.status not in ['pending', 'preview']:
        return JsonResponse({'error': 'Restore cannot be executed in current status'}, status=400)
    
    try:
        # Execute restore in background
        from .tasks import execute_restore_task
        execute_restore_task.delay(restore.pk)
        
        return JsonResponse({'success': True, 'message': 'Restore execution started'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def preview_restore_job(request, pk):
    """
    Create a preview of a restore job.
    """
    restore = get_object_or_404(RestoreJob, pk=pk)
    
    # Check if user has permission
    if not request.user.is_superuser and restore.tenant != request.tenant:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    # Check if restore can be previewed
    if restore.status != 'pending':
        return JsonResponse({'error': 'Restore cannot be previewed in current status'}, status=400)
    
    try:
        # Execute preview in background
        from .tasks import preview_restore_task
        preview_restore_task.delay(restore.pk)
        
        return JsonResponse({'success': True, 'message': 'Restore preview started'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def verify_backup(request, pk):
    """
    Verify the integrity of a backup.
    """
    backup = get_object_or_404(BackupJob, pk=pk)
    
    # Check if user has permission
    if not request.user.is_superuser and backup.tenant != request.tenant:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        # Verify backup integrity
        is_valid, message = verify_backup_integrity(backup)
        
        return JsonResponse({
            'success': is_valid,
            'message': message
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def download_backup(request, pk):
    """
    Download a backup file.
    """
    backup = get_object_or_404(BackupJob, pk=pk)
    
    # Check if user has permission
    if not request.user.is_superuser and backup.tenant != request.tenant:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    # Check if backup is completed
    if not backup.is_completed or not backup.file_path:
        return JsonResponse({'error': 'Backup not available for download'}, status=400)
    
    try:
        # Get file from storage
        from django.core.files.storage import default_storage
        if default_storage.exists(backup.file_path):
            file = default_storage.open(backup.file_path, 'rb')
            response = HttpResponse(file.read(), content_type='application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename="{backup.file_name}"'
            
            # Log activity
            log_activity(
                tenant=request.tenant,
                user=request.user,
                activity_type='BACKUP_DOWNLOADED',
                description=f'Downloaded backup: {backup.name}',
                related_object=backup
            )
            
            return response
        else:
            return JsonResponse({'error': 'Backup file not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def cleanup_backups(request):
    """
    Clean up old backups based on retention policies.
    """
    # Check if user has permission (superuser only)
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        # Clean up old backups
        cleanup_old_backups()
        
        return JsonResponse({'success': True, 'message': 'Backup cleanup completed'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def backup_progress(request, pk):
    """
    Get the progress of a backup job.
    """
    backup = get_object_or_404(BackupJob, pk=pk)
    
    # Check if user has permission
    if not request.user.is_superuser and backup.tenant != request.tenant:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    return JsonResponse({
        'status': backup.status,
        'progress': backup.progress_percentage,
        'current_step': backup.current_step,
        'error_message': backup.error_message,
        'log_entries': backup.log_entries
    })


@login_required
def restore_progress(request, pk):
    """
    Get the progress of a restore job.
    """
    restore = get_object_or_404(RestoreJob, pk=pk)
    
    # Check if user has permission
    if not request.user.is_superuser and restore.tenant != request.tenant:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    return JsonResponse({
        'status': restore.status,
        'progress': restore.progress_percentage,
        'current_step': restore.current_step,
        'error_message': restore.error_message,
        'log_entries': restore.log_entries,
        'records_restored': restore.records_restored,
        'records_skipped': restore.records_skipped,
        'records_failed': restore.records_failed
    })