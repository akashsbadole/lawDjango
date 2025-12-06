from typing import TYPE_CHECKING
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponseForbidden, HttpRequest
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from django.core.paginator import Paginator
from datetime import timedelta, date
from permissions.mixins import RoleRequiredMixin, TenantPermissionRequiredMixin

from clients.models import Client
from cases.models import Case, CaseEvent
from documents.models import Document
from billing.models import TimeEntry, Expense, Invoice, Payment
from .forms import (
    ClientForm, CaseForm, CaseEventForm, DocumentForm, 
    TimeEntryForm, ExpenseForm, QuickSearchForm
)

if TYPE_CHECKING:
    from tenants.models import Tenant
    from accounts.models import CustomUser

# Type hints for request object with tenant attribute
class TenantHttpRequest(HttpRequest):
    tenant: 'Tenant'

# Type hints for model instances with relationships
class CaseWithRelations(Case):
    events: 'CaseEventQuerySet'
    documents: 'DocumentQuerySet'
    time_entries: 'TimeEntryQuerySet'
    expenses: 'ExpenseQuerySet'

class ClientWithRelations(Client):
    cases: 'CaseQuerySet'
    documents: 'DocumentQuerySet'

class DocumentWithAccess(Document):
    def can_be_accessed_by(self, user: 'CustomUser') -> bool: ...

# Type hints for querysets
from django.db.models import QuerySet
class CaseQuerySet(QuerySet[CaseWithRelations]): ...
class CaseEventQuerySet(QuerySet[CaseEvent]): ...
class DocumentQuerySet(QuerySet[Document]): ...
class TimeEntryQuerySet(QuerySet[TimeEntry]): ...
class ExpenseQuerySet(QuerySet[Expense]): ...


class LawyerPanelRequiredMixin(RoleRequiredMixin, LoginRequiredMixin):
    """Mixin to ensure user has lawyer role and belongs to a tenant."""
    role_required = 'lawyer'
    
    def dispatch(self, request: TenantHttpRequest, *args, **kwargs):
        # Check if user is authenticated first
        if not request.user.is_authenticated:
            return redirect(f'/accounts/login/?{REDIRECT_FIELD_NAME}={request.get_full_path()}')
        
        # Also allow admins to access lawyer panel
        if not hasattr(request.user, 'role') or request.user.role.lower() not in ['lawyer', 'admin']:
            messages.error(request, "You don't have permission to access lawyer panel.")
            return redirect('home')
        
        # Get tenant - either from request.tenant (set by middleware) or from user.tenant
        tenant = getattr(request, 'tenant', None)
        if not tenant and hasattr(request.user, 'tenant'):
            tenant = request.user.tenant
        
        if not tenant:
            # Instead of redirecting to home (which might cause a loop),
            # show a clear error message and render an error template
            from django.shortcuts import render
            messages.error(
                request,
                "Your account is not associated with any law firm. "
                "Please contact your administrator to get access to a tenant."
            )
            return render(request, 'lawyer_panel/no_tenant_error.html', {
                'user': request.user,
                'title': 'No Tenant Assigned'
            })
        
        # Set tenant on request for views to use
        request.tenant = tenant
        
        return super().dispatch(request, *args, **kwargs)


class DashboardView(LawyerPanelRequiredMixin, ListView):
    """Dashboard view showing summary of lawyer's activities."""
    template_name = 'lawyer_panel/dashboard.html'
    context_object_name = 'recent_cases'
    paginate_by = 5
    
    def get_queryset(self):
        # Get recent cases assigned to the lawyer
        return Case.objects.filter(
            tenant=self.request.tenant,
            assigned_lawyers=self.request.user,
            deleted_at__isnull=True
        ).order_by('-updated_at')[:5]
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant
        user = self.request.user
        
        # Get counts and summaries
        context.update({
            'active_cases_count': Case.objects.filter(
                tenant=tenant, assigned_lawyers=user, status='open', deleted_at__isnull=True
            ).count(),
            'total_clients_count': Client.objects.filter(
                tenant=tenant, deleted_at__isnull=True
            ).count(),
            'recent_documents_count': Document.objects.filter(
                tenant=tenant, uploaded_by=user, deleted_at__isnull=True,
                created_at__gte=timezone.now() - timedelta(days=30)
            ).count(),
            'upcoming_hearings': CaseEvent.objects.filter(
                tenant=tenant, case__assigned_lawyers=user,
                event_type='hearing', event_date__gte=timezone.now(),
                event_date__lte=timezone.now() + timedelta(days=30)
            ).order_by('event_date')[:5],
            'total_billable_hours': TimeEntry.objects.filter(
                tenant=tenant, lawyer=user, is_billable=True,
                date__gte=timezone.now() - timedelta(days=30)
            ).aggregate(total=Sum('hours'))['total'] or 0,
            'total_billed_amount': Invoice.objects.filter(
                tenant=tenant, created_by=user, status='paid',
                created_at__gte=timezone.now() - timedelta(days=30)
            ).aggregate(total=Sum('total_amount'))['total'] or 0,
            'recent_time_entries': TimeEntry.objects.filter(
                tenant=tenant, lawyer=user
            ).order_by('-date', '-created_at')[:5],
            'recent_expenses': Expense.objects.filter(
                tenant=tenant, created_by=user
            ).order_by('-date', '-created_at')[:5],
            'search_form': QuickSearchForm(),
        })
        
        return context


class CaseListView(LawyerPanelRequiredMixin, ListView):
    """List view for cases assigned to the lawyer."""
    model = Case
    template_name = 'lawyer_panel/case_list.html'
    context_object_name = 'cases'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = Case.objects.filter(
            tenant=self.request.tenant,
            assigned_lawyers=self.request.user,
            deleted_at__isnull=True
        )
        
        # Apply filters
        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        case_type_filter = self.request.GET.get('case_type')
        if case_type_filter:
            queryset = queryset.filter(case_type=case_type_filter)
        
        client_filter = self.request.GET.get('client')
        if client_filter:
            queryset = queryset.filter(client_id=client_filter)
        
        # Search
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(case_number__icontains=search_query) |
                Q(client__first_name__icontains=search_query) |
                Q(client__last_name__icontains=search_query)
            )
        
        return queryset.order_by('-updated_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'status_choices': Case.STATUS_CHOICES,
            'case_type_choices': Case.CASE_TYPE_CHOICES,
            'clients': Client.objects.filter(
                tenant=self.request.tenant, deleted_at__isnull=True
            ),
            'search_form': QuickSearchForm(self.request.GET),
        })
        return context


class CaseDetailView(LawyerPanelRequiredMixin, DetailView):
    """Detail view for a specific case."""
    model = Case
    template_name = 'lawyer_panel/case_detail.html'
    context_object_name = 'case'
    
    def get_queryset(self):
        return Case.objects.filter(
            tenant=self.request.tenant,
            assigned_lawyers=self.request.user,
            deleted_at__isnull=True
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        case = self.get_object()
        
        context.update({
            'events': case.events.order_by('-event_date'),
            'documents': case.documents.filter(deleted_at__isnull=True),
            'time_entries': case.time_entries.filter(lawyer=self.request.user).order_by('-date'),
            'expenses': case.expenses.filter(created_by=self.request.user).order_by('-date'),
            'event_form': CaseEventForm(initial={'case': case}),
        })
        return context


class CaseCreateView(LawyerPanelRequiredMixin, CreateView):
    """Create view for new cases."""
    model = Case
    form_class = CaseForm
    template_name = 'lawyer_panel/case_form.html'
    success_url = reverse_lazy('lawyer_panel:case_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs
    
    def form_valid(self, form):
        form.instance.tenant = self.request.tenant
        form.instance.created_by = self.request.user
        messages.success(self.request, f'Case "{form.instance.title}" has been created successfully.')
        return super().form_valid(form)


class CaseUpdateView(LawyerPanelRequiredMixin, UpdateView):
    """Update view for existing cases."""
    model = Case
    form_class = CaseForm
    template_name = 'lawyer_panel/case_form.html'
    success_url = reverse_lazy('lawyer_panel:case_list')
    
    def get_queryset(self):
        return Case.objects.filter(
            tenant=self.request.tenant,
            assigned_lawyers=self.request.user,
            deleted_at__isnull=True
        )
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs
    
    def form_valid(self, form):
        messages.success(self.request, f'Case "{form.instance.title}" has been updated successfully.')
        return super().form_valid(form)


class ClientListView(LawyerPanelRequiredMixin, ListView):
    """List view for clients."""
    model = Client
    template_name = 'lawyer_panel/client_list.html'
    context_object_name = 'clients'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = Client.objects.filter(
            tenant=self.request.tenant,
            deleted_at__isnull=True
        )
        
        # Search
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(company__icontains=search_query)
            )
        
        return queryset.order_by('last_name', 'first_name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = QuickSearchForm(self.request.GET)
        return context


class ClientDetailView(LawyerPanelRequiredMixin, DetailView):
    """Detail view for a specific client."""
    model = Client
    template_name = 'lawyer_panel/client_detail.html'
    context_object_name = 'client'
    
    def get_queryset(self):
        return Client.objects.filter(
            tenant=self.request.tenant,
            deleted_at__isnull=True
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        client = self.get_object()
        
        context.update({
            'cases': client.cases.filter(
                assigned_lawyers=self.request.user,
                deleted_at__isnull=True
            ).order_by('-updated_at'),
            'documents': client.documents.filter(
                uploaded_by=self.request.user,
                deleted_at__isnull=True
            ).order_by('-created_at'),
        })
        return context


class ClientCreateView(LawyerPanelRequiredMixin, CreateView):
    """Create view for new clients."""
    model = Client
    form_class = ClientForm
    template_name = 'lawyer_panel/client_form.html'
    success_url = reverse_lazy('lawyer_panel:client_list')
    
    def form_valid(self, form):
        form.instance.tenant = self.request.tenant
        form.instance.created_by = self.request.user
        messages.success(self.request, f'Client "{form.instance.full_name}" has been created successfully.')
        return super().form_valid(form)


class ClientUpdateView(LawyerPanelRequiredMixin, UpdateView):
    """Update view for existing clients."""
    model = Client
    form_class = ClientForm
    template_name = 'lawyer_panel/client_form.html'
    success_url = reverse_lazy('lawyer_panel:client_list')
    
    def get_queryset(self):
        return Client.objects.filter(
            tenant=self.request.tenant,
            deleted_at__isnull=True
        )
    
    def form_valid(self, form):
        messages.success(self.request, f'Client "{form.instance.full_name}" has been updated successfully.')
        return super().form_valid(form)


class DocumentListView(LawyerPanelRequiredMixin, ListView):
    """List view for documents."""
    model = Document
    template_name = 'lawyer_panel/document_list.html'
    context_object_name = 'documents'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = Document.objects.filter(
            tenant=self.request.tenant,
            uploaded_by=self.request.user,
            deleted_at__isnull=True
        )
        
        # Apply filters
        category_filter = self.request.GET.get('category')
        if category_filter:
            queryset = queryset.filter(category=category_filter)
        
        access_level_filter = self.request.GET.get('access_level')
        if access_level_filter:
            queryset = queryset.filter(access_level=access_level_filter)
        
        case_filter = self.request.GET.get('case')
        if case_filter:
            queryset = queryset.filter(case_id=case_filter)
        
        client_filter = self.request.GET.get('client')
        if client_filter:
            queryset = queryset.filter(client_id=client_filter)
        
        # Search
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(file_name__icontains=search_query) |
                Q(tags__icontains=search_query)
            )
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'category_choices': Document.CATEGORY_CHOICES,
            'access_level_choices': Document.ACCESS_LEVEL_CHOICES,
            'cases': Case.objects.filter(
                tenant=self.request.tenant,
                assigned_lawyers=self.request.user,
                deleted_at__isnull=True
            ),
            'clients': Client.objects.filter(
                tenant=self.request.tenant,
                deleted_at__isnull=True
            ),
            'search_form': QuickSearchForm(self.request.GET),
        })
        return context


class DocumentDetailView(LawyerPanelRequiredMixin, DetailView):
    """Detail view for a specific document."""
    model = Document
    template_name = 'lawyer_panel/document_detail.html'
    context_object_name = 'document'
    
    def get_queryset(self):
        return Document.objects.filter(
            tenant=self.request.tenant,
            deleted_at__isnull=True
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        document = self.get_object()
        
        # Check if user can access this document
        if not document.can_be_accessed_by(self.request.user):
            context['access_denied'] = True
        
        return context


class DocumentCreateView(LawyerPanelRequiredMixin, CreateView):
    """Create view for new documents."""
    model = Document
    form_class = DocumentForm
    template_name = 'lawyer_panel/document_form.html'
    success_url = reverse_lazy('lawyer_panel:document_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs
    
    def form_valid(self, form):
        form.instance.tenant = self.request.tenant
        form.instance.uploaded_by = self.request.user
        messages.success(self.request, f'Document "{form.instance.title}" has been uploaded successfully.')
        return super().form_valid(form)


class TimeEntryListView(LawyerPanelRequiredMixin, ListView):
    """List view for time entries."""
    model = TimeEntry
    template_name = 'lawyer_panel/time_entry_list.html'
    context_object_name = 'time_entries'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = TimeEntry.objects.filter(
            tenant=self.request.tenant,
            lawyer=self.request.user,
            deleted_at__isnull=True
        )
        
        # Apply filters
        case_filter = self.request.GET.get('case')
        if case_filter:
            queryset = queryset.filter(case_id=case_filter)
        
        date_from = self.request.GET.get('date_from')
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        
        date_to = self.request.GET.get('date_to')
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        
        is_billed = self.request.GET.get('is_billed')
        if is_billed == 'yes':
            queryset = queryset.filter(is_billable=True)
        elif is_billed == 'no':
            queryset = queryset.filter(is_billable=False)
        
        return queryset.order_by('-date', '-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'cases': Case.objects.filter(
                tenant=self.request.tenant,
                assigned_lawyers=self.request.user,
                deleted_at__isnull=True
            ),
            'total_hours': self.get_queryset().aggregate(
                total=Sum('hours')
            )['total'] or 0,
            'total_amount': self.get_queryset().aggregate(
                total=Sum('hours') * Avg('rate')
            )['total'] or 0,
        })
        return context


class TimeEntryCreateView(LawyerPanelRequiredMixin, CreateView):
    """Create view for new time entries."""
    model = TimeEntry
    form_class = TimeEntryForm
    template_name = 'lawyer_panel/time_entry_form.html'
    success_url = reverse_lazy('lawyer_panel:time_entry_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs
    
    def form_valid(self, form):
        form.instance.tenant = self.request.tenant
        form.instance.lawyer = self.request.user
        form.instance.created_by = self.request.user
        messages.success(self.request, f'Time entry has been logged successfully.')
        return super().form_valid(form)


class ExpenseListView(LawyerPanelRequiredMixin, ListView):
    """List view for expenses."""
    model = Expense
    template_name = 'lawyer_panel/expense_list.html'
    context_object_name = 'expenses'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Expense.objects.filter(
            tenant=self.request.tenant,
            created_by=self.request.user,
            deleted_at__isnull=True
        )
        
        # Apply filters
        case_filter = self.request.GET.get('case')
        if case_filter:
            queryset = queryset.filter(case_id=case_filter)
        
        category_filter = self.request.GET.get('category')
        if category_filter:
            queryset = queryset.filter(category=category_filter)
        
        date_from = self.request.GET.get('date_from')
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        
        date_to = self.request.GET.get('date_to')
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        
        return queryset.order_by('-date', '-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'category_choices': Expense.CATEGORY_CHOICES,
            'cases': Case.objects.filter(
                tenant=self.request.tenant,
                assigned_lawyers=self.request.user,
                deleted_at__isnull=True
            ),
            'total_amount': self.get_queryset().aggregate(
                total=Sum('amount')
            )['total'] or 0,
        })
        return context


class ExpenseCreateView(LawyerPanelRequiredMixin, CreateView):
    """Create view for new expenses."""
    model = Expense
    form_class = ExpenseForm
    template_name = 'lawyer_panel/expense_form.html'
    success_url = reverse_lazy('lawyer_panel:expense_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs
    
    def form_valid(self, form):
        form.instance.tenant = self.request.tenant
        form.instance.created_by = self.request.user
        messages.success(self.request, f'Expense has been added successfully.')
        return super().form_valid(form)


class BillingDashboardView(LawyerPanelRequiredMixin, ListView):
    """Dashboard view for billing and time tracking."""
    model = TimeEntry
    template_name = 'lawyer_panel/billing_dashboard.html'
    context_object_name = 'recent_time_entries'
    paginate_by = 10
    
    def get_queryset(self):
        # Get recent time entries
        return TimeEntry.objects.filter(
            tenant=self.request.tenant,
            lawyer=self.request.user,
            deleted_at__isnull=True
        ).order_by('-date', '-created_at')[:10]
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant
        user = self.request.user
        
        # Get billing statistics
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        context.update({
            'total_billable_hours': TimeEntry.objects.filter(
                tenant=tenant, lawyer=user, is_billable=True,
                date__gte=thirty_days_ago
            ).aggregate(total=Sum('hours'))['total'] or 0,
            'total_billed_amount': Invoice.objects.filter(
                tenant=tenant, created_by=user, status='paid',
                created_at__gte=thirty_days_ago
            ).aggregate(total=Sum('total_amount'))['total'] or 0,
            'unbilled_hours': TimeEntry.objects.filter(
                tenant=tenant, lawyer=user, is_billable=True
            ).exclude(
                invoice_items__isnull=False
            ).aggregate(total=Sum('hours'))['total'] or 0,
            'recent_expenses': Expense.objects.filter(
                tenant=tenant, created_by=user
            ).order_by('-date', '-created_at')[:5],
            'total_expenses': Expense.objects.filter(
                tenant=tenant, created_by=user,
                date__gte=thirty_days_ago
            ).aggregate(total=Sum('amount'))['total'] or 0,
        })
        
        return context


@login_required
def add_case_event(request: TenantHttpRequest, case_id: int):
    """Add an event to a case."""
    if not hasattr(request.user, 'role') or request.user.role.lower() not in ['lawyer', 'admin']:
        return HttpResponseForbidden()
    
    case = get_object_or_404(
        Case, 
        pk=case_id, 
        tenant=request.tenant,
        assigned_lawyers=request.user,
        deleted_at__isnull=True
    )
    
    if request.method == 'POST':
        form = CaseEventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            event.case = case
            event.tenant = request.tenant
            event.created_by = request.user
            event.save()
            messages.success(request, f'Event "{event.title}" has been added successfully.')
            return redirect('lawyer_panel:case_detail', pk=case.pk)
    else:
        form = CaseEventForm(initial={'case': case})
    
    return render(request, 'lawyer_panel/case_event_form.html', {
        'form': form,
        'case': case,
    })


@login_required
def quick_search(request: TenantHttpRequest):
    """Quick search across different modules."""
    if not hasattr(request.user, 'role') or request.user.role.lower() not in ['lawyer', 'admin']:
        return HttpResponseForbidden()
    
    form = QuickSearchForm(request.GET)
    results = {}
    
    if form.is_valid():
        query = form.cleaned_data['query']
        search_type = form.cleaned_data['search_type']
        tenant = request.tenant
        
        if search_type in ['all', 'cases']:
            results['cases'] = Case.objects.filter(
                tenant=tenant,
                assigned_lawyers=request.user,
                deleted_at__isnull=True,
                title__icontains=query
            )[:5]
        
        if search_type in ['all', 'clients']:
            results['clients'] = Client.objects.filter(
                tenant=tenant,
                deleted_at__isnull=True
            ).filter(
                Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(email__icontains=query)
            )[:5]
        
        if search_type in ['all', 'documents']:
            results['documents'] = Document.objects.filter(
                tenant=tenant,
                uploaded_by=request.user,
                deleted_at__isnull=True,
                title__icontains=query
            )[:5]
    
    return render(request, 'lawyer_panel/quick_search_results.html', {
        'form': form,
        'results': results,
    })
