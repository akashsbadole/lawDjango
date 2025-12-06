"""
Django management command to populate the database with seed data for testing and development.
"""

import os
import random
from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils import timezone
# Faker is not in requirements.txt, so we'll create our own fake data generator
# from faker import Faker
from datetime import datetime, timedelta

# Import models from different apps
from tenants.models import Tenant, TenantSettings, TenantStatusHistory
from accounts.models import CustomUser
from clients.models import Client
from cases.models import Case, CaseEvent
from billing.models import Invoice, Payment, TimeEntry, BillingRate
from documents.models import Document

# Import sample data
from seed_data.data.sample_names import (
    FIRST_NAMES, LAST_NAMES, LAW_FIRM_NAMES, COMPANY_NAMES, JOB_TITLES
)
from seed_data.data.sample_addresses import (
    STREET_ADDRESSES, CITIES, STATES, ZIP_CODES, COUNTRIES, PHONE_AREA_CODES
)

User = get_user_model()

# Simple fake data generator since Faker is not available
class SimpleFaker:
    @staticmethod
    def paragraph(nb_sentences=3):
        sentences = [
            "This is a sample sentence for testing purposes.",
            "The legal team reviewed the documentation carefully.",
            "All necessary forms were filed with the court.",
            "The client provided additional information regarding the case.",
            "A meeting was scheduled to discuss the next steps.",
            "The research team found relevant precedents for this matter.",
            "Documents were organized and prepared for the hearing.",
            "The billing department processed the invoice correctly.",
            "Time entries were logged accurately for the work performed.",
            "The case timeline was updated with recent developments."
        ]
        return ' '.join(random.sample(sentences, min(nb_sentences, len(sentences))))
    
    @staticmethod
    def sentence(nb_words=6):
        words = [
            "legal", "document", "case", "client", "lawyer", "court", "judge", "evidence",
            "testimony", "witness", "contract", "agreement", "filing", "motion", "hearing",
            "trial", "settlement", "negotiation", "mediation", "appeal", "verdict", "judgment",
            "plaintiff", "defendant", "attorney", "counsel", "paralegal", "secretary", "clerk"
        ]
        return ' '.join(random.sample(words, min(nb_words, len(words)))).capitalize() + '.'
    
    @staticmethod
    def email():
        domains = ["example.com", "test.com", "demo.com", "sample.com"]
        return f"user{random.randint(1000, 9999)}@{random.choice(domains)}"
    
    @staticmethod
    def city():
        return random.choice(CITIES)
    
    @staticmethod
    def company():
        return random.choice(COMPANY_NAMES)

fake = SimpleFaker()


class Command(BaseCommand):
    help = 'Populate the database with seed data for testing and development'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenants',
            type=int,
            default=3,
            help='Number of tenants to create (default: 3)'
        )
        parser.add_argument(
            '--users-per-tenant',
            type=int,
            default=5,
            help='Number of users to create per tenant (default: 5)'
        )
        parser.add_argument(
            '--clients-per-tenant',
            type=int,
            default=10,
            help='Number of clients to create per tenant (default: 10)'
        )
        parser.add_argument(
            '--cases-per-tenant',
            type=int,
            default=15,
            help='Number of cases to create per tenant (default: 15)'
        )
        parser.add_argument(
            '--documents-per-case',
            type=int,
            default=3,
            help='Number of documents to create per case (default: 3)'
        )
        parser.add_argument(
            '--invoices-per-tenant',
            type=int,
            default=8,
            help='Number of invoices to create per tenant (default: 8)'
        )
        parser.add_argument(
            '--time-entries-per-case',
            type=int,
            default=5,
            help='Number of time entries to create per case (default: 5)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before creating new seed data'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output'
        )

    def handle(self, *args, **options):
        self.verbose = options['verbose']
        
        if self.verbose:
            self.stdout.write(self.style.SUCCESS('Starting seed data generation...'))
        
        try:
            with transaction.atomic():
                if options['clear']:
                    self.clear_existing_data()
                
                # Create tenants
                tenants = self.create_tenants(options['tenants'])
                
                # For each tenant, create related data
                for tenant in tenants:
                    if self.verbose:
                        self.stdout.write(f'Creating data for tenant: {tenant.name}')
                    
                    # Create users for this tenant
                    users = self.create_users_for_tenant(tenant, options['users_per_tenant'])
                    
                    # Create clients for this tenant
                    clients = self.create_clients_for_tenant(tenant, options['clients_per_tenant'])
                    
                    # Create cases for this tenant
                    cases = self.create_cases_for_tenant(
                        tenant, users, clients, options['cases_per_tenant']
                    )
                    
                    # Create documents for cases (skipped due to FileField requirements)
                    # self.create_documents_for_cases(cases, options['documents_per_case'])
                    if self.verbose and options['documents_per_case'] > 0:
                        self.stdout.write(f'  Skipped creating documents for cases (FileField requires actual files)')
                    
                    # Create billing data
                    self.create_billing_data_for_tenant(
                        tenant, users, cases, options['invoices_per_tenant'],
                        options['time_entries_per_case']
                    )
                
                if self.verbose:
                    self.stdout.write(self.style.SUCCESS('Seed data generation completed successfully!'))
        
        except Exception as e:
            raise CommandError(f'Error generating seed data: {str(e)}')

    def clear_existing_data(self):
        """Clear all existing data from the database."""
        if self.verbose:
            self.stdout.write('Clearing existing data...')
        
        # Clear in order to respect foreign key constraints
        TimeEntry.objects.all().delete()
        Payment.objects.all().delete()
        Invoice.objects.all().delete()
        BillingRate.objects.all().delete()
        Document.objects.all().delete()
        # DocumentCategory model doesn't exist, so we'll skip this
        pass
        CaseEvent.objects.all().delete()
        Case.objects.all().delete()
        Client.objects.all().delete()
        TenantStatusHistory.objects.all().delete()
        TenantSettings.objects.all().delete()
        CustomUser.objects.all().delete()
        Tenant.objects.all().delete()
        
        if self.verbose:
            self.stdout.write('Existing data cleared.')

    def create_tenants(self, count):
        """Create tenant records."""
        tenants = []
        
        for i in range(count):
            tenant_name = random.choice(LAW_FIRM_NAMES)
            # Ensure unique names
            while Tenant.objects.filter(name=tenant_name).exists():
                tenant_name = f"{random.choice(LAW_FIRM_NAMES)} {i+1}"
            
            # Ensure unique slugs
            slug = f"tenant{i+1}"
            counter = 1
            while Tenant.objects.filter(slug=slug).exists():
                slug = f"tenant{i+1}-{counter}"
                counter += 1
            
            tenant = Tenant.objects.create(
                name=tenant_name,
                slug=slug,
                plan=random.choice(['basic', 'professional', 'enterprise']),
                is_active=True,
                created_at=timezone.now()
            )
            
            # Create tenant settings
            TenantSettings.objects.create(
                tenant=tenant,
                timezone=random.choice(['UTC', 'US/Eastern', 'US/Central', 'Europe/London']),
                date_format=random.choice(['m/d/Y', 'd/m/Y', 'Y-m-d']),
                time_format=random.choice(['g:i A', 'H:i']),
                default_currency=random.choice(['USD', 'EUR', 'GBP', 'CAD', 'AUD']),
                tax_rate=Decimal(str(round(random.uniform(0, 0.1), 2))),
                invoice_prefix=random.choice(['INV', 'INV-', 'INVOICE-']),
                payment_terms=random.choice([0, 7, 14, 30, 45, 60]),
                email_notifications=random.choice([True, False]),
                sms_notifications=random.choice([False, True]),
                in_app_notifications=random.choice([True, False]),
                password_policy=random.choice(['weak', 'medium', 'strong', 'very_strong']),
                session_timeout=random.choice([15, 30, 60, 120, 240]),
                enable_client_portal=random.choice([True, False]),
                enable_document_sharing=random.choice([True, False]),
                enable_time_tracking=random.choice([True, False]),
                company_name=tenant.name,
                primary_color=random.choice(['#4e73df', '#1cc88a', '#36b9cc', '#f6c23e', '#e74a3b']),
                secondary_color=random.choice(['#858796', '#5a5c69', '#2e59d9', '#1a1a1a']),
                accent_color=random.choice(['#1cc88a', '#36b9cc', '#f6c23e', '#e74a3b']),
                text_color=random.choice(['#5a5c69', '#2e59d9', '#1a1a1a']),
                background_color=random.choice(['#f8f9fc', '#ffffff', '#f5f5f5'])
            )
            
            # Create tenant status history
            TenantStatusHistory.objects.create(
                tenant=tenant,
                new_status='active',
                changed_at=timezone.now(),
                reason='Initial setup'
            )
            
            tenants.append(tenant)
            
            if self.verbose:
                self.stdout.write(f'Created tenant: {tenant.name}')
        
        return tenants

    def create_users_for_tenant(self, tenant, count):
        """Create user records for a specific tenant."""
        users = []
        roles = ['admin', 'lawyer', 'paralegal', 'assistant', 'accountant']
        
        for i in range(count):
            first_name = random.choice(FIRST_NAMES)
            last_name = random.choice(LAST_NAMES)
            
            # Generate a unique email
            email = f"{first_name.lower()}.{last_name.lower()}.{tenant.id}@example.com"
            counter = 1
            while CustomUser.objects.filter(email=email).exists():
                email = f"{first_name.lower()}.{last_name.lower()}.{tenant.id}.{counter}@example.com"
                counter += 1
            
            user = CustomUser.objects.create_user(
                username=email,  # Django's AbstractUser requires username
                email=email,
                password='password123',  # Default password for all seed users
                first_name=first_name,
                last_name=last_name,
                role=random.choice(roles),
                tenant=tenant,
                is_active=True,
                is_staff=random.choice([True, False]),
            )
            
            users.append(user)
            
            if self.verbose:
                self.stdout.write(f'  Created user: {user.email} ({user.role})')
        
        return users

    def create_clients_for_tenant(self, tenant, count):
        """Create client records for a specific tenant."""
        clients = []
        
        for i in range(count):
            # Decide if this is an individual or company client
            is_individual = random.choice([True, False])
            
            if is_individual:
                first_name = random.choice(FIRST_NAMES)
                last_name = random.choice(LAST_NAMES)
                client_name = f"{first_name} {last_name}"
            else:
                client_name = random.choice(COMPANY_NAMES)
                first_name = None
                last_name = None
            
            street_address = random.choice(STREET_ADDRESSES)
            city = random.choice(CITIES)
            state = random.choice(STATES)
            zip_code = random.choice(ZIP_CODES)
            country = random.choice(COUNTRIES)
            
            client = Client.objects.create(
                tenant=tenant,
                first_name=first_name if first_name else random.choice(FIRST_NAMES),
                last_name=last_name if last_name else random.choice(LAST_NAMES),
                email=fake.email(),
                phone=f"+1{random.choice(PHONE_AREA_CODES)}-{random.randint(100, 999)}-{random.randint(1000, 9999)}",
                address=f"{street_address}, {city}, {state['code']} {zip_code}",
                company=client_name if not is_individual else random.choice(COMPANY_NAMES),
                notes=fake.paragraph(nb_sentences=2),
                created_at=timezone.now() - timedelta(days=random.randint(1, 365))
            )
            
            clients.append(client)
            
            if self.verbose:
                self.stdout.write(f'  Created client: {client.full_name}')
        
        return clients

    def create_cases_for_tenant(self, tenant, users, clients, count):
        """Create case records for a specific tenant."""
        cases = []
        case_types = ['civil_litigation', 'criminal_defense', 'family_law', 'corporate_law', 
                     'real_estate', 'immigration', 'intellectual_property', 'employment_law']
        case_statuses = ['open', 'in_progress', 'pending_review', 'settled', 'closed']
        
        for i in range(count):
            case_number = f"{timezone.now().year}-{random.randint(1000, 9999)}"
            
            # Ensure unique case numbers
            while Case.objects.filter(case_number=case_number).exists():
                case_number = f"{timezone.now().year}-{random.randint(1000, 9999)}"
            
            # Assign a lawyer to the case
            lawyers = [u for u in users if u.role in ['lawyer', 'admin']]
            assigned_lawyer = random.choice(lawyers) if lawyers else random.choice(users)
            
            # Assign a client to the case
            client = random.choice(clients)
            
            case = Case.objects.create(
                tenant=tenant,
                case_number=case_number,
                title=fake.sentence(nb_words=6),
                description=fake.paragraph(nb_sentences=5),
                case_type=random.choice(case_types),
                status=random.choice(case_statuses),
                client=client,
                start_date=timezone.now() - timedelta(days=random.randint(1, 730)),
                end_date=None if random.choice([True, False]) else timezone.now() - timedelta(days=random.randint(1, 365)),
                created_by=assigned_lawyer,
                created_at=timezone.now() - timedelta(days=random.randint(1, 365))
            )
            
            # Add assigned lawyers to the case
            case.assigned_lawyers.add(assigned_lawyer)
            
            # Create some case events
            self.create_case_events_for_case(case, users)
            
            cases.append(case)
            
            if self.verbose:
                self.stdout.write(f'  Created case: {case.case_number} - {case.title}')
        
        return cases

    def create_case_events_for_case(self, case, users):
        """Create case events for a specific case."""
        event_types = ['note', 'phone_call', 'email', 'meeting', 'court_appearance', 'filing', 'research']
        
        # Create 3-7 events per case
        for _ in range(random.randint(3, 7)):
            event_date = case.start_date + timedelta(days=random.randint(0, 30))
            
            CaseEvent.objects.create(
                tenant=case.tenant,
                case=case,
                event_type=random.choice(event_types),
                title=fake.sentence(nb_words=4),
                description=fake.paragraph(nb_sentences=3),
                created_by=random.choice(users),
                event_date=event_date,
                created_at=event_date
            )

    def create_documents_for_cases(self, cases, docs_per_case):
        """Create document records for cases."""
        document_types = ['complaint', 'motion', 'brief', 'contract', 'agreement', 'evidence', 'correspondence', 'research']
        
        for case in cases:
            # Create document categories if they don't exist
            # DocumentCategory model doesn't exist, so we'll use category choices directly
            for i in range(docs_per_case):
                doc_type = random.choice(document_types)
                category = random.choice(['contract', 'evidence', 'correspondence', 'court_filing',
                                      'discovery', 'motion', 'brief', 'research'])
                
                # Create document without file field to avoid JSON serialization issues
                # Skip file field entirely for now - documents will have metadata only
                document = Document.objects.create(
                    tenant=case.tenant,
                    case=case,
                    title=fake.sentence(nb_words=4),
                    description=fake.paragraph(nb_sentences=2),
                    file_name=f"{doc_type}_{case.case_number}_{i+1}.pdf",
                    file_size=random.randint(1024, 10485760),  # 1KB to 10MB
                    file_type='pdf',  # Use file_type choices from model
                    category=category,
                    access_level=random.choice(['public', 'internal', 'confidential', 'restricted']),
                    uploaded_by=random.choice(list(case.assigned_lawyers.all())),
                    created_at=timezone.now() - timedelta(days=random.randint(1, 30))
                )
            
            if self.verbose:
                self.stdout.write(f'  Created {docs_per_case} documents for case: {case.case_number}')

    def get_or_create_document_categories(self, tenant):
        """Get or create document categories for a tenant."""
        category_names = ['Pleadings', 'Motions', 'Discovery', 'Correspondence', 'Research', 'Evidence', 'Court Documents']
        categories = []
        
        for name in category_names:
            # DocumentCategory model doesn't exist, so we'll use the category choices directly
            # from the Document model
            pass
        
        return categories

    def create_billing_data_for_tenant(self, tenant, users, cases, invoice_count, time_entries_per_case):
        """Create billing data for a tenant."""
        # Create billing rates
        self.create_billing_rates_for_tenant(tenant, users)
        
        # Create invoices
        invoices = self.create_invoices_for_tenant(tenant, users, cases, invoice_count)
        
        # Create time entries
        self.create_time_entries_for_cases(cases, users, time_entries_per_case)
        
        # Create payments for some invoices
        self.create_payments_for_invoices(invoices)

    def create_billing_rates_for_tenant(self, tenant, users):
        """Create billing rates for users."""
        for user in users:
            if user.role in ['lawyer', 'admin', 'paralegal']:
                # Different rates based on role
                if user.role == 'lawyer':
                    hourly_rate = Decimal(str(round(random.uniform(150, 500), 2)))
                elif user.role == 'admin':
                    hourly_rate = Decimal(str(round(random.uniform(200, 600), 2)))
                else:  # paralegal
                    hourly_rate = Decimal(str(round(random.uniform(75, 150), 2)))
                
                BillingRate.objects.create(
                    tenant=tenant,
                    role=user.role,
                    default_rate=hourly_rate,
                    effective_date=timezone.now() - timedelta(days=random.randint(1, 365)),
                    created_at=timezone.now()
                )

    def create_invoices_for_tenant(self, tenant, users, cases, count):
        """Create invoices for a tenant."""
        invoices = []
        invoice_statuses = ['draft', 'sent', 'paid', 'overdue', 'cancelled']
        
        for i in range(count):
            case = random.choice(cases)
            created_date = timezone.now() - timedelta(days=random.randint(1, 90))
            due_date = created_date + timedelta(days=random.randint(15, 45))
            
            # Calculate amounts first
            subtotal = Decimal(str(round(random.uniform(500, 10000), 2)))
            tax_rate = Decimal(str(round(random.uniform(0, 0.1), 2)))
            tax_amount = subtotal * tax_rate
            total_amount = subtotal + tax_amount
            
            invoice = Invoice.objects.create(
                tenant=tenant,
                invoice_number=f"INV-{tenant.id}-{timezone.now().year}-{i+1:04d}",
                case=case,
                client=case.client,
                status=random.choice(invoice_statuses),
                issue_date=created_date,
                due_date=due_date,
                subtotal=subtotal,
                tax_rate=tax_rate,
                tax_amount=tax_amount,
                total_amount=total_amount,
                notes=fake.paragraph(nb_sentences=2),
                created_by=random.choice(users),
                created_at=created_date
            )
            
            invoices.append(invoice)
            
            if self.verbose:
                self.stdout.write(f'  Created invoice: {invoice.invoice_number}')
        
        return invoices

    def create_time_entries_for_cases(self, cases, users, count_per_case):
        """Create time entries for cases."""
        for case in cases:
            # Get billing rates for this case's assigned lawyer
            try:
                # Get the assigned lawyer
                assigned_lawyer = case.assigned_lawyers.first()
                if not assigned_lawyer:
                    continue
                    
                billing_rate = BillingRate.objects.filter(
                    role=assigned_lawyer.role,
                    tenant=case.tenant
                ).first()
                
                if not billing_rate:
                    # Create a default billing rate if none exists
                    billing_rate = BillingRate.objects.create(
                        tenant=case.tenant,
                        role=assigned_lawyer.role,
                        default_rate=Decimal('250.00'),
                        effective_date=timezone.now() - timedelta(days=365),
                        created_at=timezone.now()
                    )
            except Exception:
                continue
            
            for i in range(count_per_case):
                # Get the assigned lawyer
                assigned_lawyer = case.assigned_lawyers.first()
                if not assigned_lawyer:
                    continue
                    
                # Random date within the case timeline
                # Ensure both dates are date objects for subtraction
                now_date = timezone.now().date()
                case_start_date = case.start_date.date() if hasattr(case.start_date, 'date') else case.start_date
                days_since_open = (now_date - case_start_date).days
                entry_date = case_start_date + timedelta(days=random.randint(0, max(0, days_since_open)))
                
                # Random duration between 0.1 and 8 hours
                hours = round(random.uniform(0.1, 8.0), 2)
                
                # Ensure entry_date is a date object, not datetime
                if hasattr(entry_date, 'date'):
                    entry_date = entry_date.date()
                elif isinstance(entry_date, timezone.datetime):
                    entry_date = entry_date.date()
                
                TimeEntry.objects.create(
                    tenant=case.tenant,
                    case=case,
                    lawyer=assigned_lawyer,
                    description=fake.paragraph(nb_sentences=2),
                    hours=Decimal(str(hours)),
                    rate=billing_rate.default_rate,
                    date=entry_date,
                    is_billable=random.choice([True, False]),
                    created_at=timezone.now() - timedelta(days=random.randint(1, 30))
                )
            
            if self.verbose:
                self.stdout.write(f'  Created {count_per_case} time entries for case: {case.case_number}')

    def create_payments_for_invoices(self, invoices):
        """Create payments for some invoices."""
        for invoice in invoices:
            # Only create payments for invoices that are sent or overdue
            if invoice.status in ['sent', 'overdue']:
                # 70% chance of having at least one payment
                if random.random() < 0.7:
                    # Create 1-3 payments
                    num_payments = random.randint(1, 3)
                    
                    for i in range(num_payments):
                        # Payment date should be after invoice issue date
                        payment_date = invoice.issue_date + timedelta(days=random.randint(1, 60))
                        
                        # Calculate total paid from all payments
                        total_paid = sum(p.amount for p in invoice.payments.all())
                        remaining_balance = invoice.total_amount - total_paid
                        if remaining_balance <= 0:
                            break
                        
                        # Random payment amount (either partial or full)
                        if i == num_payments - 1 or random.random() < 0.5:
                            # Last payment or full payment
                            payment_amount = remaining_balance
                        else:
                            # Partial payment
                            payment_amount = remaining_balance * Decimal(str(round(random.uniform(0.3, 0.7), 2)))
                        
                        payment = Payment.objects.create(
                            tenant=invoice.tenant,
                            invoice=invoice,
                            amount=payment_amount,
                            payment_date=payment_date,
                            payment_method=random.choice(['check', 'credit_card', 'bank_transfer', 'cash']),
                            reference=f"Payment-{invoice.invoice_number}-{i+1}",
                            notes=fake.sentence(),
                            created_at=payment_date
                        )
                        
                        # Update invoice status if fully paid
                        total_paid = sum(p.amount for p in invoice.payments.all())
                        if total_paid >= invoice.total_amount:
                            invoice.status = 'paid'
                            invoice.save()
                    
                    if self.verbose:
                        self.stdout.write(f'  Created {num_payments} payments for invoice: {invoice.invoice_number}')