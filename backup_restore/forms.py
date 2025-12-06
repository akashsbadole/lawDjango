from django import forms
from django.utils import timezone
from .models import BackupJob, RestoreJob, BackupSchedule


class BackupJobForm(forms.ModelForm):
    """
    Form for creating and updating backup jobs.
    """
    class Meta:
        model = BackupJob
        fields = [
            'name', 'description', 'backup_type',
            'include_database', 'include_media', 'include_documents', 'include_settings',
            'compressed', 'encrypted', 'parent_backup'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'backup_type': forms.Select(attrs={'class': 'form-select'}),
            'include_database': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'include_media': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'include_documents': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'include_settings': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'compressed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'encrypted': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'parent_backup': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        if tenant:
            # Filter parent backups by tenant
            self.fields['parent_backup'].queryset = BackupJob.objects.filter(
                tenant=tenant,
                status='completed',
                backup_type='full'
            )


class BackupJobWizardForm(forms.ModelForm):
    """
    Form for creating backup jobs with wizard-like interface.
    """
    class Meta:
        model = BackupJob
        fields = [
            'name', 'description', 'backup_type',
            'include_database', 'include_media', 'include_documents', 'include_settings',
            'compressed', 'encrypted'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'backup_type': forms.Select(attrs={'class': 'form-select'}),
            'include_database': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'include_media': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'include_documents': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'include_settings': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'compressed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'encrypted': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        backup_type = cleaned_data.get('backup_type')
        
        # For incremental backups, we need a parent backup
        if backup_type == 'incremental':
            parent_backup = self.data.get('parent_backup')
            if not parent_backup:
                raise forms.ValidationError(
                    'Incremental backups require a parent backup to be selected.'
                )
        
        # At least one option must be selected
        include_database = cleaned_data.get('include_database')
        include_media = cleaned_data.get('include_media')
        include_documents = cleaned_data.get('include_documents')
        include_settings = cleaned_data.get('include_settings')
        
        if not any([include_database, include_media, include_documents, include_settings]):
            raise forms.ValidationError(
                'At least one backup option must be selected.'
            )
        
        return cleaned_data


class RestoreJobForm(forms.ModelForm):
    """
    Form for creating and updating restore jobs.
    """
    class Meta:
        model = RestoreJob
        fields = [
            'name', 'description', 'backup_file', 'backup_job',
            'restore_database', 'restore_media', 'restore_documents', 'restore_settings',
            'conflict_resolution'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'backup_file': forms.FileInput(attrs={'class': 'form-control'}),
            'backup_job': forms.Select(attrs={'class': 'form-select'}),
            'restore_database': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'restore_media': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'restore_documents': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'restore_settings': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'conflict_resolution': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        if tenant:
            # Filter backup jobs by tenant
            self.fields['backup_job'].queryset = BackupJob.objects.filter(
                tenant=tenant,
                status='completed'
            )
    
    def clean(self):
        cleaned_data = super().clean()
        backup_file = cleaned_data.get('backup_file')
        backup_job = cleaned_data.get('backup_job')
        
        # Either backup_file or backup_job must be provided
        if not backup_file and not backup_job:
            raise forms.ValidationError(
                'Either a backup file or an existing backup job must be selected.'
            )
        
        # At least one restore option must be selected
        restore_database = cleaned_data.get('restore_database')
        restore_media = cleaned_data.get('restore_media')
        restore_documents = cleaned_data.get('restore_documents')
        restore_settings = cleaned_data.get('restore_settings')
        
        if not any([restore_database, restore_media, restore_documents, restore_settings]):
            raise forms.ValidationError(
                'At least one restore option must be selected.'
            )
        
        return cleaned_data


class RestoreJobWizardForm(forms.ModelForm):
    """
    Form for creating restore jobs with wizard-like interface.
    """
    class Meta:
        model = RestoreJob
        fields = [
            'name', 'description', 'backup_file', 'backup_job',
            'restore_database', 'restore_media', 'restore_documents', 'restore_settings',
            'conflict_resolution'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'backup_file': forms.FileInput(attrs={'class': 'form-control'}),
            'backup_job': forms.Select(attrs={'class': 'form-select'}),
            'restore_database': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'restore_media': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'restore_documents': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'restore_settings': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'conflict_resolution': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        if tenant:
            # Filter backup jobs by tenant
            self.fields['backup_job'].queryset = BackupJob.objects.filter(
                tenant=tenant,
                status='completed'
            )
    
    def clean(self):
        cleaned_data = super().clean()
        backup_file = cleaned_data.get('backup_file')
        backup_job = cleaned_data.get('backup_job')
        
        # Either backup_file or backup_job must be provided
        if not backup_file and not backup_job:
            raise forms.ValidationError(
                'Either a backup file or an existing backup job must be selected.'
            )
        
        # At least one restore option must be selected
        restore_database = cleaned_data.get('restore_database')
        restore_media = cleaned_data.get('restore_media')
        restore_documents = cleaned_data.get('restore_documents')
        restore_settings = cleaned_data.get('restore_settings')
        
        if not any([restore_database, restore_media, restore_documents, restore_settings]):
            raise forms.ValidationError(
                'At least one restore option must be selected.'
            )
        
        return cleaned_data


class BackupScheduleForm(forms.ModelForm):
    """
    Form for creating and updating backup schedules.
    """
    class Meta:
        model = BackupSchedule
        fields = [
            'name', 'description', 'frequency', 'backup_type',
            'is_active', 'run_at', 'run_day', 'run_weekday',
            'retention_days', 'retention_count',
            'include_database', 'include_media', 'include_documents', 'include_settings',
            'compress', 'encrypt',
            'email_notification', 'email_recipients'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'frequency': forms.Select(attrs={'class': 'form-select'}),
            'backup_type': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'run_at': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'run_day': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 31}),
            'run_weekday': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 6}),
            'retention_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'retention_count': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'include_database': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'include_media': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'include_documents': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'include_settings': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'compress': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'encrypt': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_notification': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_recipients': forms.Textarea(attrs={'rows': 2, 'placeholder': 'email1@example.com, email2@example.com'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        frequency = cleaned_data.get('frequency')
        run_day = cleaned_data.get('run_day')
        run_weekday = cleaned_data.get('run_weekday')
        retention_days = cleaned_data.get('retention_days')
        retention_count = cleaned_data.get('retention_count')
        email_notification = cleaned_data.get('email_notification')
        email_recipients = cleaned_data.get('email_recipients')
        
        # Validate frequency-specific fields
        if frequency == 'monthly' and not run_day:
            raise forms.ValidationError(
                'Monthly backups require a day of the month to be specified.'
            )
        
        if frequency == 'weekly' and run_weekday is None:
            raise forms.ValidationError(
                'Weekly backups require a day of the week to be specified.'
            )
        
        # Validate retention settings
        if not retention_days and not retention_count:
            raise forms.ValidationError(
                'Either retention days or retention count must be specified.'
            )
        
        # Validate email recipients if email notification is enabled
        if email_notification and not email_recipients:
            raise forms.ValidationError(
                'Email recipients must be specified when email notifications are enabled.'
            )
        
        # At least one backup option must be selected
        include_database = cleaned_data.get('include_database')
        include_media = cleaned_data.get('include_media')
        include_documents = cleaned_data.get('include_documents')
        include_settings = cleaned_data.get('include_settings')
        
        if not any([include_database, include_media, include_documents, include_settings]):
            raise forms.ValidationError(
                'At least one backup option must be selected.'
            )
        
        return cleaned_data
    
    def clean_email_recipients(self):
        """
        Validate email recipients format.
        """
        email_recipients = self.cleaned_data.get('email_recipients')
        if not email_recipients:
            return email_recipients
        
        # Split by comma and validate each email
        emails = [email.strip() for email in email_recipients.split(',') if email.strip()]
        invalid_emails = []
        
        for email in emails:
            if not forms.EmailField().clean(email):
                invalid_emails.append(email)
        
        if invalid_emails:
            raise forms.ValidationError(
                f'Invalid email addresses: {", ".join(invalid_emails)}'
            )
        
        # Return cleaned email list
        return ', '.join(emails)


class BackupSearchForm(forms.Form):
    """
    Form for searching backup jobs.
    """
    query = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search backups...'
        })
    )
    status = forms.ChoiceField(
        choices=[('', 'All Status')] + list(BackupJob.STATUS_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    backup_type = forms.ChoiceField(
        choices=[('', 'All Types')] + list(BackupJob.BACKUP_TYPE_CHOICES),
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


class RestoreSearchForm(forms.Form):
    """
    Form for searching restore jobs.
    """
    query = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search restores...'
        })
    )
    status = forms.ChoiceField(
        choices=[('', 'All Status')] + list(RestoreJob.STATUS_CHOICES),
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


class ScheduleSearchForm(forms.Form):
    """
    Form for searching backup schedules.
    """
    query = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search schedules...'
        })
    )
    is_active = forms.ChoiceField(
        choices=[('', 'All'), ('true', 'Active'), ('false', 'Inactive')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    frequency = forms.ChoiceField(
        choices=[('', 'All Frequencies')] + list(BackupSchedule.FREQUENCY_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )