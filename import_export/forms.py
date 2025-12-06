import json
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .models import ImportJob, ExportJob, ImportTemplate


class ImportJobForm(forms.ModelForm):
    """
    Form for creating and updating import jobs.
    """
    class Meta:
        model = ImportJob
        fields = [
            'model_type', 'file', 'file_format', 'field_mappings',
            'skip_header', 'update_existing', 'dry_run'
        ]
        widgets = {
            'model_type': forms.Select(attrs={'class': 'form-control'}),
            'file_format': forms.Select(attrs={'class': 'form-control'}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'field_mappings': forms.HiddenInput(),
            'skip_header': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'update_existing': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'dry_run': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set tenant and user
        if self.tenant:
            self.instance.tenant = self.tenant
        if self.user:
            self.instance.user = self.user
    
    def clean_file(self):
        """Validate the uploaded file."""
        file = self.cleaned_data.get('file')
        if not file:
            raise ValidationError(_("Please select a file to import."))
        
        # Check file size (max 50MB)
        max_size = 50 * 1024 * 1024  # 50MB in bytes
        if file.size > max_size:
            raise ValidationError(_("File size must be less than 50MB."))
        
        # Check file extension
        file_format = self.cleaned_data.get('file_format', 'csv')
        allowed_extensions = {
            'csv': ['.csv'],
            'xlsx': ['.xlsx', '.xls'],
            'json': ['.json']
        }
        
        file_extension = file.name.lower().split('.')[-1]
        if f".{file_extension}" not in allowed_extensions.get(file_format, []):
            raise ValidationError(
                _(f"File extension '.{file_extension}' is not valid for {file_format.upper()} format.")
            )
        
        return file
    
    def clean_field_mappings(self):
        """Validate field mappings JSON."""
        field_mappings = self.cleaned_data.get('field_mappings')
        if field_mappings:
            try:
                if isinstance(field_mappings, str):
                    json.loads(field_mappings)
                elif isinstance(field_mappings, dict):
                    pass  # Already a dict
                else:
                    raise ValidationError(_("Field mappings must be a valid JSON object."))
            except json.JSONDecodeError:
                raise ValidationError(_("Field mappings must be a valid JSON object."))
        
        return field_mappings


class ImportJobUpdateForm(forms.ModelForm):
    """
    Form for updating import job settings.
    """
    class Meta:
        model = ImportJob
        fields = ['field_mappings', 'skip_header', 'update_existing', 'dry_run']
        widgets = {
            'field_mappings': forms.HiddenInput(),
            'skip_header': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'update_existing': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'dry_run': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ExportJobForm(forms.ModelForm):
    """
    Form for creating and updating export jobs.
    """
    class Meta:
        model = ExportJob
        fields = [
            'model_type', 'export_type', 'file_format', 'filters',
            'selected_ids', 'field_selection', 'include_relations'
        ]
        widgets = {
            'model_type': forms.Select(attrs={'class': 'form-control'}),
            'export_type': forms.Select(attrs={'class': 'form-control'}),
            'file_format': forms.Select(attrs={'class': 'form-control'}),
            'filters': forms.HiddenInput(),
            'selected_ids': forms.HiddenInput(),
            'field_selection': forms.HiddenInput(),
            'include_relations': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set tenant and user
        if self.tenant:
            self.instance.tenant = self.tenant
        if self.user:
            self.instance.user = self.user
    
    def clean_filters(self):
        """Validate filters JSON."""
        filters = self.cleaned_data.get('filters')
        if filters:
            try:
                if isinstance(filters, str):
                    json.loads(filters)
                elif isinstance(filters, dict):
                    pass  # Already a dict
                else:
                    raise ValidationError(_("Filters must be a valid JSON object."))
            except json.JSONDecodeError:
                raise ValidationError(_("Filters must be a valid JSON object."))
        
        return filters
    
    def clean_selected_ids(self):
        """Validate selected IDs JSON."""
        selected_ids = self.cleaned_data.get('selected_ids')
        if selected_ids:
            try:
                if isinstance(selected_ids, str):
                    ids = json.loads(selected_ids)
                    if not isinstance(ids, list):
                        raise ValidationError(_("Selected IDs must be a list."))
                elif isinstance(selected_ids, list):
                    pass  # Already a list
                else:
                    raise ValidationError(_("Selected IDs must be a list."))
            except json.JSONDecodeError:
                raise ValidationError(_("Selected IDs must be a valid JSON array."))
        
        return selected_ids
    
    def clean_field_selection(self):
        """Validate field selection JSON."""
        field_selection = self.cleaned_data.get('field_selection')
        if field_selection:
            try:
                if isinstance(field_selection, str):
                    fields = json.loads(field_selection)
                    if not isinstance(fields, list):
                        raise ValidationError(_("Field selection must be a list."))
                elif isinstance(field_selection, list):
                    pass  # Already a list
                else:
                    raise ValidationError(_("Field selection must be a list."))
            except json.JSONDecodeError:
                raise ValidationError(_("Field selection must be a valid JSON array."))
        
        return field_selection


class ImportTemplateForm(forms.ModelForm):
    """
    Form for creating and updating import templates.
    """
    class Meta:
        model = ImportTemplate
        fields = [
            'name', 'description', 'model_type', 'field_mappings',
            'required_fields', 'default_values', 'validation_rules',
            'sample_file', 'skip_header', 'encoding', 'delimiter',
            'update_existing', 'is_public'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'model_type': forms.Select(attrs={'class': 'form-control'}),
            'field_mappings': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'required_fields': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'default_values': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'validation_rules': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'sample_file': forms.FileInput(attrs={'class': 'form-control'}),
            'skip_header': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'encoding': forms.Select(attrs={'class': 'form-control'}),
            'delimiter': forms.TextInput(attrs={'class': 'form-control'}),
            'update_existing': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set tenant and user
        if self.tenant:
            self.instance.tenant = self.tenant
        if self.user:
            self.instance.created_by = self.user
        
        # Add help text for JSON fields
        self.fields['field_mappings'].help_text = _(
            "JSON object mapping import file columns to model fields. "
            "Example: {\"First Name\": \"first_name\", \"Email\": \"email\"}"
        )
        self.fields['required_fields'].help_text = _(
            "JSON array of required field names. "
            "Example: [\"first_name\", \"last_name\", \"email\"]"
        )
        self.fields['default_values'].help_text = _(
            "JSON object with default values for fields. "
            "Example: {\"status\": \"active\", \"source\": \"import\"}"
        )
        self.fields['validation_rules'].help_text = _(
            "JSON object with validation rules for fields. "
            "Example: {\"email\": {\"type\": \"email\"}, \"age\": {\"type\": \"number\", \"min\": 18}}"
        )
    
    def clean_field_mappings(self):
        """Validate field mappings JSON."""
        field_mappings = self.cleaned_data.get('field_mappings')
        if field_mappings:
            try:
                if isinstance(field_mappings, str):
                    field_mappings = json.loads(field_mappings)
                
                if not isinstance(field_mappings, dict):
                    raise ValidationError(_("Field mappings must be a JSON object."))
                
                return field_mappings
            except json.JSONDecodeError:
                raise ValidationError(_("Field mappings must be a valid JSON object."))
        
        return field_mappings
    
    def clean_required_fields(self):
        """Validate required fields JSON."""
        required_fields = self.cleaned_data.get('required_fields')
        if required_fields:
            try:
                if isinstance(required_fields, str):
                    required_fields = json.loads(required_fields)
                
                if not isinstance(required_fields, list):
                    raise ValidationError(_("Required fields must be a JSON array."))
                
                return required_fields
            except json.JSONDecodeError:
                raise ValidationError(_("Required fields must be a valid JSON array."))
        
        return required_fields
    
    def clean_default_values(self):
        """Validate default values JSON."""
        default_values = self.cleaned_data.get('default_values')
        if default_values:
            try:
                if isinstance(default_values, str):
                    default_values = json.loads(default_values)
                
                if not isinstance(default_values, dict):
                    raise ValidationError(_("Default values must be a JSON object."))
                
                return default_values
            except json.JSONDecodeError:
                raise ValidationError(_("Default values must be a valid JSON object."))
        
        return default_values
    
    def clean_validation_rules(self):
        """Validate validation rules JSON."""
        validation_rules = self.cleaned_data.get('validation_rules')
        if validation_rules:
            try:
                if isinstance(validation_rules, str):
                    validation_rules = json.loads(validation_rules)
                
                if not isinstance(validation_rules, dict):
                    raise ValidationError(_("Validation rules must be a JSON object."))
                
                return validation_rules
            except json.JSONDecodeError:
                raise ValidationError(_("Validation rules must be a valid JSON object."))
        
        return validation_rules
    
    def clean_sample_file(self):
        """Validate the sample file."""
        sample_file = self.cleaned_data.get('sample_file')
        if sample_file:
            # Check file size (max 10MB)
            max_size = 10 * 1024 * 1024  # 10MB in bytes
            if sample_file.size > max_size:
                raise ValidationError(_("Sample file size must be less than 10MB."))
            
            # Check file extension
            allowed_extensions = ['.csv', '.xlsx', '.xls']
            file_extension = sample_file.name.lower().split('.')[-1]
            if f".{file_extension}" not in allowed_extensions:
                raise ValidationError(
                    _(f"File extension '.{file_extension}' is not allowed. "
                      f"Allowed extensions: {', '.join(allowed_extensions)}")
                )
        
        return sample_file


class FieldMappingForm(forms.Form):
    """
    Form for mapping import file fields to model fields.
    """
    def __init__(self, *args, **kwargs):
        self.import_fields = kwargs.pop('import_fields', [])
        self.model_fields = kwargs.pop('model_fields', [])
        self.existing_mappings = kwargs.pop('existing_mappings', {})
        super().__init__(*args, **kwargs)
        
        # Create a field for each import field
        for import_field in self.import_fields:
            field_name = f"map_{import_field}"
            self.fields[field_name] = forms.ChoiceField(
                choices=[('', '-- Do not import --')] + [(f, f) for f in self.model_fields],
                required=False,
                label=import_field,
                widget=forms.Select(attrs={'class': 'form-control'})
            )
            
            # Set initial value if mapping exists
            if import_field in self.existing_mappings:
                self.fields[field_name].initial = self.existing_mappings[import_field]
    
    def get_mappings(self):
        """Get the field mappings as a dictionary."""
        mappings = {}
        for import_field in self.import_fields:
            field_name = f"map_{import_field}"
            model_field = self.cleaned_data.get(field_name)
            if model_field:
                mappings[import_field] = model_field
        return mappings


class ExportFilterForm(forms.Form):
    """
    Form for filtering export data.
    """
    def __init__(self, *args, **kwargs):
        self.model_type = kwargs.pop('model_type', None)
        super().__init__(*args, **kwargs)
        
        # Add model-specific filter fields
        if self.model_type == 'clients':
            self.fields['first_name'] = forms.CharField(
                required=False,
                label=_('First Name'),
                widget=forms.TextInput(attrs={'class': 'form-control'})
            )
            self.fields['last_name'] = forms.CharField(
                required=False,
                label=_('Last Name'),
                widget=forms.TextInput(attrs={'class': 'form-control'})
            )
            self.fields['email'] = forms.CharField(
                required=False,
                label=_('Email'),
                widget=forms.TextInput(attrs={'class': 'form-control'})
            )
        
        elif self.model_type == 'cases':
            self.fields['title'] = forms.CharField(
                required=False,
                label=_('Title'),
                widget=forms.TextInput(attrs={'class': 'form-control'})
            )
            self.fields['case_number'] = forms.CharField(
                required=False,
                label=_('Case Number'),
                widget=forms.TextInput(attrs={'class': 'form-control'})
            )
            self.fields['status'] = forms.ChoiceField(
                required=False,
                label=_('Status'),
                choices=[('', 'All')] + [
                    ('open', 'Open'),
                    ('closed', 'Closed'),
                    ('pending', 'Pending'),
                    ('suspended', 'Suspended'),
                    ('appealed', 'Appealed'),
                    ('settled', 'Settled'),
                ],
                widget=forms.Select(attrs={'class': 'form-control'})
            )
        
        # Add date range filters
        self.fields['created_after'] = forms.DateField(
            required=False,
            label=_('Created After'),
            widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
        )
        self.fields['created_before'] = forms.DateField(
            required=False,
            label=_('Created Before'),
            widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
        )
    
    def get_filters(self):
        """Get the filters as a dictionary."""
        filters = {}
        for field_name, value in self.cleaned_data.items():
            if value:
                filters[field_name] = value
        return filters