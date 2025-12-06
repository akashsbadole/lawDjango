from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.db import transaction
from django.http import Http404
from .models import Client
from .forms import ClientForm, ClientSearchForm
from permissions.utils import TenantPermissionRequiredMixin
from audit.utils import log_activity


class TenantRequiredMixin:
    """
    Mixin to ensure tenant is available and user has access.
    """
    def dispatch(self, request, *args, **kwargs):
        # Check if tenant is available in request
        if not hasattr(request, 'tenant') or not request.tenant:
            messages.error(request, "No tenant specified.")
            return redirect('home')
        
        # Check if user belongs to this tenant or is superadmin
        if not request.user.is_superuser and (not hasattr(request.user, 'tenant') or request.user.tenant != request.tenant):
            messages.error(request, "You don't have permission to access this tenant's data.")
            return redirect('home')
        
        return super().dispatch(request, *args, **kwargs)


class ClientListView(TenantPermissionRequiredMixin, LoginRequiredMixin, ListView):
    """
    View to list all clients for the current tenant.
    """
    model = Client
    template_name = 'clients/client_list.html'
    context_object_name = 'clients'
    paginate_by = 10
    permission_required = 'clients.view_client'
    
    def get_queryset(self):
        # Filter clients by current tenant
        queryset = Client.objects.active_for_tenant(self.request.tenant)
        
        # Handle search
        search_form = ClientSearchForm(self.request.GET)
        if search_form.is_valid() and search_form.cleaned_data.get('query'):
            query = search_form.cleaned_data['query']
            queryset = Client.objects.search(query, self.request.tenant)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = ClientSearchForm(self.request.GET)
        context['tenant'] = self.request.tenant
        return context


class ClientDetailView(TenantPermissionRequiredMixin, LoginRequiredMixin, DetailView):
    """
    View to show details of a specific client.
    """
    model = Client
    template_name = 'clients/client_detail.html'
    context_object_name = 'client'
    permission_required = 'clients.view_client'
    
    def get_object(self):
        # Get client by ID and ensure it belongs to the current tenant
        client = get_object_or_404(Client, pk=self.kwargs['pk'])
        
        # Check if client belongs to the current tenant
        if client.tenant != self.request.tenant:
            raise Http404("Client not found or you don't have permission to view it.")
        
        return client
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = self.request.tenant
        return context


class ClientCreateView(TenantPermissionRequiredMixin, LoginRequiredMixin, CreateView):
    """
    View to create a new client.
    """
    model = Client
    form_class = ClientForm
    template_name = 'clients/client_form.html'
    permission_required = 'clients.add_client'
    
    def get_success_url(self):
        return reverse_lazy('clients:detail', kwargs={'pk': self.object.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = self.request.tenant
        context['title'] = 'Add New Client'
        return context
    
    def form_valid(self, form):
        # Check email uniqueness within tenant
        email = form.cleaned_data['email']
        if Client.objects.filter(
            email__iexact=email, 
            tenant=self.request.tenant
        ).exists():
            form.add_error('email', 'A client with this email already exists in your firm.')
            return self.form_invalid(form)
        
        # Create client with tenant and user information
        with transaction.atomic():
            client = form.save(commit=False)
            client.tenant = self.request.tenant
            client.created_by = self.request.user
            client.save()
            
            # Log activity
            log_activity(
                tenant=self.request.tenant,
                user=self.request.user,
                activity_type='CLIENT_CREATED',
                description=f'Created new client: {client.full_name}',
                related_object=client
            )
            
            messages.success(
                self.request,
                f'Client "{client.full_name}" has been created successfully.'
            )
        
        return super().form_valid(form)


class ClientUpdateView(TenantPermissionRequiredMixin, LoginRequiredMixin, UpdateView):
    """
    View to update an existing client.
    """
    model = Client
    form_class = ClientForm
    template_name = 'clients/client_form.html'
    permission_required = 'clients.change_client'
    
    def get_object(self):
        # Get client by ID and ensure it belongs to the current tenant
        client = get_object_or_404(Client, pk=self.kwargs['pk'])
        
        # Check if client belongs to the current tenant
        if client.tenant != self.request.tenant:
            raise Http404("Client not found or you don't have permission to edit it.")
        
        return client
    
    def get_success_url(self):
        return reverse_lazy('clients:detail', kwargs={'pk': self.object.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = self.request.tenant
        context['title'] = f'Edit Client: {self.object.full_name}'
        return context
    
    def form_valid(self, form):
        # Check email uniqueness within tenant (excluding current client)
        email = form.cleaned_data['email']
        if Client.objects.filter(
            email__iexact=email, 
            tenant=self.request.tenant
        ).exclude(pk=self.object.pk).exists():
            form.add_error('email', 'A client with this email already exists in your firm.')
            return self.form_invalid(form)
        
        with transaction.atomic():
            # Get old values for audit
            old_values = {
                'first_name': self.object.first_name,
                'last_name': self.object.last_name,
                'email': self.object.email,
                'phone': self.object.phone,
                'address': self.object.address,
            }
            
            client = form.save()
            
            # Log activity with changes
            log_activity(
                tenant=self.request.tenant,
                user=self.request.user,
                activity_type='CLIENT_UPDATED',
                description=f'Updated client: {client.full_name}',
                related_object=client,
                metadata={
                    'old_values': old_values,
                    'new_values': {
                        'first_name': client.first_name,
                        'last_name': client.last_name,
                        'email': client.email,
                        'phone': client.phone,
                        'address': client.address,
                    }
                }
            )
            
            messages.success(
                self.request,
                f'Client "{client.full_name}" has been updated successfully.'
            )
        
        return super().form_valid(form)


class ClientDeleteView(TenantPermissionRequiredMixin, LoginRequiredMixin, DeleteView):
    """
    View to soft delete a client.
    """
    model = Client
    template_name = 'clients/client_confirm_delete.html'
    success_url = reverse_lazy('clients:list')
    permission_required = 'clients.delete_client'
    
    def get_object(self):
        # Get client by ID and ensure it belongs to the current tenant
        client = get_object_or_404(Client, pk=self.kwargs['pk'])
        
        # Check if client belongs to the current tenant
        if client.tenant != self.request.tenant:
            raise Http404("Client not found or you don't have permission to delete it.")
        
        return client
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = self.request.tenant
        return context
    
    def delete(self, request, *args, **kwargs):
        client = self.get_object()
        client.soft_delete()
        
        # Log activity
        log_activity(
            tenant=request.tenant,
            user=request.user,
            activity_type='CLIENT_DELETED',
            description=f'Deleted client: {client.full_name}',
            related_object=client,
            metadata={
                'deleted_client_data': {
                    'full_name': client.full_name,
                    'email': client.email,
                    'phone': client.phone,
                }
            }
        )
        
        messages.success(
            request,
            f'Client "{client.full_name}" has been deleted successfully.'
        )
        return redirect(self.success_url)
