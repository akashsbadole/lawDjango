"""
Tenant Email Templates Models
Implements Feature #15 from todo.md: Tenant-Level Email Templates
"""
from django.db import models
from django.template import Template, Context
from django.utils import timezone


class EmailTemplate(models.Model):
    """
    Customizable email templates per tenant.
    """
    TEMPLATE_TYPES = [
        ('welcome', 'Welcome Email'),
        ('case_update', 'Case Update'),
        ('invoice_sent', 'Invoice Sent'),
        ('invoice_reminder', 'Invoice Reminder'),
        ('payment_received', 'Payment Received'),
        ('document_shared', 'Document Shared'),
        ('appointment_reminder', 'Appointment Reminder'),
        ('case_closed', 'Case Closed'),
        ('new_message', 'New Message'),
        ('password_reset', 'Password Reset'),
        ('team_invite', 'Team Invitation'),
        ('custom', 'Custom Template'),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='email_templates'
    )
    template_type = models.CharField(
        max_length=50,
        choices=TEMPLATE_TYPES
    )
    name = models.CharField(max_length=200)
    subject = models.CharField(max_length=500)
    body_html = models.TextField(
        help_text='HTML body with Django template variables'
    )
    body_text = models.TextField(
        blank=True,
        help_text='Plain text version (optional)'
    )
    is_active = models.BooleanField(default=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_email_templates'
    )
    
    class Meta:
        db_table = 'tenant_email_templates'
        unique_together = ['tenant', 'template_type']
        ordering = ['template_type', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.tenant.name})"
    
    def render_subject(self, context_dict):
        """Render subject with context variables."""
        template = Template(self.subject)
        context = Context(context_dict)
        return template.render(context)
    
    def render_body_html(self, context_dict):
        """Render HTML body with context variables."""
        template = Template(self.body_html)
        context = Context(context_dict)
        return template.render(context)
    
    def render_body_text(self, context_dict):
        """Render plain text body with context variables."""
        if not self.body_text:
            # Strip HTML tags as fallback
            import re
            html = self.render_body_html(context_dict)
            return re.sub('<[^<]+?>', '', html)
        
        template = Template(self.body_text)
        context = Context(context_dict)
        return template.render(context)
    
    @classmethod
    def get_template(cls, tenant, template_type):
        """Get template for tenant, falling back to default if not found."""
        try:
            return cls.objects.get(
                tenant=tenant,
                template_type=template_type,
                is_active=True
            )
        except cls.DoesNotExist:
            return cls.get_default_template(template_type)
    
    @classmethod
    def get_default_template(cls, template_type):
        """Get default template for a type."""
        defaults = {
            'welcome': {
                'subject': 'Welcome to {{ tenant_name }}!',
                'body_html': '''
                    <h1>Welcome, {{ user_name }}!</h1>
                    <p>Thank you for joining {{ tenant_name }}.</p>
                    <p>You can now access your account at:</p>
                    <p><a href="{{ login_url }}">{{ login_url }}</a></p>
                    <p>Best regards,<br>{{ tenant_name }} Team</p>
                '''
            },
            'case_update': {
                'subject': 'Case Update: {{ case_title }}',
                'body_html': '''
                    <h1>Case Update</h1>
                    <p>Dear {{ client_name }},</p>
                    <p>There has been an update to your case: <strong>{{ case_title }}</strong></p>
                    <p>{{ update_message }}</p>
                    <p>Best regards,<br>{{ lawyer_name }}<br>{{ tenant_name }}</p>
                '''
            },
            'invoice_sent': {
                'subject': 'Invoice #{{ invoice_number }} from {{ tenant_name }}',
                'body_html': '''
                    <h1>Invoice #{{ invoice_number }}</h1>
                    <p>Dear {{ client_name }},</p>
                    <p>Please find attached your invoice for {{ amount }}.</p>
                    <p>Due date: {{ due_date }}</p>
                    <p><a href="{{ payment_url }}">Pay Now</a></p>
                    <p>Best regards,<br>{{ tenant_name }}</p>
                '''
            },
            'invoice_reminder': {
                'subject': 'Payment Reminder: Invoice #{{ invoice_number }}',
                'body_html': '''
                    <h1>Payment Reminder</h1>
                    <p>Dear {{ client_name }},</p>
                    <p>This is a friendly reminder that invoice #{{ invoice_number }} for {{ amount }} is due on {{ due_date }}.</p>
                    <p><a href="{{ payment_url }}">Pay Now</a></p>
                    <p>Best regards,<br>{{ tenant_name }}</p>
                '''
            },
            'payment_received': {
                'subject': 'Payment Received - Thank You!',
                'body_html': '''
                    <h1>Payment Received</h1>
                    <p>Dear {{ client_name }},</p>
                    <p>We have received your payment of {{ amount }} for invoice #{{ invoice_number }}.</p>
                    <p>Thank you for your prompt payment!</p>
                    <p>Best regards,<br>{{ tenant_name }}</p>
                '''
            },
            'team_invite': {
                'subject': 'You\'ve been invited to join {{ tenant_name }}',
                'body_html': '''
                    <h1>Team Invitation</h1>
                    <p>Hello {{ user_name }},</p>
                    <p>{{ inviter_name }} has invited you to join {{ tenant_name }} as a {{ role }}.</p>
                    <p><a href="{{ invite_url }}">Accept Invitation</a></p>
                    <p>This invitation expires in 7 days.</p>
                    <p>Best regards,<br>{{ tenant_name }}</p>
                '''
            },
        }
        
        default = defaults.get(template_type, {
            'subject': 'Notification from {{ tenant_name }}',
            'body_html': '<p>{{ message }}</p>'
        })
        
        # Return a mock template object
        class MockTemplate:
            def __init__(self, subject, body_html):
                self.subject = subject
                self.body_html = body_html
                self.body_text = ''
            
            def render_subject(self, context_dict):
                template = Template(self.subject)
                return template.render(Context(context_dict))
            
            def render_body_html(self, context_dict):
                template = Template(self.body_html)
                return template.render(Context(context_dict))
            
            def render_body_text(self, context_dict):
                import re
                html = self.render_body_html(context_dict)
                return re.sub('<[^<]+?>', '', html)
        
        return MockTemplate(default['subject'], default['body_html'])


class EmailLog(models.Model):
    """
    Log of all emails sent per tenant.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('bounced', 'Bounced'),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='email_logs'
    )
    template = models.ForeignKey(
        EmailTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    recipient_email = models.EmailField()
    recipient_name = models.CharField(max_length=200, blank=True)
    subject = models.CharField(max_length=500)
    body_preview = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'tenant_email_logs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Email to {self.recipient_email} - {self.status}"
    
    def mark_sent(self):
        """Mark email as sent."""
        self.status = 'sent'
        self.sent_at = timezone.now()
        self.save()
    
    def mark_failed(self, error_message):
        """Mark email as failed."""
        self.status = 'failed'
        self.error_message = error_message
        self.save()
