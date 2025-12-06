from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from .models import Role, TenantPermission, UserRole

User = get_user_model()


class RoleForm(forms.ModelForm):
    """
    Form for creating and editing roles.
    """
    permissions = forms.ModelMultipleChoiceField(
        queryset=TenantPermission.objects.all().order_by('module', 'name'),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text=_("Select the permissions that this role should have.")
    )
    
    class Meta:
        model = Role
        fields = ['name', 'description', 'permissions']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        if self.tenant:
            # Filter permissions by module and order them
            self.fields['permissions'].queryset = TenantPermission.objects.all().order_by('module', 'name')
    
    def clean_name(self):
        name = self.cleaned_data['name']
        
        # Check if role name is unique within the tenant
        if self.tenant:
            qs = Role.objects.filter(name__iexact=name, tenant=self.tenant)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            
            if qs.exists():
                raise forms.ValidationError(_("A role with this name already exists for this tenant."))
        
        return name
    
    def save(self, commit=True):
        role = super().save(commit=False)
        
        # Set the tenant if not already set
        if self.tenant and not role.tenant_id:
            role.tenant = self.tenant
        
        if commit:
            role.save()
            self.save_m2m()
        
        return role


class UserRoleForm(forms.ModelForm):
    """
    Form for assigning a role to a user.
    """
    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text=_("Select the user to assign this role to.")
    )
    
    class Meta:
        model = UserRole
        fields = ['user']
    
    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        self.role = kwargs.pop('role', None)
        super().__init__(*args, **kwargs)
        
        if self.tenant:
            # Filter users by tenant
            self.fields['user'].queryset = User.objects.filter(tenant=self.tenant).order_by('email')
        
        # Exclude users who already have this role
        if self.role and self.tenant:
            existing_user_ids = UserRole.objects.filter(
                role=self.role,
                tenant=self.tenant
            ).values_list('user_id', flat=True)
            
            if existing_user_ids:
                self.fields['user'].queryset = self.fields['user'].queryset.exclude(id__in=existing_user_ids)
    
    def clean_user(self):
        user = self.cleaned_data['user']
        
        # Check if user already has this role
        if self.role and self.tenant:
            if UserRole.objects.filter(
                user=user,
                role=self.role,
                tenant=self.tenant
            ).exists():
                raise forms.ValidationError(_("This user already has this role."))
        
        return user
    
    def save(self, commit=True, assigned_by=None):
        user_role = super().save(commit=False)
        
        # Set the tenant and role if not already set
        if self.tenant and not user_role.tenant_id:
            user_role.tenant = self.tenant
        
        if self.role and not user_role.role_id:
            user_role.role = self.role
        
        if assigned_by and not user_role.assigned_by_id:
            user_role.assigned_by = assigned_by
        
        if commit:
            user_role.save()
        
        return user_role


class UserRoleBulkForm(forms.Form):
    """
    Form for assigning multiple roles to multiple users.
    """
    users = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        help_text=_("Select the users to assign roles to.")
    )
    
    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        help_text=_("Select the roles to assign to the selected users.")
    )
    
    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        if self.tenant:
            # Filter users and roles by tenant
            self.fields['users'].queryset = User.objects.filter(tenant=self.tenant).order_by('email')
            self.fields['roles'].queryset = Role.objects.filter(tenant=self.tenant).order_by('name')


class PermissionForm(forms.ModelForm):
    """
    Form for creating and editing permissions.
    """
    class Meta:
        model = TenantPermission
        fields = ['name', 'codename', 'description', 'module']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def clean_codename(self):
        codename = self.cleaned_data['codename']
        
        # Check if codename is unique
        qs = TenantPermission.objects.filter(codename__iexact=codename)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        
        if qs.exists():
            raise forms.ValidationError(_("A permission with this codename already exists."))
        
        return codename


class UserPermissionFilterForm(forms.Form):
    """
    Form for filtering users by permissions.
    """
    permission = forms.ModelChoiceField(
        queryset=TenantPermission.objects.all().order_by('module', 'name'),
        required=False,
        empty_label=_("All Permissions"),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    role = forms.ModelChoiceField(
        queryset=Role.objects.all().order_by('name'),
        required=False,
        empty_label=_("All Roles"),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        if self.tenant:
            # Filter roles by tenant
            self.fields['role'].queryset = Role.objects.filter(tenant=self.tenant).order_by('name')