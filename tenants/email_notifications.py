from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags


def send_tenant_status_notification(tenant, old_status, new_status, reason=None, changed_by=None):
    """
    Send email notification about tenant status change.
    """
    # Get tenant admin users
    from accounts.models import CustomUser
    admin_users = CustomUser.objects.filter(
        tenant=tenant,
        role='admin',
        is_active=True
    )
    
    # Prepare email context
    context = {
        'tenant': tenant,
        'old_status': old_status,
        'new_status': new_status,
        'reason': reason,
        'changed_by': changed_by,
        'site_name': getattr(settings, 'SITE_NAME', 'Law Firm Management'),
    }
    
    # Determine email subject and template based on new status
    if new_status == 'suspended':
        subject = f'Your Law Firm "{tenant.name}" has been suspended'
        template = 'tenants/emails/tenant_suspended.html'
    elif new_status == 'deleted':
        subject = f'Your Law Firm "{tenant.name}" has been deleted'
        template = 'tenants/emails/tenant_deleted.html'
    elif new_status == 'trial_expired':
        subject = f'Trial for "{tenant.name}" has expired'
        template = 'tenants/emails/tenant_trial_expired.html'
    elif new_status == 'active' and old_status in ['suspended', 'deleted', 'trial_expired']:
        subject = f'Your Law Firm "{tenant.name}" has been restored'
        template = 'tenants/emails/tenant_restored.html'
    else:
        subject = f'Status change for "{tenant.name}"'
        template = 'tenants/emails/tenant_status_changed.html'
    
    # Render email content
    html_message = render_to_string(template, context)
    plain_message = strip_tags(html_message)
    
    # Send emails to all admin users
    for user in admin_users:
        try:
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@lawfirm.com'),
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False
            )
        except Exception as e:
            # Log error but continue with other users
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send email to {user.email}: {e}")


def send_tenant_deletion_warning(tenant, days_until_deletion=7):
    """
    Send warning email before permanent tenant deletion.
    """
    from accounts.models import CustomUser
    admin_users = CustomUser.objects.filter(
        tenant=tenant,
        role='admin',
        is_active=True
    )
    
    context = {
        'tenant': tenant,
        'days_until_deletion': days_until_deletion,
        'deletion_date': tenant.deleted_at,
        'site_name': getattr(settings, 'SITE_NAME', 'Law Firm Management'),
    }
    
    subject = f'Warning: "{tenant.name}" will be permanently deleted in {days_until_deletion} days'
    template = 'tenants/emails/tenant_deletion_warning.html'
    
    html_message = render_to_string(template, context)
    plain_message = strip_tags(html_message)
    
    for user in admin_users:
        try:
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@lawfirm.com'),
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send deletion warning to {user.email}: {e}")


def send_tenant_suspension_warning(tenant, days_until_suspension=3):
    """
    Send warning email before tenant suspension.
    """
    from accounts.models import CustomUser
    admin_users = CustomUser.objects.filter(
        tenant=tenant,
        role='admin',
        is_active=True
    )
    
    context = {
        'tenant': tenant,
        'days_until_suspension': days_until_suspension,
        'site_name': getattr(settings, 'SITE_NAME', 'Law Firm Management'),
    }
    
    subject = f'Warning: "{tenant.name}" will be suspended in {days_until_suspension} days'
    template = 'tenants/emails/tenant_suspension_warning.html'
    
    html_message = render_to_string(template, context)
    plain_message = strip_tags(html_message)
    
    for user in admin_users:
        try:
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@lawfirm.com'),
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send suspension warning to {user.email}: {e}")


def send_trial_expiration_warning(tenant, days_until_expiration=7):
    """
    Send warning email before trial expiration.
    """
    from accounts.models import CustomUser
    admin_users = CustomUser.objects.filter(
        tenant=tenant,
        role='admin',
        is_active=True
    )
    
    context = {
        'tenant': tenant,
        'days_until_expiration': days_until_expiration,
        'site_name': getattr(settings, 'SITE_NAME', 'Law Firm Management'),
    }
    
    subject = f'Warning: Trial for "{tenant.name}" expires in {days_until_expiration} days'
    template = 'tenants/emails/trial_expiration_warning.html'
    
    html_message = render_to_string(template, context)
    plain_message = strip_tags(html_message)
    
    for user in admin_users:
        try:
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@lawfirm.com'),
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send trial warning to {user.email}: {e}")