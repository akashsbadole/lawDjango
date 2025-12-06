from typing import TYPE_CHECKING
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.db import transaction
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.views.generic.edit import FormView

from core.types import TenantHttpRequest
from .models import ClientRequest, RequestNote
from .forms import (
    ClientRequestForm,
    ClientRequestUpdateForm,
    RequestNoteForm,
    ClientRequestSearchForm,
    ClientRequestAssignForm,
    ClientRequestReviewForm
)
from permissions.utils import TenantPermissionRequiredMixin
from audit.utils import log_activity
from clients.models import Client

if TYPE_CHECKING:
    from tenants.models import Tenant


class TenantRequiredMixin:
    """
    Mixin to ensure tenant is available and user has access.
    """
    def dispatch(self, request: TenantHttpRequest, *args, **kwargs):
        # Check if tenant is available in request
        if not hasattr(request, 'tenant') or not request.tenant:
            messages.error(request, "No tenant specified.")
            return redirect('home')
        
        # Check if user belongs to this tenant or is superadmin
        if not request.user.is_superuser and (not hasattr(request.user, 'tenant') or request.user.tenant != request.tenant):  # type: ignore
            messages.error(request, "You don't have permission to access this tenant's data.")
            return redirect('home')
        
        return super().dispatch(request, *args, **kwargs)


class ClientRequestListView(TenantPermissionRequiredMixin, LoginRequiredMixin, ListView):
    """
    View to list all client requests for the current tenant.
    """
    model = ClientRequest
    template_name = 'client_requests/request_list.html'
    context_object_name = 'requests'
    paginate_by = 10
    permission_required = 'client_requests.view_clientrequest'
    
    def get_queryset(self):
        # Filter requests by current tenant
        queryset = ClientRequest.objects.active_for_tenant(self.request.tenant)
        
        # Handle search and filters
        search_form = ClientRequestSearchForm(self.request.GET)
        if search_form.is_valid():
            # Apply filters
            query = search_form.cleaned_data.get('query')
            if query:
                queryset = ClientRequest.objects.search(query, self.request.tenant)  # type: ignore
            
            status = search_form.cleaned_data.get('status')
            if status:
                queryset = queryset.filter(status=status)
            
            priority = search_form.cleaned_data.get('priority')
            if priority:
                queryset = queryset.filter(priority=priority)
            
            request_type = search_form.cleaned_data.get('request_type')
            if request_type:
                queryset = queryset.filter(request_type=request_type)
            
            date_from = search_form.cleaned_data.get('date_from')
            if date_from:
                queryset = queryset.filter(created_at__date__gte=date_from)
            
            date_to = search_form.cleaned_data.get('date_to')
            if date_to:
                queryset = queryset.filter(created_at__date__lte=date_to)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = ClientRequestSearchForm(self.request.GET)
        context['tenant'] = self.request.tenant  # type: ignore
        
        # Add statistics
        stats = ClientRequest.objects.get_statistics(self.request.tenant)  # type: ignore
        context['stats'] = stats
        
        return context


class ClientRequestDetailView(TenantPermissionRequiredMixin, LoginRequiredMixin, DetailView):
    """
    View to show details of a specific client request.
    """
    model = ClientRequest
    template_name = 'client_requests/request_detail.html'
    context_object_name = 'request'
    permission_required = 'client_requests.view_clientrequest'
    
    def get_object(self, queryset=None):
        # Get request by ID and ensure it belongs to the current tenant
        client_request = get_object_or_404(ClientRequest, pk=self.kwargs['pk'])
        
        # Check if request belongs to the current tenant
        if client_request.tenant != self.request.tenant:
            raise Http404("Request not found or you don't have permission to view it.")
        
        return client_request
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = self.request.tenant  # type: ignore
        context['notes'] = self.object.notes.all()
        context['note_form'] = RequestNoteForm()
        
        # Add forms for workflow actions
        context['assign_form'] = ClientRequestAssignForm(tenant=self.request.tenant)  # type: ignore
        context['review_form'] = ClientRequestReviewForm()
        
        return context


class ClientRequestCreateView(TenantPermissionRequiredMixin, LoginRequiredMixin, CreateView):
    """
    View to create a new client request.
    """
    model = ClientRequest
    form_class = ClientRequestForm
    template_name = 'client_requests/request_form.html'
    permission_required = 'client_requests.add_clientrequest'
    
    def get_success_url(self):
        return reverse_lazy('client_requests:detail', kwargs={'pk': self.object.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = self.request.tenant  # type: ignore
        context['title'] = 'Create New Client Request'
        return context
    
    def form_valid(self, form):
        # Create request with tenant and user information
        with transaction.atomic():
            client_request = form.save(commit=False)
            client_request.tenant = self.request.tenant  # type: ignore
            client_request.created_by = self.request.user
            client_request.save()
            
            # Log activity
            log_activity(
                tenant=self.request.tenant,  # type: ignore
                user=self.request.user,
                activity_type='CLIENT_REQUEST_CREATED',
                description=f'Created new client request: {client_request.title}',
                related_object=client_request
            )
            
            messages.success(
                self.request,
                f'Client request "{client_request.title}" has been created successfully.'
            )
        
        return super().form_valid(form)


class ClientRequestUpdateView(TenantPermissionRequiredMixin, LoginRequiredMixin, UpdateView):
    """
    View to update an existing client request.
    """
    model = ClientRequest
    form_class = ClientRequestUpdateForm
    template_name = 'client_requests/request_form.html'
    permission_required = 'client_requests.change_clientrequest'
    
    def get_object(self, queryset=None):
        # Get request by ID and ensure it belongs to the current tenant
        client_request = get_object_or_404(ClientRequest, pk=self.kwargs['pk'])
        
        # Check if request belongs to the current tenant
        if client_request.tenant != self.request.tenant:
            raise Http404("Request not found or you don't have permission to edit it.")
        
        return client_request
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['tenant'] = self.request.tenant  # type: ignore
        return kwargs
    
    def get_success_url(self):
        return reverse_lazy('client_requests:detail', kwargs={'pk': self.object.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = self.request.tenant  # type: ignore
        context['title'] = f'Edit Request: {self.object.title}'
        return context
    
    def form_valid(self, form):
        with transaction.atomic():
            # Get old values for audit
            old_values = {
                'title': self.object.title,
                'description': self.object.description,
                'status': self.object.status,
                'priority': self.object.priority,
                'assigned_lawyer': self.object.assigned_lawyer,
            }
            
            client_request = form.save()
            
            # Log activity with changes
            log_activity(
                tenant=self.request.tenant,  # type: ignore
                user=self.request.user,
                activity_type='CLIENT_REQUEST_UPDATED',
                description=f'Updated client request: {client_request.title}',
                related_object=client_request,
                metadata={
                    'old_values': old_values,
                    'new_values': {
                        'title': client_request.title,
                        'description': client_request.description,
                        'status': client_request.status,
                        'priority': client_request.priority,
                        'assigned_lawyer': client_request.assigned_lawyer,
                    }
                }
            )
            
            messages.success(
                self.request,
                f'Client request "{client_request.title}" has been updated successfully.'
            )
        
        return super().form_valid(form)


class ClientRequestDeleteView(TenantPermissionRequiredMixin, LoginRequiredMixin, DeleteView):
    """
    View to soft delete a client request.
    """
    model = ClientRequest
    template_name = 'client_requests/request_confirm_delete.html'
    success_url = reverse_lazy('client_requests:list')
    permission_required = 'client_requests.delete_clientrequest'
    
    def get_object(self, queryset=None):
        # Get request by ID and ensure it belongs to the current tenant
        client_request = get_object_or_404(ClientRequest, pk=self.kwargs['pk'])
        
        # Check if request belongs to the current tenant
        if client_request.tenant != self.request.tenant:
            raise Http404("Request not found or you don't have permission to delete it.")
        
        return client_request
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = self.request.tenant  # type: ignore
        return context
    
    def delete(self, request, *args, **kwargs):
        client_request = self.get_object()
        client_request.soft_delete()
        
        # Log activity
        log_activity(
            tenant=request.tenant,  # type: ignore
            user=request.user,
            activity_type='CLIENT_REQUEST_DELETED',
            description=f'Deleted client request: {client_request.title}',
            related_object=client_request,
            metadata={
                'deleted_request_data': {
                    'title': client_request.title,
                    'client_name': client_request.client_name,
                    'email': client_request.client_email,
                }
            }
        )
        
        messages.success(
            request,
            f'Client request "{client_request.title}" has been deleted successfully.'
        )
        return redirect(self.success_url)


@login_required
@require_POST
def add_note(request, pk):
    """
    Add a note to a client request.
    """
    client_request = get_object_or_404(ClientRequest, pk=pk)
    
    # Check if request belongs to the current tenant
    if client_request.tenant != request.tenant:  # type: ignore
        raise Http404("Request not found or you don't have permission to add notes.")
    
    form = RequestNoteForm(request.POST)
    if form.is_valid():
        with transaction.atomic():
            note = form.save(commit=False)
            note.request = client_request
            note.created_by = request.user
            note.tenant = request.tenant  # type: ignore
            note.save()
            
            # Log activity
            log_activity(
                tenant=request.tenant,  # type: ignore
                user=request.user,
                activity_type='REQUEST_NOTE_ADDED',
                description=f'Added note to request: {client_request.title}',
                related_object=client_request,
                metadata={'note_content': note.note[:100]}  # First 100 chars
            )
            
            messages.success(request, 'Note has been added successfully.')
    
    return redirect('client_requests:detail', pk=client_request.pk)


@login_required
@require_POST
def assign_lawyer(request, pk):
    """
    Assign a lawyer to a client request.
    """
    client_request = get_object_or_404(ClientRequest, pk=pk)
    
    # Check if request belongs to the current tenant
    if client_request.tenant != request.tenant:  # type: ignore
        raise Http404("Request not found or you don't have permission to assign.")
    
    form = ClientRequestAssignForm(request.POST, tenant=request.tenant)
    if form.is_valid():
        assigned_lawyer = form.cleaned_data['assigned_lawyer']
        
        with transaction.atomic():
            old_lawyer = client_request.assigned_lawyer
            client_request.assigned_lawyer = assigned_lawyer
            client_request.save()
            
            # Log activity
            log_activity(
                tenant=request.tenant,  # type: ignore
                user=request.user,
                activity_type='REQUEST_ASSIGNED',
                description=f'Assigned lawyer to request: {client_request.title}',
                related_object=client_request,
                metadata={
                    'old_lawyer': old_lawyer.email if old_lawyer else None,
                    'new_lawyer': assigned_lawyer.email if assigned_lawyer else None,
                }
            )
            
            if assigned_lawyer:
                messages.success(
                    request, 
                    f'Request has been assigned to {assigned_lawyer.get_full_name() or assigned_lawyer.email}.'
                )
            else:
                messages.success(request, 'Lawyer assignment has been removed.')
    
    return redirect('client_requests:detail', pk=client_request.pk)


@login_required
@require_POST
def review_request(request, pk):
    """
    Review a client request (approve or reject).
    """
    client_request = get_object_or_404(ClientRequest, pk=pk)
    
    # Check if request belongs to the current tenant
    if client_request.tenant != request.tenant:  # type: ignore
        raise Http404("Request not found or you don't have permission to review.")
    
    form = ClientRequestReviewForm(request.POST)
    if form.is_valid():
        action = form.cleaned_data['action']
        rejection_reason = form.cleaned_data.get('rejection_reason', '')
        notes = form.cleaned_data.get('notes', '')
        
        with transaction.atomic():
            if action == 'approve':
                client_request.approve(reviewed_by=request.user)
                status_text = 'approved'
                
                # Create client record if not exists
                if not client_request.converted_to_client:
                    client = Client.objects.create(
                        first_name=client_request.client_name.split()[0] if ' ' in client_request.client_name else client_request.client_name,
                        last_name=client_request.client_name.split()[-1] if ' ' in client_request.client_name else '',
                        email=client_request.client_email,
                        phone=client_request.client_phone,
                        company=client_request.client_company,
                        tenant=request.tenant,  # type: ignore
                        created_by=request.user,
                        notes=f"Created from client request: {client_request.title}\n\n{client_request.description}"
                    )
                    client_request.convert_to_client(client, converted_by=request.user)
                
            else:  # reject
                client_request.reject(reason=rejection_reason, reviewed_by=request.user)
                status_text = 'rejected'
            
            # Add review note if provided
            if notes:
                RequestNote.objects.create(
                    request=client_request,
                    note=f"Review action: {action.upper()}\n\n{notes}",
                    is_internal=True,
                    created_by=request.user,
                    tenant=request.tenant  # type: ignore
                )
            
            # Log activity
            log_activity(
                tenant=request.tenant,  # type: ignore
                user=request.user,
                activity_type=f'REQUEST_{action.upper()}',
                description=f'{action.title()}d client request: {client_request.title}',
                related_object=client_request,
                metadata={
                    'action': action,
                    'rejection_reason': rejection_reason if action == 'reject' else None,
                    'notes': notes,
                }
            )
            
            messages.success(
                request, 
                f'Request has been {status_text} successfully.'
            )
    
    return redirect('client_requests:detail', pk=client_request.pk)


@login_required
@require_POST
def submit_for_review(request, pk):
    """
    Submit a client request for review.
    """
    client_request = get_object_or_404(ClientRequest, pk=pk)
    
    # Check if request belongs to the current tenant
    if client_request.tenant != request.tenant:  # type: ignore
        raise Http404("Request not found or you don't have permission to submit for review.")
    
    if client_request.can_be_reviewed:
        with transaction.atomic():
            client_request.submit_for_review(reviewed_by=request.user)
            
            # Log activity
            log_activity(
                tenant=request.tenant,  # type: ignore
                user=request.user,
                activity_type='REQUEST_SUBMITTED_FOR_REVIEW',
                description=f'Submitted request for review: {client_request.title}',
                related_object=client_request
            )
            
            messages.success(request, 'Request has been submitted for review.')
    else:
        messages.error(request, 'This request cannot be submitted for review.')
    
    return redirect('client_requests:detail', pk=client_request.pk)
