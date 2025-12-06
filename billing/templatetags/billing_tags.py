from django import template
from django.db.models import Sum
from django.utils import timezone
from ..models import Invoice, TimeEntry, Payment

register = template.Library()


@register.simple_tag
def get_unpaid_invoices_count(tenant):
    """Get count of unpaid invoices for tenant."""
    return Invoice.objects.unpaid(tenant).count()


@register.simple_tag
def get_monthly_revenue(tenant):
    """Get total revenue for current month."""
    current_month = timezone.now().replace(day=1)
    monthly_payments = Payment.objects.active_for_tenant(tenant).filter(
        payment_date__gte=current_month
    )
    revenue = monthly_payments.aggregate(total=Sum('amount'))['total'] or 0
    return "{:.2f}".format(revenue)


@register.simple_tag
def get_unbilled_time_entries_count(tenant):
    """Get count of unbilled time entries for tenant."""
    return TimeEntry.objects.unbilled(tenant).count()


@register.simple_tag
def get_overdue_invoices_count(tenant):
    """Get count of overdue invoices for tenant."""
    return Invoice.objects.overdue(tenant).count()


@register.simple_tag
def get_total_outstanding(tenant):
    """Get total outstanding amount for unpaid invoices."""
    unpaid_invoices = Invoice.objects.unpaid(tenant)
    total = unpaid_invoices.aggregate(total=Sum('total_amount'))['total'] or 0
    return "{:.2f}".format(total)