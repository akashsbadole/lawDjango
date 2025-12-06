from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q
from datetime import timedelta, datetime
from decimal import Decimal

from tenants.models import Tenant
from accounts.models import CustomUser
from subscriptions.models import TenantSubscription, Payment, Invoice
from platform_admin.models import PlatformMetrics
from clients.models import Client
from cases.models import Case
from documents.models import Document


class Command(BaseCommand):
    help = 'Generate platform analytics and reports'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--period',
            type=str,
            choices=['daily', 'weekly', 'monthly', 'yearly'],
            default='monthly',
            help='Period for analytics generation'
        )
        parser.add_argument(
            '--date',
            type=str,
            help='Specific date (YYYY-MM-DD) for analytics generation'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Generate analytics without saving to database'
        )
    
    def handle(self, *args, **options):
        period = options.get('period', 'monthly')
        date_str = options.get('date')
        dry_run = options.get('dry_run', False)
        
        if date_str:
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                self.stdout.write(self.style.ERROR('Invalid date format. Use YYYY-MM-DD'))
                return
        else:
            target_date = timezone.now().date()
        
        self.stdout.write(
            self.style.SUCCESS(f'Generating {period} analytics for {target_date}...')
        )
        
        # Generate analytics data
        analytics_data = self.generate_analytics_data(target_date, period)
        
        if dry_run:
            self.display_analytics(analytics_data)
        else:
            self.save_analytics(analytics_data, target_date, period)
            self.stdout.write(
                self.style.SUCCESS(f'Successfully generated {period} analytics for {target_date}')
            )
    
    def generate_analytics_data(self, target_date, period):
        """Generate comprehensive analytics data."""
        # Calculate date range based on period
        if period == 'daily':
            start_date = target_date
            end_date = target_date + timedelta(days=1)
        elif period == 'weekly':
            start_date = target_date - timedelta(days=target_date.weekday())
            end_date = start_date + timedelta(days=7)
        elif period == 'monthly':
            start_date = target_date.replace(day=1)
            # Find first day of next month
            if start_date.month == 12:
                end_date = start_date.replace(year=start_date.year + 1, month=1, day=1)
            else:
                end_date = start_date.replace(month=start_date.month + 1, day=1)
        else:  # yearly
            start_date = target_date.replace(month=1, day=1)
            end_date = start_date.replace(year=start_date.year + 1, month=1, day=1)
        
        # Generate analytics for the period
        analytics = {
            'period': period,
            'start_date': start_date,
            'end_date': end_date,
            'tenants': self.get_tenant_analytics(start_date, end_date),
            'users': self.get_user_analytics(start_date, end_date),
            'subscriptions': self.get_subscription_analytics(start_date, end_date),
            'revenue': self.get_revenue_analytics(start_date, end_date),
            'storage': self.get_storage_analytics(start_date, end_date),
            'performance': self.get_performance_analytics(start_date, end_date),
            'feature_usage': self.get_feature_usage_analytics(start_date, end_date),
        }
        
        return analytics
    
    def get_tenant_analytics(self, start_date, end_date):
        """Generate tenant-related analytics."""
        base_queryset = Tenant.objects.all()
        
        # Total tenants
        total_tenants = base_queryset.count()
        
        # Active tenants
        active_tenants = base_queryset.filter(is_active=True).count()
        
        # New tenants in period
        new_tenants = base_queryset.filter(
            created_at__gte=start_date,
            created_at__lt=end_date
        ).count()
        
        # Churned tenants in period
        churned_tenants = base_queryset.filter(
            deleted_at__gte=start_date,
            deleted_at__lt=end_date
        ).count()
        
        # Tenants by plan
        tenants_by_plan = list(
            base_queryset.values('plan').annotate(
                count=Count('id')
            ).order_by('-count')
        )
        
        return {
            'total': total_tenants,
            'active': active_tenants,
            'new': new_tenants,
            'churned': churned_tenants,
            'by_plan': tenants_by_plan,
            'growth_rate': (new_tenants / max(total_tenants - new_tenants, 1)) * 100,
            'churn_rate': (churned_tenants / max(total_tenants, 1)) * 100,
        }
    
    def get_user_analytics(self, start_date, end_date):
        """Generate user-related analytics."""
        base_queryset = CustomUser.objects.all()
        
        # Total users
        total_users = base_queryset.count()
        
        # Active users (logged in within last 30 days)
        active_users = base_queryset.filter(
            last_login__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        # New users in period
        new_users = base_queryset.filter(
            date_joined__gte=start_date,
            date_joined__lt=end_date
        ).count()
        
        # Users by role
        users_by_role = list(
            base_queryset.values('role').annotate(
                count=Count('id')
            ).order_by('-count')
        )
        
        # Users per tenant (average)
        users_per_tenant = base_queryset.values('tenant').annotate(
            user_count=Count('id')
        ).aggregate(avg_users=Avg('user_count'))['avg_users'] or 0
        
        return {
            'total': total_users,
            'active': active_users,
            'new': new_users,
            'by_role': users_by_role,
            'avg_per_tenant': round(users_per_tenant, 2),
            'activation_rate': (active_users / max(total_users, 1)) * 100,
        }
    
    def get_subscription_analytics(self, start_date, end_date):
        """Generate subscription-related analytics."""
        base_queryset = TenantSubscription.objects.all()
        
        # Total subscriptions
        total_subscriptions = base_queryset.count()
        
        # Active subscriptions
        active_subscriptions = base_queryset.filter(status='active').count()
        
        # Trial subscriptions
        trial_subscriptions = base_queryset.filter(status='trial').count()
        
        # Expired subscriptions in period
        expired_subscriptions = base_queryset.filter(
            status='expired',
            updated_at__gte=start_date,
            updated_at__lt=end_date
        ).count()
        
        # New subscriptions in period
        new_subscriptions = base_queryset.filter(
            created_at__gte=start_date,
            created_at__lt=end_date
        ).count()
        
        # Subscriptions by plan
        subscriptions_by_plan = list(
            base_queryset.values('plan__name').annotate(
                count=Count('id')
            ).order_by('-count')
        )
        
        return {
            'total': total_subscriptions,
            'active': active_subscriptions,
            'trial': trial_subscriptions,
            'expired': expired_subscriptions,
            'new': new_subscriptions,
            'by_plan': subscriptions_by_plan,
            'conversion_rate': (active_subscriptions / max(total_subscriptions, 1)) * 100,
        }
    
    def get_revenue_analytics(self, start_date, end_date):
        """Generate revenue-related analytics."""
        base_queryset = Payment.objects.filter(
            status='completed',
            payment_date__gte=start_date,
            payment_date__lt=end_date
        )
        
        # Total revenue
        total_revenue = base_queryset.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        # Revenue by month (for longer periods)
        revenue_by_month = list(
            base_queryset.extra(
                select={'month': "strftime('%%Y-%%m', payment_date)"}
            ).values('month').annotate(
                total=Sum('amount'),
                count=Count('id')
            ).order_by('month')
        )
        
        # Revenue by tenant
        revenue_by_tenant = list(
            base_queryset.values('invoice__tenant__name').annotate(
                total=Sum('amount'),
                count=Count('id')
            ).order_by('-total')[:10]
        )
        
        # Average revenue per tenant
        avg_revenue_per_tenant = base_queryset.values(
            'invoice__tenant'
        ).annotate(
            tenant_total=Sum('amount')
        ).aggregate(avg=Avg('tenant_total'))['avg'] or Decimal('0.00')
        
        # Monthly recurring revenue (MRR)
        active_subscriptions = TenantSubscription.objects.filter(status='active')
        mrr = sum(
            sub.plan.monthly_price for sub in active_subscriptions
            if sub.plan
        ) if active_subscriptions else Decimal('0.00')
        
        return {
            'total': total_revenue,
            'mrr': mrr,
            'avg_per_tenant': avg_revenue_per_tenant,
            'by_month': revenue_by_month,
            'by_tenant': revenue_by_tenant,
        }
    
    def get_storage_analytics(self, start_date, end_date):
        """Generate storage-related analytics."""
        # This is a simplified version - in production, you'd track actual file sizes
        total_documents = Document.objects.filter(
            created_at__gte=start_date,
            created_at__lt=end_date
        ).count()
        
        # Estimate storage usage (simplified)
        estimated_storage_mb = total_documents * 2  # Assume 2MB per document average
        
        # Storage by tenant
        storage_by_tenant = list(
            Document.objects.filter(
                created_at__gte=start_date,
                created_at__lt=end_date
            ).values('tenant__name').annotate(
                count=Count('id')
            ).order_by('-count')[:10]
        )
        
        return {
            'total_documents': total_documents,
            'estimated_storage_mb': estimated_storage_mb,
            'by_tenant': storage_by_tenant,
        }
    
    def get_performance_analytics(self, start_date, end_date):
        """Generate performance-related analytics."""
        # This would typically come from monitoring tools
        # For now, we'll use placeholder data
        return {
            'avg_response_time_ms': 150,  # Placeholder
            'uptime_percentage': 99.9,    # Placeholder
            'error_rate_percentage': 0.1,   # Placeholder
        }
    
    def get_feature_usage_analytics(self, start_date, end_date):
        """Generate feature usage analytics."""
        # Documents created
        documents_created = Document.objects.filter(
            created_at__gte=start_date,
            created_at__lt=end_date
        ).count()
        
        # Cases created
        cases_created = Case.objects.filter(
            created_at__gte=start_date,
            created_at__lt=end_date
        ).count()
        
        # Clients created
        clients_created = Client.objects.filter(
            created_at__gte=start_date,
            created_at__lt=end_date
        ).count()
        
        # Invoices generated
        invoices_generated = Invoice.objects.filter(
            created_at__gte=start_date,
            created_at__lt=end_date
        ).count()
        
        return {
            'documents_created': documents_created,
            'cases_created': cases_created,
            'clients_created': clients_created,
            'invoices_generated': invoices_generated,
        }
    
    def display_analytics(self, analytics_data):
        """Display analytics data to console."""
        self.stdout.write(self.style.SUCCESS('\n=== Platform Analytics ==='))
        
        # Tenant analytics
        tenants = analytics_data['tenants']
        self.stdout.write(f"\nTenants:")
        self.stdout.write(f"  Total: {tenants['total']}")
        self.stdout.write(f"  Active: {tenants['active']}")
        self.stdout.write(f"  New: {tenants['new']}")
        self.stdout.write(f"  Churned: {tenants['churned']}")
        self.stdout.write(f"  Growth Rate: {tenants['growth_rate']:.2f}%")
        self.stdout.write(f"  Churn Rate: {tenants['churn_rate']:.2f}%")
        
        # User analytics
        users = analytics_data['users']
        self.stdout.write(f"\nUsers:")
        self.stdout.write(f"  Total: {users['total']}")
        self.stdout.write(f"  Active: {users['active']}")
        self.stdout.write(f"  New: {users['new']}")
        self.stdout.write(f"  Avg per Tenant: {users['avg_per_tenant']}")
        self.stdout.write(f"  Activation Rate: {users['activation_rate']:.2f}%")
        
        # Subscription analytics
        subscriptions = analytics_data['subscriptions']
        self.stdout.write(f"\nSubscriptions:")
        self.stdout.write(f"  Total: {subscriptions['total']}")
        self.stdout.write(f"  Active: {subscriptions['active']}")
        self.stdout.write(f"  Trial: {subscriptions['trial']}")
        self.stdout.write(f"  New: {subscriptions['new']}")
        self.stdout.write(f"  Conversion Rate: {subscriptions['conversion_rate']:.2f}%")
        
        # Revenue analytics
        revenue = analytics_data['revenue']
        self.stdout.write(f"\nRevenue:")
        self.stdout.write(f"  Total: ${revenue['total']}")
        self.stdout.write(f"  MRR: ${revenue['mrr']}")
        self.stdout.write(f"  Avg per Tenant: ${revenue['avg_per_tenant']}")
        
        # Feature usage analytics
        features = analytics_data['feature_usage']
        self.stdout.write(f"\nFeature Usage:")
        self.stdout.write(f"  Documents Created: {features['documents_created']}")
        self.stdout.write(f"  Cases Created: {features['cases_created']}")
        self.stdout.write(f"  Clients Created: {features['clients_created']}")
        self.stdout.write(f"  Invoices Generated: {features['invoices_generated']}")
    
    def save_analytics(self, analytics_data, target_date, period):
        """Save analytics data to database."""
        # Create PlatformMetrics record
        metrics = PlatformMetrics.objects.create(
            metric_type=period,
            date=target_date,
            
            # Tenant metrics
            total_tenants=analytics_data['tenants']['total'],
            active_tenants=analytics_data['tenants']['active'],
            new_tenants=analytics_data['tenants']['new'],
            churned_tenants=analytics_data['tenants']['churned'],
            
            # User metrics
            total_users=analytics_data['users']['total'],
            active_users=analytics_data['users']['active'],
            new_users=analytics_data['users']['new'],
            
            # Subscription metrics
            total_subscriptions=analytics_data['subscriptions']['total'],
            active_subscriptions=analytics_data['subscriptions']['active'],
            trial_subscriptions=analytics_data['subscriptions']['trial'],
            expired_subscriptions=analytics_data['subscriptions']['expired'],
            
            # Revenue metrics
            total_revenue=analytics_data['revenue']['total'],
            monthly_recurring_revenue=analytics_data['revenue']['mrr'],
            average_revenue_per_tenant=analytics_data['revenue']['avg_per_tenant'],
            
            # Storage metrics
            total_storage_used_mb=analytics_data['storage']['estimated_storage_mb'],
            average_storage_per_tenant_mb=analytics_data['storage']['estimated_storage_mb'] / max(analytics_data['tenants']['total'], 1),
            
            # Performance metrics
            average_response_time_ms=analytics_data['performance']['avg_response_time_ms'],
            uptime_percentage=analytics_data['performance']['uptime_percentage'],
            error_rate_percentage=analytics_data['performance']['error_rate_percentage'],
            
            # Feature usage metrics
            documents_created=analytics_data['feature_usage']['documents_created'],
            cases_created=analytics_data['feature_usage']['cases_created'],
            clients_created=analytics_data['feature_usage']['clients_created'],
            invoices_generated=analytics_data['feature_usage']['invoices_generated'],
            
            # Additional metrics as JSON
            additional_metrics={
                'tenants_by_plan': analytics_data['tenants']['by_plan'],
                'users_by_role': analytics_data['users']['by_role'],
                'subscriptions_by_plan': analytics_data['subscriptions']['by_plan'],
                'revenue_by_month': analytics_data['revenue']['by_month'],
                'revenue_by_tenant': analytics_data['revenue']['by_tenant'],
                'storage_by_tenant': analytics_data['storage']['by_tenant'],
            }
        )
        
        return metrics