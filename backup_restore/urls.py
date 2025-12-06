from django.urls import path
from . import views

app_name = 'backup_restore'

urlpatterns = [
    # Backup Job URLs
    path('backups/', views.BackupJobListView.as_view(), name='backup_list'),
    path('backups/create/', views.BackupJobCreateView.as_view(), name='backup_create'),
    path('backups/<int:pk>/', views.BackupJobDetailView.as_view(), name='backup_detail'),
    path('backups/<int:pk>/edit/', views.BackupJobUpdateView.as_view(), name='backup_edit'),
    path('backups/<int:pk>/delete/', views.BackupJobDeleteView.as_view(), name='backup_delete'),
    
    # Restore Job URLs
    path('restores/', views.RestoreJobListView.as_view(), name='restore_list'),
    path('restores/create/', views.RestoreJobCreateView.as_view(), name='restore_create'),
    path('restores/<int:pk>/', views.RestoreJobDetailView.as_view(), name='restore_detail'),
    path('restores/<int:pk>/edit/', views.RestoreJobUpdateView.as_view(), name='restore_edit'),
    path('restores/<int:pk>/delete/', views.RestoreJobDeleteView.as_view(), name='restore_delete'),
    
    # Backup Schedule URLs
    path('schedules/', views.BackupScheduleListView.as_view(), name='schedule_list'),
    path('schedules/create/', views.BackupScheduleCreateView.as_view(), name='schedule_create'),
    path('schedules/<int:pk>/', views.BackupScheduleDetailView.as_view(), name='schedule_detail'),
    path('schedules/<int:pk>/edit/', views.BackupScheduleUpdateView.as_view(), name='schedule_edit'),
    path('schedules/<int:pk>/delete/', views.BackupScheduleDeleteView.as_view(), name='schedule_delete'),
    
    # Action URLs
    path('backups/<int:pk>/execute/', views.execute_backup_job, name='backup_execute'),
    path('restores/<int:pk>/execute/', views.execute_restore_job, name='restore_execute'),
    path('restores/<int:pk>/preview/', views.preview_restore_job, name='restore_preview'),
    path('backups/<int:pk>/verify/', views.verify_backup, name='backup_verify'),
    path('backups/<int:pk>/download/', views.download_backup, name='backup_download'),
    path('cleanup/', views.cleanup_backups, name='cleanup'),
    
    # Progress URLs
    path('backups/<int:pk>/progress/', views.backup_progress, name='backup_progress'),
    path('restores/<int:pk>/progress/', views.restore_progress, name='restore_progress'),
]