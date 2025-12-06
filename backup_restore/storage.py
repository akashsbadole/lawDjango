"""
Storage management for backup and restore operations.

This module handles storage configuration, location management,
and access control for backup files.
"""

import os
import shutil
from datetime import datetime, timedelta
from django.conf import settings
from django.core.files.storage import default_storage, FileSystemStorage
from django.utils import timezone
from cryptography.fernet import Fernet
import logging

logger = logging.getLogger(__name__)


class BackupStorageManager:
    """
    Manages storage locations and access for backup files.
    """
    
    def __init__(self, tenant=None):
        self.tenant = tenant
        self.storage = self._get_storage()
    
    def _get_storage(self):
        """
        Get the appropriate storage backend based on configuration.
        """
        # Default to Django's default storage
        return default_storage
    
    def get_backup_path(self, backup_job):
        """
        Generate a secure path for storing backup files.
        """
        if not self.tenant:
            raise ValueError("Tenant is required for backup path generation")
        
        # Create tenant-specific directory structure
        base_path = f"backups/{self.tenant.slug}"
        
        # Add date and backup type to filename
        date_str = timezone.now().strftime("%Y%m%d_%H%M%S")
        backup_type = backup_job.backup_type.lower()
        
        # Generate filename
        filename = f"{backup_job.name}_{date_str}_{backup_type}.tar.gz"
        
        # If encrypted, add .enc extension
        if backup_job.encrypted:
            filename += ".enc"
        
        return os.path.join(base_path, filename)
    
    def store_backup(self, backup_job, file_path):
        """
        Store a backup file with proper permissions and metadata.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Backup file not found: {file_path}")
        
        # Get target path
        target_path = self.get_backup_path(backup_job)
        
        # Ensure directory exists
        directory = os.path.dirname(target_path)
        if not self.storage.exists(directory):
            # For Django's Storage, we need to create the directory by saving a dummy file
            # then deleting it, or using the storage's implementation-specific method
            if hasattr(self.storage, 'makedirs'):
                self.storage.makedirs(directory)
            else:
                # Create a dummy file to ensure directory exists
                from io import BytesIO
                dummy_path = os.path.join(directory, '.gitkeep')
                self.storage.save(dummy_path, BytesIO(b''))
                self.storage.delete(dummy_path)
        
        # Copy file to storage
        with open(file_path, 'rb') as source_file:
            self.storage.save(target_path, source_file)
        
        # Set file permissions if using local storage
        if isinstance(self.storage, FileSystemStorage):
            full_path = self.storage.path(target_path)
            os.chmod(full_path, 0o600)  # Read/write for owner only
        
        logger.info(f"Stored backup file: {target_path}")
        return target_path
    
    def get_backup_file(self, backup_job):
        """
        Retrieve a backup file for download or restore.
        """
        if not backup_job.file_path:
            raise FileNotFoundError("No file path associated with this backup job")
        
        if not self.storage.exists(backup_job.file_path):
            raise FileNotFoundError(f"Backup file not found: {backup_job.file_path}")
        
        return self.storage.open(backup_job.file_path, 'rb')
    
    def delete_backup(self, backup_job):
        """
        Securely delete a backup file.
        """
        if not backup_job.file_path:
            return True  # Nothing to delete
        
        try:
            # Delete from storage
            self.storage.delete(backup_job.file_path)
            
            # Clean up empty directories if using local storage
            if isinstance(self.storage, FileSystemStorage):
                self._cleanup_empty_dirs(backup_job.file_path)
            
            logger.info(f"Deleted backup file: {backup_job.file_path}")
            return True
        except Exception as e:
            logger.error(f"Error deleting backup file {backup_job.file_path}: {str(e)}")
            return False
    
    def _cleanup_empty_dirs(self, file_path):
        """
        Clean up empty directories after file deletion.
        """
        try:
            dir_path = os.path.dirname(file_path)
            
            # Go up the directory tree
            while dir_path and dir_path != 'backups':
                try:
                    # Try to remove the directory
                    self.storage.delete(dir_path)
                    dir_path = os.path.dirname(dir_path)
                except OSError:
                    # Directory not empty, stop here
                    break
        except Exception as e:
            logger.warning(f"Error cleaning up directories: {str(e)}")
    
    def get_backup_size(self, backup_job):
        """
        Get the size of a backup file.
        """
        if not backup_job.file_path:
            return 0
        
        try:
            return self.storage.size(backup_job.file_path)
        except FileNotFoundError:
            return 0
    
    def verify_backup_integrity(self, backup_job):
        """
        Verify the integrity of a backup file.
        """
        if not backup_job.file_path or not backup_job.file_hash:
            return False, "No file path or hash available for verification"
        
        try:
            with self.get_backup_file(backup_job) as backup_file:
                # Calculate current hash
                import hashlib
                hash_sha256 = hashlib.sha256()
                
                # Read file in chunks
                for chunk in iter(lambda: backup_file.read(4096), b""):
                    hash_sha256.update(chunk)
                
                current_hash = hash_sha256.hexdigest()
                
                # Compare with stored hash
                if current_hash == backup_job.file_hash:
                    return True, "Integrity verified"
                else:
                    return False, f"Hash mismatch: expected {backup_job.file_hash}, got {current_hash}"
        except Exception as e:
            return False, f"Error verifying integrity: {str(e)}"
    
    def cleanup_old_backups(self, retention_days=None, retention_count=None):
        """
        Clean up old backups based on retention policy.
        """
        from .models import BackupJob
        
        if not retention_days and not retention_count:
            return 0  # No retention policy
        
        # Get cutoff date
        cutoff_date = None
        if retention_days:
            cutoff_date = timezone.now() - timedelta(days=retention_days)
        
        # Get backups to delete
        backups_to_delete = BackupJob.objects.filter(
            tenant=self.tenant,
            status='completed'
        )
        
        if cutoff_date:
            backups_to_delete = backups_to_delete.filter(created_at__lt=cutoff_date)
        
        # If retention count is specified, keep only the most recent backups
        if retention_count:
            # Order by creation date and get all but the most recent
            backup_ids = list(backups_to_delete.order_by('-created_at').values_list('id', flat=True)[retention_count:])
            backups_to_delete = backups_to_delete.filter(id__in=backup_ids)
        
        # Delete backups
        deleted_count = 0
        for backup in backups_to_delete:
            if self.delete_backup(backup):
                deleted_count += 1
                backup.delete()
        
        logger.info(f"Cleaned up {deleted_count} old backups for tenant {self.tenant.slug if self.tenant else 'unknown'}")
        return deleted_count
    
    def get_storage_usage(self):
        """
        Get storage usage statistics for the tenant.
        """
        from .models import BackupJob
        
        # Get all completed backups for tenant
        backups = BackupJob.objects.filter(
            tenant=self.tenant,
            status='completed'
        )
        
        total_size = 0
        backup_count = 0
        
        for backup in backups:
            if backup.file_size:
                total_size += backup.file_size
                backup_count += 1
        
        return {
            'total_size': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'backup_count': backup_count,
            'largest_backup': backups.order_by('-file_size').first() if backups.exists() else None,
            'newest_backup': backups.order_by('-created_at').first() if backups.exists() else None,
            'oldest_backup': backups.order_by('created_at').first() if backups.exists() else None,
        }


class EncryptedStorageWrapper:
    """
    Wrapper for storage that provides encryption/decryption.
    """
    
    def __init__(self, base_storage, encryption_key=None):
        self.base_storage = base_storage
        self.encryption_key = encryption_key
    
    def _get_cipher(self):
        """
        Get encryption cipher.
        """
        if not self.encryption_key:
            # Generate a new key
            self.encryption_key = Fernet.generate_key()
        
        return Fernet(self.encryption_key)
    
    def save(self, name, content):
        """
        Save content with encryption.
        """
        if isinstance(content, str):
            content = content.encode('utf-8')
        
        # Encrypt content
        cipher = self._get_cipher()
        encrypted_content = cipher.encrypt(content)
        
        # Save with .enc extension
        encrypted_name = name + ".enc"
        return self.base_storage.save(encrypted_name, encrypted_content)
    
    def open(self, name, mode='rb'):
        """
        Open and decrypt content.
        """
        # Ensure it's an encrypted file
        if not name.endswith('.enc'):
            # Try to find the encrypted version
            encrypted_name = name + ".enc"
            if self.base_storage.exists(encrypted_name):
                name = encrypted_name
            else:
                return self.base_storage.open(name, mode)
        
        # Open encrypted file
        encrypted_file = self.base_storage.open(name, mode)
        
        # Decrypt content
        cipher = self._get_cipher()
        decrypted_content = cipher.decrypt(encrypted_file.read())
        
        # Return as file-like object
        from io import BytesIO
        return BytesIO(decrypted_content)
    
    def exists(self, name):
        """
        Check if file exists (encrypted or unencrypted).
        """
        # Try encrypted version first
        encrypted_name = name + ".enc"
        if self.base_storage.exists(encrypted_name):
            return True
        
        # Try unencrypted version
        return self.base_storage.exists(name)
    
    def delete(self, name):
        """
        Delete both encrypted and unencrypted versions.
        """
        # Delete encrypted version
        encrypted_name = name + ".enc"
        if self.base_storage.exists(encrypted_name):
            self.base_storage.delete(encrypted_name)
        
        # Delete unencrypted version
        if self.base_storage.exists(name):
            self.base_storage.delete(name)
    
    def size(self, name):
        """
        Get file size (encrypted or unencrypted).
        """
        # Try encrypted version first
        encrypted_name = name + ".enc"
        if self.base_storage.exists(encrypted_name):
            return self.base_storage.size(encrypted_name)
        
        # Try unencrypted version
        return self.base_storage.size(name)
    
    def get_encryption_key(self):
        """
        Get the encryption key.
        """
        return self.encryption_key


def get_backup_storage_manager(tenant):
    """
    Get a backup storage manager for the specified tenant.
    """
    return BackupStorageManager(tenant)


def get_encrypted_storage(tenant, encryption_key=None):
    """
    Get an encrypted storage wrapper for the specified tenant.
    """
    base_storage = get_backup_storage_manager(tenant).storage
    return EncryptedStorageWrapper(base_storage, encryption_key)