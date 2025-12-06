"""
Tests for document module in multi-tenant context.
"""

import os
import tempfile
from django.test import TestCase, TransactionTestCase
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, models
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta

User = get_user_model()

from documents.models import Document
from cases.models import Case
from clients.models import Client
from tenants.models import Tenant
from tests.utils import TenantTestCase, MultiTenantTestCase, TenantMixinTestMixin, FileTestCase
from tests.fixtures import create_test_clients, create_test_cases


class DocumentModelTests(FileTestCase):
    """Test Document model."""
    
    def test_document_creation(self):
        """Test basic document creation."""
        # Create a test file
        test_file = SimpleUploadedFile(
            "test_document.pdf",
            b"file content",
            content_type="application/pdf"
        )
        
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        document = Document.objects.create(
            tenant=self.active_tenant,
            title='Test Document',
            description='Test document description',
            file=test_file,
            category='contract',
            access_level='internal',
            client=client,
            uploaded_by=self.admin_user
        )
        
        self.assertEqual(document.title, 'Test Document')
        self.assertEqual(document.description, 'Test document description')
        self.assertEqual(document.category, 'contract')
        self.assertEqual(document.access_level, 'internal')
        self.assertEqual(document.client, client)
        self.assertEqual(document.tenant, self.active_tenant)
        self.assertEqual(document.uploaded_by, self.admin_user)
        self.assertFalse(document.is_deleted)
        self.assertEqual(document.version, 1)
        self.assertTrue(document.is_latest_version)
    
    def test_document_str_representation(self):
        """Test document string representation."""
        test_file = SimpleUploadedFile(
            "test_document.pdf",
            b"file content",
            content_type="application/pdf"
        )
        
        document = Document.objects.create(
            tenant=self.active_tenant,
            title='Test Document',
            file=test_file,
            uploaded_by=self.admin_user
        )
        
        self.assertEqual(str(document), 'Test Document (test_document.pdf)')
    
    def test_document_category_choices(self):
        """Test document category choices."""
        test_file = SimpleUploadedFile(
            "test_document.pdf",
            b"file content",
            content_type="application/pdf"
        )
        
        # Test all valid category choices
        for category, _ in Document.CATEGORY_CHOICES:
            document = Document.objects.create(
                tenant=self.active_tenant,
                title=f'Document with {category} category',
                file=test_file,
                category=category,
                uploaded_by=self.admin_user
            )
            self.assertEqual(document.category, category)
    
    def test_document_type_choices(self):
        """Test document type choices."""
        # Test all valid document type choices
        for file_type, _ in Document.DOCUMENT_TYPE_CHOICES:
            test_file = SimpleUploadedFile(
                f"test_document.{file_type}",
                b"file content",
                content_type="application/octet-stream"
            )
            
            document = Document.objects.create(
                tenant=self.active_tenant,
                title=f'Document of type {file_type}',
                file=test_file,
                file_type=file_type,
                uploaded_by=self.admin_user
            )
            self.assertEqual(document.file_type, file_type)
    
    def test_document_access_level_choices(self):
        """Test document access level choices."""
        test_file = SimpleUploadedFile(
            "test_document.pdf",
            b"file content",
            content_type="application/pdf"
        )
        
        # Test all valid access level choices
        for access_level, _ in Document.ACCESS_LEVEL_CHOICES:
            document = Document.objects.create(
                tenant=self.active_tenant,
                title=f'Document with {access_level} access',
                file=test_file,
                access_level=access_level,
                uploaded_by=self.admin_user
            )
            self.assertEqual(document.access_level, access_level)
    
    def test_document_soft_delete(self):
        """Test document soft delete functionality."""
        test_file = SimpleUploadedFile(
            "test_document.pdf",
            b"file content",
            content_type="application/pdf"
        )
        
        document = Document.objects.create(
            tenant=self.active_tenant,
            title='To Delete',
            file=test_file,
            uploaded_by=self.admin_user
        )
        
        # Verify document exists
        self.assertTrue(Document.objects.filter(pk=document.pk).exists())
        
        # Soft delete document
        document.soft_delete()
        
        # Verify document is marked as deleted
        document.refresh_from_db()
        self.assertTrue(document.is_deleted)
        self.assertIsNotNone(document.deleted_at)
        
        # Verify document doesn't appear in default queries
        self.assertNotIn(document, list(Document.objects.get_queryset()))
        self.assertIn(document, list(Document.objects.all()))
    
    def test_document_restore(self):
        """Test document restore functionality."""
        test_file = SimpleUploadedFile(
            "test_document.pdf",
            b"file content",
            content_type="application/pdf"
        )
        
        document = Document.objects.create(
            tenant=self.active_tenant,
            title='To Restore',
            file=test_file,
            uploaded_by=self.admin_user
        )
        
        # Soft delete document first
        document.soft_delete()
        
        # Restore document
        document.restore()
        
        # Verify document is restored
        document.refresh_from_db()
        self.assertFalse(document.is_deleted)
        self.assertIsNone(document.deleted_at)
        
        # Verify document appears in default queries
        self.assertIn(document, list(Document.objects.get_queryset()))
    
    def test_document_file_properties(self):
        """Test document file-related properties."""
        test_file = SimpleUploadedFile(
            "test_document.pdf",
            b"file content",
            content_type="application/pdf"
        )
        
        document = Document.objects.create(
            tenant=self.active_tenant,
            title='Test Document',
            file=test_file,
            uploaded_by=self.admin_user
        )
        
        # Test file extension
        self.assertEqual(document.file_extension, '.pdf')
        
        # Test file size in MB
        self.assertGreater(document.file_size_mb, 0)
        self.assertLess(document.file_size_mb, 1)  # Should be less than 1MB
    
    def test_document_tags(self):
        """Test document tags functionality."""
        test_file = SimpleUploadedFile(
            "test_document.pdf",
            b"file content",
            content_type="application/pdf"
        )
        
        document = Document.objects.create(
            tenant=self.active_tenant,
            title='Test Document',
            file=test_file,
            tags='contract, legal, important',
            uploaded_by=self.admin_user
        )
        
        # Test tag list property
        tag_list = document.tag_list
        self.assertIn('contract', tag_list)
        self.assertIn('legal', tag_list)
        self.assertIn('important', tag_list)
        self.assertEqual(len(tag_list), 3)
    
    def test_document_versioning(self):
        """Test document versioning functionality."""
        test_file1 = SimpleUploadedFile(
            "test_document_v1.pdf",
            b"file content v1",
            content_type="application/pdf"
        )
        
        test_file2 = SimpleUploadedFile(
            "test_document_v2.pdf",
            b"file content v2",
            content_type="application/pdf"
        )
        
        # Create original document
        document_v1 = Document.objects.create(
            tenant=self.active_tenant,
            title='Test Document',
            file=test_file1,
            uploaded_by=self.admin_user
        )
        
        # Create new version
        document_v2 = document_v1.create_new_version(test_file2, self.admin_user)
        
        # Verify versioning
        self.assertEqual(document_v1.version, 1)
        self.assertEqual(document_v2.version, 2)
        self.assertFalse(document_v1.is_latest_version)
        self.assertTrue(document_v2.is_latest_version)
        self.assertEqual(document_v2.parent_document, document_v1)
    
    def test_document_upload_path(self):
        """Test document upload path generation."""
        test_file = SimpleUploadedFile(
            "test_document.pdf",
            b"file content",
            content_type="application/pdf"
        )
        
        document = Document.objects.create(
            tenant=self.active_tenant,
            title='Test Document',
            file=test_file,
            uploaded_by=self.admin_user
        )
        
        # Check that file path includes tenant slug
        file_path = document.file.path
        self.assertIn(self.active_tenant.slug, file_path)
        self.assertIn('documents', file_path)
        self.assertIn(str(timezone.now().year), file_path)
        self.assertIn(f"{timezone.now().month:02d}", file_path)
    
    def test_document_access_control(self):
        """Test document access control."""
        test_file = SimpleUploadedFile(
            "test_document.pdf",
            b"file content",
            content_type="application/pdf"
        )
        
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        case = Case.objects.create(
            tenant=self.active_tenant,
            title='Test Case',
            case_number='CASE-001',
            client=client
        )
        case.assigned_lawyers.add(self.lawyer_user)
        
        document = Document.objects.create(
            tenant=self.active_tenant,
            title='Restricted Document',
            file=test_file,
            access_level='restricted',
            case=case,
            uploaded_by=self.admin_user
        )
        
        # Test access control
        self.assertTrue(document.can_be_accessed_by(self.admin_user))  # Admin can access
        self.assertTrue(document.can_be_accessed_by(self.lawyer_user))  # Assigned lawyer can access
        self.assertFalse(document.can_be_accessed_by(self.paralegal_user))  # Paralegal cannot access
        
        # Test cross-tenant access
        other_tenant = self.create_tenant(name='Other Tenant')
        other_user = self.create_user_for_tenant(other_tenant, username='otheruser')
        self.assertFalse(document.can_be_accessed_by(other_user))  # Different tenant


class DocumentManagerTests(TenantTestCase):
    """Test DocumentManager methods."""
    
    def test_active_manager(self):
        """Test active manager returns only active documents."""
        test_file = SimpleUploadedFile(
            "test_document.pdf",
            b"file content",
            content_type="application/pdf"
        )
        
        active_document = Document.objects.create(
            tenant=self.active_tenant,
            title='Active Document',
            file=test_file,
            uploaded_by=self.admin_user
        )
        
        deleted_document = Document.objects.create(
            tenant=self.active_tenant,
            title='Deleted Document',
            file=test_file,
            uploaded_by=self.admin_user
        )
        deleted_document.soft_delete()
        
        # Get active documents
        active_documents = Document.objects.get_queryset()
        self.assertIn(active_document, active_documents)
        self.assertNotIn(deleted_document, active_documents)
    
    def test_all_with_deleted_manager(self):
        """Test all_with_deleted manager returns all documents."""
        test_file = SimpleUploadedFile(
            "test_document.pdf",
            b"file content",
            content_type="application/pdf"
        )
        
        active_document = Document.objects.create(
            tenant=self.active_tenant,
            title='Active Document',
            file=test_file,
            uploaded_by=self.admin_user
        )
        
        deleted_document = Document.objects.create(
            tenant=self.active_tenant,
            title='Deleted Document',
            file=test_file,
            uploaded_by=self.admin_user
        )
        deleted_document.soft_delete()
        
        # Get all documents
        all_documents = Document.objects.all()
        self.assertIn(active_document, all_documents)
        self.assertIn(deleted_document, all_documents)
    
    def test_by_category_manager(self):
        """Test by_category manager method."""
        test_file = SimpleUploadedFile(
            "test_document.pdf",
            b"file content",
            content_type="application/pdf"
        )
        
        contract_doc = Document.objects.create(
            tenant=self.active_tenant,
            title='Contract Document',
            file=test_file,
            category='contract',
            uploaded_by=self.admin_user
        )
        
        evidence_doc = Document.objects.create(
            tenant=self.active_tenant,
            title='Evidence Document',
            file=test_file,
            category='evidence',
            uploaded_by=self.admin_user
        )
        
        # Get contract documents
        contract_documents = Document.objects.filter(category='contract', tenant=self.active_tenant)
        self.assertIn(contract_doc, list(contract_documents))
        self.assertNotIn(evidence_doc, list(contract_documents))
        
        # Get evidence documents
        evidence_documents = Document.objects.filter(category='evidence', tenant=self.active_tenant)
        self.assertIn(evidence_doc, list(evidence_documents))
        self.assertNotIn(contract_doc, list(evidence_documents))
    
    def test_by_access_level_manager(self):
        """Test by_access_level manager method."""
        test_file = SimpleUploadedFile(
            "test_document.pdf",
            b"file content",
            content_type="application/pdf"
        )
        
        public_doc = Document.objects.create(
            tenant=self.active_tenant,
            title='Public Document',
            file=test_file,
            access_level='public',
            uploaded_by=self.admin_user
        )
        
        confidential_doc = Document.objects.create(
            tenant=self.active_tenant,
            title='Confidential Document',
            file=test_file,
            access_level='confidential',
            uploaded_by=self.admin_user
        )
        
        # Get public documents
        public_documents = Document.objects.filter(access_level='public', tenant=self.active_tenant)
        self.assertIn(public_doc, list(public_documents))
        self.assertNotIn(confidential_doc, list(public_documents))
        
        # Get confidential documents
        confidential_documents = Document.objects.filter(access_level='confidential', tenant=self.active_tenant)
        self.assertIn(confidential_doc, list(confidential_documents))
        self.assertNotIn(public_doc, list(confidential_documents))
    
    def test_by_case_manager(self):
        """Test by_case manager method."""
        test_file = SimpleUploadedFile(
            "test_document.pdf",
            b"file content",
            content_type="application/pdf"
        )
        
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        case1 = Case.objects.create(
            tenant=self.active_tenant,
            title='Case 1',
            case_number='CASE-001',
            client=client
        )
        
        case2 = Case.objects.create(
            tenant=self.active_tenant,
            title='Case 2',
            case_number='CASE-002',
            client=client
        )
        
        doc1 = Document.objects.create(
            tenant=self.active_tenant,
            title='Document for Case 1',
            file=test_file,
            case=case1,
            uploaded_by=self.admin_user
        )
        
        doc2 = Document.objects.create(
            tenant=self.active_tenant,
            title='Document for Case 2',
            file=test_file,
            case=case2,
            uploaded_by=self.admin_user
        )
        
        # Get documents for case1
        case1_documents = Document.objects.filter(case=case1, tenant=self.active_tenant)
        self.assertIn(doc1, list(case1_documents))
        self.assertNotIn(doc2, list(case1_documents))
        
        # Get documents for case2
        case2_documents = Document.objects.filter(case=case2, tenant=self.active_tenant)
        self.assertIn(doc2, list(case2_documents))
        self.assertNotIn(doc1, list(case2_documents))
    
    def test_by_client_manager(self):
        """Test by_client manager method."""
        test_file = SimpleUploadedFile(
            "test_document.pdf",
            b"file content",
            content_type="application/pdf"
        )
        
        client1 = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Client',
            last_name='One',
            email='client1@example.com'
        )
        
        client2 = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Client',
            last_name='Two',
            email='client2@example.com'
        )
        
        doc1 = Document.objects.create(
            tenant=self.active_tenant,
            title='Document for Client 1',
            file=test_file,
            client=client1,
            uploaded_by=self.admin_user
        )
        
        doc2 = Document.objects.create(
            tenant=self.active_tenant,
            title='Document for Client 2',
            file=test_file,
            client=client2,
            uploaded_by=self.admin_user
        )
        
        # Get documents for client1
        client1_documents = Document.objects.filter(client=client1, tenant=self.active_tenant)
        self.assertIn(doc1, list(client1_documents))
        self.assertNotIn(doc2, list(client1_documents))
        
        # Get documents for client2
        client2_documents = Document.objects.filter(client=client2, tenant=self.active_tenant)
        self.assertIn(doc2, list(client2_documents))
        self.assertNotIn(doc1, list(client2_documents))
    
    def test_latest_versions_manager(self):
        """Test latest_versions manager method."""
        test_file1 = SimpleUploadedFile(
            "test_document_v1.pdf",
            b"file content v1",
            content_type="application/pdf"
        )
        
        test_file2 = SimpleUploadedFile(
            "test_document_v2.pdf",
            b"file content v2",
            content_type="application/pdf"
        )
        
        # Create original document
        doc_v1 = Document.objects.create(
            tenant=self.active_tenant,
            title='Test Document',
            file=test_file1,
            uploaded_by=self.admin_user
        )
        
        # Create new version
        doc_v2 = doc_v1.create_new_version(test_file2, self.admin_user)
        
        # Get latest versions
        latest_docs = Document.objects.filter(is_latest_version=True, tenant=self.active_tenant)
        self.assertIn(doc_v2, list(latest_docs))
        self.assertNotIn(doc_v1, list(latest_docs))
    
    def test_search_manager(self):
        """Test search manager method."""
        test_file = SimpleUploadedFile(
            "test_document.pdf",
            b"file content",
            content_type="application/pdf"
        )
        
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='John',
            last_name='Doe',
            email='john@example.com'
        )
        
        case = Case.objects.create(
            tenant=self.active_tenant,
            title='Contract Dispute',
            case_number='CASE-001',
            client=client
        )
        
        doc1 = Document.objects.create(
            tenant=self.active_tenant,
            title='Contract Agreement',
            file=test_file,
            description='Contract agreement with vendor',
            tags='contract, legal',
            case=case,
            uploaded_by=self.admin_user
        )
        
        doc2 = Document.objects.create(
            tenant=self.active_tenant,
            title='Meeting Notes',
            file=test_file,
            description='Meeting notes with client',
            tags='meeting, notes',
            uploaded_by=self.admin_user
        )
        
        # Search by title
        results = Document.objects.filter(title__icontains='Contract', tenant=self.active_tenant)
        self.assertIn(doc1, list(results))
        self.assertNotIn(doc2, list(results))
        
        # Search by tags
        results = Document.objects.filter(tags__icontains='meeting', tenant=self.active_tenant)
        self.assertIn(doc2, list(results))
        self.assertNotIn(doc1, list(results))
        
        # Search by client name
        results = Document.objects.filter(
            models.Q(client__first_name__icontains='John') |
            models.Q(client__last_name__icontains='John'),
            tenant=self.active_tenant
        )
        self.assertIn(doc1, list(results))
        self.assertIn(doc2, list(results))


class DocumentTenantIsolationTests(MultiTenantTestCase, TenantMixinTestMixin):
    """Test document isolation between tenants."""
    
    def test_documents_isolated_by_tenant(self):
        """Test that documents are properly isolated by tenant."""
        test_file1 = SimpleUploadedFile(
            "test_document1.pdf",
            b"file content 1",
            content_type="application/pdf"
        )
        
        test_file2 = SimpleUploadedFile(
            "test_document2.pdf",
            b"file content 2",
            content_type="application/pdf"
        )
        
        # Create documents for different tenants
        doc1 = Document.objects.create(
            tenant=self.tenant1,
            title='Tenant 1 Document',
            file=test_file1,
            uploaded_by=self.tenant1_admin
        )
        
        doc2 = Document.objects.create(
            tenant=self.tenant2,
            title='Tenant 2 Document',
            file=test_file2,
            uploaded_by=self.tenant2_admin
        )
        
        # Test isolation
        self.assertTenantIsolation(
            Document,
            self.tenant1,
            self.tenant2,
            {'title': 'Tenant 1 Document'},
            {'title': 'Tenant 2 Document'}
        )
    
    def test_document_paths_isolated_by_tenant(self):
        """Test that document file paths are isolated by tenant."""
        test_file1 = SimpleUploadedFile(
            "test_document1.pdf",
            b"file content 1",
            content_type="application/pdf"
        )
        
        test_file2 = SimpleUploadedFile(
            "test_document2.pdf",
            b"file content 2",
            content_type="application/pdf"
        )
        
        # Create documents for different tenants
        doc1 = Document.objects.create(
            tenant=self.tenant1,
            title='Tenant 1 Document',
            file=test_file1,
            uploaded_by=self.tenant1_admin
        )
        
        doc2 = Document.objects.create(
            tenant=self.tenant2,
            title='Tenant 2 Document',
            file=test_file2,
            uploaded_by=self.tenant2_admin
        )
        
        # Check that file paths include tenant slugs
        path1 = doc1.file.path
        path2 = doc2.file.path
        
        self.assertIn(self.tenant1.slug, path1)
        self.assertIn(self.tenant2.slug, path2)
        self.assertNotIn(self.tenant1.slug, path2)
        self.assertNotIn(self.tenant2.slug, path1)


class DocumentTransactionTests(TransactionTestCase):
    """Test document functionality with transactions."""
    
    def test_document_creation_rollback_on_error(self):
        """Test document creation rollback on error."""
        # Create a tenant
        tenant = Tenant.objects.create(
            name='Test Tenant',
            slug='test-tenant'
        )
        
        # Create a user
        user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='testpass123',
            tenant=tenant
        )
        
        # Try to create a document with invalid data
        test_file = SimpleUploadedFile(
            "test_document.pdf",
            b"file content",
            content_type="application/pdf"
        )
        
        with self.assertRaises(IntegrityError):
            Document.objects.create(
                tenant=tenant,
                title='',  # Invalid: empty title
                file=test_file,
                uploaded_by=user
            )
        
        # Verify tenant and user still exist (transaction rolled back)
        self.assertTrue(Tenant.objects.filter(slug='test-tenant').exists())
        self.assertTrue(User.objects.filter(username='testuser').exists())
    
    def test_document_soft_delete_transaction(self):
        """Test document soft delete in transaction."""
        test_file = SimpleUploadedFile(
            "test_document.pdf",
            b"file content",
            content_type="application/pdf"
        )
        
        document = Document.objects.create(
            tenant=self.active_tenant,
            title='Test Document',
            file=test_file,
            uploaded_by=self.admin_user
        )
        
        # Soft delete in transaction
        with self.assertNumQueries(1):
            document.soft_delete()
        
        # Verify document is soft deleted
        document.refresh_from_db()
        self.assertTrue(document.is_deleted)
        self.assertIsNotNone(document.deleted_at)


class DocumentIntegrationTests(TenantTestCase):
    """Test document integration with other modules."""
    
    def test_document_case_relationship(self):
        """Test document-case relationship."""
        test_file = SimpleUploadedFile(
            "test_document.pdf",
            b"file content",
            content_type="application/pdf"
        )
        
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        case = Case.objects.create(
            tenant=self.active_tenant,
            title='Test Case',
            case_number='CASE-001',
            client=client
        )
        
        document = Document.objects.create(
            tenant=self.active_tenant,
            title='Test Document',
            file=test_file,
            case=case,
            uploaded_by=self.admin_user
        )
        
        # Test relationship
        self.assertEqual(document.case, case)
        self.assertTrue(Document.objects.filter(case=case).exists())
    
    def test_document_client_relationship(self):
        """Test document-client relationship."""
        test_file = SimpleUploadedFile(
            "test_document.pdf",
            b"file content",
            content_type="application/pdf"
        )
        
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        document = Document.objects.create(
            tenant=self.active_tenant,
            title='Test Document',
            file=test_file,
            client=client,
            uploaded_by=self.admin_user
        )
        
        # Test relationship
        self.assertEqual(document.client, client)
        self.assertTrue(Document.objects.filter(client=client).exists())


class DocumentPerformanceTests(TenantTestCase):
    """Test document performance with large datasets."""
    
    def test_large_dataset_query_performance(self):
        """Test query performance with large document dataset."""
        test_file = SimpleUploadedFile(
            "test_document.pdf",
            b"file content",
            content_type="application/pdf"
        )
        
        # Create many documents
        documents = []
        for i in range(100):
            document = Document.objects.create(
                tenant=self.active_tenant,
                title=f'Document {i}',
                file=test_file,
                uploaded_by=self.admin_user
            )
            documents.append(document)
        
        # Test query performance
        with self.assertNumQueries(1):
            results = list(Document.objects.filter(title__startswith='Document 1'))
        
        # Should find documents 1, 10, 11, etc.
        self.assertGreater(len(results), 10)
        self.assertLess(len(results), 20)  # Shouldn't find all 100
    
    def test_storage_usage_calculation(self):
        """Test storage usage calculation."""
        test_file = SimpleUploadedFile(
            "test_document.pdf",
            b"file content",
            content_type="application/pdf"
        )
        
        # Create documents of different sizes
        for i in range(10):
            Document.objects.create(
                tenant=self.active_tenant,
                title=f'Document {i}',
                file=test_file,
                file_size=1024 * 1024 * i,  # i MB in bytes
                uploaded_by=self.admin_user
            )
        
        # Test storage usage calculation
        total_usage = Document.objects.filter(tenant=self.active_tenant).aggregate(
            total_size=models.Sum('file_size')
        )['total_size'] or 0
        
        # Should be sum of all document sizes (0+1+2+...+9 MB = 45 MB)
        expected_usage = sum(range(10)) * 1024 * 1024
        self.assertEqual(total_usage, expected_usage)
    
    def test_large_documents_query(self):
        """Test query for large documents."""
        test_file = SimpleUploadedFile(
            "test_document.pdf",
            b"file content",
            content_type="application/pdf"
        )
        
        # Create documents of different sizes
        small_doc = Document.objects.create(
            tenant=self.active_tenant,
            title='Small Document',
            file=test_file,
            file_size=1024 * 1024,  # 1 MB
            uploaded_by=self.admin_user
        )
        
        large_doc = Document.objects.create(
            tenant=self.active_tenant,
            title='Large Document',
            file=test_file,
            file_size=20 * 1024 * 1024,  # 20 MB
            uploaded_by=self.admin_user
        )
        
        # Test large documents query
        large_documents = Document.objects.filter(file_size__gt=10*1024*1024, tenant=self.active_tenant)
        self.assertIn(large_doc, list(large_documents))
        self.assertNotIn(small_doc, list(large_documents))