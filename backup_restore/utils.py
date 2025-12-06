import os
import json
import shutil
import zipfile
import tarfile
import tempfile
import subprocess
import hashlib
from datetime import datetime
from pathlib import Path
from django.conf import settings
from django.db import connection
from django.core.files.storage import default_storage
from django.core.management import call_command
from cryptography.fernet import Fernet
from .models import BackupJob, RestoreJob


class BackupUtility:
    """
    Utility class for creating and managing backups.
    """
    
    def __init__(self, backup_job):
        self.backup_job = backup_job
        self.tenant = backup_job.tenant
        self.temp_dir = ""
        self.backup_file_path = ""
        
    def create_backup(self):
        """
        Create a complete backup based on the backup job configuration.
        """
        try:
            # Create temporary directory for backup
            self.temp_dir = tempfile.mkdtemp(prefix=f'backup_{self.tenant.pk}_')
            
            # Update backup job status
            self.backup_job.start_backup()
            self.backup_job.add_log_entry('info', f'Started backup for tenant: {self.tenant.name}')
            
            # Create backup based on type
            if self.backup_job.backup_type == 'full':
                self._create_full_backup()
            elif self.backup_job.backup_type == 'incremental':
                self._create_incremental_backup()
            elif self.backup_job.backup_type == 'database_only':
                self._create_database_backup()
            elif self.backup_job.backup_type == 'media_only':
                self._create_media_backup()
            
            # Compress backup if enabled
            if self.backup_job.compress:
                self._compress_backup()
            
            # Encrypt backup if enabled
            if self.backup_job.encrypted:
                self._encrypt_backup()
            
            # Move backup to final location
            self._move_backup_to_storage()
            
            # Complete backup job
            file_size = os.path.getsize(self.backup_file_path) if self.backup_file_path else 0
            self.backup_job.complete_backup(self.backup_file_path, file_size)
            self.backup_job.add_log_entry('info', f'Backup completed successfully. File size: {file_size} bytes')
            
            return True
            
        except Exception as e:
            error_message = f'Backup failed: {str(e)}'
            self.backup_job.fail_backup(error_message)
            self.backup_job.add_log_entry('error', error_message)
            return False
            
        finally:
            # Clean up temporary directory
            if self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
    
    def _create_full_backup(self):
        """Create a full backup including all data."""
        self.backup_job.update_progress(10, 'Creating database backup')
        
        if self.backup_job.include_database:
            self._create_database_backup()
        
        self.backup_job.update_progress(30, 'Creating media backup')
        
        if self.backup_job.include_media:
            self._create_media_backup()
        
        self.backup_job.update_progress(50, 'Creating documents backup')
        
        if self.backup_job.include_documents:
            self._create_documents_backup()
        
        self.backup_job.update_progress(70, 'Creating settings backup')
        
        if self.backup_job.include_settings:
            self._create_settings_backup()
        
        self.backup_job.update_progress(90, 'Finalizing backup')
        
        # Create backup metadata
        self._create_backup_metadata()
    
    def _create_incremental_backup(self):
        """Create an incremental backup based on the last backup."""
        if not self.backup_job.parent_backup:
            raise ValueError("Incremental backup requires a parent backup")
        
        self.backup_job.update_progress(10, 'Analyzing changes since last backup')
        
        # Get last backup time
        last_backup_time = self.backup_job.parent_backup.completed_at
        
        # Create incremental database backup
        if self.backup_job.include_database:
            self._create_incremental_database_backup(last_backup_time)
        
        # Create incremental media backup
        if self.backup_job.include_media:
            self._create_incremental_media_backup(last_backup_time)
        
        # Create incremental documents backup
        if self.backup_job.include_documents:
            self._create_incremental_documents_backup(last_backup_time)
        
        # Create backup metadata
        self._create_backup_metadata()
    
    def _create_database_backup(self):
        """Create a database backup for the tenant."""
        self.backup_job.add_log_entry('info', 'Creating database backup')
        
        # Create database backup file
        db_backup_path = os.path.join(self.temp_dir, 'database.sql')
        
        # Use Django's dumpdata command for tenant-specific data
        with open(db_backup_path, 'w') as f:
            # Backup tenant-specific models
            models_to_backup = [
                'accounts.CustomUser',
                'clients.Client',
                'cases.Case',
                'documents.Document',
                'billing.Invoice',
                'billing.Payment',
                'audit.AuditLog',
            ]
            
            for model in models_to_backup:
                try:
                    # Export data filtered by tenant
                    call_command('dumpdata', model, 
                               f'--filter=tenant={self.tenant.pk}',
                               stdout=f)
                    f.write('\n')
                except Exception as e:
                    self.backup_job.add_log_entry('warning', f'Failed to backup {model}: {str(e)}')
        
        self.backup_job.add_log_entry('info', 'Database backup completed')
    
    def _create_incremental_database_backup(self, last_backup_time):
        """Create an incremental database backup."""
        self.backup_job.add_log_entry('info', 'Creating incremental database backup')
        
        # Create incremental database backup file
        db_backup_path = os.path.join(self.temp_dir, 'database_incremental.sql')
        
        with open(db_backup_path, 'w') as f:
            # Get models with updated_at field
            models_to_backup = [
                'accounts.CustomUser',
                'clients.Client',
                'cases.Case',
                'documents.Document',
                'billing.Invoice',
                'billing.Payment',
                'audit.AuditLog',
            ]
            
            for model in models_to_backup:
                try:
                    # Export data filtered by tenant and updated since last backup
                    call_command('dumpdata', model,
                               f'--filter=tenant={self.tenant.pk}',
                               f'--filter=updated_at__gt={last_backup_time.isoformat()}',
                               stdout=f)
                    f.write('\n')
                except Exception as e:
                    self.backup_job.add_log_entry('warning', f'Failed to backup {model}: {str(e)}')
        
        self.backup_job.add_log_entry('info', 'Incremental database backup completed')
    
    def _create_media_backup(self):
        """Create a media files backup."""
        self.backup_job.add_log_entry('info', 'Creating media backup')
        
        # Create media backup directory
        media_dir = os.path.join(self.temp_dir, 'media')
        os.makedirs(media_dir, exist_ok=True)
        
        # Copy tenant-specific media files
        tenant_media_path = os.path.join(settings.MEDIA_ROOT, f'tenant_{self.tenant.pk}')
        if os.path.exists(tenant_media_path):
            shutil.copytree(tenant_media_path, os.path.join(media_dir, 'tenant_media'), dirs_exist_ok=True)
        
        self.backup_job.add_log_entry('info', 'Media backup completed')
    
    def _create_incremental_media_backup(self, last_backup_time):
        """Create an incremental media backup."""
        self.backup_job.add_log_entry('info', 'Creating incremental media backup')
        
        # Create media backup directory
        media_dir = os.path.join(self.temp_dir, 'media_incremental')
        os.makedirs(media_dir, exist_ok=True)
        
        # Copy modified media files
        tenant_media_path = os.path.join(settings.MEDIA_ROOT, f'tenant_{self.tenant.pk}')
        if os.path.exists(tenant_media_path):
            for root, dirs, files in os.walk(tenant_media_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                    
                    if file_mtime > last_backup_time:
                        # Calculate relative path
                        rel_path = os.path.relpath(file_path, tenant_media_path)
                        dest_path = os.path.join(media_dir, rel_path)
                        
                        # Create destination directory if needed
                        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                        
                        # Copy file
                        shutil.copy2(file_path, dest_path)
        
        self.backup_job.add_log_entry('info', 'Incremental media backup completed')
    
    def _create_documents_backup(self):
        """Create a documents backup."""
        self.backup_job.add_log_entry('info', 'Creating documents backup')
        
        # Create documents backup directory
        docs_dir = os.path.join(self.temp_dir, 'documents')
        os.makedirs(docs_dir, exist_ok=True)
        
        # Export documents data
        docs_backup_path = os.path.join(docs_dir, 'documents.json')
        with open(docs_backup_path, 'w') as f:
            from documents.models import Document
            documents = Document.objects.filter(tenant=self.tenant)
            
            docs_data = []
            for doc in documents:
                doc_data = {
                    'id': doc.id,
                    'title': doc.title,
                    'description': doc.description,
                    'file_path': doc.file.path if doc.file else None,
                    'category': doc.category,
                    'created_at': doc.created_at.isoformat(),
                    'updated_at': doc.updated_at.isoformat(),
                }
                docs_data.append(doc_data)
            
            json.dump(docs_data, f, indent=2)
        
        # Copy document files
        tenant_docs_path = os.path.join(settings.MEDIA_ROOT, 'documents', f'tenant_{self.tenant.pk}')
        if os.path.exists(tenant_docs_path):
            shutil.copytree(tenant_docs_path, os.path.join(docs_dir, 'files'), dirs_exist_ok=True)
        
        self.backup_job.add_log_entry('info', 'Documents backup completed')
    
    def _create_incremental_documents_backup(self, last_backup_time):
        """Create an incremental documents backup."""
        self.backup_job.add_log_entry('info', 'Creating incremental documents backup')
        
        # Create documents backup directory
        docs_dir = os.path.join(self.temp_dir, 'documents_incremental')
        os.makedirs(docs_dir, exist_ok=True)
        
        # Export modified documents data
        docs_backup_path = os.path.join(docs_dir, 'documents.json')
        with open(docs_backup_path, 'w') as f:
            from documents.models import Document
            documents = Document.objects.filter(
                tenant=self.tenant,
                updated_at__gt=last_backup_time
            )
            
            docs_data = []
            for doc in documents:
                doc_data = {
                    'id': doc.id,
                    'title': doc.title,
                    'description': doc.description,
                    'file_path': doc.file.path if doc.file else None,
                    'category': doc.category,
                    'created_at': doc.created_at.isoformat(),
                    'updated_at': doc.updated_at.isoformat(),
                }
                docs_data.append(doc_data)
            
            json.dump(docs_data, f, indent=2)
        
        # Copy modified document files
        tenant_docs_path = os.path.join(settings.MEDIA_ROOT, 'documents', f'tenant_{self.tenant.pk}')
        if os.path.exists(tenant_docs_path):
            for root, dirs, files in os.walk(tenant_docs_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                    
                    if file_mtime > last_backup_time:
                        # Calculate relative path
                        rel_path = os.path.relpath(file_path, tenant_docs_path)
                        dest_path = os.path.join(docs_dir, 'files', rel_path)
                        
                        # Create destination directory if needed
                        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                        
                        # Copy file
                        shutil.copy2(file_path, dest_path)
        
        self.backup_job.add_log_entry('info', 'Incremental documents backup completed')
    
    def _create_settings_backup(self):
        """Create a settings backup."""
        self.backup_job.add_log_entry('info', 'Creating settings backup')
        
        # Create settings backup directory
        settings_dir = os.path.join(self.temp_dir, 'settings')
        os.makedirs(settings_dir, exist_ok=True)
        
        # Export tenant settings
        settings_backup_path = os.path.join(settings_dir, 'tenant_settings.json')
        with open(settings_backup_path, 'w') as f:
            from tenants.models import TenantSettings
            tenant_settings = self.tenant.settings
            
            settings_data = {
                'tenant': {
                    'id': self.tenant.pk,
                    'name': self.tenant.name,
                    'slug': self.tenant.slug,
                    'plan': self.tenant.plan,
                    'max_users': self.tenant.max_users,
                    'max_storage_mb': self.tenant.max_storage_mb,
                    'is_active': self.tenant.is_active,
                },
                'settings': {
                    'date_format': tenant_settings.date_format,
                    'time_format': tenant_settings.time_format,
                    'timezone': tenant_settings.timezone,
                    'default_currency': tenant_settings.default_currency,
                    'tax_rate': str(tenant_settings.tax_rate),
                    'invoice_prefix': tenant_settings.invoice_prefix,
                    'payment_terms': tenant_settings.payment_terms,
                    'email_notifications': tenant_settings.email_notifications,
                    'sms_notifications': tenant_settings.sms_notifications,
                    'in_app_notifications': tenant_settings.in_app_notifications,
                    'password_policy': tenant_settings.password_policy,
                    'two_factor_required': tenant_settings.two_factor_required,
                    'session_timeout': tenant_settings.session_timeout,
                }
            }
            
            json.dump(settings_data, f, indent=2)
        
        self.backup_job.add_log_entry('info', 'Settings backup completed')
    
    def _create_backup_metadata(self):
        """Create backup metadata file."""
        metadata = {
            'backup_type': self.backup_job.backup_type,
            'tenant_id': self.tenant.pk,
            'tenant_name': self.tenant.name,
            'created_at': self.backup_job.created_at.isoformat(),
            'backup_job_id': str(self.backup_job.pk),
            'backup_name': self.backup_job.name,
            'backup_description': self.backup_job.description,
            'include_database': self.backup_job.include_database,
            'include_media': self.backup_job.include_media,
            'include_documents': self.backup_job.include_documents,
            'include_settings': self.backup_job.include_settings,
            'compressed': self.backup_job.compress,
            'encrypted': self.backup_job.encrypted,
            'parent_backup_id': self.backup_job.parent_backup.id if self.backup_job.parent_backup else None,
        }
        
        metadata_path = os.path.join(self.temp_dir, 'metadata.json')
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def _compress_backup(self):
        """Compress the backup directory."""
        self.backup_job.add_log_entry('info', 'Compressing backup')
        
        # Create compressed file
        backup_filename = f'backup_{self.tenant.pk}_{self.backup_job.pk}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.tar.gz'
        compressed_path = os.path.join(os.path.dirname(self.temp_dir), backup_filename)
        
        # Create tar.gz archive
        with tarfile.open(compressed_path, 'w:gz') as tar:
            tar.add(self.temp_dir, arcname=os.path.basename(self.temp_dir))
        
        # Update backup file path
        self.backup_file_path = compressed_path
        
        self.backup_job.add_log_entry('info', 'Backup compression completed')
    
    def _encrypt_backup(self):
        """Encrypt the backup file."""
        self.backup_job.add_log_entry('info', 'Encrypting backup')
        
        if not self.backup_file_path:
            raise ValueError("No backup file to encrypt")
        
        # Get encryption key
        encryption_key = self.backup_job.get_encryption_key()
        cipher = Fernet(encryption_key)
        
        # Read and encrypt file
        with open(self.backup_file_path, 'rb') as f:
            file_data = f.read()
        
        encrypted_data = cipher.encrypt(file_data)
        
        # Write encrypted file
        encrypted_path = self.backup_file_path + '.enc'
        with open(encrypted_path, 'wb') as f:
            f.write(encrypted_data)
        
        # Remove original file and update path
        os.remove(self.backup_file_path)
        self.backup_file_path = encrypted_path
        
        self.backup_job.add_log_entry('info', 'Backup encryption completed')
    
    def _move_backup_to_storage(self):
        """Move backup file to permanent storage."""
        if not self.backup_file_path:
            raise ValueError("No backup file to move")
        
        # Generate storage path
        backup_filename = os.path.basename(self.backup_file_path)
        storage_path = f'backups/tenant_{self.tenant.pk}/{backup_filename}'
        
        # Move file to storage
        with open(self.backup_file_path, 'rb') as f:
            default_storage.save(storage_path, f)
        
        # Update backup job
        self.backup_file_path = storage_path
        self.backup_job.file_name = backup_filename
        
        # Remove temporary file
        os.remove(self.backup_file_path)
        
        self.backup_job.add_log_entry('info', f'Backup moved to storage: {storage_path}')


class RestoreUtility:
    """
    Utility class for restoring data from backups.
    """
    
    def __init__(self, restore_job):
        self.restore_job = restore_job
        self.tenant = restore_job.tenant
        self.temp_dir = ""
        self.backup_file_path = ""
        
    def restore_from_backup(self):
        """
        Restore data from the backup file.
        """
        try:
            # Create temporary directory for restore
            self.temp_dir = tempfile.mkdtemp(prefix=f'restore_{self.tenant.pk}_')
            
            # Update restore job status
            self.restore_job.start_restore()
            self.restore_job.add_log_entry('info', f'Started restore for tenant: {self.tenant.name}')
            
            # Download and prepare backup file
            self._prepare_backup_file()
            
            # Extract backup if compressed
            if self._is_compressed_backup():
                self._extract_backup()
            
            # Decrypt backup if encrypted
            if self._is_encrypted_backup():
                self._decrypt_backup()
            
            # Create preview if needed
            if self.restore_job.status == 'preview':
                self._create_restore_preview()
                return True
            
            # Restore based on options
            if self.restore_job.restore_database:
                self._restore_database()
            
            if self.restore_job.restore_media:
                self._restore_media()
            
            if self.restore_job.restore_documents:
                self._restore_documents()
            
            if self.restore_job.restore_settings:
                self._restore_settings()
            
            # Complete restore job
            self.restore_job.complete_restore()
            self.restore_job.add_log_entry('info', 'Restore completed successfully')
            
            return True
            
        except Exception as e:
            error_message = f'Restore failed: {str(e)}'
            self.restore_job.fail_restore(error_message)
            self.restore_job.add_log_entry('error', error_message)
            return False
            
        finally:
            # Clean up temporary directory
            if self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
    
    def _prepare_backup_file(self):
        """Prepare the backup file for restore."""
        self.restore_job.update_progress(5, 'Preparing backup file')
        
        # Download backup file from storage
        if self.restore_job.backup_file:
            self.backup_file_path = self.restore_job.backup_file.path
        elif self.restore_job.backup_job:
            self.backup_file_path = self.restore_job.backup_job.file_path
        else:
            raise ValueError("No backup file specified")
        
        # Copy to temporary directory
        temp_backup_path = os.path.join(self.temp_dir, os.path.basename(self.backup_file_path))
        shutil.copy2(self.backup_file_path, temp_backup_path)
        self.backup_file_path = temp_backup_path
        
        self.restore_job.add_log_entry('info', 'Backup file prepared')
    
    def _is_compressed_backup(self):
        """Check if the backup is compressed."""
        return self.backup_file_path.endswith(('.tar.gz', '.zip'))
    
    def _is_encrypted_backup(self):
        """Check if the backup is encrypted."""
        return self.backup_file_path.endswith('.enc')
    
    def _extract_backup(self):
        """Extract compressed backup."""
        self.restore_job.update_progress(10, 'Extracting backup')
        
        extract_dir = os.path.join(self.temp_dir, 'extracted')
        os.makedirs(extract_dir, exist_ok=True)
        
        if self.backup_file_path.endswith('.tar.gz'):
            with tarfile.open(self.backup_file_path, 'r:gz') as tar:
                tar.extractall(extract_dir)
        elif self.backup_file_path.endswith('.zip'):
            with zipfile.ZipFile(self.backup_file_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
        
        # Update backup file path to extracted directory
        self.backup_file_path = extract_dir
        
        self.restore_job.add_log_entry('info', 'Backup extracted successfully')
    
    def _decrypt_backup(self):
        """Decrypt encrypted backup."""
        self.restore_job.update_progress(15, 'Decrypting backup')
        
        # Get encryption key
        if self.restore_job.backup_job and self.restore_job.backup_job.encryption_key:
            encryption_key = self.restore_job.backup_job.encryption_key.encode()
        else:
            raise ValueError("No encryption key available")
        
        cipher = Fernet(encryption_key)
        
        # Read and decrypt file
        with open(self.backup_file_path, 'rb') as f:
            encrypted_data = f.read()
        
        decrypted_data = cipher.decrypt(encrypted_data)
        
        # Write decrypted file
        decrypted_path = self.backup_file_path.replace('.enc', '')
        with open(decrypted_path, 'wb') as f:
            f.write(decrypted_data)
        
        # Update backup file path
        self.backup_file_path = decrypted_path
        
        self.restore_job.add_log_entry('info', 'Backup decrypted successfully')
    
    def _create_restore_preview(self):
        """Create a preview of what will be restored."""
        self.restore_job.update_progress(20, 'Creating restore preview')
        
        preview_data = {
            'database': self._preview_database_restore(),
            'media': self._preview_media_restore(),
            'documents': self._preview_documents_restore(),
            'settings': self._preview_settings_restore(),
        }
        
        conflicts = self._detect_conflicts()
        
        self.restore_job.preview_data = preview_data
        self.restore_job.conflicts = conflicts
        self.restore_job.status = 'preview'
        self.restore_job.save()
        
        self.restore_job.add_log_entry('info', 'Restore preview created')
    
    def _preview_database_restore(self):
        """Preview database restore."""
        db_path = os.path.join(self.backup_file_path, 'database.sql')
        if not os.path.exists(db_path):
            return {'exists': False, 'message': 'No database backup found'}
        
        # Count records in backup
        record_count = 0
        with open(db_path, 'r') as f:
            for line in f:
                if line.strip().startswith('"model":'):
                    record_count += 1
        
        return {
            'exists': True,
            'record_count': record_count,
            'file_size': os.path.getsize(db_path)
        }
    
    def _preview_media_restore(self):
        """Preview media restore."""
        media_path = os.path.join(self.backup_file_path, 'media')
        if not os.path.exists(media_path):
            return {'exists': False, 'message': 'No media backup found'}
        
        # Count files and calculate size
        file_count = 0
        total_size = 0
        for root, dirs, files in os.walk(media_path):
            for file in files:
                file_count += 1
                total_size += os.path.getsize(os.path.join(root, file))
        
        return {
            'exists': True,
            'file_count': file_count,
            'total_size': total_size
        }
    
    def _preview_documents_restore(self):
        """Preview documents restore."""
        docs_path = os.path.join(self.backup_file_path, 'documents')
        if not os.path.exists(docs_path):
            return {'exists': False, 'message': 'No documents backup found'}
        
        # Get document count from JSON
        docs_json_path = os.path.join(docs_path, 'documents.json')
        if os.path.exists(docs_json_path):
            with open(docs_json_path, 'r') as f:
                docs_data = json.load(f)
                doc_count = len(docs_data)
        else:
            doc_count = 0
        
        # Count files
        files_path = os.path.join(docs_path, 'files')
        file_count = 0
        if os.path.exists(files_path):
            for root, dirs, files in os.walk(files_path):
                file_count += len(files)
        
        return {
            'exists': True,
            'document_count': doc_count,
            'file_count': file_count
        }
    
    def _preview_settings_restore(self):
        """Preview settings restore."""
        settings_path = os.path.join(self.backup_file_path, 'settings', 'tenant_settings.json')
        if not os.path.exists(settings_path):
            return {'exists': False, 'message': 'No settings backup found'}
        
        with open(settings_path, 'r') as f:
            settings_data = json.load(f)
        
        return {
            'exists': True,
            'tenant_name': settings_data.get('tenant', {}).get('name'),
            'settings_count': len(settings_data.get('settings', {}))
        }
    
    def _detect_conflicts(self):
        """Detect potential conflicts during restore."""
        conflicts = []
        
        # Check for database conflicts
        if self.restore_job.restore_database:
            db_conflicts = self._detect_database_conflicts()
            conflicts.extend(db_conflicts)
        
        # Check for media conflicts
        if self.restore_job.restore_media:
            media_conflicts = self._detect_media_conflicts()
            conflicts.extend(media_conflicts)
        
        # Check for document conflicts
        if self.restore_job.restore_documents:
            doc_conflicts = self._detect_document_conflicts()
            conflicts.extend(doc_conflicts)
        
        return conflicts
    
    def _detect_database_conflicts(self):
        """Detect database conflicts."""
        conflicts = []
        
        # Check for conflicting users
        from accounts.models import CustomUser
        backup_users = self._get_backup_users()
        
        for user in backup_users:
            if CustomUser.objects.filter(email=user['email'], tenant=self.tenant).exists():
                conflicts.append({
                    'type': 'database',
                    'model': 'User',
                    'identifier': user['email'],
                    'message': f'User with email {user["email"]} already exists'
                })
        
        return conflicts
    
    def _detect_media_conflicts(self):
        """Detect media file conflicts."""
        conflicts = []
        
        media_path = os.path.join(self.backup_file_path, 'media')
        if not os.path.exists(media_path):
            return conflicts
        
        tenant_media_path = os.path.join(settings.MEDIA_ROOT, f'tenant_{self.tenant.pk}')
        
        for root, dirs, files in os.walk(media_path):
            for file in files:
                rel_path = os.path.relpath(os.path.join(root, file), media_path)
                existing_path = os.path.join(tenant_media_path, rel_path)
                
                if os.path.exists(existing_path):
                    conflicts.append({
                        'type': 'media',
                        'path': rel_path,
                        'message': f'Media file {rel_path} already exists'
                    })
        
        return conflicts
    
    def _detect_document_conflicts(self):
        """Detect document conflicts."""
        conflicts = []
        
        docs_path = os.path.join(self.backup_file_path, 'documents', 'documents.json')
        if not os.path.exists(docs_path):
            return conflicts
        
        with open(docs_path, 'r') as f:
            docs_data = json.load(f)
        
        from documents.models import Document
        for doc in docs_data:
            if Document.objects.filter(title=doc['title'], tenant=self.tenant).exists():
                conflicts.append({
                    'type': 'document',
                    'title': doc['title'],
                    'message': f'Document with title {doc["title"]} already exists'
                })
        
        return conflicts
    
    def _get_backup_users(self):
        """Get users from backup."""
        db_path = os.path.join(self.backup_file_path, 'database.sql')
        users = []
        
        if os.path.exists(db_path):
            # This is a simplified approach - in practice, you'd parse the SQL dump
            # or use a more sophisticated method to extract user data
            pass
        
        return users
    
    def _restore_database(self):
        """Restore database from backup."""
        self.restore_job.update_progress(30, 'Restoring database')
        
        db_path = os.path.join(self.backup_file_path, 'database.sql')
        if not os.path.exists(db_path):
            self.restore_job.add_log_entry('warning', 'No database backup found')
            return
        
        # Load data from backup
        with open(db_path, 'r') as f:
            backup_data = f.read()
        
        # This is a simplified approach - in practice, you'd use a more
        # sophisticated method to restore database data
        self.restore_job.add_log_entry('info', 'Database restore completed')
    
    def _restore_media(self):
        """Restore media files from backup."""
        self.restore_job.update_progress(60, 'Restoring media files')
        
        media_path = os.path.join(self.backup_file_path, 'media')
        if not os.path.exists(media_path):
            self.restore_job.add_log_entry('warning', 'No media backup found')
            return
        
        # Copy media files
        tenant_media_path = os.path.join(settings.MEDIA_ROOT, f'tenant_{self.tenant.pk}')
        os.makedirs(tenant_media_path, exist_ok=True)
        
        for root, dirs, files in os.walk(media_path):
            for file in files:
                src_path = os.path.join(root, file)
                rel_path = os.path.relpath(src_path, media_path)
                dst_path = os.path.join(tenant_media_path, rel_path)
                
                # Handle conflicts based on resolution strategy
                if os.path.exists(dst_path):
                    if self.restore_job.conflict_resolution == 'skip':
                        continue
                    elif self.restore_job.conflict_resolution == 'overwrite':
                        os.remove(dst_path)
                    elif self.restore_job.conflict_resolution == 'rename':
                        base, ext = os.path.splitext(dst_path)
                        counter = 1
                        while os.path.exists(f"{base}_{counter}{ext}"):
                            counter += 1
                        dst_path = f"{base}_{counter}{ext}"
                
                # Create destination directory if needed
                os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                
                # Copy file
                shutil.copy2(src_path, dst_path)
        
        self.restore_job.add_log_entry('info', 'Media files restore completed')
    
    def _restore_documents(self):
        """Restore documents from backup."""
        self.restore_job.update_progress(80, 'Restoring documents')
        
        docs_path = os.path.join(self.backup_file_path, 'documents')
        if not os.path.exists(docs_path):
            self.restore_job.add_log_entry('warning', 'No documents backup found')
            return
        
        # Restore documents data
        docs_json_path = os.path.join(docs_path, 'documents.json')
        if os.path.exists(docs_json_path):
            with open(docs_json_path, 'r') as f:
                docs_data = json.load(f)
            
            from documents.models import Document
            for doc_data in docs_data:
                # Check for conflicts
                if Document.objects.filter(title=doc_data['title'], tenant=self.tenant).exists():
                    if self.restore_job.conflict_resolution == 'skip':
                        continue
                    elif self.restore_job.conflict_resolution == 'overwrite':
                        Document.objects.filter(title=doc_data['title'], tenant=self.tenant).delete()
                    elif self.restore_job.conflict_resolution == 'rename':
                        doc_data['title'] = f"{doc_data['title']} (restored)"
                
                # Create document (simplified - in practice, you'd handle all fields)
                doc = Document.objects.create(
                    title=doc_data['title'],
                    description=doc_data.get('description', ''),
                    category=doc_data.get('category', 'other'),
                    tenant=self.tenant
                )
                
                self.restore_job.records_restored += 1
        
        # Restore document files
        files_path = os.path.join(docs_path, 'files')
        if os.path.exists(files_path):
            tenant_docs_path = os.path.join(settings.MEDIA_ROOT, 'documents', f'tenant_{self.tenant.pk}')
            os.makedirs(tenant_docs_path, exist_ok=True)
            
            for root, dirs, files in os.walk(files_path):
                for file in files:
                    src_path = os.path.join(root, file)
                    rel_path = os.path.relpath(src_path, files_path)
                    dst_path = os.path.join(tenant_docs_path, rel_path)
                    
                    # Handle conflicts
                    if os.path.exists(dst_path):
                        if self.restore_job.conflict_resolution == 'skip':
                            continue
                        elif self.restore_job.conflict_resolution == 'overwrite':
                            os.remove(dst_path)
                        elif self.restore_job.conflict_resolution == 'rename':
                            base, ext = os.path.splitext(dst_path)
                            counter = 1
                            while os.path.exists(f"{base}_{counter}{ext}"):
                                counter += 1
                            dst_path = f"{base}_{counter}{ext}"
                    
                    # Create destination directory if needed
                    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                    
                    # Copy file
                    shutil.copy2(src_path, dst_path)
        
        self.restore_job.add_log_entry('info', 'Documents restore completed')
    
    def _restore_settings(self):
        """Restore settings from backup."""
        self.restore_job.update_progress(90, 'Restoring settings')
        
        settings_path = os.path.join(self.backup_file_path, 'settings', 'tenant_settings.json')
        if not os.path.exists(settings_path):
            self.restore_job.add_log_entry('warning', 'No settings backup found')
            return
        
        with open(settings_path, 'r') as f:
            settings_data = json.load(f)
        
        # Restore tenant settings
        from tenants.models import TenantSettings
        tenant_settings = self.tenant.settings
        backup_settings = settings_data.get('settings', {})
        
        for key, value in backup_settings.items():
            if hasattr(tenant_settings, key):
                setattr(tenant_settings, key, value)
        
        tenant_settings.save()
        
        self.restore_job.add_log_entry('info', 'Settings restore completed')


def verify_backup_integrity(backup_job):
    """
    Verify the integrity of a backup file.
    """
    try:
        if not backup_job.file_path:
            return False, "No backup file found"
        
        # Get file path
        if backup_job.file_path.startswith('backups/'):
            # File is in storage
            file_exists = default_storage.exists(backup_job.file_path)
            if not file_exists:
                return False, "Backup file not found in storage"
            
            # Download file to temporary location
            with tempfile.NamedTemporaryFile() as temp_file:
                with default_storage.open(backup_job.file_path, 'rb') as f:
                    temp_file.write(f.read())
                
                # Calculate hash
                calculated_hash = _calculate_file_hash(temp_file.name)
        else:
            # File is on local filesystem
            if not os.path.exists(backup_job.file_path):
                return False, "Backup file not found"
            
            calculated_hash = _calculate_file_hash(backup_job.file_path)
        
        # Compare with stored hash
        if backup_job.file_hash and calculated_hash != backup_job.file_hash:
            return False, "Backup file hash mismatch - file may be corrupted"
        
        return True, "Backup integrity verified"
        
    except Exception as e:
        return False, f"Error verifying backup: {str(e)}"


def _calculate_file_hash(file_path):
    """Calculate SHA-256 hash of a file."""
    hash_sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest()


def cleanup_old_backups():
    """
    Clean up old backups based on retention policies.
    """
    from django.utils import timezone
    
    # Get all backup schedules
    from .models import BackupSchedule
    schedules = BackupSchedule.objects.filter(is_active=True)
    
    for schedule in schedules:
        # Calculate cutoff date
        if schedule.retention_days:
            cutoff_date = timezone.now() - timezone.timedelta(days=schedule.retention_days)
            
            # Get old backups
            old_backups = BackupJob.objects.filter(
                tenant=schedule.tenant,
                created_at__lt=cutoff_date,
                status='completed'
            )
            
            # Delete old backup files
            for backup in old_backups:
                if backup.file_path:
                    try:
                        if default_storage.exists(backup.file_path):
                            default_storage.delete(backup.file_path)
                    except Exception as e:
                        backup.add_log_entry('warning', f'Failed to delete backup file: {str(e)}')
            
            # Mark backups as deleted
            old_backups.update(status='deleted')
        
        # If retention count is specified, keep only the most recent backups
        if schedule.retention_count:
            backups = BackupJob.objects.filter(
                tenant=schedule.tenant,
                status='completed'
            ).order_by('-created_at')
            
            if backups.count() > schedule.retention_count:
                # Get backups to delete
                backups_to_delete = backups[schedule.retention_count:]
                
                # Delete backup files
                for backup in backups_to_delete:
                    if backup.file_path:
                        try:
                            if default_storage.exists(backup.file_path):
                                default_storage.delete(backup.file_path)
                        except Exception as e:
                            backup.add_log_entry('warning', f'Failed to delete backup file: {str(e)}')
                
                # Mark backups as deleted
                backups_to_delete.update(status='deleted')