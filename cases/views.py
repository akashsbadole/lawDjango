from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.db.models import Q
from django.utils import timezone
from django.http import Http404

from .models import Case, CaseEvent
from .forms import CaseForm, CaseEventForm, CaseSearchForm, CaseEventSearchForm
from tenants.models import Tenant
from permissions.utils import TenantPermissionRequiredMixin
from audit.utils import log_activity


class TenantRequiredMixin(UserPassesTestMixin):
    """Mixin to ensure user belongs to a tenant."""
    
    def test_func(self):
        return hasattr(self.request.user, 'tenant') and self.request.user.tenant is not None
    
    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        raise Http404("You don't have access to this tenant.")


class CaseListView(TenantPermissionRequiredMixin, LoginRequiredMixin, ListView):
    """List view for cases with tenant filtering and search."""
    model = Case
    template_name = 'cases/case_list.html'
    context_object_name = 'cases'
    paginate_by = 10
    permission_required = 'cases.view_case'
    
    def get_queryset(self):
        """Filter cases by tenant and search criteria."""
        tenant = self.request.tenant
        queryset = Case.objects.active_for_tenant(tenant)
        
        # Apply search filters
        form = CaseSearchForm(self.request.GET, tenant=tenant)
        if form.is_valid():
            query = form.cleaned_data.get('query')
            if query:
                queryset = queryset.filter(
                    Q(title__icontains=query) |
                    Q(case_number__icontains=query) |
                    Q(description__icontains=query) |
                    Q(client__first_name__icontains=query) |
                    Q(client__last_name__icontains=query) |
                    Q(client__email__icontains=query)
                )
            
            status = form.cleaned_data.get('status')
            if status:
                queryset = queryset.filter(status=status)
            
            case_type = form.cleaned_data.get('case_type')
            if case_type:
                queryset = queryset.filter(case_type=case_type)
            
            client = form.cleaned_data.get('client')
            if client:
                queryset = queryset.filter(client=client)
            
            assigned_lawyer = form.cleaned_data.get('assigned_lawyer')
            if assigned_lawyer:
                queryset = queryset.filter(assigned_lawyers=assigned_lawyer)
            
            date_from = form.cleaned_data.get('date_from')
            if date_from:
                queryset = queryset.filter(start_date__gte=date_from)
            
            date_to = form.cleaned_data.get('date_to')
            if date_to:
                queryset = queryset.filter(start_date__lte=date_to)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        """Add search form to context."""
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant
        context['search_form'] = CaseSearchForm(self.request.GET, tenant=tenant)
        return context


class CaseDetailView(TenantPermissionRequiredMixin, LoginRequiredMixin, DetailView):
    """Detail view for a case with events."""
    model = Case
    template_name = 'cases/case_detail.html'
    context_object_name = 'case'
    permission_required = 'cases.view_case'
    
    def get_queryset(self):
        """Filter cases by tenant."""
        return Case.objects.active_for_tenant(self.request.tenant)
    
    def get_context_data(self, **kwargs):
        """Add events and event form to context."""
        context = super().get_context_data(**kwargs)
        case = self.get_object()
        
        # Get events for this case
        events = CaseEvent.objects.for_case(case, self.request.tenant).order_by('-event_date')
        context['events'] = events
        
        # Add event form
        if self.request.method == 'POST' and 'event_form' in self.request.POST:
            context['event_form'] = CaseEventForm(
                self.request.POST,
                tenant=self.request.tenant,
                case=case
            )
        else:
            context['event_form'] = CaseEventForm(
                tenant=self.request.tenant,
                case=case
            )
        
        # Add event search form
        context['event_search_form'] = CaseEventSearchForm(
            self.request.GET,
            tenant=self.request.tenant
        )
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle event creation."""
        self.object = self.get_object()
        case = self.object
        
        if 'event_form' in request.POST:
            form = CaseEventForm(
                request.POST,
                tenant=case.tenant,
                case=case
            )
            
            if form.is_valid():
                event = form.save(commit=False)
                event.tenant = self.request.tenant
                event.case = case
                event.created_by = request.user
                event.save()
                
                messages.success(request, 'Event added successfully.')
                return redirect('cases:detail', pk=case.pk)
            else:
                context = self.get_context_data(object=self.object)
                context['event_form'] = form
                return self.render_to_response(context)
        
        return super().get(request, *args, **kwargs)


class CaseCreateView(TenantPermissionRequiredMixin, LoginRequiredMixin, CreateView):
    """Create view for a new case."""
    model = Case
    form_class = CaseForm
    template_name = 'cases/case_form.html'
    success_url = reverse_lazy('cases:list')
    permission_required = 'cases.add_case'
    
    def get_form_kwargs(self):
        """Pass tenant and user to form."""
        kwargs = super().get_form_kwargs()
        kwargs['tenant'] = self.request.tenant
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        """Set tenant and created_by before saving."""
        form.instance.tenant = self.request.tenant
        form.instance.created_by = self.request.user
        
        case = form.save()
        
        # Log activity
        log_activity(
            tenant=self.request.tenant,
            user=self.request.user,
            activity_type='CASE_CREATED',
            description=f'Created new case: {case.title} ({case.case_number})',
            related_object=case
        )
        
        messages.success(self.request, 'Case created successfully.')
        return super().form_valid(form)


class CaseUpdateView(TenantPermissionRequiredMixin, LoginRequiredMixin, UpdateView):
    """Update view for a case."""
    model = Case
    form_class = CaseForm
    template_name = 'cases/case_form.html'
    permission_required = 'cases.change_case'
    
    def get_queryset(self):
        """Filter cases by tenant."""
        return Case.objects.active_for_tenant(self.request.tenant)
    
    def get_form_kwargs(self):
        """Pass tenant and user to form."""
        kwargs = super().get_form_kwargs()
        kwargs['tenant'] = self.request.tenant
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        """Update case and show success message."""
        # Get old values for audit
        old_values = {
            'title': self.object.title,
            'description': self.object.description,
            'status': self.object.status,
            'case_type': self.object.case_type,
        }
        
        case = form.save()
        
        # Log activity with changes
        log_activity(
            tenant=self.request.tenant,
            user=self.request.user,
            activity_type='CASE_UPDATED',
            description=f'Updated case: {case.title} ({case.case_number})',
            related_object=case,
            metadata={
                'old_values': old_values,
                'new_values': {
                    'title': case.title,
                    'description': case.description,
                    'status': case.status,
                    'case_type': case.case_type,
                }
            }
        )
        
        messages.success(self.request, 'Case updated successfully.')
        return super().form_valid(form)


class CaseDeleteView(TenantPermissionRequiredMixin, LoginRequiredMixin, DeleteView):
    """Delete view for a case (soft delete)."""
    model = Case
    template_name = 'cases/case_confirm_delete.html'
    success_url = reverse_lazy('cases:list')
    permission_required = 'cases.delete_case'
    
    def get_queryset(self):
        """Filter cases by tenant."""
        return Case.objects.active_for_tenant(self.request.user.tenant)
    
    def delete(self, request, *args, **kwargs):
        """Perform soft delete."""
        self.object = self.get_object()
        case = self.object
        case.soft_delete()
        
        # Log activity
        log_activity(
            tenant=request.tenant,
            user=request.user,
            activity_type='CASE_DELETED',
            description=f'Deleted case: {case.title} ({case.case_number})',
            related_object=case,
            metadata={
                'deleted_case_data': {
                    'title': case.title,
                    'case_number': case.case_number,
                    'status': case.status,
                }
            }
        )
        
        messages.success(request, 'Case deleted successfully.')
        return redirect(self.get_success_url())


class CaseEventCreateView(TenantPermissionRequiredMixin, LoginRequiredMixin, CreateView):
    """Create view for a new case event."""
    model = CaseEvent
    form_class = CaseEventForm
    template_name = 'cases/caseevent_form.html'
    permission_required = 'cases.change_case'  # Using change_case as it's modifying case data
    
    def dispatch(self, request, *args, **kwargs):
        """Get case object and validate tenant access."""
        self.case = get_object_or_404(
            Case.objects.active_for_tenant(request.tenant),
            pk=kwargs['case_pk']
        )
        return super().dispatch(request, *args, **kwargs)
    
    def get_form_kwargs(self):
        """Pass tenant and case to form."""
        kwargs = super().get_form_kwargs()
        kwargs['tenant'] = self.request.tenant
        kwargs['case'] = self.case
        return kwargs
    
    def form_valid(self, form):
        """Set tenant, case, and created_by before saving."""
        form.instance.tenant = self.request.tenant
        form.instance.case = self.case
        form.instance.created_by = self.request.user
        
        event = form.save()
        
        # Log activity
        log_activity(
            tenant=self.request.tenant,
            user=self.request.user,
            activity_type='CASE_EVENT_CREATED',
            description=f'Added event to case {self.case.case_number}: {event.title}',
            related_object=event,
            metadata={
                'case_id': self.case.id,
                'case_number': self.case.case_number,
                'event_type': event.event_type,
            }
        )
        
        messages.success(self.request, 'Event created successfully.')
        return super().form_valid(form)
    
    def get_success_url(self):
        """Redirect to case detail view."""
        return reverse_lazy('cases:detail', kwargs={'pk': self.case.pk})


class CaseEventUpdateView(TenantPermissionRequiredMixin, LoginRequiredMixin, UpdateView):
    """Update view for a case event."""
    model = CaseEvent
    form_class = CaseEventForm
    template_name = 'cases/caseevent_form.html'
    permission_required = 'cases.change_case'  # Using change_case as it's modifying case data
    
    def get_queryset(self):
        """Filter events by tenant."""
        return CaseEvent.objects.for_tenant(self.request.tenant)
    
    def get_form_kwargs(self):
        """Pass tenant and case to form."""
        kwargs = super().get_form_kwargs()
        kwargs['tenant'] = self.request.tenant
        kwargs['case'] = self.get_object().case
        return kwargs
    
    def form_valid(self, form):
        """Update event and show success message."""
        messages.success(self.request, 'Event updated successfully.')
        return super().form_valid(form)
    
    def get_success_url(self):
        """Redirect to case detail view."""
        return reverse_lazy('cases:detail', kwargs={'pk': self.get_object().case.pk})


class CaseEventDeleteView(TenantPermissionRequiredMixin, LoginRequiredMixin, DeleteView):
    """Delete view for a case event."""
    model = CaseEvent
    template_name = 'cases/caseevent_confirm_delete.html'
    permission_required = 'cases.change_case'  # Using change_case as it's modifying case data
    
    def get_queryset(self):
        """Filter events by tenant."""
        return CaseEvent.objects.for_tenant(self.request.tenant)
    
    def get_success_url(self):
        """Redirect to case detail view."""
        return reverse_lazy('cases:detail', kwargs={'pk': self.get_object().case.pk})
    
    def delete(self, request, *args, **kwargs):
        """Delete event and show success message."""
        self.object = self.get_object()
        messages.success(request, 'Event deleted successfully.')
        return super().delete(request, *args, **kwargs)
