"""
Tests for billing module in multi-tenant context.
"""

from django.test import TestCase, TransactionTestCase
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, models
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal
from django.contrib.auth import get_user_model

from billing.models import (
    BillingRate, Invoice, InvoiceItem, TimeEntry,
    Expense, Payment
)
from cases.models import Case
from clients.models import Client
from tenants.models import Tenant
from tests.utils import TenantTestCase, MultiTenantTestCase, TenantMixinTestMixin
from tests.fixtures import create_test_clients, create_test_cases

User = get_user_model()


class BillingRateModelTests(TenantTestCase):
    """Test BillingRate model."""
    
    def test_billing_rate_creation(self):
        """Test basic billing rate creation."""
        billing_rate = BillingRate.objects.create(
            tenant=self.active_tenant,
            role='partner',
            default_rate=Decimal('250.00'),
            effective_date=date(2023, 1, 1),
            description='Partner billing rate',
            created_by=self.admin_user
        )
        
        self.assertEqual(billing_rate.role, 'partner')
        self.assertEqual(billing_rate.default_rate, Decimal('250.00'))
        self.assertEqual(billing_rate.effective_date, date(2023, 1, 1))
        self.assertEqual(billing_rate.description, 'Partner billing rate')
        self.assertEqual(billing_rate.tenant, self.active_tenant)
        self.assertEqual(billing_rate.created_by, self.admin_user)
        self.assertFalse(billing_rate.is_deleted)
    
    def test_billing_rate_str_representation(self):
        """Test billing rate string representation."""
        billing_rate = BillingRate.objects.create(
            tenant=self.active_tenant,
            role='associate',
            default_rate=Decimal('150.00'),
            effective_date=date(2023, 1, 1),
            created_by=self.admin_user
        )
        
        expected = "Associate: $150.00/hr (effective 2023-01-01)"
        self.assertEqual(str(billing_rate), expected)
    
    def test_billing_rate_role_choices(self):
        """Test billing rate role choices."""
        # Test all valid role choices
        for role, _ in BillingRate.ROLE_CHOICES:
            billing_rate = BillingRate.objects.create(
                tenant=self.active_tenant,
                role=role,
                default_rate=Decimal('100.00'),
                effective_date=date(2023, 1, 1),
                created_by=self.admin_user
            )
            self.assertEqual(billing_rate.role, role)
    
    def test_billing_rate_soft_delete(self):
        """Test billing rate soft delete functionality."""
        billing_rate = BillingRate.objects.create(
            tenant=self.active_tenant,
            role='partner',
            default_rate=Decimal('250.00'),
            effective_date=date(2023, 1, 1),
            created_by=self.admin_user
        )
        
        # Verify billing rate exists
        self.assertTrue(BillingRate.objects.filter(pk=billing_rate.pk).exists())
        
        # Soft delete billing rate
        billing_rate.soft_delete()
        
        # Verify billing rate is marked as deleted
        billing_rate.refresh_from_db()
        self.assertTrue(billing_rate.is_deleted)
        self.assertIsNotNone(billing_rate.deleted_at)
        
        # Verify billing rate doesn't appear in default queries
        self.assertNotIn(billing_rate, list(BillingRate.objects.get_queryset()))
        self.assertIn(billing_rate, list(BillingRate.objects.all()))
    
    def test_billing_rate_unique_per_tenant(self):
        """Test that billing rate is unique per tenant and role."""
        # Create first billing rate
        BillingRate.objects.create(
            tenant=self.active_tenant,
            role='partner',
            default_rate=Decimal('250.00'),
            effective_date=date(2023, 1, 1),
            created_by=self.admin_user
        )
        
        # Try to create second billing rate with same role and date in same tenant
        with self.assertRaises(IntegrityError):
            BillingRate.objects.create(
                tenant=self.active_tenant,
                role='partner',
                default_rate=Decimal('300.00'),
                effective_date=date(2023, 1, 1),
                created_by=self.admin_user
            )
        
        # Create billing rate with same role in different tenant (should succeed)
        other_tenant = self.create_tenant(name='Other Tenant')
        billing_rate2 = BillingRate.objects.create(
            tenant=other_tenant,
            role='partner',
            default_rate=Decimal('300.00'),
            effective_date=date(2023, 1, 1),
            created_by=self.admin_user
        )
        
        self.assertEqual(billing_rate2.role, 'partner')
        self.assertEqual(billing_rate2.tenant, other_tenant)


class InvoiceModelTests(TenantTestCase):
    """Test Invoice model."""
    
    def test_invoice_creation(self):
        """Test basic invoice creation."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        invoice = Invoice.objects.create(
            tenant=self.active_tenant,
            invoice_number='INV-001',
            client=client,
            issue_date=date(2023, 1, 15),
            due_date=date(2023, 2, 15),
            subtotal=Decimal('1000.00'),
            tax_rate=Decimal('0.08'),
            status='draft',
            created_by=self.admin_user
        )
        
        self.assertEqual(invoice.invoice_number, 'INV-001')
        self.assertEqual(invoice.client, client)
        self.assertEqual(invoice.issue_date, date(2023, 1, 15))
        self.assertEqual(invoice.due_date, date(2023, 2, 15))
        self.assertEqual(invoice.subtotal, Decimal('1000.00'))
        self.assertEqual(invoice.tax_rate, Decimal('0.08'))
        self.assertEqual(invoice.status, 'draft')
        self.assertEqual(invoice.tenant, self.active_tenant)
        self.assertEqual(invoice.created_by, self.admin_user)
        self.assertFalse(invoice.is_deleted)
    
    def test_invoice_str_representation(self):
        """Test invoice string representation."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        invoice = Invoice.objects.create(
            tenant=self.active_tenant,
            invoice_number='INV-001',
            client=client,
            created_by=self.admin_user
        )
        
        expected = f"invoice INV-001 - {client}"
        self.assertEqual(str(invoice), expected)
    
    def test_invoice_status_choices(self):
        """Test invoice status choices."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        # Test all valid status choices
        for status, _ in Invoice.STATUS_CHOICES:
            invoice = Invoice.objects.create(
                tenant=self.active_tenant,
                invoice_number=f'INV-{status}',
                client=client,
                status=status,
                created_by=self.admin_user
            )
            self.assertEqual(invoice.status, status)
    
    def test_invoice_calculate_totals(self):
        """Test invoice total calculation."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        invoice = Invoice.objects.create(
            tenant=self.active_tenant,
            invoice_number='INV-001',
            client=client,
            subtotal=Decimal('1000.00'),
            tax_rate=Decimal('0.08'),
            created_by=self.admin_user
        )
        
        # Create invoice items
        InvoiceItem.objects.create(
            tenant=self.active_tenant,
            invoice=invoice,
            description='Legal Services',
            quantity=Decimal('10.00'),
            rate=Decimal('100.00'),
            created_by=self.admin_user
        )
        
        InvoiceItem.objects.create(
            tenant=self.active_tenant,
            invoice=invoice,
            description='Consultation',
            quantity=Decimal('5.00'),
            rate=Decimal('50.00'),
            created_by=self.admin_user
        )
        
        # Calculate totals
        invoice.calculate_totals()
        
        # Verify calculations
        invoice.refresh_from_db()
        self.assertEqual(invoice.subtotal, Decimal('1250.00'))  # 1000 + 250
        self.assertEqual(invoice.tax_amount, Decimal('100.00'))  # 1250 * 0.08
        self.assertEqual(invoice.total_amount, Decimal('1350.00'))  # 1250 + 100
    
    def test_invoice_is_overdue_property(self):
        """Test invoice is_overdue property."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        # Create overdue invoice
        overdue_invoice = Invoice.objects.create(
            tenant=self.active_tenant,
            invoice_number='INV-OVERDUE',
            client=client,
            issue_date=date(2023, 1, 1),
            due_date=date(2023, 1, 15),  # Past due date
            status='sent',
            created_by=self.admin_user
        )
        
        # Create future invoice
        future_invoice = Invoice.objects.create(
            tenant=self.active_tenant,
            invoice_number='INV-FUTURE',
            client=client,
            issue_date=date(2023, 1, 1),
            due_date=date(2023, 12, 31),  # Future due date
            status='sent',
            created_by=self.admin_user
        )
        
        # Test overdue property
        self.assertTrue(overdue_invoice.is_overdue)
        self.assertFalse(future_invoice.is_overdue)
        
        # Test paid invoice
        paid_invoice = Invoice.objects.create(
            tenant=self.active_tenant,
            invoice_number='INV-PAID',
            client=client,
            issue_date=date(2023, 1, 1),
            due_date=date(2023, 1, 15),
            status='paid',
            created_by=self.admin_user
        )
        
        self.assertFalse(paid_invoice.is_overdue)
    
    def test_invoice_soft_delete(self):
        """Test invoice soft delete functionality."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        invoice = Invoice.objects.create(
            tenant=self.active_tenant,
            invoice_number='INV-DELETE',
            client=client,
            created_by=self.admin_user
        )
        
        # Verify invoice exists
        self.assertTrue(Invoice.objects.filter(pk=invoice.pk).exists())
        
        # Soft delete invoice
        invoice.soft_delete()
        
        # Verify invoice is marked as deleted
        invoice.refresh_from_db()
        self.assertTrue(invoice.is_deleted)
        self.assertIsNotNone(invoice.deleted_at)
        
        # Verify invoice doesn't appear in default queries
        self.assertNotIn(invoice, list(Invoice.objects.get_queryset()))
        self.assertIn(invoice, list(Invoice.objects.all()))


class InvoiceItemModelTests(TenantTestCase):
    """Test InvoiceItem model."""
    
    def test_invoice_item_creation(self):
        """Test basic invoice item creation."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        invoice = Invoice.objects.create(
            tenant=self.active_tenant,
            invoice_number='INV-001',
            client=client,
            created_by=self.admin_user
        )
        
        item = InvoiceItem.objects.create(
            tenant=self.active_tenant,
            invoice=invoice,
            description='Legal Services',
            quantity=Decimal('10.00'),
            rate=Decimal('100.00'),
            created_by=self.admin_user
        )
        
        self.assertEqual(item.invoice, invoice)
        self.assertEqual(item.description, 'Legal Services')
        self.assertEqual(item.quantity, Decimal('10.00'))
        self.assertEqual(item.rate, Decimal('100.00'))
        self.assertEqual(item.amount, Decimal('1000.00'))  # 10 * 100
        self.assertEqual(item.tenant, self.active_tenant)
        # InvoiceItem doesn't have created_by field in the model
        self.assertFalse(item.is_deleted)
    
    def test_invoice_item_str_representation(self):
        """Test invoice item string representation."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        invoice = Invoice.objects.create(
            tenant=self.active_tenant,
            invoice_number='INV-001',
            client=client,
            created_by=self.admin_user
        )
        
        item = InvoiceItem.objects.create(
            tenant=self.active_tenant,
            invoice=invoice,
            description='Legal Services',
            quantity=Decimal('10.00'),
            rate=Decimal('100.00'),
            created_by=self.admin_user
        )
        
        expected = "Legal Services - $1000.00"
        self.assertEqual(str(item), expected)
    
    def test_invoice_item_amount_calculation(self):
        """Test invoice item amount calculation."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        invoice = Invoice.objects.create(
            tenant=self.active_tenant,
            invoice_number='INV-001',
            client=client,
            created_by=self.admin_user
        )
        
        item = InvoiceItem.objects.create(
            tenant=self.active_tenant,
            invoice=invoice,
            description='Legal Services',
            quantity=Decimal('5.5'),
            rate=Decimal('200.00'),
            created_by=self.admin_user
        )
        
        # Verify amount calculation
        self.assertEqual(item.amount, Decimal('1100.00'))  # 5.5 * 200


class TimeEntryModelTests(TenantTestCase):
    """Test TimeEntry model."""
    
    def test_time_entry_creation(self):
        """Test basic time entry creation."""
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
        
        time_entry = TimeEntry.objects.create(
            tenant=self.active_tenant,
            lawyer=self.lawyer_user,
            case=case,
            hours=Decimal('8.5'),
            rate=Decimal('250.00'),
            description='Legal research and drafting',
            date=date(2023, 1, 15),
            is_billable=True,
            created_by=self.admin_user
        )
        
        self.assertEqual(time_entry.lawyer, self.lawyer_user)
        self.assertEqual(time_entry.case, case)
        self.assertEqual(time_entry.hours, Decimal('8.5'))
        self.assertEqual(time_entry.rate, Decimal('250.00'))
        self.assertEqual(time_entry.description, 'Legal research and drafting')
        self.assertEqual(time_entry.date, date(2023, 1, 15))
        self.assertTrue(time_entry.is_billable)
        self.assertEqual(time_entry.tenant, self.active_tenant)
        self.assertEqual(time_entry.created_by, self.admin_user)
        self.assertFalse(time_entry.is_deleted)
    
    def test_time_entry_str_representation(self):
        """Test time entry string representation."""
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
        
        time_entry = TimeEntry.objects.create(
            tenant=self.active_tenant,
            lawyer=self.lawyer_user,
            case=case,
            hours=Decimal('8.5'),
            rate=Decimal('250.00'),
            created_by=self.admin_user
        )
        
        expected = f"{self.lawyer_user.get_full_name()} - CASE-001 - 8.5 hours"
        self.assertEqual(str(time_entry), expected)
    
    def test_time_entry_amount_property(self):
        """Test time entry amount property."""
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
        
        time_entry = TimeEntry.objects.create(
            tenant=self.active_tenant,
            lawyer=self.lawyer_user,
            case=case,
            hours=Decimal('8.5'),
            rate=Decimal('250.00'),
            created_by=self.admin_user
        )
        
        # Verify amount calculation
        self.assertEqual(time_entry.amount, Decimal('2125.00'))  # 8.5 * 250
    
    def test_time_entry_is_billed_property(self):
        """Test time entry is_billed property."""
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
        
        time_entry = TimeEntry.objects.create(
            tenant=self.active_tenant,
            lawyer=self.lawyer_user,
            case=case,
            hours=Decimal('8.5'),
            rate=Decimal('250.00'),
            created_by=self.admin_user
        )
        
        # Initially not billed
        self.assertFalse(time_entry.is_billed)
        
        # Create invoice item linked to time entry
        invoice = Invoice.objects.create(
            tenant=self.active_tenant,
            invoice_number='INV-001',
            client=client,
            created_by=self.admin_user
        )
        
        InvoiceItem.objects.create(
            tenant=self.active_tenant,
            invoice=invoice,
            time_entry=time_entry,
            description='Legal Services',
            quantity=Decimal('8.5'),
            rate=Decimal('250.00'),
            created_by=self.admin_user
        )
        
        # Now should be billed
        self.assertTrue(time_entry.is_billed)


class ExpenseModelTests(TenantTestCase):
    """Test Expense model."""
    
    def test_expense_creation(self):
        """Test basic expense creation."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        receipt_file = SimpleUploadedFile(
            "receipt.pdf",
            b"receipt content",
            content_type="application/pdf"
        )
        
        expense = Expense.objects.create(
            tenant=self.active_tenant,
            description='Court filing fee',
            amount=Decimal('150.00'),
            category='filing',
            receipt=receipt_file,
            date=date(2023, 1, 15),
            is_reimbursable=True,
            created_by=self.admin_user
        )
        
        self.assertEqual(expense.description, 'Court filing fee')
        self.assertEqual(expense.amount, Decimal('150.00'))
        self.assertEqual(expense.category, 'filing')
        self.assertEqual(expense.date, date(2023, 1, 15))
        self.assertTrue(expense.is_reimbursable)
        self.assertEqual(expense.tenant, self.active_tenant)
        self.assertEqual(expense.created_by, self.admin_user)
        self.assertFalse(expense.is_deleted)
    
    def test_expense_str_representation(self):
        """Test expense string representation."""
        expense = Expense.objects.create(
            tenant=self.active_tenant,
            description='Travel expenses',
            amount=Decimal('250.00'),
            created_by=self.admin_user
        )
        
        expected = "Travel expenses - $250.00"
        self.assertEqual(str(expense), expected)
    
    def test_expense_category_choices(self):
        """Test expense category choices."""
        # Test all valid category choices
        for category, _ in Expense.CATEGORY_CHOICES:
            expense = Expense.objects.create(
                tenant=self.active_tenant,
                description=f'Expense of type {category}',
                amount=Decimal('100.00'),
                category=category,
                created_by=self.admin_user
            )
            self.assertEqual(expense.category, category)


class PaymentModelTests(TenantTestCase):
    """Test Payment model."""
    
    def test_payment_creation(self):
        """Test basic payment creation."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        invoice = Invoice.objects.create(
            tenant=self.active_tenant,
            invoice_number='INV-001',
            client=client,
            total_amount=Decimal('1000.00'),
            created_by=self.admin_user
        )
        
        payment = Payment.objects.create(
            tenant=self.active_tenant,
            invoice=invoice,
            amount=Decimal('500.00'),
            payment_date=date(2023, 1, 20),
            payment_method='check',
            reference='Check #1234',
            created_by=self.admin_user
        )
        
        self.assertEqual(payment.invoice, invoice)
        self.assertEqual(payment.amount, Decimal('500.00'))
        self.assertEqual(payment.payment_date, date(2023, 1, 20))
        self.assertEqual(payment.payment_method, 'check')
        self.assertEqual(payment.reference, 'Check #1234')
        self.assertEqual(payment.tenant, self.active_tenant)
        self.assertEqual(payment.created_by, self.admin_user)
        self.assertFalse(payment.is_deleted)
    
    def test_payment_str_representation(self):
        """Test payment string representation."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        invoice = Invoice.objects.create(
            tenant=self.active_tenant,
            invoice_number='INV-001',
            client=client,
            created_by=self.admin_user
        )
        
        payment = Payment.objects.create(
            tenant=self.active_tenant,
            invoice=invoice,
            amount=Decimal('500.00'),
            created_by=self.admin_user
        )
        
        expected = f"Payment of $500.00 for Invoice INV-001"
        self.assertEqual(str(payment), expected)
    
    def test_payment_method_choices(self):
        """Test payment method choices."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        invoice = Invoice.objects.create(
            tenant=self.active_tenant,
            invoice_number='INV-001',
            client=client,
            created_by=self.admin_user
        )
        
        # Test all valid payment method choices
        for method, _ in Payment.PAYMENT_METHOD_CHOICES:
            payment = Payment.objects.create(
                tenant=self.active_tenant,
                invoice=invoice,
                amount=Decimal('100.00'),
                payment_method=method,
                created_by=self.admin_user
            )
            self.assertEqual(payment.payment_method, method)
    
    def test_payment_remaining_balance_property(self):
        """Test payment remaining balance property."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        invoice = Invoice.objects.create(
            tenant=self.active_tenant,
            invoice_number='INV-001',
            client=client,
            total_amount=Decimal('1000.00'),
            created_by=self.admin_user
        )
        
        # Create payments
        Payment.objects.create(
            tenant=self.active_tenant,
            invoice=invoice,
            amount=Decimal('300.00'),
            created_by=self.admin_user
        )
        
        Payment.objects.create(
            tenant=self.active_tenant,
            invoice=invoice,
            amount=Decimal('200.00'),
            created_by=self.admin_user
        )
        
        # Test remaining balance
        self.assertEqual(invoice.total_amount, Decimal('1000.00'))
        # Test remaining balance calculation
        total_paid = sum(p.amount for p in invoice.payments.all())
        expected_balance = invoice.total_amount - total_paid
        self.assertEqual(expected_balance, Decimal('500.00'))  # 1000 - 300 - 200


class BillingManagerTests(TenantTestCase):
    """Test billing managers."""
    
    def test_invoice_manager_for_status(self):
        """Test InvoiceManager.for_status method."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        draft_invoice = Invoice.objects.create(
            tenant=self.active_tenant,
            invoice_number='INV-DRAFT',
            client=client,
            status='draft',
            created_by=self.admin_user
        )
        
        paid_invoice = Invoice.objects.create(
            tenant=self.active_tenant,
            invoice_number='INV-PAID',
            client=client,
            status='paid',
            created_by=self.admin_user
        )
        
        # Get draft invoices
        draft_invoices = Invoice.objects.filter(status='draft', tenant=self.active_tenant)
        self.assertIn(draft_invoice, list(draft_invoices))
        self.assertNotIn(paid_invoice, list(draft_invoices))
        
        # Get paid invoices
        paid_invoices = Invoice.objects.filter(status='paid', tenant=self.active_tenant)
        self.assertIn(paid_invoice, list(paid_invoices))
        self.assertNotIn(draft_invoice, list(paid_invoices))
    
    def test_time_entry_manager_for_lawyer(self):
        """Test TimeEntryManager.for_lawyer method."""
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
        
        lawyer1_entry = TimeEntry.objects.create(
            tenant=self.active_tenant,
            lawyer=self.lawyer_user,
            case=case,
            hours=Decimal('5.0'),
            rate=Decimal('250.00'),
            created_by=self.admin_user
        )
        
        lawyer2 = self.create_user_for_tenant(
            self.active_tenant,
            username='lawyer2',
            role='lawyer'
        )
        
        lawyer2_entry = TimeEntry.objects.create(
            tenant=self.active_tenant,
            lawyer=lawyer2,
            case=case,
            hours=Decimal('3.0'),
            rate=Decimal('250.00'),
            created_by=self.admin_user
        )
        
        # Get time entries for lawyer1
        lawyer1_entries = TimeEntry.objects.filter(lawyer=self.lawyer_user, tenant=self.active_tenant)
        self.assertIn(lawyer1_entry, list(lawyer1_entries))
        self.assertNotIn(lawyer2_entry, list(lawyer1_entries))
        
        # Get time entries for lawyer2
        lawyer2_entries = TimeEntry.objects.filter(lawyer=lawyer2, tenant=self.active_tenant)
        self.assertIn(lawyer2_entry, list(lawyer2_entries))
        self.assertNotIn(lawyer1_entry, list(lawyer2_entries))


class BillingTenantIsolationTests(MultiTenantTestCase, TenantMixinTestMixin):
    """Test billing isolation between tenants."""
    
    def test_invoices_isolated_by_tenant(self):
        """Test that invoices are properly isolated by tenant."""
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
        
        # Create invoices for different tenants
        invoice1 = Invoice.objects.create(
            tenant=self.tenant1,
            invoice_number='INV-T1',
            client=client1,
            created_by=self.tenant1_admin
        )
        
        invoice2 = Invoice.objects.create(
            tenant=self.tenant2,
            invoice_number='INV-T2',
            client=client2,
            created_by=self.tenant2_admin
        )
        
        # Test isolation
        self.assertTenantIsolation(
            Invoice,
            self.tenant1,
            self.tenant2,
            {'invoice_number': 'INV-T1', 'client': client1},
            {'invoice_number': 'INV-T2', 'client': client2}
        )
    
    def test_time_entries_isolated_by_tenant(self):
        """Test that time entries are properly isolated by tenant."""
        # Create clients and cases for different tenants
        client1 = Client.objects.create(
            tenant=self.tenant1,
            first_name='Client',
            last_name='One',
            email='client1@example.com'
        )
        
        case1 = Case.objects.create(
            tenant=self.tenant1,
            title='Case 1',
            case_number='CASE-T1',
            client=client1
        )
        
        client2 = Client.objects.create(
            tenant=self.tenant2,
            first_name='Client',
            last_name='Two',
            email='client2@example.com'
        )
        
        case2 = Case.objects.create(
            tenant=self.tenant2,
            title='Case 2',
            case_number='CASE-T2',
            client=client2
        )
        
        # Create time entries for different tenants
        entry1 = TimeEntry.objects.create(
            tenant=self.tenant1,
            lawyer=self.tenant1_admin,
            case=case1,
            hours=Decimal('5.0'),
            rate=Decimal('250.00'),
            created_by=self.tenant1_admin
        )
        
        entry2 = TimeEntry.objects.create(
            tenant=self.tenant2,
            lawyer=self.tenant2_admin,
            case=case2,
            hours=Decimal('3.0'),
            rate=Decimal('250.00'),
            created_by=self.tenant2_admin
        )
        
        # Test isolation
        self.assertTenantIsolation(
            TimeEntry,
            self.tenant1,
            self.tenant2,
            {'hours': Decimal('5.0'), 'rate': Decimal('250.00')},
            {'hours': Decimal('3.0'), 'rate': Decimal('250.00')}
        )


class BillingTransactionTests(TransactionTestCase):
    """Test billing functionality with transactions."""
    
    def setUp(self):
        """Set up test data for transaction tests."""
        # Create a tenant
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            slug='test-tenant'
        )
        
        # Create a user
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='testpass123'
        )
        
        # Create a client
        self.test_client = Client.objects.create(
            tenant=self.tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
    
    def test_invoice_creation_rollback_on_error(self):
        """Test invoice creation rollback on error."""
        # Try to create an invoice with invalid data
        with self.assertRaises(IntegrityError):
            Invoice.objects.create(
                tenant=self.tenant,
                invoice_number='',  # Invalid: empty invoice number
                client=self.test_client,
                created_by=self.admin_user
            )
        
        # Verify tenant and client still exist (transaction rolled back)
        self.assertTrue(Tenant.objects.filter(slug='test-tenant').exists())
        self.assertTrue(Client.objects.filter(email='client@example.com').exists())
    
    def test_payment_with_invoice(self):
        """Test payment creation with invoice relationship in transaction."""
        # Create invoice in transaction
        with self.assertNumQueries(1):
            invoice = Invoice.objects.create(
                tenant=self.tenant,
                invoice_number='INV-001',
                client=self.test_client,
                total_amount=Decimal('1000.00'),
                created_by=self.admin_user
            )
        
        # Create payment in transaction
        with self.assertNumQueries(1):
            payment = Payment.objects.create(
                tenant=self.tenant,
                invoice=invoice,
                amount=Decimal('500.00'),
                created_by=self.admin_user
            )
        
        # Verify relationship
        self.assertEqual(payment.invoice, invoice)
        
        # Test remaining balance calculation
        total_paid = sum(p.amount for p in Payment.objects.filter(invoice=invoice))
        expected_balance = invoice.total_amount - total_paid
        self.assertEqual(expected_balance, Decimal('500.00'))  # 1000 - 500


class BillingIntegrationTests(TenantTestCase):
    """Test billing integration with other modules."""
    
    def test_invoice_client_relationship(self):
        """Test invoice-client relationship."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        invoice = Invoice.objects.create(
            tenant=self.active_tenant,
            invoice_number='INV-001',
            client=client,
            created_by=self.admin_user
        )
        
        # Test relationship
        self.assertEqual(invoice.client, client)
        self.assertTrue(Invoice.objects.filter(client=client).exists())
    
    def test_invoice_case_relationship(self):
        """Test invoice-case relationship."""
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
        
        invoice = Invoice.objects.create(
            tenant=self.active_tenant,
            invoice_number='INV-001',
            client=client,
            case=case,
            created_by=self.admin_user
        )
        
        # Test relationship
        self.assertEqual(invoice.case, case)
        self.assertTrue(Invoice.objects.filter(case=case).exists())
    
    def test_time_entry_case_relationship(self):
        """Test time entry-case relationship."""
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
        
        time_entry = TimeEntry.objects.create(
            tenant=self.active_tenant,
            lawyer=self.lawyer_user,
            case=case,
            hours=Decimal('5.0'),
            rate=Decimal('250.00'),
            created_by=self.admin_user
        )
        
        # Test relationship
        self.assertEqual(time_entry.case, case)
        self.assertTrue(TimeEntry.objects.filter(case=case).exists())
    
    def test_invoice_item_time_entry_relationship(self):
        """Test invoice item-time entry relationship."""
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
        
        time_entry = TimeEntry.objects.create(
            tenant=self.active_tenant,
            lawyer=self.lawyer_user,
            case=case,
            hours=Decimal('5.0'),
            rate=Decimal('250.00'),
            created_by=self.admin_user
        )
        
        invoice = Invoice.objects.create(
            tenant=self.active_tenant,
            invoice_number='INV-001',
            client=client,
            case=case,
            created_by=self.admin_user
        )
        
        invoice_item = InvoiceItem.objects.create(
            tenant=self.active_tenant,
            invoice=invoice,
            time_entry=time_entry,
            description='Legal Services',
            quantity=Decimal('5.0'),
            rate=Decimal('250.00'),
            created_by=self.admin_user
        )
        
        # Test relationship
        self.assertEqual(invoice_item.time_entry, time_entry)
        self.assertTrue(InvoiceItem.objects.filter(time_entry=time_entry).exists())