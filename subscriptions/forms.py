from django import forms
from django.utils import timezone
from django.contrib.auth import get_user_model
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Row, Column, Submit, HTML
from decimal import Decimal

from .models import (
    SubscriptionPlan, PaymentMethod, TenantSubscription,
    Invoice, SubscriptionFeature, UsageRecord
)

User = get_user_model()


class PlanSelectionForm(forms.Form):
    """
    Form for selecting a subscription plan.
    """
    plan = forms.ModelChoiceField(
        queryset=SubscriptionPlan.objects.public(),
        empty_label="Select a plan",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    payment_method = forms.ModelChoiceField(
        queryset=PaymentMethod.objects.none(),
        empty_label="Select a payment method",
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        if tenant:
            # Filter payment methods by tenant
            self.fields['payment_method'].queryset = PaymentMethod.objects.filter(
                tenant=tenant,
                is_active=True
            )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                'Choose Your Plan',
                Row(
                    Column('plan', css_class='form-group col-md-12 mb-3'),
                ),
            ),
            Fieldset(
                'Payment Method',
                Row(
                    Column('payment_method', css_class='form-group col-md-12 mb-3'),
                ),
            ),
            Submit('submit', 'Subscribe', css_class='btn btn-primary')
        )


class PaymentMethodForm(forms.ModelForm):
    """
    Form for adding/editing payment methods.
    """
    class Meta:
        model = PaymentMethod
        fields = ['method_type', 'details']
        widgets = {
            'method_type': forms.Select(attrs={'class': 'form-select'}),
            'details': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                'Payment Method Details',
                'method_type',
                'details',
                Submit('submit', 'Save Payment Method', css_class='btn btn-primary')
            )
        )
    
    def clean_details(self):
        """Validate the details JSON field."""
        details = self.cleaned_data.get('details')
        method_type = self.cleaned_data.get('method_type')
        
        if method_type == 'credit_card':
            # Validate credit card details
            required_fields = ['card_number', 'expiry_month', 'expiry_year', 'cvv']
            for field in required_fields:
                if not details.get(field):
                    raise forms.ValidationError(f"Credit card {field.replace('_', ' ')} is required.")
        
        elif method_type == 'bank_transfer':
            # Validate bank transfer details
            required_fields = ['account_number', 'routing_number', 'account_name']
            for field in required_fields:
                if not details.get(field):
                    raise forms.ValidationError(f"Bank {field.replace('_', ' ')} is required.")
        
        return details


class SubscriptionUpdateForm(forms.Form):
    """
    Form for updating subscription (upgrade/downgrade).
    """
    plan = forms.ModelChoiceField(
        queryset=SubscriptionPlan.objects.public(),
        empty_label="Select a new plan",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    def __init__(self, *args, **kwargs):
        current_plan = kwargs.pop('current_plan', None)
        super().__init__(*args, **kwargs)
        
        if current_plan:
            # Exclude current plan from options
            self.fields['plan'].queryset = SubscriptionPlan.objects.public().exclude(
                id=current_plan.id
            )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                'Update Your Subscription',
                Row(
                    Column('plan', css_class='form-group col-md-12 mb-3'),
                ),
            ),
            Submit('submit', 'Update Subscription', css_class='btn btn-primary')
        )


class InvoicePaymentForm(forms.Form):
    """
    Form for processing invoice payments.
    """
    payment_method = forms.ChoiceField(
        choices=[
            ('stripe', 'Credit Card (Stripe)'),
            ('paypal', 'PayPal'),
            ('bank_transfer', 'Bank Transfer'),
        ],
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                'Payment Method',
                'payment_method',
                Submit('submit', 'Process Payment', css_class='btn btn-primary')
            )
        )


class UsageFilterForm(forms.Form):
    """
    Form for filtering usage records.
    """
    feature = forms.ModelChoiceField(
        queryset=SubscriptionFeature.objects.filter(is_active=True),
        empty_label="All Features",
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    period = forms.ChoiceField(
        choices=[
            ('', 'All Periods'),
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
            ('yearly', 'Yearly'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                'Filter Usage Records',
                Row(
                    Column('feature', css_class='form-group col-md-6 mb-3'),
                    Column('period', css_class='form-group col-md-6 mb-3'),
                ),
                Row(
                    Column('date_from', css_class='form-group col-md-6 mb-3'),
                    Column('date_to', css_class='form-group col-md-6 mb-3'),
                ),
                Submit('submit', 'Filter', css_class='btn btn-primary')
            )
        )


class SubscriptionFeatureForm(forms.ModelForm):
    """
    Form for creating/editing subscription features.
    """
    class Meta:
        model = SubscriptionFeature
        fields = ['name', 'code', 'description', 'feature_type', 'default_value', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'feature_type': forms.Select(attrs={'class': 'form-select'}),
            'default_value': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                'Feature Details',
                'name',
                'code',
                'description',
                'feature_type',
                'default_value',
                'is_active',
                Submit('submit', 'Save Feature', css_class='btn btn-primary')
            )
        )


class PlanFeatureForm(forms.ModelForm):
    """
    Form for linking features to plans.
    """
    class Meta:
        model = None  # Will be set in __init__
        fields = ['value', 'is_included']
        widgets = {
            'value': forms.TextInput(attrs={'class': 'form-control'}),
            'is_included': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        plan = kwargs.pop('plan', None)
        super().__init__(*args, **kwargs)
        
        if plan:
            # Set the model dynamically based on the plan
            self._meta.model = type('TempPlanFeature', (forms.ModelForm,), {'Meta': type('Meta', (), {
                'model': None,
                'fields': ['value', 'is_included'],
                'widgets': {
                    'value': forms.TextInput(attrs={'class': 'form-control'}),
                    'is_included': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
                }
            })})
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                'Plan Feature Configuration',
                'value',
                'is_included',
                Submit('submit', 'Save', css_class='btn btn-primary')
            )
        )


class SubscriptionPlanForm(forms.ModelForm):
    """
    Form for creating/editing subscription plans.
    """
    class Meta:
        model = SubscriptionPlan
        fields = [
            'name', 'slug', 'plan_type', 'description', 'price',
            'billing_cycle', 'max_users', 'max_storage_mb',
            'is_active', 'is_public', 'trial_days', 'setup_fee'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
            'plan_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'billing_cycle': forms.Select(attrs={'class': 'form-select'}),
            'max_users': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_storage_mb': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'trial_days': forms.NumberInput(attrs={'class': 'form-control'}),
            'setup_fee': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                'Basic Information',
                Row(
                    Column('name', css_class='form-group col-md-6 mb-3'),
                    Column('slug', css_class='form-group col-md-6 mb-3'),
                ),
                Row(
                    Column('plan_type', css_class='form-group col-md-6 mb-3'),
                    Column('billing_cycle', css_class='form-group col-md-6 mb-3'),
                ),
            ),
            Fieldset(
                'Description',
                'description',
            ),
            Fieldset(
                'Pricing',
                Row(
                    Column('price', css_class='form-group col-md-6 mb-3'),
                    Column('setup_fee', css_class='form-group col-md-6 mb-3'),
                ),
            ),
            Fieldset(
                'Limits',
                Row(
                    Column('max_users', css_class='form-group col-md-6 mb-3'),
                    Column('max_storage_mb', css_class='form-group col-md-6 mb-3'),
                ),
            ),
            Fieldset(
                'Settings',
                Row(
                    Column('is_active', css_class='form-group col-md-4 mb-3'),
                    Column('is_public', css_class='form-group col-md-4 mb-3'),
                    Column('trial_days', css_class='form-group col-md-4 mb-3'),
                ),
            ),
            Submit('submit', 'Save Plan', css_class='btn btn-primary')
        )


class UsageRecordForm(forms.ModelForm):
    """
    Form for creating/editing usage records.
    """
    class Meta:
        model = UsageRecord
        fields = ['feature', 'current_usage', 'limit', 'period', 'period_start', 'period_end']
        widgets = {
            'feature': forms.Select(attrs={'class': 'form-select'}),
            'current_usage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'limit': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'period': forms.Select(attrs={'class': 'form-select'}),
            'period_start': forms.DateTimeInput(attrs={'class': 'form-control'}),
            'period_end': forms.DateTimeInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                'Usage Record Details',
                Row(
                    Column('feature', css_class='form-group col-md-6 mb-3'),
                    Column('period', css_class='form-group col-md-6 mb-3'),
                ),
                Row(
                    Column('current_usage', css_class='form-group col-md-6 mb-3'),
                    Column('limit', css_class='form-group col-md-6 mb-3'),
                ),
                Row(
                    Column('period_start', css_class='form-group col-md-6 mb-3'),
                    Column('period_end', css_class='form-group col-md-6 mb-3'),
                ),
                Submit('submit', 'Save Usage Record', css_class='btn btn-primary')
            )
        )