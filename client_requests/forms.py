from django import forms
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from .models import ClientRequest, RequestNote

User = get_user_model()


class ClientRequestForm(forms.ModelForm):
    """
    Form for creating and updating client requests.
    """
    class Meta:
        model = ClientRequest
        fields = [
            'title',
            'description',
            'request_type',
            'priority',
            'client_name',
            'client_email',
            'client_phone',
            'client_company',
            'preferred_contact_method',
            'preferred_contact_time',
            'budget_range',
            'urgency_details',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter request title',
                'autofocus': True
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Describe your legal needs in detail...'
            }),
            'request_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'priority': forms.Select(attrs={
                'class': 'form-control'
            }),
            'client_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter client full name'
            }),
            'client_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter client email address'
            }),
            'client_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter client phone number'
            }),
            'client_company': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter client company (optional)'
            }),
            'preferred_contact_method': forms.Select(attrs={
                'class': 'form-control'
            }),
            'preferred_contact_time': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'e.g., Weekdays 9-5, Evenings only, etc.'
            }),
            'budget_range': forms.Select(attrs={
                'class': 'form-control'
            }),
            'urgency_details': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Explain why this is urgent (if applicable)'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make all fields required except optional ones
        self.fields['client_phone'].required = False
        self.fields['client_company'].required = False
        self.fields['preferred_contact_time'].required = False
        self.fields['urgency_details'].required = False
        
        # Add help text
        self.fields['description'].help_text = _("Provide a detailed description of your legal needs")
        self.fields['preferred_contact_time'].help_text = _("When is the best time to contact you?")
        self.fields['urgency_details'].help_text = _("If this matter is urgent, please explain why")
    
    def clean_client_email(self):
        """Validate client email format."""
        email = self.cleaned_data.get('client_email')
        if not email:
            raise forms.ValidationError(_("Client email is required"))
        return email.lower()
    
    def clean_title(self):
        """Validate title."""
        title = self.cleaned_data.get('title')
        if not title or len(title.strip()) < 5:
            raise forms.ValidationError(_("Title must be at least 5 characters long"))
        return title.strip()
    
    def clean_description(self):
        """Validate description."""
        description = self.cleaned_data.get('description')
        if not description or len(description.strip()) < 20:
            raise forms.ValidationError(_("Description must be at least 20 characters long"))
        return description.strip()


class ClientRequestUpdateForm(forms.ModelForm):
    """
    Form for updating client requests (includes workflow fields).
    """
    class Meta:
        model = ClientRequest
        fields = [
            'title',
            'description',
            'request_type',
            'priority',
            'status',
            'client_name',
            'client_email',
            'client_phone',
            'client_company',
            'preferred_contact_method',
            'preferred_contact_time',
            'budget_range',
            'urgency_details',
            'assigned_lawyer',
            'rejection_reason',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5
            }),
            'request_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'priority': forms.Select(attrs={
                'class': 'form-control'
            }),
            'status': forms.Select(attrs={
                'class': 'form-control'
            }),
            'client_name': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'client_email': forms.EmailInput(attrs={
                'class': 'form-control'
            }),
            'client_phone': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'client_company': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'preferred_contact_method': forms.Select(attrs={
                'class': 'form-control'
            }),
            'preferred_contact_time': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2
            }),
            'budget_range': forms.Select(attrs={
                'class': 'form-control'
            }),
            'urgency_details': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),
            'assigned_lawyer': forms.Select(attrs={
                'class': 'form-control'
            }),
            'rejection_reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Provide reason for rejection...'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        # Filter assigned_lawyer choices by tenant
        if tenant and 'assigned_lawyer' in self.fields:
            self.fields['assigned_lawyer'].queryset = User.objects.filter(  # type: ignore
                tenant=tenant,
                is_active=True
            ).order_by('first_name', 'last_name')
        
        # Make rejection reason required when status is rejected
        if self.instance and self.instance.status == 'rejected':
            self.fields['rejection_reason'].required = True
    
    def clean(self):
        """Custom validation for form fields."""
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        rejection_reason = cleaned_data.get('rejection_reason')
        
        # Require rejection reason when status is rejected
        if status == 'rejected' and not rejection_reason:
            self.add_error('rejection_reason', _('Rejection reason is required when rejecting a request'))
        
        return cleaned_data


class RequestNoteForm(forms.ModelForm):
    """
    Form for adding notes to client requests.
    """
    class Meta:
        model = RequestNote
        fields = [
            'note',
            'is_internal',
        ]
        widgets = {
            'note': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Enter your note here...',
                'autofocus': True
            }),
            'is_internal': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['is_internal'].help_text = _(
            "Internal notes are only visible to staff members, not to clients"
        )
    
    def clean_note(self):
        """Validate note content."""
        note = self.cleaned_data.get('note')
        if not note or len(note.strip()) < 3:
            raise forms.ValidationError(_("Note must be at least 3 characters long"))
        return note.strip()


class ClientRequestSearchForm(forms.Form):
    """
    Form for searching client requests.
    """
    query = forms.CharField(
        label=_('Search'),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by title, client name, email, or company...',
            'autocomplete': 'off'
        }),
        required=False
    )
    
    status = forms.ChoiceField(
        label=_('Status'),
        choices=[('', 'All Statuses')] + ClientRequest.STATUS_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        required=False
    )
    
    priority = forms.ChoiceField(
        label=_('Priority'),
        choices=[('', 'All Priorities')] + ClientRequest.PRIORITY_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        required=False
    )
    
    request_type = forms.ChoiceField(
        label=_('Request Type'),
        choices=[('', 'All Types')] + ClientRequest.REQUEST_TYPE_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        required=False
    )
    
    date_from = forms.DateField(
        label=_('From Date'),
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        required=False
    )
    
    date_to = forms.DateField(
        label=_('To Date'),
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        required=False
    )


class ClientRequestAssignForm(forms.Form):
    """
    Form for assigning a lawyer to a client request.
    """
    assigned_lawyer = forms.ModelChoiceField(
        label=_('Assign to Lawyer'),
        queryset=User.objects.none(),
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        required=False
    )
    
    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        if tenant:
            self.fields['assigned_lawyer'].queryset = User.objects.filter(
                tenant=tenant,
                is_active=True
            ).order_by('first_name', 'last_name')  # type: ignore


class ClientRequestReviewForm(forms.Form):
    """
    Form for reviewing client requests (approve/reject).
    """
    action = forms.ChoiceField(
        label=_('Action'),
        choices=[
            ('approve', 'Approve Request'),
            ('reject', 'Reject Request'),
        ],
        widget=forms.RadioSelect(attrs={
            'class': 'form-check-input'
        }),
        required=True
    )
    
    rejection_reason = forms.CharField(
        label=_('Rejection Reason'),
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Please provide a reason for rejection...'
        }),
        required=False
    )
    
    notes = forms.CharField(
        label=_('Review Notes'),
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Add any additional notes about this review...'
        }),
        required=False
    )
    
    def clean(self):
        """Custom validation for review form."""
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        rejection_reason = cleaned_data.get('rejection_reason')
        
        # Require rejection reason when action is reject
        if action == 'reject' and not rejection_reason:
            self.add_error('rejection_reason', _('Rejection reason is required when rejecting a request'))
        
        return cleaned_data