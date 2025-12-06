from django import forms
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.contrib.auth import get_user_model
from .models import Document

User = get_user_model()


class DocumentForm(forms.ModelForm):
    """
    Form for creating and updating documents.
    """
    tags = forms.CharField(
        max_length=500,
        required=False,
        help_text="Enter tags separated by commas",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., contract, urgent, client-name'
        })
    )
    
    class Meta:
        model = Document
        fields = [
            'title', 'description', 'file', 'category', 'access_level',
            'case', 'client', 'tags'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter document title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Enter document description'
            }),
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.jpg,.jpeg,.png,.gif'
            }),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'access_level': forms.Select(attrs={'class': 'form-control'}),
            'case': forms.Select(attrs={'class': 'form-control'}),
            'client': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        # Filter case and client options by tenant
        if self.tenant:
            self.fields['case'].queryset = self.fields['case'].queryset.filter(
                tenant=self.tenant, deleted_at__isnull=True
            )
            self.fields['client'].queryset = self.fields['client'].queryset.filter(
                tenant=self.tenant, deleted_at__isnull=True
            )
        
        # Add empty choice for case and client
        self.fields['case'].empty_label = "-- Select Case (Optional) --"
        self.fields['client'].empty_label = "-- Select Client (Optional) --"
        
        # Set required fields
        self.fields['title'].required = True
        self.fields['file'].required = True
        self.fields['category'].required = True
        self.fields['access_level'].required = True
    
    def clean_file(self):
        """
        Validate the uploaded file.
        """
        file = self.cleaned_data.get('file')
        if not file:
            return file
        
        # Check file size (50MB limit)
        max_size = 50 * 1024 * 1024  # 50MB in bytes
        if file.size > max_size:
            raise ValidationError(f"File size cannot exceed 50MB. Current size: {file.size / (1024*1024):.2f}MB")
        
        # Check file type
        allowed_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', 
                             '.txt', '.jpg', '.jpeg', '.png', '.gif', '.zip', '.rar']
        file_extension = file.name.lower().split('.')[-1]
        if f'.{file_extension}' not in allowed_extensions:
            raise ValidationError(f"File type '.{file_extension}' is not allowed. Allowed types: {', '.join(allowed_extensions)}")
        
        # Check storage quota for tenant
        if self.tenant:
            current_storage = self.tenant.get_storage_used()
            available_storage = (self.tenant.max_storage_mb * 1024 * 1024) - current_storage
            if file.size > available_storage:
                raise ValidationError(
                    f"File size exceeds available storage quota. "
                    f"Available: {available_storage / (1024*1024):.2f}MB, "
                    f"Required: {file.size / (1024*1024):.2f}MB"
                )
        
        return file
    
    def clean_tags(self):
        """
        Clean and format tags.
        """
        tags = self.cleaned_data.get('tags', '')
        if tags:
            # Split by comma, strip whitespace, and remove empty tags
            tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
            # Remove duplicates and join back with comma
            unique_tags = []
            for tag in tag_list:
                if tag.lower() not in [t.lower() for t in unique_tags]:
                    unique_tags.append(tag)
            return ', '.join(unique_tags)
        return tags
    
    def save(self, commit=True):
        """
        Save the document with tenant and user information.
        """
        document = super().save(commit=False)
        
        if self.tenant:
            document.tenant = self.tenant
        
        if self.user:
            document.uploaded_by = self.user
        
        if commit:
            document.save()
        
        return document


class DocumentUpdateForm(forms.ModelForm):
    """
    Form for updating document details (without changing the file).
    """
    tags = forms.CharField(
        max_length=500,
        required=False,
        help_text="Enter tags separated by commas",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., contract, urgent, client-name'
        })
    )
    
    class Meta:
        model = Document
        fields = [
            'title', 'description', 'category', 'access_level',
            'case', 'client', 'tags'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter document title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Enter document description'
            }),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'access_level': forms.Select(attrs={'class': 'form-control'}),
            'case': forms.Select(attrs={'class': 'form-control'}),
            'client': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        # Filter case and client options by tenant
        if self.tenant:
            self.fields['case'].queryset = self.fields['case'].queryset.filter(
                tenant=self.tenant, deleted_at__isnull=True
            )
            self.fields['client'].queryset = self.fields['client'].queryset.filter(
                tenant=self.tenant, deleted_at__isnull=True
            )
        
        # Add empty choice for case and client
        self.fields['case'].empty_label = "-- Select Case (Optional) --"
        self.fields['client'].empty_label = "-- Select Client (Optional) --"
        
        # Pre-populate tags field if instance exists
        if self.instance and self.instance.tags:
            self.fields['tags'].initial = self.instance.tags
    
    def clean_tags(self):
        """
        Clean and format tags.
        """
        tags = self.cleaned_data.get('tags', '')
        if tags:
            # Split by comma, strip whitespace, and remove empty tags
            tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
            # Remove duplicates and join back with comma
            unique_tags = []
            for tag in tag_list:
                if tag.lower() not in [t.lower() for t in unique_tags]:
                    unique_tags.append(tag)
            return ', '.join(unique_tags)
        return tags


class DocumentVersionForm(forms.ModelForm):
    """
    Form for uploading a new version of an existing document.
    """
    class Meta:
        model = Document
        fields = ['file']
        widgets = {
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.jpg,.jpeg,.png,.gif'
            })
        }
    
    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        self.parent_document = kwargs.pop('parent_document', None)
        super().__init__(*args, **kwargs)
        
        self.fields['file'].required = True
        self.fields['file'].label = "New Version File"
    
    def clean_file(self):
        """
        Validate the uploaded file for a new version.
        """
        file = self.cleaned_data.get('file')
        if not file:
            return file
        
        # Check file size (50MB limit)
        max_size = 50 * 1024 * 1024  # 50MB in bytes
        if file.size > max_size:
            raise ValidationError(f"File size cannot exceed 50MB. Current size: {file.size / (1024*1024):.2f}MB")
        
        # Check file type
        allowed_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', 
                             '.txt', '.jpg', '.jpeg', '.png', '.gif', '.zip', '.rar']
        file_extension = file.name.lower().split('.')[-1]
        if f'.{file_extension}' not in allowed_extensions:
            raise ValidationError(f"File type '.{file_extension}' is not allowed. Allowed types: {', '.join(allowed_extensions)}")
        
        # Check storage quota for tenant
        if self.tenant:
            current_storage = self.tenant.get_storage_used()
            available_storage = (self.tenant.max_storage_mb * 1024 * 1024) - current_storage
            if file.size > available_storage:
                raise ValidationError(
                    f"File size exceeds available storage quota. "
                    f"Available: {available_storage / (1024*1024):.2f}MB, "
                    f"Required: {file.size / (1024*1024):.2f}MB"
                )
        
        return file


class DocumentSearchForm(forms.Form):
    """
    Form for searching documents.
    """
    query = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search documents...'
        })
    )
    
    category = forms.ChoiceField(
        choices=[('', 'All Categories')] + Document.CATEGORY_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    access_level = forms.ChoiceField(
        choices=[('', 'All Access Levels')] + Document.ACCESS_LEVEL_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    file_type = forms.ChoiceField(
        choices=[('', 'All File Types')] + Document.DOCUMENT_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    case = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="All Cases",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    client = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="All Clients",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    tags = forms.CharField(
        max_length=255,
        required=False,
        help_text="Filter by tags (comma-separated)",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., contract, urgent'
        })
    )
    
    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        # Filter case and client options by tenant
        if self.tenant:
            from cases.models import Case
            from clients.models import Client
            
            self.fields['case'].queryset = Case.objects.filter(
                tenant=self.tenant, deleted_at__isnull=True
            )
            self.fields['client'].queryset = Client.objects.filter(
                tenant=self.tenant, deleted_at__isnull=True
            )