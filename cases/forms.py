from django import forms
from django.utils import timezone
from .models import Case, CaseEvent
from clients.models import Client


class CaseForm(forms.ModelForm):
    """
    Form for creating and updating Case instances.
    """
    class Meta:
        model = Case
        fields = [
            'title', 'case_number', 'description', 'status', 'case_type',
            'client', 'assigned_lawyers', 'start_date', 'end_date', 'outcome', 'notes'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter case title'
            }),
            'case_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter case number'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Enter case description'
            }),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'case_type': forms.Select(attrs={'class': 'form-control'}),
            'client': forms.Select(attrs={'class': 'form-control'}),
            'assigned_lawyers': forms.CheckboxSelectMultiple(),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'end_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'outcome': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Enter case outcome'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Enter additional notes'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter clients by tenant
        if self.tenant:
            self.fields['client'].queryset = Client.objects.active_for_tenant(self.tenant)
        
        # Filter assigned lawyers by tenant
        if self.tenant:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            self.fields['assigned_lawyers'].queryset = User.objects.filter(
                tenant=self.tenant,
                is_active=True
            )
    
    def clean_case_number(self):
        """Validate that the case number is unique within the tenant."""
        case_number = self.cleaned_data['case_number']
        
        if self.tenant:
            queryset = Case.objects.filter(
                case_number=case_number,
                tenant=self.tenant
            )
            
            # Exclude current instance if updating
            if self.instance and self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            
            if queryset.exists():
                raise forms.ValidationError(
                    'A case with this number already exists for your firm.'
                )
        
        return case_number
    
    def clean_end_date(self):
        """Validate that end_date is after start_date."""
        start_date = self.cleaned_data.get('start_date')
        end_date = self.cleaned_data.get('end_date')
        
        if start_date and end_date and end_date < start_date:
            raise forms.ValidationError(
                'End date cannot be before start date.'
            )
        
        return end_date


class CaseEventForm(forms.ModelForm):
    """
    Form for creating and updating CaseEvent instances.
    """
    class Meta:
        model = CaseEvent
        fields = ['event_type', 'title', 'description', 'event_date']
        widgets = {
            'event_type': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter event title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Enter event description'
            }),
            'event_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        self.case = kwargs.pop('case', None)
        super().__init__(*args, **kwargs)
        
        # Set default event_date to current datetime
        if not self.instance.pk:  # Only for new events
            self.fields['event_date'].initial = timezone.now().strftime('%Y-%m-%dT%H:%M')


class CaseSearchForm(forms.Form):
    """
    Form for searching cases.
    """
    query = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search cases...'
        })
    )
    
    status = forms.ChoiceField(
        choices=[('', 'All Status')] + Case.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    case_type = forms.ChoiceField(
        choices=[('', 'All Types')] + Case.CASE_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    client = forms.ModelChoiceField(
        queryset=Client.objects.none(),
        required=False,
        empty_label="All Clients",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    assigned_lawyer = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="All Lawyers",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        if self.tenant:
            # Filter clients by tenant
            self.fields['client'].queryset = Client.objects.active_for_tenant(self.tenant)
            
            # Filter lawyers by tenant
            from django.contrib.auth import get_user_model
            User = get_user_model()
            self.fields['assigned_lawyer'].queryset = User.objects.filter(
                tenant=self.tenant,
                is_active=True
            )
    
    def clean(self):
        """Validate date range."""
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        
        if date_from and date_to and date_from > date_to:
            raise forms.ValidationError(
                'Start date cannot be after end date.'
            )
        
        return cleaned_data


class CaseEventSearchForm(forms.Form):
    """
    Form for searching case events.
    """
    query = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search events...'
        })
    )
    
    event_type = forms.ChoiceField(
        choices=[('', 'All Types')] + CaseEvent.EVENT_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    def clean(self):
        """Validate date range."""
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        
        if date_from and date_to and date_from > date_to:
            raise forms.ValidationError(
                'Start date cannot be after end date.'
            )
        
        return cleaned_data