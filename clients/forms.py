from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Client


class ClientForm(forms.ModelForm):
    """
    Form for creating and updating clients.
    """
    class Meta:
        model = Client
        fields = [
            'first_name',
            'last_name',
            'email',
            'phone',
            'address',
            'company',
            'occupation',
            'case_history',
            'notes',
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter first name',
                'autofocus': True
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter last name'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter email address'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter phone number'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter address'
            }),
            'company': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter company name'
            }),
            'occupation': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter occupation'
            }),
            'case_history': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Enter case history'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Enter additional notes'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make all fields required except optional ones
        self.fields['phone'].required = False
        self.fields['address'].required = False
        self.fields['company'].required = False
        self.fields['occupation'].required = False
        self.fields['case_history'].required = False
        self.fields['notes'].required = False
        
        # Add help text
        self.fields['case_history'].help_text = _("Brief history of legal cases involving this client")
        self.fields['notes'].help_text = _("Additional notes about the client")
    
    def clean_email(self):
        """Validate email format and uniqueness within tenant."""
        email = self.cleaned_data.get('email')
        if not email:
            raise forms.ValidationError(_("Email is required"))
        
        # Check if email already exists for this tenant (for update case)
        if self.instance and self.instance.pk:
            # This is an update, so exclude the current instance
            if Client.objects.filter(
                email__iexact=email, 
                tenant=self.instance.tenant
            ).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError(_("A client with this email already exists"))
        else:
            # This is a create operation, but we don't have tenant yet
            # The uniqueness check will be done in the view
            pass
        
        return email.lower()


class ClientSearchForm(forms.Form):
    """
    Form for searching clients.
    """
    query = forms.CharField(
        label=_('Search'),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by name, email, or company...',
            'autocomplete': 'off'
        }),
        required=False
    )