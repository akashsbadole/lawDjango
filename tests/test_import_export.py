"""
Tests for import/export module in multi-tenant context.
"""

import os
import tempfile
import csv
from io import StringIO
from django.test import TestCase, TransactionTestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal
from django.contrib.auth import get_user_model

from import_export.models import ImportJob, ExportJob, ImportTemplate
from clients.models import Client
from cases.models import Case
from tenants.models import Tenant
from tests.utils import TenantTestCase, MultiTenantTestCase, TenantMixinTestMixin

User = get_user_model()


class ImportJobModelTests(TenantTestCase):
    """Test ImportJob model."""
    
    def test_import_job_creation(self):
        """Test basic import job creation."""
        import_job = ImportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            file_format='csv',
            status='pending',
            total_records=100,
            field_mappings={
                'first_name': 'First Name',
                'last_name': 'Last Name',
                'email': 'Email Address'
            },
            skip_header=True,
            update_existing=False,
            dry_run=False,
            user=self.admin_user
        )
        
        self.assertEqual(import_job.tenant, self.active_tenant)
        self.assertEqual(import_job.model_type, 'clients')
        self.assertEqual(import_job.file_format, 'csv')
        self.assertEqual(import_job.status, 'pending')
        self.assertEqual(import_job.total_records, 100)
        self.assertEqual(import_job.field_mappings['first_name'], 'First Name')
        self.assertTrue(import_job.skip_header)
        self.assertFalse(import_job.update_existing)
        self.assertFalse(import_job.dry_run)
        self.assertEqual(import_job.user, self.admin_user)
    
    def test_import_job_str_representation(self):
        """Test import job string representation."""
        import_job = ImportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            file_format='csv',
            status='pending',
            user=self.admin_user
        )
        
        expected = "Import clients - Pending"
        self.assertEqual(str(import_job), expected)
    
    def test_import_job_progress_percentage_property(self):
        """Test progress_percentage property."""
        # Job with no records
        empty_job = ImportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            file_format='csv',
            status='pending',
            total_records=0,
            user=self.admin_user
        )
        
        self.assertEqual(empty_job.progress_percentage, 0)
        
        # Job with progress
        progress_job = ImportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            file_format='csv',
            status='processing',
            total_records=100,
            processed_records=50,
            user=self.admin_user
        )
        
        self.assertEqual(progress_job.progress_percentage, 50)
    
    def test_import_job_is_completed_property(self):
        """Test is_completed property."""
        # Completed job
        completed_job = ImportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            file_format='csv',
            status='completed',
            user=self.admin_user
        )
        
        self.assertTrue(completed_job.is_completed)
        
        # Failed job
        failed_job = ImportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            file_format='csv',
            status='failed',
            user=self.admin_user
        )
        
        self.assertTrue(failed_job.is_completed)
        
        # Processing job
        processing_job = ImportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            file_format='csv',
            status='processing',
            user=self.admin_user
        )
        
        self.assertFalse(processing_job.is_completed)
    
    def test_import_job_is_running_property(self):
        """Test is_running property."""
        # Running job
        running_job = ImportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            file_format='csv',
            status='processing',
            user=self.admin_user
        )
        
        self.assertTrue(running_job.is_running)
        
        # Not running job
        pending_job = ImportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            file_format='csv',
            status='pending',
            user=self.admin_user
        )
        
        self.assertFalse(pending_job.is_running)
    
    def test_import_job_file_size_mb_property(self):
        """Test file_size_mb property."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(suffix='.csv') as temp_file:
            temp_file.write(b'a' * (1024 * 1024))  # 1MB
            temp_file.seek(0)
            
            # Create import job with file
            import_job = ImportJob.objects.create(
                tenant=self.active_tenant,
                model_type='clients',
                file_format='csv',
                status='pending',
                user=self.admin_user
            )
            
            # Manually set file and file_size for testing
            import_job.file.save('test.csv', temp_file)
            import_job.file_size = 1024 * 1024  # 1MB in bytes
            import_job.save()
            
            self.assertEqual(import_job.file_size_mb, 1.0)
    
    def test_import_job_start_processing_method(self):
        """Test start_processing method."""
        import_job = ImportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            file_format='csv',
            status='pending',
            user=self.admin_user
        )
        
        # Verify initial state
        self.assertEqual(import_job.status, 'pending')
        self.assertIsNone(import_job.started_at)
        
        # Start processing
        import_job.start_processing()
        
        # Verify updated state
        import_job.refresh_from_db()
        self.assertEqual(import_job.status, 'processing')
        self.assertIsNotNone(import_job.started_at)
    
    def test_import_job_complete_processing_method(self):
        """Test complete_processing method."""
        import_job = ImportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            file_format='csv',
            status='processing',
            user=self.admin_user
        )
        
        # Complete processing
        import_job.complete_processing()
        
        # Verify updated state
        import_job.refresh_from_db()
        self.assertEqual(import_job.status, 'completed')
        self.assertIsNotNone(import_job.completed_at)
    
    def test_import_job_fail_processing_method(self):
        """Test fail_processing method."""
        import_job = ImportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            file_format='csv',
            status='processing',
            user=self.admin_user
        )
        
        # Fail processing
        error_summary = "Invalid data format"
        import_job.fail_processing(error_summary=error_summary)
        
        # Verify updated state
        import_job.refresh_from_db()
        self.assertEqual(import_job.status, 'failed')
        self.assertIsNotNone(import_job.completed_at)
        self.assertEqual(import_job.error_summary, error_summary)
    
    def test_import_job_cancel_processing_method(self):
        """Test cancel_processing method."""
        import_job = ImportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            file_format='csv',
            status='processing',
            user=self.admin_user
        )
        
        # Cancel processing
        import_job.cancel_processing()
        
        # Verify updated state
        import_job.refresh_from_db()
        self.assertEqual(import_job.status, 'cancelled')
        self.assertIsNotNone(import_job.completed_at)
    
    def test_import_job_add_error_method(self):
        """Test add_error method."""
        import_job = ImportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            file_format='csv',
            status='processing',
            failed_records=0,
            user=self.admin_user
        )
        
        # Add error
        import_job.add_error(
            row_number=5,
            error_message="Invalid email format",
            record_data={'first_name': 'John', 'email': 'invalid-email'}
        )
        
        # Verify error was added
        import_job.refresh_from_db()
        self.assertEqual(import_job.failed_records, 1)
        self.assertEqual(len(import_job.errors), 1)
        self.assertEqual(import_job.errors[0]['row'], 5)
        self.assertEqual(import_job.errors[0]['error'], "Invalid email format")
        self.assertEqual(import_job.errors[0]['data']['first_name'], 'John')
    
    def test_import_job_ordering(self):
        """Test import job ordering by created_at."""
        # Create jobs in random order
        job3 = ImportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            file_format='csv',
            status='pending',
            user=self.admin_user
        )
        
        job1 = ImportJob.objects.create(
            tenant=self.active_tenant,
            model_type='cases',
            file_format='csv',
            status='pending',
            user=self.admin_user
        )
        
        job2 = ImportJob.objects.create(
            tenant=self.active_tenant,
            model_type='documents',
            file_format='csv',
            status='pending',
            user=self.admin_user
        )
        
        # Verify ordering (newest first)
        jobs = list(ImportJob.objects.all())
        self.assertEqual(jobs[0], job3)  # Most recent
        self.assertEqual(jobs[1], job2)  # Middle
        self.assertEqual(jobs[2], job1)  # Oldest


class ExportJobModelTests(TenantTestCase):
    """Test ExportJob model."""
    
    def test_export_job_creation(self):
        """Test basic export job creation."""
        export_job = ExportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            export_type='all',
            file_format='csv',
            status='pending',
            total_records=100,
            filters={
                'created_after': '2023-01-01',
                'status': 'active'
            },
            field_selection=['first_name', 'last_name', 'email'],
            include_relations=True,
            user=self.admin_user
        )
        
        self.assertEqual(export_job.tenant, self.active_tenant)
        self.assertEqual(export_job.model_type, 'clients')
        self.assertEqual(export_job.export_type, 'all')
        self.assertEqual(export_job.file_format, 'csv')
        self.assertEqual(export_job.status, 'pending')
        self.assertEqual(export_job.total_records, 100)
        self.assertEqual(export_job.filters['created_after'], '2023-01-01')
        self.assertEqual(export_job.field_selection, ['first_name', 'last_name', 'email'])
        self.assertTrue(export_job.include_relations)
        self.assertEqual(export_job.user, self.admin_user)
    
    def test_export_job_str_representation(self):
        """Test export job string representation."""
        export_job = ExportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            export_type='filtered',
            file_format='csv',
            status='pending',
            user=self.admin_user
        )
        
        expected = "Export clients - Pending"
        self.assertEqual(str(export_job), expected)
    
    def test_export_job_progress_percentage_property(self):
        """Test progress_percentage property."""
        # Job with no records
        empty_job = ExportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            file_format='csv',
            status='pending',
            total_records=0,
            user=self.admin_user
        )
        
        self.assertEqual(empty_job.progress_percentage, 0)
        
        # Job with progress
        progress_job = ExportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            file_format='csv',
            status='processing',
            total_records=100,
            processed_records=50,
            user=self.admin_user
        )
        
        self.assertEqual(progress_job.progress_percentage, 50)
    
    def test_export_job_is_completed_property(self):
        """Test is_completed property."""
        # Completed job
        completed_job = ExportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            file_format='csv',
            status='completed',
            user=self.admin_user
        )
        
        self.assertTrue(completed_job.is_completed)
        
        # Processing job
        processing_job = ExportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            file_format='csv',
            status='processing',
            user=self.admin_user
        )
        
        self.assertFalse(processing_job.is_completed)
    
    def test_export_job_is_running_property(self):
        """Test is_running property."""
        # Running job
        running_job = ExportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            file_format='csv',
            status='processing',
            user=self.admin_user
        )
        
        self.assertTrue(running_job.is_running)
        
        # Not running job
        pending_job = ExportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            file_format='csv',
            status='pending',
            user=self.admin_user
        )
        
        self.assertFalse(pending_job.is_running)
    
    def test_export_job_file_size_mb_property(self):
        """Test file_size_mb property."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(suffix='.csv') as temp_file:
            temp_file.write(b'a' * (2 * 1024 * 1024))  # 2MB
            temp_file.seek(0)
            
            # Create export job with file
            export_job = ExportJob.objects.create(
                tenant=self.active_tenant,
                model_type='clients',
                file_format='csv',
                status='completed',
                user=self.admin_user
            )
            
            # Manually set file and file_size for testing
            export_job.file.save('test.csv', temp_file)
            export_job.file_size = 2 * 1024 * 1024  # 2MB in bytes
            export_job.save()
            
            self.assertEqual(export_job.file_size_mb, 2.0)
    
    def test_export_job_download_url_property(self):
        """Test download_url property."""
        # Job with file
        with tempfile.NamedTemporaryFile(suffix='.csv') as temp_file:
            temp_file.write(b'test content')
            temp_file.seek(0)
            
            export_job = ExportJob.objects.create(
                tenant=self.active_tenant,
                model_type='clients',
                file_format='csv',
                status='completed',
                user=self.admin_user
            )
            
            export_job.file.save('test.csv', temp_file)
            
            self.assertIsNotNone(export_job.download_url)
            self.assertTrue(export_job.download_url.endswith('test.csv'))
        
        # Job without file
        export_job_no_file = ExportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            file_format='csv',
            status='pending',
            user=self.admin_user
        )
        
        self.assertIsNone(export_job_no_file.download_url)
    
    def test_export_job_start_processing_method(self):
        """Test start_processing method."""
        export_job = ExportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            file_format='csv',
            status='pending',
            user=self.admin_user
        )
        
        # Verify initial state
        self.assertEqual(export_job.status, 'pending')
        self.assertIsNone(export_job.started_at)
        
        # Start processing
        export_job.start_processing()
        
        # Verify updated state
        export_job.refresh_from_db()
        self.assertEqual(export_job.status, 'processing')
        self.assertIsNotNone(export_job.started_at)
    
    def test_export_job_complete_processing_method(self):
        """Test complete_processing method."""
        export_job = ExportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            file_format='csv',
            status='processing',
            user=self.admin_user
        )
        
        # Complete processing
        export_job.complete_processing()
        
        # Verify updated state
        export_job.refresh_from_db()
        self.assertEqual(export_job.status, 'completed')
        self.assertIsNotNone(export_job.completed_at)
    
    def test_export_job_fail_processing_method(self):
        """Test fail_processing method."""
        export_job = ExportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            file_format='csv',
            status='processing',
            user=self.admin_user
        )
        
        # Fail processing
        error_summary = "Export timeout"
        export_job.fail_processing(error_summary=error_summary)
        
        # Verify updated state
        export_job.refresh_from_db()
        self.assertEqual(export_job.status, 'failed')
        self.assertIsNotNone(export_job.completed_at)
        self.assertEqual(export_job.error_summary, error_summary)
    
    def test_export_job_cancel_processing_method(self):
        """Test cancel_processing method."""
        export_job = ExportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            file_format='csv',
            status='processing',
            user=self.admin_user
        )
        
        # Cancel processing
        export_job.cancel_processing()
        
        # Verify updated state
        export_job.refresh_from_db()
        self.assertEqual(export_job.status, 'cancelled')
        self.assertIsNotNone(export_job.completed_at)
    
    def test_export_job_add_error_method(self):
        """Test add_error method."""
        export_job = ExportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            file_format='csv',
            status='processing',
            user=self.admin_user
        )
        
        # Add error
        export_job.add_error("Memory limit exceeded")
        
        # Verify error was added
        export_job.refresh_from_db()
        self.assertEqual(len(export_job.errors), 1)
        self.assertEqual(export_job.errors[0]['error'], "Memory limit exceeded")
    
    def test_export_job_ordering(self):
        """Test export job ordering by created_at."""
        # Create jobs in random order
        job3 = ExportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            file_format='csv',
            status='pending',
            user=self.admin_user
        )
        
        job1 = ExportJob.objects.create(
            tenant=self.active_tenant,
            model_type='cases',
            file_format='csv',
            status='pending',
            user=self.admin_user
        )
        
        job2 = ExportJob.objects.create(
            tenant=self.active_tenant,
            model_type='documents',
            file_format='csv',
            status='pending',
            user=self.admin_user
        )
        
        # Verify ordering (newest first)
        jobs = list(ExportJob.objects.all())
        self.assertEqual(jobs[0], job3)  # Most recent
        self.assertEqual(jobs[1], job2)  # Middle
        self.assertEqual(jobs[2], job1)  # Oldest


class ImportTemplateModelTests(TenantTestCase):
    """Test ImportTemplate model."""
    
    def test_import_template_creation(self):
        """Test basic import template creation."""
        import_template = ImportTemplate.objects.create(
            tenant=self.active_tenant,
            name='Client Import Template',
            description='Template for importing client data',
            model_type='clients',
            field_mappings={
                'first_name': 'First Name',
                'last_name': 'Last Name',
                'email': 'Email Address',
                'phone': 'Phone Number'
            },
            required_fields=['first_name', 'last_name', 'email'],
            default_values={
                'status': 'active',
                'source': 'import'
            },
            validation_rules={
                'email': {
                    'type': 'email',
                    'required': True
                },
                'phone': {
                    'type': 'phone',
                    'required': False
                }
            },
            skip_header=True,
            encoding='utf-8',
            delimiter=',',
            update_existing=False,
            created_by=self.admin_user,
            is_public=False
        )
        
        self.assertEqual(import_template.tenant, self.active_tenant)
        self.assertEqual(import_template.name, 'Client Import Template')
        self.assertEqual(import_template.description, 'Template for importing client data')
        self.assertEqual(import_template.model_type, 'clients')
        self.assertEqual(import_template.field_mappings['first_name'], 'First Name')
        self.assertEqual(import_template.required_fields, ['first_name', 'last_name', 'email'])
        self.assertEqual(import_template.default_values['status'], 'active')
        self.assertEqual(import_template.validation_rules['email']['type'], 'email')
        self.assertTrue(import_template.skip_header)
        self.assertEqual(import_template.encoding, 'utf-8')
        self.assertEqual(import_template.delimiter, ',')
        self.assertFalse(import_template.update_existing)
        self.assertEqual(import_template.created_by, self.admin_user)
        self.assertFalse(import_template.is_public)
    
    def test_import_template_str_representation(self):
        """Test import template string representation."""
        import_template = ImportTemplate.objects.create(
            tenant=self.active_tenant,
            name='Client Template',
            model_type='clients',
            created_by=self.admin_user
        )
        
        expected = "Client Template (Clients)"
        self.assertEqual(str(import_template), expected)
    
    def test_import_template_get_field_mapping_dict(self):
        """Test get_field_mapping_dict method."""
        import_template = ImportTemplate.objects.create(
            tenant=self.active_tenant,
            name='Client Template',
            model_type='clients',
            field_mappings={
                'first_name': 'First Name',
                'last_name': 'Last Name'
            },
            created_by=self.admin_user
        )
        
        mappings = import_template.get_field_mapping_dict()
        self.assertEqual(mappings['first_name'], 'First Name')
        self.assertEqual(mappings['last_name'], 'Last Name')
    
    def test_import_template_get_required_fields_list(self):
        """Test get_required_fields_list method."""
        import_template = ImportTemplate.objects.create(
            tenant=self.active_tenant,
            name='Client Template',
            model_type='clients',
            required_fields=['first_name', 'last_name', 'email'],
            created_by=self.admin_user
        )
        
        required_fields = import_template.get_required_fields_list()
        self.assertEqual(required_fields, ['first_name', 'last_name', 'email'])
    
    def test_import_template_get_default_values_dict(self):
        """Test get_default_values_dict method."""
        import_template = ImportTemplate.objects.create(
            tenant=self.active_tenant,
            name='Client Template',
            model_type='clients',
            default_values={
                'status': 'active',
                'source': 'import'
            },
            created_by=self.admin_user
        )
        
        default_values = import_template.get_default_values_dict()
        self.assertEqual(default_values['status'], 'active')
        self.assertEqual(default_values['source'], 'import')
    
    def test_import_template_get_validation_rules_dict(self):
        """Test get_validation_rules_dict method."""
        import_template = ImportTemplate.objects.create(
            tenant=self.active_tenant,
            name='Client Template',
            model_type='clients',
            validation_rules={
                'email': {
                    'type': 'email',
                    'required': True
                }
            },
            created_by=self.admin_user
        )
        
        validation_rules = import_template.get_validation_rules_dict()
        self.assertEqual(validation_rules['email']['type'], 'email')
        self.assertTrue(validation_rules['email']['required'])
    
    def test_import_template_validate_record_valid(self):
        """Test validate_record method with valid record."""
        import_template = ImportTemplate.objects.create(
            tenant=self.active_tenant,
            name='Client Template',
            model_type='clients',
            required_fields=['first_name', 'email'],
            validation_rules={
                'email': {
                    'type': 'email',
                    'required': True
                },
                'first_name': {
                    'min_length': 2,
                    'max_length': 50
                }
            },
            created_by=self.admin_user
        )
        
        # Valid record
        record_data = {
            'first_name': 'John',
            'email': 'john@example.com'
        }
        
        is_valid, errors = import_template.validate_record(record_data)
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
    
    def test_import_template_validate_record_invalid(self):
        """Test validate_record method with invalid record."""
        import_template = ImportTemplate.objects.create(
            tenant=self.active_tenant,
            name='Client Template',
            model_type='clients',
            required_fields=['first_name', 'email'],
            validation_rules={
                'email': {
                    'type': 'email',
                    'required': True
                },
                'first_name': {
                    'min_length': 2,
                    'max_length': 50
                }
            },
            created_by=self.admin_user
        )
        
        # Invalid record (missing required field, invalid email, too short first name)
        record_data = {
            'first_name': 'J',  # Too short
            'email': 'invalid-email'  # Invalid format
        }
        
        is_valid, errors = import_template.validate_record(record_data)
        
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)
        self.assertTrue(any('first_name' in error for error in errors))
        self.assertTrue(any('email' in error for error in errors))
    
    def test_import_template_ordering(self):
        """Test import template ordering by model_type and name."""
        # Create templates in random order
        template3 = ImportTemplate.objects.create(
            tenant=self.active_tenant,
            name='Document Template',
            model_type='documents',
            created_by=self.admin_user
        )
        
        template1 = ImportTemplate.objects.create(
            tenant=self.active_tenant,
            name='Case Template',
            model_type='cases',
            created_by=self.admin_user
        )
        
        template2 = ImportTemplate.objects.create(
            tenant=self.active_tenant,
            name='Client Template',
            model_type='clients',
            created_by=self.admin_user
        )
        
        # Verify ordering (by model_type, then name)
        templates = list(ImportTemplate.objects.all())
        self.assertEqual(templates[0], template2)  # clients - Client Template
        self.assertEqual(templates[1], template1)  # cases - Case Template
        self.assertEqual(templates[2], template3)  # documents - Document Template


class ImportExportTenantIsolationTests(MultiTenantTestCase, TenantMixinTestMixin):
    """Test import/export isolation between tenants."""
    
    def test_import_jobs_isolated_by_tenant(self):
        """Test that import jobs are properly isolated by tenant."""
        # Create import jobs for different tenants
        job1 = ImportJob.objects.create(
            tenant=self.tenant1,
            model_type='clients',
            file_format='csv',
            status='pending',
            user=self.tenant1_admin
        )
        
        job2 = ImportJob.objects.create(
            tenant=self.tenant2,
            model_type='clients',
            file_format='csv',
            status='pending',
            user=self.tenant2_admin
        )
        
        # Test isolation
        self.assertTenantIsolation(
            ImportJob,
            self.tenant1,
            self.tenant2,
            {'model_type': 'clients'},
            {'model_type': 'clients'}
        )
    
    def test_export_jobs_isolated_by_tenant(self):
        """Test that export jobs are properly isolated by tenant."""
        # Create export jobs for different tenants
        job1 = ExportJob.objects.create(
            tenant=self.tenant1,
            model_type='clients',
            file_format='csv',
            status='pending',
            user=self.tenant1_admin
        )
        
        job2 = ExportJob.objects.create(
            tenant=self.tenant2,
            model_type='clients',
            file_format='csv',
            status='pending',
            user=self.tenant2_admin
        )
        
        # Test isolation
        self.assertTenantIsolation(
            ExportJob,
            self.tenant1,
            self.tenant2,
            {'model_type': 'clients'},
            {'model_type': 'clients'}
        )
    
    def test_import_templates_isolated_by_tenant(self):
        """Test that import templates are properly isolated by tenant."""
        # Create import templates for different tenants
        template1 = ImportTemplate.objects.create(
            tenant=self.tenant1,
            name='Client Template',
            model_type='clients',
            created_by=self.tenant1_admin
        )
        
        template2 = ImportTemplate.objects.create(
            tenant=self.tenant2,
            name='Client Template',
            model_type='clients',
            created_by=self.tenant2_admin
        )
        
        # Test isolation
        self.assertTenantIsolation(
            ImportTemplate,
            self.tenant1,
            self.tenant2,
            {'model_type': 'clients'},
            {'model_type': 'clients'}
        )


class ImportExportTransactionTests(TransactionTestCase):
    """Test import/export functionality with transactions."""
    
    def setUp(self):
        """Set up test data for transaction tests."""
        # Create a tenant
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            slug='test-tenant'
        )
        
        # Create a user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_import_job_creation_rollback_on_error(self):
        """Test import job creation rollback on error."""
        # Try to create an import job with invalid data
        with self.assertRaises(Exception):  # IntegrityError or ValidationError
            ImportJob.objects.create(
                tenant=self.tenant,
                model_type='',  # Invalid: empty model type
                file_format='csv',
                user=self.user
            )
        
        # Verify tenant and user still exist (transaction rolled back)
        self.assertTrue(Tenant.objects.filter(slug='test-tenant').exists())
        self.assertTrue(User.objects.filter(username='testuser').exists())
    
    def test_export_job_creation_rollback_on_error(self):
        """Test export job creation rollback on error."""
        # Try to create an export job with invalid data
        with self.assertRaises(Exception):  # IntegrityError or ValidationError
            ExportJob.objects.create(
                tenant=self.tenant,
                model_type='',  # Invalid: empty model type
                file_format='csv',
                user=self.user
            )
        
        # Verify tenant and user still exist (transaction rolled back)
        self.assertTrue(Tenant.objects.filter(slug='test-tenant').exists())
        self.assertTrue(User.objects.filter(username='testuser').exists())


class ImportExportIntegrationTests(TenantTestCase):
    """Test import/export integration with other modules."""
    
    def test_import_job_client_relationship(self):
        """Test import job-client relationship through model_type."""
        import_job = ImportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            file_format='csv',
            status='pending',
            user=self.admin_user
        )
        
        # Test relationship
        self.assertEqual(import_job.model_type, 'clients')
        self.assertTrue(ImportJob.objects.filter(model_type='clients').exists())
    
    def test_export_job_client_relationship(self):
        """Test export job-client relationship through model_type."""
        export_job = ExportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            file_format='csv',
            status='pending',
            user=self.admin_user
        )
        
        # Test relationship
        self.assertEqual(export_job.model_type, 'clients')
        self.assertTrue(ExportJob.objects.filter(model_type='clients').exists())
    
    def test_import_template_client_relationship(self):
        """Test import template-client relationship through model_type."""
        import_template = ImportTemplate.objects.create(
            tenant=self.active_tenant,
            name='Client Template',
            model_type='clients',
            created_by=self.admin_user
        )
        
        # Test relationship
        self.assertEqual(import_template.model_type, 'clients')
        self.assertTrue(ImportTemplate.objects.filter(model_type='clients').exists())
    
    def test_import_job_user_relationship(self):
        """Test import job-user relationship."""
        import_job = ImportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            file_format='csv',
            status='pending',
            user=self.admin_user
        )
        
        # Test relationship
        self.assertEqual(import_job.user, self.admin_user)
        self.assertTrue(ImportJob.objects.filter(user=self.admin_user).exists())
    
    def test_export_job_user_relationship(self):
        """Test export job-user relationship."""
        export_job = ExportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            file_format='csv',
            status='pending',
            user=self.admin_user
        )
        
        # Test relationship
        self.assertEqual(export_job.user, self.admin_user)
        self.assertTrue(ExportJob.objects.filter(user=self.admin_user).exists())
    
    def test_import_template_created_by_relationship(self):
        """Test import template-created_by relationship."""
        import_template = ImportTemplate.objects.create(
            tenant=self.active_tenant,
            name='Client Template',
            model_type='clients',
            created_by=self.admin_user
        )
        
        # Test relationship
        self.assertEqual(import_template.created_by, self.admin_user)
        self.assertTrue(ImportTemplate.objects.filter(created_by=self.admin_user).exists())


class ImportExportFileHandlingTests(TenantTestCase):
    """Test file handling in import/export functionality."""
    
    def test_csv_file_upload_parsing(self):
        """Test CSV file upload and parsing."""
        # Create CSV content
        csv_content = """First Name,Last Name,Email,Phone
John,Doe,john@example.com,555-1234
Jane,Smith,jane@example.com,555-5678"""
        
        # Create uploaded file
        csv_file = SimpleUploadedFile(
            "clients.csv",
            csv_content.encode('utf-8'),
            content_type="text/csv"
        )
        
        # Create import job
        import_job = ImportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            file_format='csv',
            file=csv_file,
            status='pending',
            user=self.admin_user
        )
        
        # Verify file was processed
        import_job.save()  # Trigger save method to set metadata
        self.assertEqual(import_job.original_filename, 'clients.csv')
        self.assertGreater(import_job.file_size, 0)
    
    def test_excel_file_upload_parsing(self):
        """Test Excel file upload and parsing."""
        # Create a simple Excel file (simulated)
        excel_content = b"simulated excel content"
        
        # Create uploaded file
        excel_file = SimpleUploadedFile(
            "clients.xlsx",
            excel_content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        # Create import job
        import_job = ImportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            file_format='xlsx',
            file=excel_file,
            status='pending',
            user=self.admin_user
        )
        
        # Verify file was processed
        import_job.save()  # Trigger save method to set metadata
        self.assertEqual(import_job.original_filename, 'clients.xlsx')
        self.assertGreater(import_job.file_size, 0)
    
    def test_json_file_export_generation(self):
        """Test JSON file export generation."""
        # Create some test clients
        client1 = Client.objects.create(
            tenant=self.active_tenant,
            first_name='John',
            last_name='Doe',
            email='john@example.com'
        )
        
        client2 = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Jane',
            last_name='Smith',
            email='jane@example.com'
        )
        
        # Create export job
        export_job = ExportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            file_format='json',
            status='processing',
            total_records=2,
            processed_records=2,
            user=self.admin_user
        )
        
        # Complete export with JSON file
        json_content = json.dumps([
            {
                'first_name': client1.first_name,
                'last_name': client1.last_name,
                'email': client1.email
            },
            {
                'first_name': client2.first_name,
                'last_name': client2.last_name,
                'email': client2.email
            }
        ], indent=2)
        
        json_file = SimpleUploadedFile(
            "clients.json",
            json_content.encode('utf-8'),
            content_type="application/json"
        )
        
        export_job.file = json_file
        export_job.complete_processing()
        
        # Verify export was completed
        export_job.refresh_from_db()
        self.assertEqual(export_job.status, 'completed')
        self.assertIsNotNone(export_job.file)
        self.assertGreater(export_job.file_size, 0)
    
    def test_csv_file_export_generation(self):
        """Test CSV file export generation."""
        # Create some test clients
        client1 = Client.objects.create(
            tenant=self.active_tenant,
            first_name='John',
            last_name='Doe',
            email='john@example.com'
        )
        
        client2 = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Jane',
            last_name='Smith',
            email='jane@example.com'
        )
        
        # Create export job
        export_job = ExportJob.objects.create(
            tenant=self.active_tenant,
            model_type='clients',
            file_format='csv',
            status='processing',
            total_records=2,
            processed_records=2,
            user=self.admin_user
        )
        
        # Complete export with CSV file
        csv_content = """First Name,Last Name,Email
John,Doe,john@example.com
Jane,Smith,jane@example.com
"""
        
        csv_file = SimpleUploadedFile(
            "clients.csv",
            csv_content.encode('utf-8'),
            content_type="text/csv"
        )
        
        export_job.file = csv_file
        export_job.complete_processing()
        
        # Verify export was completed
        export_job.refresh_from_db()
        self.assertEqual(export_job.status, 'completed')
        self.assertIsNotNone(export_job.file)
        self.assertGreater(export_job.file_size, 0)