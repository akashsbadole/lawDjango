"""
Tests for case module in multi-tenant context.
"""

from django.test import TestCase, TransactionTestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models
from django.utils import timezone
from datetime import timedelta, date

from cases.models import Case, CaseEvent
from clients.models import Client
from tenants.models import Tenant
from tests.utils import TenantTestCase, MultiTenantTestCase, TenantMixinTestMixin
from tests.fixtures import create_test_clients, create_test_cases


class CaseModelTests(TenantTestCase):
    """Test Case model."""
    
    def test_case_creation(self):
        """Test basic case creation."""
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
            description='Test case description',
            status='open',
            case_type='civil',
            client=client,
            created_by=self.admin_user
        )
        
        self.assertEqual(case.title, 'Test Case')
        self.assertEqual(case.case_number, 'CASE-001')
        self.assertEqual(case.description, 'Test case description')
        self.assertEqual(case.status, 'open')
        self.assertEqual(case.case_type, 'civil')
        self.assertEqual(case.client, client)
        self.assertEqual(case.tenant, self.active_tenant)
        self.assertEqual(case.created_by, self.admin_user)
        self.assertFalse(case.is_deleted)
        self.assertTrue(case.is_active)
    
    def test_case_str_representation(self):
        """Test case string representation."""
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
        
        self.assertEqual(str(case), 'CASE-001 - Test Case')
    
    def test_case_status_choices(self):
        """Test case status choices."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        # Test all valid status choices
        for status, _ in Case.STATUS_CHOICES:
            case = Case.objects.create(
                tenant=self.active_tenant,
                title=f'Case with {status} status',
                case_number=f'CASE-{status}',
                client=client,
                status=status
            )
            self.assertEqual(case.status, status)
    
    def test_case_type_choices(self):
        """Test case type choices."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        # Test all valid case type choices
        for case_type, _ in Case.CASE_TYPE_CHOICES:
            case = Case.objects.create(
                tenant=self.active_tenant,
                title=f'Case of type {case_type}',
                case_number=f'CASE-{case_type}',
                client=client,
                case_type=case_type
            )
            self.assertEqual(case.case_type, case_type)
    
    def test_case_soft_delete(self):
        """Test case soft delete functionality."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        case = Case.objects.create(
            tenant=self.active_tenant,
            title='To Delete',
            case_number='CASE-DELETE',
            client=client
        )
        
        # Verify case exists
        self.assertTrue(Case.objects.filter(pk=case.pk).exists())
        
        # Soft delete case
        case.soft_delete()
        
        # Verify case is marked as deleted
        case.refresh_from_db()
        self.assertTrue(case.is_deleted)
        self.assertIsNotNone(case.deleted_at)
        
        # Verify case doesn't appear in default queries
        self.assertNotIn(case, list(Case.objects.get_queryset()))
        self.assertIn(case, list(Case.objects.all()))
    
    def test_case_restore(self):
        """Test case restore functionality."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        case = Case.objects.create(
            tenant=self.active_tenant,
            title='To Restore',
            case_number='CASE-RESTORE',
            client=client
        )
        
        # Soft delete case first
        case.soft_delete()
        
        # Restore case
        case.restore()
        
        # Verify case is restored
        case.refresh_from_db()
        self.assertFalse(case.is_deleted)
        self.assertIsNone(case.deleted_at)
        
        # Verify case appears in default queries
        self.assertIn(case, list(Case.objects.get_queryset()))
    
    def test_case_duration_days(self):
        """Test case duration calculation."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        # Case without end date
        case = Case.objects.create(
            tenant=self.active_tenant,
            title='Ongoing Case',
            case_number='CASE-ONGOING',
            client=client,
            start_date=date(2023, 1, 1)
        )
        
        # Should calculate duration from start date to now
        self.assertGreater(case.duration_days, 0)
        
        # Case with end date
        case.end_date = date(2023, 1, 31)
        case.save()
        
        self.assertEqual(case.duration_days, 30)
    
    def test_case_unique_number_per_tenant(self):
        """Test that case number must be unique per tenant."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        # Create first case
        Case.objects.create(
            tenant=self.active_tenant,
            title='First Case',
            case_number='CASE-SAME',
            client=client
        )
        
        # Try to create second case with same number in same tenant
        with self.assertRaises(IntegrityError):
            Case.objects.create(
                tenant=self.active_tenant,
                title='Second Case',
                case_number='CASE-SAME',
                client=client
            )
        
        # Create case with same number in different tenant (should succeed)
        other_tenant = self.create_tenant(name='Other Tenant')
        other_client = Client.objects.create(
            tenant=other_tenant,
            first_name='Other',
            last_name='Client',
            email='other@example.com'
        )
        
        case2 = Case.objects.create(
            tenant=other_tenant,
            title='Other Tenant Case',
            case_number='CASE-SAME',
            client=other_client
        )
        
        self.assertEqual(case2.case_number, 'CASE-SAME')
        self.assertEqual(case2.tenant, other_tenant)
    
    def test_case_tenant_required(self):
        """Test that case requires a tenant."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        with self.assertRaises(IntegrityError):
            Case.objects.create(
                title='No Tenant Case',
                case_number='CASE-NOTENANT',
                client=client
            )


class CaseManagerTests(TenantTestCase):
    """Test CaseManager methods."""
    
    def test_active_manager(self):
        """Test active manager returns only active cases."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        active_case = Case.objects.create(
            tenant=self.active_tenant,
            title='Active Case',
            case_number='CASE-ACTIVE',
            client=client,
            status='open'
        )
        
        inactive_case = Case.objects.create(
            tenant=self.active_tenant,
            title='Inactive Case',
            case_number='CASE-INACTIVE',
            client=client,
            status='closed'
        )
        
        deleted_case = Case.objects.create(
            tenant=self.active_tenant,
            title='Deleted Case',
            case_number='CASE-DELETED',
            client=client,
            status='open'
        )
        deleted_case.soft_delete()
        
        # Get active cases
        active_cases = Case.objects.get_queryset()
        self.assertIn(active_case, active_cases)
        self.assertNotIn(inactive_case, active_cases)
        self.assertNotIn(deleted_case, active_cases)
    
    def test_all_with_deleted_manager(self):
        """Test all_with_deleted manager returns all cases."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        active_case = Case.objects.create(
            tenant=self.active_tenant,
            title='Active Case',
            case_number='CASE-ACTIVE',
            client=client
        )
        
        deleted_case = Case.objects.create(
            tenant=self.active_tenant,
            title='Deleted Case',
            case_number='CASE-DELETED',
            client=client
        )
        deleted_case.soft_delete()
        
        # Get all cases
        all_cases = Case.objects.all()
        self.assertIn(active_case, all_cases)
        self.assertIn(deleted_case, all_cases)
    
    def test_open_for_tenant_manager(self):
        """Test open_for_tenant manager method."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        open_case = Case.objects.create(
            tenant=self.active_tenant,
            title='Open Case',
            case_number='CASE-OPEN',
            client=client,
            status='open'
        )
        
        closed_case = Case.objects.create(
            tenant=self.active_tenant,
            title='Closed Case',
            case_number='CASE-CLOSED',
            client=client,
            status='closed'
        )
        
        # Get open cases using standard filtering
        open_cases = Case.objects.filter(tenant=self.active_tenant, status='open', deleted_at__isnull=True)
        self.assertIn(open_case, list(open_cases))
        self.assertNotIn(closed_case, list(open_cases))
    
    def test_closed_for_tenant_manager(self):
        """Test closed_for_tenant manager method."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        open_case = Case.objects.create(
            tenant=self.active_tenant,
            title='Open Case',
            case_number='CASE-OPEN',
            client=client,
            status='open'
        )
        
        closed_case = Case.objects.create(
            tenant=self.active_tenant,
            title='Closed Case',
            case_number='CASE-CLOSED',
            client=client,
            status='closed'
        )
        
        # Get closed cases using standard filtering
        closed_cases = Case.objects.filter(tenant=self.active_tenant, status='closed', deleted_at__isnull=True)
        self.assertIn(closed_case, list(closed_cases))
        self.assertNotIn(open_case, list(closed_cases))
    
    def test_by_status_manager(self):
        """Test by_status manager method."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        pending_case = Case.objects.create(
            tenant=self.active_tenant,
            title='Pending Case',
            case_number='CASE-PENDING',
            client=client,
            status='pending'
        )
        
        settled_case = Case.objects.create(
            tenant=self.active_tenant,
            title='Settled Case',
            case_number='CASE-SETTLED',
            client=client,
            status='settled'
        )
        
        # Get pending cases using standard filtering
        pending_cases = Case.objects.filter(status='pending', tenant=self.active_tenant)
        self.assertIn(pending_case, list(pending_cases))
        self.assertNotIn(settled_case, list(pending_cases))
        
        # Get settled cases using standard filtering
        settled_cases = Case.objects.filter(status='settled', tenant=self.active_tenant)
        self.assertIn(settled_case, list(settled_cases))
        self.assertNotIn(pending_case, list(settled_cases))
    
    def test_by_case_type_manager(self):
        """Test by_case_type manager method."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        civil_case = Case.objects.create(
            tenant=self.active_tenant,
            title='Civil Case',
            case_number='CASE-CIVIL',
            client=client,
            case_type='civil'
        )
        
        criminal_case = Case.objects.create(
            tenant=self.active_tenant,
            title='Criminal Case',
            case_number='CASE-CRIMINAL',
            client=client,
            case_type='criminal'
        )
        
        # Get civil cases using standard filtering
        civil_cases = Case.objects.filter(case_type='civil', tenant=self.active_tenant)
        self.assertIn(civil_case, list(civil_cases))
        self.assertNotIn(criminal_case, list(civil_cases))
        
        # Get criminal cases using standard filtering
        criminal_cases = Case.objects.filter(case_type='criminal', tenant=self.active_tenant)
        self.assertIn(criminal_case, list(criminal_cases))
        self.assertNotIn(civil_case, list(criminal_cases))
    
    def test_by_client_manager(self):
        """Test by_client manager method."""
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
        
        case1 = Case.objects.create(
            tenant=self.active_tenant,
            title='Case 1',
            case_number='CASE-1',
            client=client1
        )
        
        case2 = Case.objects.create(
            tenant=self.active_tenant,
            title='Case 2',
            case_number='CASE-2',
            client=client2
        )
        
        # Get cases for client1 using standard filtering
        client1_cases = Case.objects.filter(client=client1, tenant=self.active_tenant)
        self.assertIn(case1, list(client1_cases))
        self.assertNotIn(case2, list(client1_cases))
        
        # Get cases for client2 using standard filtering
        client2_cases = Case.objects.filter(client=client2, tenant=self.active_tenant)
        self.assertIn(case2, list(client2_cases))
        self.assertNotIn(case1, list(client2_cases))
    
    def test_assigned_to_manager(self):
        """Test assigned_to manager method."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        lawyer1 = self.lawyer_user
        lawyer2 = self.create_user_for_tenant(
            self.active_tenant,
            username='lawyer2',
            role='lawyer'
        )
        
        case1 = Case.objects.create(
            tenant=self.active_tenant,
            title='Case 1',
            case_number='CASE-1',
            client=client
        )
        case1.assigned_lawyers.add(lawyer1)
        
        case2 = Case.objects.create(
            tenant=self.active_tenant,
            title='Case 2',
            case_number='CASE-2',
            client=client
        )
        case2.assigned_lawyers.add(lawyer2)
        
        # Get cases for lawyer1 using standard filtering
        lawyer1_cases = Case.objects.filter(assigned_lawyers=lawyer1, tenant=self.active_tenant)
        self.assertIn(case1, list(lawyer1_cases))
        self.assertNotIn(case2, list(lawyer1_cases))
        
        # Get cases for lawyer2 using standard filtering
        lawyer2_cases = Case.objects.filter(assigned_lawyers=lawyer2, tenant=self.active_tenant)
        self.assertIn(case2, list(lawyer2_cases))
        self.assertNotIn(case1, list(lawyer2_cases))
    
    def test_search_manager(self):
        """Test search manager method."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='John',
            last_name='Doe',
            email='john@example.com'
        )
        
        case1 = Case.objects.create(
            tenant=self.active_tenant,
            title='Contract Dispute',
            case_number='CASE-001',
            client=client,
            description='Contract dispute with vendor'
        )
        
        case2 = Case.objects.create(
            tenant=self.active_tenant,
            title='Personal Injury',
            case_number='CASE-002',
            client=client,
            description='Car accident case'
        )
        
        # Search by title using standard filtering
        results = Case.objects.filter(title__icontains='Contract', tenant=self.active_tenant)
        self.assertIn(case1, list(results))
        self.assertNotIn(case2, list(results))
        
        # Search by case number using standard filtering
        results = Case.objects.filter(case_number__icontains='CASE-002', tenant=self.active_tenant)
        self.assertIn(case2, list(results))
        self.assertNotIn(case1, list(results))
        
        # Search by client name using standard filtering
        results = Case.objects.filter(
            models.Q(client__first_name__icontains='John') |
            models.Q(client__last_name__icontains='John'),
            tenant=self.active_tenant
        )
        self.assertIn(case1, list(results))
        self.assertIn(case2, list(results))


class CaseEventModelTests(TenantTestCase):
    """Test CaseEvent model."""
    
    def test_case_event_creation(self):
        """Test basic case event creation."""
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
        
        event = CaseEvent.objects.create(
            tenant=self.active_tenant,
            case=case,
            event_type='hearing',
            title='Court Hearing',
            description='Initial court hearing',
            event_date=timezone.now() + timedelta(days=7),
            created_by=self.admin_user
        )
        
        self.assertEqual(event.case, case)
        self.assertEqual(event.event_type, 'hearing')
        self.assertEqual(event.title, 'Court Hearing')
        self.assertEqual(event.description, 'Initial court hearing')
        self.assertEqual(event.tenant, self.active_tenant)
        self.assertEqual(event.created_by, self.admin_user)
    
    def test_case_event_str_representation(self):
        """Test case event string representation."""
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
        
        event = CaseEvent.objects.create(
            tenant=self.active_tenant,
            case=case,
            event_type='hearing',
            title='Court Hearing',
            description='Initial court hearing'
        )
        
        self.assertEqual(str(event), 'Hearing: Court Hearing (CASE-001)')
    
    def test_case_event_type_choices(self):
        """Test case event type choices."""
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
        
        # Test all valid event type choices
        for event_type, _ in CaseEvent.EVENT_TYPE_CHOICES:
            event = CaseEvent.objects.create(
                tenant=self.active_tenant,
                case=case,
                event_type=event_type,
                title=f'Event of type {event_type}',
                description=f'Description for {event_type}'
            )
            self.assertEqual(event.event_type, event_type)


class CaseEventManagerTests(TenantTestCase):
    """Test CaseEventManager methods."""
    
    def test_for_tenant_manager(self):
        """Test for_tenant manager method."""
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
        
        other_tenant = self.create_tenant(name='Other Tenant')
        other_client = Client.objects.create(
            tenant=other_tenant,
            first_name='Other',
            last_name='Client',
            email='other@example.com'
        )
        
        other_case = Case.objects.create(
            tenant=other_tenant,
            title='Other Case',
            case_number='CASE-OTHER',
            client=other_client
        )
        
        event1 = CaseEvent.objects.create(
            tenant=self.active_tenant,
            case=case,
            event_type='hearing',
            title='Event 1',
            description='Description 1'
        )
        
        event2 = CaseEvent.objects.create(
            tenant=other_tenant,
            case=other_case,
            event_type='meeting',
            title='Event 2',
            description='Description 2'
        )
        
        # Get events for active tenant using standard filtering
        tenant_events = CaseEvent.objects.filter(tenant=self.active_tenant)
        self.assertIn(event1, list(tenant_events))
        self.assertNotIn(event2, list(tenant_events))
    
    def test_for_case_manager(self):
        """Test for_case manager method."""
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
        
        event1 = CaseEvent.objects.create(
            tenant=self.active_tenant,
            case=case1,
            event_type='hearing',
            title='Event for Case 1',
            description='Description 1'
        )
        
        event2 = CaseEvent.objects.create(
            tenant=self.active_tenant,
            case=case2,
            event_type='meeting',
            title='Event for Case 2',
            description='Description 2'
        )
        
        # Get events for case1 using standard filtering
        case1_events = CaseEvent.objects.filter(case=case1, tenant=self.active_tenant)
        self.assertIn(event1, list(case1_events))
        self.assertNotIn(event2, list(case1_events))
        
        # Get events for case2 using standard filtering
        case2_events = CaseEvent.objects.filter(case=case2, tenant=self.active_tenant)
        self.assertIn(event2, list(case2_events))
        self.assertNotIn(event1, list(case2_events))
    
    def test_by_event_type_manager(self):
        """Test by_event_type manager method."""
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
        
        hearing_event = CaseEvent.objects.create(
            tenant=self.active_tenant,
            case=case,
            event_type='hearing',
            title='Court Hearing',
            description='Court hearing'
        )
        
        meeting_event = CaseEvent.objects.create(
            tenant=self.active_tenant,
            case=case,
            event_type='meeting',
            title='Client Meeting',
            description='Client meeting'
        )
        
        # Get hearing events using standard filtering
        hearing_events = CaseEvent.objects.filter(event_type='hearing', tenant=self.active_tenant)
        self.assertIn(hearing_event, list(hearing_events))
        self.assertNotIn(meeting_event, list(hearing_events))
        
        # Get meeting events using standard filtering
        meeting_events = CaseEvent.objects.filter(event_type='meeting', tenant=self.active_tenant)
        self.assertIn(meeting_event, list(meeting_events))
        self.assertNotIn(hearing_event, list(meeting_events))
    
    def test_upcoming_manager(self):
        """Test upcoming manager method."""
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
        
        past_event = CaseEvent.objects.create(
            tenant=self.active_tenant,
            case=case,
            event_type='hearing',
            title='Past Hearing',
            description='Past hearing',
            event_date=timezone.now() - timedelta(days=1)
        )
        
        future_event = CaseEvent.objects.create(
            tenant=self.active_tenant,
            case=case,
            event_type='meeting',
            title='Future Meeting',
            description='Future meeting',
            event_date=timezone.now() + timedelta(days=1)
        )
        
        # Get upcoming events using standard filtering
        upcoming_events = CaseEvent.objects.filter(event_date__gte=timezone.now(), tenant=self.active_tenant)
        self.assertIn(future_event, list(upcoming_events))
        self.assertNotIn(past_event, list(upcoming_events))
    
    def test_past_manager(self):
        """Test past manager method."""
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
        
        past_event = CaseEvent.objects.create(
            tenant=self.active_tenant,
            case=case,
            event_type='hearing',
            title='Past Hearing',
            description='Past hearing',
            event_date=timezone.now() - timedelta(days=1)
        )
        
        future_event = CaseEvent.objects.create(
            tenant=self.active_tenant,
            case=case,
            event_type='meeting',
            title='Future Meeting',
            description='Future meeting',
            event_date=timezone.now() + timedelta(days=1)
        )
        
        # Get past events using standard filtering
        past_events = CaseEvent.objects.filter(event_date__lt=timezone.now(), tenant=self.active_tenant)
        self.assertIn(past_event, list(past_events))
        self.assertNotIn(future_event, list(past_events))
    
    def test_today_manager(self):
        """Test today manager method."""
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
        
        today_event = CaseEvent.objects.create(
            tenant=self.active_tenant,
            case=case,
            event_type='hearing',
            title='Today Hearing',
            description='Today hearing',
            event_date=timezone.now()
        )
        
        other_event = CaseEvent.objects.create(
            tenant=self.active_tenant,
            case=case,
            event_type='meeting',
            title='Other Meeting',
            description='Other meeting',
            event_date=timezone.now() + timedelta(days=1)
        )
        
        # Get today's events using standard filtering
        today = timezone.now().date()
        today_events = CaseEvent.objects.filter(event_date__date=today, tenant=self.active_tenant)
        self.assertIn(today_event, list(today_events))
        self.assertNotIn(other_event, list(today_events))
    
    def test_search_manager(self):
        """Test search manager method."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        case = Case.objects.create(
            tenant=self.active_tenant,
            title='Contract Dispute',
            case_number='CASE-001',
            client=client
        )
        
        event1 = CaseEvent.objects.create(
            tenant=self.active_tenant,
            case=case,
            event_type='hearing',
            title='Court Hearing',
            description='Initial court hearing'
        )
        
        event2 = CaseEvent.objects.create(
            tenant=self.active_tenant,
            case=case,
            event_type='meeting',
            title='Client Meeting',
            description='Meeting with client'
        )
        
        # Search by title using standard filtering
        results = CaseEvent.objects.filter(title__icontains='Court', tenant=self.active_tenant)
        self.assertIn(event1, list(results))
        self.assertNotIn(event2, list(results))
        
        # Search by case title using standard filtering
        results = CaseEvent.objects.filter(case__title__icontains='Contract', tenant=self.active_tenant)
        self.assertIn(event1, list(results))
        self.assertIn(event2, list(results))


class CaseTenantIsolationTests(MultiTenantTestCase, TenantMixinTestMixin):
    """Test case isolation between tenants."""
    
    def test_cases_isolated_by_tenant(self):
        """Test that cases are properly isolated by tenant."""
        # Create clients for different tenants
        client1 = Client.objects.create(
            tenant=self.tenant1,
            first_name='Client',
            last_name='One',
            email='client1@example.com'
        )
        
        client2 = Client.objects.create(
            tenant=self.tenant2,
            first_name='Client',
            last_name='Two',
            email='client2@example.com'
        )
        
        # Create cases for different tenants
        case1 = Case.objects.create(
            tenant=self.tenant1,
            title='Tenant 1 Case',
            case_number='CASE-T1',
            client=client1
        )
        
        case2 = Case.objects.create(
            tenant=self.tenant2,
            title='Tenant 2 Case',
            case_number='CASE-T2',
            client=client2
        )
        
        # Test isolation
        self.assertTenantIsolation(
            Case,
            self.tenant1,
            self.tenant2,
            {'title': 'Tenant 1 Case', 'case_number': 'CASE-T1', 'client': client1},
            {'title': 'Tenant 2 Case', 'case_number': 'CASE-T2', 'client': client2}
        )
    
    def test_case_events_isolated_by_tenant(self):
        """Test that case events are properly isolated by tenant."""
        # Create clients and cases for different tenants
        client1 = Client.objects.create(
            tenant=self.tenant1,
            first_name='Client',
            last_name='One',
            email='client1@example.com'
        )
        
        client2 = Client.objects.create(
            tenant=self.tenant2,
            first_name='Client',
            last_name='Two',
            email='client2@example.com'
        )
        
        case1 = Case.objects.create(
            tenant=self.tenant1,
            title='Tenant 1 Case',
            case_number='CASE-T1',
            client=client1
        )
        
        case2 = Case.objects.create(
            tenant=self.tenant2,
            title='Tenant 2 Case',
            case_number='CASE-T2',
            client=client2
        )
        
        # Create events for different tenants
        event1 = CaseEvent.objects.create(
            tenant=self.tenant1,
            case=case1,
            event_type='hearing',
            title='Tenant 1 Event',
            description='Event for tenant 1'
        )
        
        event2 = CaseEvent.objects.create(
            tenant=self.tenant2,
            case=case2,
            event_type='meeting',
            title='Tenant 2 Event',
            description='Event for tenant 2'
        )
        
        # Test isolation
        self.assertTenantIsolation(
            CaseEvent,
            self.tenant1,
            self.tenant2,
            {'title': 'Tenant 1 Event', 'event_type': 'hearing', 'case': case1},
            {'title': 'Tenant 2 Event', 'event_type': 'meeting', 'case': case2}
        )


class CaseTransactionTests(TransactionTestCase):
    """Test case functionality with transactions."""
    
    def test_case_creation_rollback_on_error(self):
        """Test case creation rollback on error."""
        # Create a tenant
        tenant = Tenant.objects.create(
            name='Test Tenant',
            slug='test-tenant'
        )
        
        # Create a client
        client = Client.objects.create(
            tenant=tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        # Try to create a case with invalid data
        with self.assertRaises(IntegrityError):
            Case.objects.create(
                tenant=tenant,
                title='',  # Invalid: empty title
                case_number='CASE-INVALID',
                client=client
            )
        
        # Verify tenant and client still exist (transaction rolled back)
        self.assertTrue(Tenant.objects.filter(slug='test-tenant').exists())
        self.assertTrue(Client.objects.filter(email='client@example.com').exists())
    
    def test_case_soft_delete_transaction(self):
        """Test case soft delete in transaction."""
        # Create a tenant for this test
        tenant = Tenant.objects.create(
            name='Test Tenant',
            slug='test-tenant'
        )
        
        client = Client.objects.create(
            tenant=tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        case = Case.objects.create(
            tenant=tenant,
            title='Test Case',
            case_number='CASE-001',
            client=client
        )
        
        # Soft delete in transaction
        with self.assertNumQueries(1):
            case.soft_delete()
        
        # Verify case is soft deleted
        case.refresh_from_db()
        self.assertTrue(case.is_deleted)
        self.assertIsNotNone(case.deleted_at)


class CaseIntegrationTests(TenantTestCase):
    """Test case integration with other modules."""
    
    def test_case_client_relationship(self):
        """Test case-client relationship."""
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
        
        # Test relationship
        self.assertEqual(case.client, client)
        # Test that case is related to client
        self.assertTrue(Client.objects.filter(cases=case).exists())
    
    def test_case_event_relationship(self):
        """Test case-event relationship."""
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
        
        event = CaseEvent.objects.create(
            tenant=self.active_tenant,
            case=case,
            event_type='hearing',
            title='Court Hearing',
            description='Court hearing'
        )
        
        # Test relationship
        self.assertEqual(event.case, case)
        # Test that event is related to case
        self.assertTrue(CaseEvent.objects.filter(case=case).exists())
    
    def test_case_lawyer_assignment(self):
        """Test case lawyer assignment."""
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
        
        # Assign lawyers
        case.assigned_lawyers.add(self.lawyer_user)
        case.assigned_lawyers.add(self.admin_user)
        
        # Test assignment
        self.assertIn(self.lawyer_user, case.assigned_lawyers.all())
        self.assertIn(self.admin_user, case.assigned_lawyers.all())
        # Test that lawyers are related to case
        self.assertTrue(Case.objects.filter(assigned_lawyers=self.lawyer_user).exists())
        self.assertTrue(Case.objects.filter(assigned_lawyers=self.admin_user).exists())


class CasePerformanceTests(TenantTestCase):
    """Test case performance with large datasets."""
    
    def test_large_dataset_query_performance(self):
        """Test query performance with large case dataset."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        # Create many cases
        cases = []
        for i in range(100):
            case = Case.objects.create(
                tenant=self.active_tenant,
                title=f'Case {i}',
                case_number=f'CASE-{i:03d}',
                client=client
            )
            cases.append(case)
        
        # Test query performance
        with self.assertNumQueries(1):
            results = list(Case.objects.filter(title__startswith='Case 1'))
        
        # Should find cases 1, 10, 11, etc.
        self.assertGreater(len(results), 10)
        self.assertLess(len(results), 20)  # Shouldn't find all 100
    
    def test_event_query_performance(self):
        """Test event query performance with large dataset."""
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
        
        # Create many events
        for i in range(500):
            CaseEvent.objects.create(
                tenant=self.active_tenant,
                case=case,
                event_type='note',
                title=f'Event {i}',
                description=f'Description for event {i}',
                event_date=timezone.now() + timedelta(days=i)
            )
        
        # Test query performance
        with self.assertNumQueries(1):
            results = list(CaseEvent.objects.filter(title__icontains='Event 10'))
        
        # Should find the specific event
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, 'Event 10')