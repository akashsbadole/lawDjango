"""
Tenant Registration Forms
"""
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Field, Div, HTML

from .models import Tenant

User = get_user_model()


class TenantRegistrationForm(forms.ModelForm):
    """
    Form for registering a new tenant (law firm) with admin user.
    """
    # Admin user fields
    admin_email = forms.EmailField(
        label='Admin Email',
        widget=forms.EmailInput(attrs={
            'placeholder': 'admin@yourfirm.com',
            'hx-get': '/tenants/api/check-email/',
            'hx-trigger': 'blur',
            'hx-target': '#email-status'
        })
    )
    admin_password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'placeholder': '••••••••'})
    )
    admin_password_confirm = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={'placeholder': '••••••••'})
    )
    admin_first_name = forms.CharField(
        label='First Name',
        max_length=150,
        widget=forms.TextInput(attrs={'placeholder': 'John'})
    )
    admin_last_name = forms.CharField(
        label='Last Name',
        max_length=150,
        widget=forms.TextInput(attrs={'placeholder': 'Doe'})
    )
    
    # Plan selection
    plan = forms.ChoiceField(
        choices=[
            ('free', 'Free - 3 users, 10 cases'),
            ('pro', 'Pro - $99/mo - 10 users, unlimited cases'),
            ('enterprise', 'Enterprise - $299/mo - Unlimited'),
        ],
        initial='free',
        widget=forms.RadioSelect()
    )
    
    # Terms acceptance
    accept_terms = forms.BooleanField(
        label='I accept the Terms of Service and Privacy Policy',
        required=True
    )
    
    class Meta:
        model = Tenant
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'Your Law Firm Name',
                'hx-get': '/tenants/api/check-slug/',
                'hx-trigger': 'blur',
                'hx-target': '#slug-status',
                'hx-vals': 'js:{slug: this.value}'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h4 class="mb-3">Law Firm Information</h4>'),
            'name',
            HTML('<div id="slug-status" class="small text-muted mb-3"></div>'),
            
            HTML('<hr><h4 class="mb-3">Admin Account</h4>'),
            Row(
                Column('admin_first_name', css_class='form-group col-md-6 mb-0'),
                Column('admin_last_name', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            'admin_email',
            HTML('<div id="email-status" class="small text-muted mb-3"></div>'),
            Row(
                Column('admin_password', css_class='form-group col-md-6 mb-0'),
                Column('admin_password_confirm', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            
            HTML('<hr><h4 class="mb-3">Choose Your Plan</h4>'),
            'plan',
            
            HTML('<hr>'),
            'accept_terms',
            
            Submit('submit', 'Create Account', css_class='btn btn-primary btn-lg btn-block mt-4')
        )
    
    def clean_name(self):
        name = self.cleaned_data['name']
        slug = slugify(name)
        
        if len(slug) < 3:
            raise ValidationError('Firm name must be at least 3 characters.')
        
        return name
    
    def clean_admin_email(self):
        email = self.cleaned_data['admin_email']
        
        if User.objects.filter(email=email).exists():
            raise ValidationError('This email is already registered.')
        
        return email
    
    def clean_admin_password(self):
        password = self.cleaned_data['admin_password']
        validate_password(password)
        return password
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('admin_password')
        password_confirm = cleaned_data.get('admin_password_confirm')
        
        if password and password_confirm and password != password_confirm:
            raise ValidationError({'admin_password_confirm': 'Passwords do not match.'})
        
        return cleaned_data


class TenantOnboardingForm(forms.ModelForm):
    """Form for tenant onboarding steps."""
    
    class Meta:
        model = Tenant
        fields = ['name', 'phone', 'address', 'website']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'name',
            Row(
                Column('phone', css_class='form-group col-md-6 mb-0'),
                Column('website', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            'address',
            Submit('submit', 'Save & Continue', css_class='btn btn-primary')
        )


class TeamInviteForm(forms.Form):
    """Form for inviting team members."""
    
    email = forms.EmailField(
        label='Email Address',
        widget=forms.EmailInput(attrs={'placeholder': 'colleague@yourfirm.com'})
    )
    first_name = forms.CharField(
        label='First Name',
        max_length=150
    )
    last_name = forms.CharField(
        label='Last Name',
        max_length=150
    )
    role = forms.ChoiceField(
        choices=[
            ('lawyer', 'Lawyer'),
            ('paralegal', 'Paralegal'),
            ('billing_manager', 'Billing Manager'),
            ('staff', 'Read-only Staff'),
        ]
    )
    
    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('first_name', css_class='form-group col-md-6 mb-0'),
                Column('last_name', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            'email',
            'role',
            Submit('submit', 'Send Invitation', css_class='btn btn-primary')
        )
    
    def clean_email(self):
        email = self.cleaned_data['email']
        
        if User.objects.filter(email=email).exists():
            raise ValidationError('This email is already registered.')
        
        return email
