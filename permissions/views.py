from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import CreateView, DeleteView, ListView, UpdateView
from django.views.generic.edit import FormView

from .forms import (
    RoleForm, UserRoleForm, UserRoleBulkForm, 
    PermissionForm, UserPermissionFilterForm
)
from .models import Role, TenantPermission, UserRole
from .utils import (
    has_permission, has_role, get_user_permissions, 
    get_user_roles, get_permission_context, TenantPermissionRequiredMixin
)

User = get_user_model()


@method_decorator(login_required, name='dispatch')
class RoleListView(TenantPermissionRequiredMixin, ListView):
    """
    View to list all roles for the current tenant.
    """
    model = Role
    template_name = 'permissions/role_list.html'
    context_object_name = 'roles'
    permission_codename = 'roles.view_role'
    
    def get_queryset(self):
        tenant = getattr(self.request.user, 'tenant', None)
        if tenant:
            return Role.objects.filter(tenant=tenant).prefetch_related('permissions')
        return Role.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_permission_context(self.request))
        return context


@method_decorator(login_required, name='dispatch')
class RoleCreateView(TenantPermissionRequiredMixin, CreateView):
    """
    View to create a new role.
    """
    model = Role
    form_class = RoleForm
    template_name = 'permissions/role_form.html'
    success_url = reverse_lazy('permissions:role_list')
    permission_codename = 'roles.add_role'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['tenant'] = getattr(self.request.user, 'tenant', None)
        return kwargs
    
    def form_valid(self, form):
        messages.success(self.request, 'Role created successfully.')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_permission_context(self.request))
        context['title'] = 'Create Role'
        return context


@method_decorator(login_required, name='dispatch')
class RoleUpdateView(TenantPermissionRequiredMixin, UpdateView):
    """
    View to update an existing role.
    """
    model = Role
    form_class = RoleForm
    template_name = 'permissions/role_form.html'
    success_url = reverse_lazy('permissions:role_list')
    permission_codename = 'roles.change_role'
    
    def get_queryset(self):
        tenant = getattr(self.request.user, 'tenant', None)
        if tenant:
            return Role.objects.filter(tenant=tenant)
        return Role.objects.none()
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['tenant'] = getattr(self.request.user, 'tenant', None)
        return kwargs
    
    def form_valid(self, form):
        messages.success(self.request, 'Role updated successfully.')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_permission_context(self.request))
        context['title'] = 'Update Role'
        return context


@method_decorator(login_required, name='dispatch')
class RoleDeleteView(TenantPermissionRequiredMixin, DeleteView):
    """
    View to delete a role.
    """
    model = Role
    template_name = 'permissions/role_confirm_delete.html'
    success_url = reverse_lazy('permissions:role_list')
    permission_codename = 'roles.delete_role'
    
    def get_queryset(self):
        tenant = getattr(self.request.user, 'tenant', None)
        if tenant:
            return Role.objects.filter(tenant=tenant, is_system_role=False)
        return Role.objects.none()
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Role deleted successfully.')
        return super().delete(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_permission_context(self.request))
        return context


@login_required
def role_users_view(request, role_id):
    """
    View to list and manage users assigned to a specific role.
    """
    tenant = getattr(request.user, 'tenant', None)
    if not tenant:
        return redirect('permission_denied')
    
    if not has_permission(request.user, 'roles.view_role', tenant):
        return redirect('permission_denied')
    
    role = get_object_or_404(Role, id=role_id, tenant=tenant)
    
    # Handle user assignment form
    if request.method == 'POST' and 'assign_user' in request.POST:
        if not has_permission(request.user, 'roles.assign_role', tenant):
            messages.error(request, "You don't have permission to assign roles.")
            return redirect('permissions:role_users', role_id=role.id)
        
        form = UserRoleForm(request.POST, tenant=tenant, role=role)
        if form.is_valid():
            form.save(assigned_by=request.user)
            messages.success(request, f"User assigned to {role.name} role successfully.")
            return redirect('permissions:role_users', role_id=role.id)
    else:
        form = UserRoleForm(tenant=tenant, role=role)
    
    # Get users with this role
    user_roles = UserRole.objects.filter(
        role=role,
        tenant=tenant
    ).select_related('user', 'assigned_by').order_by('user__email')
    
    context = {
        'role': role,
        'user_roles': user_roles,
        'form': form,
    }
    context.update(get_permission_context(request))
    
    return render(request, 'permissions/role_users.html', context)


@login_required
def remove_user_role_view(request, role_id, user_role_id):
    """
    View to remove a user from a role.
    """
    tenant = getattr(request.user, 'tenant', None)
    if not tenant:
        return redirect('permission_denied')
    
    if not has_permission(request.user, 'roles.assign_role', tenant):
        messages.error(request, "You don't have permission to remove roles.")
        return redirect('permission_denied')
    
    role = get_object_or_404(Role, id=role_id, tenant=tenant)
    user_role = get_object_or_404(UserRole, id=user_role_id, role=role, tenant=tenant)
    
    if request.method == 'POST':
        user_email = user_role.user.email
        user_role.delete()
        messages.success(request, f"{user_email} removed from {role.name} role successfully.")
        return redirect('permissions:role_users', role_id=role.id)
    
    context = {
        'role': role,
        'user_role': user_role,
    }
    context.update(get_permission_context(request))
    
    return render(request, 'permissions/remove_user_role.html', context)


@login_required
def user_permissions_view(request, user_id=None):
    """
    View to display and manage user permissions.
    """
    tenant = getattr(request.user, 'tenant', None)
    if not tenant:
        return redirect('permission_denied')
    
    if not has_permission(request.user, 'users.view_user', tenant):
        return redirect('permission_denied')
    
    # Handle filtering
    filter_form = UserPermissionFilterForm(request.GET or None, tenant=tenant)
    users = User.objects.filter(tenant=tenant)
    
    # Apply filters if provided
    if filter_form.is_valid():
        permission = filter_form.cleaned_data.get('permission')
        role = filter_form.cleaned_data.get('role')
        
        if permission:
            # Filter users who have this specific permission
            users_with_permission = []
            for user in users:
                if has_permission(user, permission.codename, tenant):
                    users_with_permission.append(user.id)
            users = users.filter(id__in=users_with_permission)
        
        if role:
            # Filter users who have this specific role
            user_ids = UserRole.objects.filter(
                role=role,
                tenant=tenant
            ).values_list('user_id', flat=True)
            users = users.filter(id__in=user_ids)
    
    # Get user details if a specific user is requested
    selected_user = None
    user_roles = []
    user_permissions = []
    
    if user_id:
        selected_user = get_object_or_404(User, id=user_id, tenant=tenant)
        user_roles = UserRole.objects.filter(
            user=selected_user,
            tenant=tenant
        ).select_related('role').order_by('role__name')
        user_permissions = get_user_permissions(selected_user, tenant)
    
    context = {
        'users': users.order_by('email'),
        'filter_form': filter_form,
        'selected_user': selected_user,
        'user_roles': user_roles,
        'user_permissions': user_permissions,
    }
    context.update(get_permission_context(request))
    
    return render(request, 'permissions/user_permissions.html', context)


@method_decorator(login_required, name='dispatch')
class BulkRoleAssignmentView(TenantPermissionRequiredMixin, FormView):
    """
    View to assign multiple roles to multiple users.
    """
    form_class = UserRoleBulkForm
    template_name = 'permissions/bulk_role_assignment.html'
    success_url = reverse_lazy('permissions:user_permissions')
    permission_codename = 'roles.assign_role'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['tenant'] = getattr(self.request.user, 'tenant', None)
        return kwargs
    
    def form_valid(self, form):
        tenant = getattr(self.request.user, 'tenant', None)
        users = form.cleaned_data['users']
        roles = form.cleaned_data['roles']
        
        with transaction.atomic():
            for user in users:
                for role in roles:
                    # Check if the user already has this role
                    if not UserRole.objects.filter(
                        user=user,
                        role=role,
                        tenant=tenant
                    ).exists():
                        UserRole.objects.create(
                            user=user,
                            role=role,
                            tenant=tenant,
                            assigned_by=self.request.user
                        )
        
        messages.success(
            self.request,
            f"Successfully assigned roles to {len(users)} user(s)."
        )
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_permission_context(self.request))
        return context


@method_decorator(login_required, name='dispatch')
class PermissionListView(TenantPermissionRequiredMixin, ListView):
    """
    View to list all permissions.
    """
    model = TenantPermission
    template_name = 'permissions/permission_list.html'
    context_object_name = 'permissions'
    permission_codename = 'roles.view_role'
    
    def get_queryset(self):
        return TenantPermission.objects.all().order_by('module', 'name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_permission_context(self.request))
        
        # Group permissions by module
        permissions_by_module = {}
        for permission in context['permissions']:
            if permission.module not in permissions_by_module:
                permissions_by_module[permission.module] = []
            permissions_by_module[permission.module].append(permission)
        
        context['permissions_by_module'] = permissions_by_module
        return context


@login_required
def permission_matrix_view(request):
    """
    View to display a matrix of roles and permissions.
    """
    tenant = getattr(request.user, 'tenant', None)
    if not tenant:
        return redirect('permission_denied')
    
    if not has_permission(request.user, 'roles.view_role', tenant):
        return redirect('permission_denied')
    
    roles = Role.objects.filter(tenant=tenant).prefetch_related('permissions')
    permissions = TenantPermission.objects.all().order_by('module', 'name')
    
    # Create a matrix of role permissions
    role_permissions = {}
    for role in roles:
        role_permissions[role.id] = set(role.permissions.values_list('codename', flat=True))
    
    context = {
        'roles': roles,
        'permissions': permissions,
        'role_permissions': role_permissions,
    }
    context.update(get_permission_context(request))
    
    return render(request, 'permissions/permission_matrix.html', context)
