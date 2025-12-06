from django.apps import AppConfig


class BackupRestoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backup_restore"
    verbose_name = "Backup & Restore"