from django import forms
from django.utils import timezone
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Field, Div, HTML
from django.core.exceptions import ValidationError
from django.db.models import Q
from clients.models import Client
from cases.models import Case, CaseEvent
from documents.models import Document
from billing.models import TimeEntry, Expense
from .models import LawyerProfile, PracticeArea, LawyerQualification


class ClientForm(forms.ModelForm):
    """Form for creating and editing clients."""
    
    class Meta:
        model = Client
        fields = ['first_name', 'last_name', 'email', 'phone', 'address', 'company', 'occupation', 'notes']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('first_name', css_class='form-group col-md-6 mb-0'),
                Column('last_name', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            'email',
            'phone',
            'address',
            Row(
                Column('company', css_class='form-group col-md-6 mb-0'),
                Column('occupation', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            'notes',
            Submit('submit', 'Save Client', css_class='btn btn-primary')
        )


class CaseForm(forms.ModelForm):
    """Form for creating and editing cases."""
    
    class Meta:
        model = Case
        fields = ['title', 'case_number', 'description', 'status', 'case_type', 'client', 'assigned_lawyers', 'start_date', 'end_date', 'notes']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Filter clients and lawyers by tenant
        if self.request and hasattr(self.request, 'tenant'):
            self.fields['client'].queryset = Client.objects.filter(tenant=self.request.tenant, deleted_at__isnull=True)  # type: ignore
            self.fields['assigned_lawyers'].queryset = self.request.tenant.users.filter(role__in=['lawyer', 'admin'])  # type: ignore
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('title', css_class='form-group col-md-8 mb-0'),
                Column('case_number', css_class='form-group col-md-4 mb-0'),
                css_class='form-row'
            ),
            Row(
                Column('status', css_class='form-group col-md-6 mb-0'),
                Column('case_type', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            'client',
            'assigned_lawyers',
            Row(
                Column('start_date', css_class='form-group col-md-6 mb-0'),
                Column('end_date', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            'description',
            'notes',
            Submit('submit', 'Save Case', css_class='btn btn-primary')
        )


class CaseEventForm(forms.ModelForm):
    """Form for adding events to cases."""
    
    class Meta:
        model = CaseEvent
        fields = ['event_type', 'title', 'description', 'event_date']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'event_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default event date to current datetime
        if not self.instance.pk:
            self.fields['event_date'].initial = timezone.now()
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'event_type',
            'title',
            'description',
            'event_date',
            Submit('submit', 'Add Event', css_class='btn btn-primary')
        )


class DocumentForm(forms.ModelForm):
    """Form for uploading and editing documents."""
    
    class Meta:
        model = Document
        fields = ['title', 'description', 'file', 'category', 'access_level', 'case', 'client', 'tags']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'tags': forms.TextInput(attrs={'placeholder': 'Enter tags separated by commas'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Filter cases and clients by tenant
        if self.request and hasattr(self.request, 'tenant'):
            self.fields['case'].queryset = Case.objects.filter(tenant=self.request.tenant, deleted_at__isnull=True)  # type: ignore
            self.fields['client'].queryset = Client.objects.filter(tenant=self.request.tenant, deleted_at__isnull=True)  # type: ignore
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'title',
            'description',
            'file',
            Row(
                Column('category', css_class='form-group col-md-6 mb-0'),
                Column('access_level', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            Row(
                Column('case', css_class='form-group col-md-6 mb-0'),
                Column('client', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            'tags',
            Submit('submit', 'Upload Document', css_class='btn btn-primary')
        )


class TimeEntryForm(forms.ModelForm):
    """Form for creating and editing time entries."""
    
    class Meta:
        model = TimeEntry
        fields = ['case', 'hours', 'rate', 'description', 'date', 'is_billable']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'date': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Filter cases by tenant and assigned lawyer
        if self.request and hasattr(self.request, 'tenant'):
            self.fields['case'].queryset = Case.objects.filter(  # type: ignore
                tenant=self.request.tenant,
                deleted_at__isnull=True,
                assigned_lawyers=self.request.user
            )
        
        # Set default values
        if not self.instance.pk:
            self.fields['date'].initial = timezone.now().date()
            self.fields['lawyer'].initial = self.request.user
            self.fields['rate'].initial = self._get_default_rate()
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'case',
            Row(
                Column('hours', css_class='form-group col-md-4 mb-0'),
                Column('rate', css_class='form-group col-md-4 mb-0'),
                Column('is_billable', css_class='form-group col-md-4 mb-0'),
                css_class='form-row'
            ),
            'date',
            'description',
            Submit('submit', 'Log Time', css_class='btn btn-primary')
        )
    
    def _get_default_rate(self):
        """Get default billing rate for the current user."""
        from billing.models import BillingRate
        try:
            # Try to get the latest billing rate for the user's role
            role_mapping = {
                'admin': 'partner',
                'lawyer': 'associate',
                'paralegal': 'paralegal',
            }
            role = role_mapping.get(self.request.user.role, 'associate')  # type: ignore
            rate = BillingRate.objects.filter(  # type: ignore
                tenant=self.request.tenant,
                role=role
            ).latest('effective_date')
            return rate.default_rate
        except Exception:
            return 150.00  # Default fallback rate


class ExpenseForm(forms.ModelForm):
    """Form for creating and editing expenses."""
    
    class Meta:
        model = Expense
        fields = ['description', 'amount', 'category', 'receipt', 'date', 'is_reimbursable', 'case']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Filter cases by tenant and assigned lawyer
        if self.request and hasattr(self.request, 'tenant'):
            self.fields['case'].queryset = Case.objects.filter(  # type: ignore
                tenant=self.request.tenant,
                deleted_at__isnull=True,
                assigned_lawyers=self.request.user
            )
        
        # Set default values
        if not self.instance.pk:
            self.fields['date'].initial = timezone.now().date()
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'description',
            Row(
                Column('amount', css_class='form-group col-md-6 mb-0'),
                Column('category', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            'receipt',
            Row(
                Column('date', css_class='form-group col-md-6 mb-0'),
                Column('is_reimbursable', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            'case',
            Submit('submit', 'Add Expense', css_class='btn btn-primary')
        )


class QuickSearchForm(forms.Form):
    """Form for quick search across different modules."""
    query = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search cases, clients, documents...',
            'autocomplete': 'off'
        })
    )
    search_type = forms.ChoiceField(
        choices=[
            ('all', 'All'),
            ('cases', 'Cases'),
            ('clients', 'Clients'),
            ('documents', 'Documents'),
        ],
        initial='all',
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class LawyerProfileForm(forms.ModelForm):
    """Form for creating and editing lawyer profiles."""
    
    class Meta:
        model = LawyerProfile
        fields = [
            'bar_number', 'law_school', 'graduation_year', 'experience_level',
            'years_of_experience', 'practice_areas', 'specializations',
            'billing_method', 'hourly_rate', 'consultation_fee', 'retainer_fee',
            'contingency_percentage', 'bio', 'languages', 'website', 'linkedin_profile',
            'is_available', 'max_cases'
        ]
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4}),
            'specializations': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Enter specializations separated by commas'}),
            'languages': forms.TextInput(attrs={'placeholder': 'Enter languages separated by commas'}),
            'website': forms.URLInput(attrs={'placeholder': 'https://example.com'}),
            'linkedin_profile': forms.URLInput(attrs={'placeholder': 'https://linkedin.com/in/username'}),
            'graduation_year': forms.NumberInput(attrs={'min': 1900, 'max': timezone.now().year + 10}),
            'years_of_experience': forms.NumberInput(attrs={'min': 0}),
            'hourly_rate': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'consultation_fee': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'retainer_fee': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'contingency_percentage': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'max': '100'}),
            'max_cases': forms.NumberInput(attrs={'min': 1}),
            'practice_areas': forms.CheckboxSelectMultiple(),
        }
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Filter practice areas by tenant
        if self.request and hasattr(self.request, 'tenant'):
            self.fields['practice_areas'].queryset = PracticeArea.objects.filter(  # type: ignore
                tenant=self.request.tenant,
                is_active=True
            )
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h4>Professional Information</h4>'),
            Row(
                Column('bar_number', css_class='form-group col-md-6 mb-0'),
                Column('law_school', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            Row(
                Column('graduation_year', css_class='form-group col-md-4 mb-0'),
                Column('experience_level', css_class='form-group col-md-4 mb-0'),
                Column('years_of_experience', css_class='form-group col-md-4 mb-0'),
                css_class='form-row'
            ),
            
            HTML('<hr><h4>Specialization</h4>'),
            'practice_areas',
            'specializations',
            
            HTML('<hr><h4>Billing Information</h4>'),
            Row(
                Column('billing_method', css_class='form-group col-md-6 mb-0'),
                Column('consultation_fee', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            Row(
                Column('hourly_rate', css_class='form-group col-md-4 mb-0'),
                Column('retainer_fee', css_class='form-group col-md-4 mb-0'),
                Column('contingency_percentage', css_class='form-group col-md-4 mb-0'),
                css_class='form-row'
            ),
            
            HTML('<hr><h4>Professional Details</h4>'),
            'bio',
            Row(
                Column('languages', css_class='form-group col-md-6 mb-0'),
                Column('website', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            'linkedin_profile',
            
            HTML('<hr><h4>Availability</h4>'),
            Row(
                Column('is_available', css_class='form-group col-md-6 mb-0'),
                Column('max_cases', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            
            Submit('submit', 'Save Profile', css_class='btn btn-primary')
        )
    
    def clean(self):
        cleaned_data = super().clean()
        billing_method = cleaned_data.get('billing_method')
        hourly_rate = cleaned_data.get('hourly_rate')
        consultation_fee = cleaned_data.get('consultation_fee')
        retainer_fee = cleaned_data.get('retainer_fee')
        contingency_percentage = cleaned_data.get('contingency_percentage')
        
        # Validate billing method fields
        if billing_method == 'hourly' and not hourly_rate:
            raise ValidationError('Hourly rate is required for hourly billing method.')
        
        if billing_method == 'fixed' and not hourly_rate:
            raise ValidationError('Base rate is required for fixed fee billing method.')
        
        if billing_method == 'contingency' and not contingency_percentage:
            raise ValidationError('Contingency percentage is required for contingency billing method.')
        
        if billing_method == 'retainer' and not retainer_fee:
            raise ValidationError('Retainer fee is required for retainer billing method.')
        
        if billing_method == 'hybrid':
            if not hourly_rate:
                raise ValidationError('Hourly rate is required for hybrid billing method.')
            if not retainer_fee:
                raise ValidationError('Retainer fee is required for hybrid billing method.')
        
        return cleaned_data


class PracticeAreaForm(forms.ModelForm):
    """Form for creating and editing practice areas."""
    
    class Meta:
        model = PracticeArea
        fields = ['name', 'description', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'name',
            'description',
            'is_active',
            Submit('submit', 'Save Practice Area', css_class='btn btn-primary')
        )
    
    def clean_name(self):
        name = self.cleaned_data['name']
        tenant = getattr(self.instance, 'tenant', None) or getattr(self, 'tenant', None)  # type: ignore
        
        # Check for duplicate practice area name within the same tenant
        if tenant and PracticeArea.objects.filter(name__iexact=name, tenant=tenant).exclude(pk=self.instance.pk).exists():
            raise ValidationError('A practice area with this name already exists for your firm.')
        
        return name


class LawyerQualificationForm(forms.ModelForm):
    """Form for creating and editing lawyer qualifications."""
    
    class Meta:
        model = LawyerQualification
        fields = ['qualification_type', 'title', 'institution', 'year_obtained', 'description', 'certificate_file']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'year_obtained': forms.NumberInput(attrs={'min': 1900, 'max': timezone.now().year + 10}),
        }
    
    def __init__(self, *args, **kwargs):
        self.lawyer_profile = kwargs.pop('lawyer_profile', None)
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('qualification_type', css_class='form-group col-md-6 mb-0'),
                Column('year_obtained', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            'title',
            'institution',
            'description',
            'certificate_file',
            Submit('submit', 'Save Qualification', css_class='btn btn-primary')
        )
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.lawyer_profile:
            instance.lawyer_profile = self.lawyer_profile
            instance.tenant = self.lawyer_profile.tenant
        if commit:
            instance.save()
        return instance


class LawyerProfileSearchForm(forms.Form):
    """Form for searching and filtering lawyer profiles."""
    
    search = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by name, bar number, law school...'
        })
    )
    
    experience_level = forms.MultipleChoiceField(
        choices=LawyerProfile.EXPERIENCE_LEVELS,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    
    practice_areas = forms.ModelMultipleChoiceField(
        queryset=PracticeArea.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    
    billing_method = forms.MultipleChoiceField(
        choices=LawyerProfile.BILLING_METHODS,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    
    is_available = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    min_experience = forms.IntegerField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Min years'})
    )
    
    max_experience = forms.IntegerField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Max years'})
    )
    
    has_qualifications = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Filter practice areas by tenant
        if self.request and hasattr(self.request, 'tenant'):
            self.fields['practice_areas'].queryset = PracticeArea.objects.filter(  # type: ignore
                tenant=self.request.tenant,
                is_active=True
            )
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'search',
            HTML('<h5>Experience Level</h5>'),
            'experience_level',
            HTML('<h5>Practice Areas</h5>'),
            'practice_areas',
            HTML('<h5>Billing Method</h5>'),
            'billing_method',
            HTML('<h5>Experience Range</h5>'),
            Row(
                Column('min_experience', css_class='form-group col-md-6 mb-0'),
                Column('max_experience', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            Row(
                Column('is_available', css_class='form-group col-md-4 mb-0'),
                Column('has_qualifications', css_class='form-group col-md-4 mb-0'),
                Column(Submit('search', 'Search', css_class='btn btn-primary mt-4'), css_class='form-group col-md-4 mb-0 d-flex align-items-end'),
                css_class='form-row'
            )
        )
    
    def clean(self):
        cleaned_data = super().clean()
        min_exp = cleaned_data.get('min_experience')
        max_exp = cleaned_data.get('max_experience')
        
        if min_exp and max_exp and min_exp > max_exp:
            raise ValidationError('Minimum experience cannot be greater than maximum experience.')
        
        return cleaned_data


class LawyerAvailabilityForm(forms.ModelForm):
    """Form for updating lawyer availability settings."""
    
    class Meta:
        model = LawyerProfile
        fields = ['is_available', 'max_cases']
        widgets = {
            'max_cases': forms.NumberInput(attrs={'min': 1}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'is_available',
            'max_cases',
            Submit('submit', 'Update Availability', css_class='btn btn-primary')
        )