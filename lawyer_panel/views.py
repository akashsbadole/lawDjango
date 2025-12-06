from typing import TYPE_CHECKING
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.views.decorators.http import require_http_methods
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponseForbidden, HttpRequest
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from django.core.paginator import Paginator
from datetime import timedelta, date
from permissions.mixins import RoleRequiredMixin, TenantPermissionRequiredMixin

from core.types import TenantHttpRequest
from clients.models import Client
from cases.models import Case, CaseEvent
from documents.models import Document
from billing.models import TimeEntry, Expense, Invoice, Payment, InvoiceItem
from .forms import (
    ClientForm, CaseForm, CaseEventForm, DocumentForm,
    TimeEntryForm, ExpenseForm, QuickSearchForm, LawyerProfileForm,
    PracticeAreaForm, LawyerQualificationForm, LawyerProfileSearchForm,
    LawyerAvailabilityForm
)
from .models import LawyerProfile, PracticeArea, LawyerQualification

if TYPE_CHECKING:
    from tenants.models import Tenant
    from accounts.models import CustomUser

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
        if not hasattr(request.user, 'role') or request.user.role.lower() not in ['lawyer', 'admin']:  # type: ignore
            messages.error(request, "You don't have permission to access lawyer panel.")
            return redirect('home')
        
        # Get tenant - either from request.tenant (set by middleware) or from user.tenant
        tenant = getattr(request, 'tenant', None)
        if not tenant and hasattr(request.user, 'tenant'):  # type: ignore
            tenant = request.user.tenant  # type: ignore
        
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
            tenant=self.request.tenant,  # type: ignore
            assigned_lawyers=self.request.user,
            deleted_at__isnull=True
        ).order_by('-updated_at')[:5]
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant  # type: ignore
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
            tenant=self.request.tenant,  # type: ignore
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
                tenant=self.request.tenant, deleted_at__isnull=True  # type: ignore
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
            tenant=self.request.tenant,  # type: ignore
            assigned_lawyers=self.request.user,
            deleted_at__isnull=True
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        case = self.get_object()
        
        context.update({
            'events': case.events.order_by('-event_date'),  # type: ignore
            'documents': case.documents.filter(deleted_at__isnull=True),  # type: ignore
            'time_entries': case.time_entries.filter(lawyer=self.request.user).order_by('-date'),  # type: ignore
            'expenses': case.expenses.filter(created_by=self.request.user).order_by('-date'),  # type: ignore
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
        form.instance.tenant = self.request.tenant  # type: ignore
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
            tenant=self.request.tenant,  # type: ignore
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
            tenant=self.request.tenant,  # type: ignore
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
            tenant=self.request.tenant,  # type: ignore
            deleted_at__isnull=True
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        client = self.get_object()
        
        context.update({
            'cases': client.cases.filter(  # type: ignore
                assigned_lawyers=self.request.user,
                deleted_at__isnull=True
            ).order_by('-updated_at'),
            'documents': client.documents.filter(  # type: ignore
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
        form.instance.tenant = self.request.tenant  # type: ignore
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
            tenant=self.request.tenant,  # type: ignore
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
            tenant=self.request.tenant,  # type: ignore
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
                tenant=self.request.tenant,  # type: ignore
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
        form.instance.tenant = self.request.tenant  # type: ignore
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
            tenant=self.request.tenant,  # type: ignore
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
                tenant=self.request.tenant,  # type: ignore
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
        form.instance.tenant = self.request.tenant  # type: ignore
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
            tenant=self.request.tenant,  # type: ignore
            lawyer=self.request.user,
            deleted_at__isnull=True
        ).order_by('-date', '-created_at')[:10]
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant  # type: ignore
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
    if not hasattr(request.user, 'role') or request.user.role.lower() not in ['lawyer', 'admin']:  # type: ignore
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
    if not hasattr(request.user, 'role') or request.user.role.lower() not in ['lawyer', 'admin']:  # type: ignore
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


# Lawyer Profile Views

class LawyerProfileListView(LawyerPanelRequiredMixin, ListView):
    """List view for lawyer profiles with filtering capabilities."""
    model = LawyerProfile
    template_name = 'lawyer_panel/lawyer_profile_list.html'
    context_object_name = 'lawyer_profiles'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = LawyerProfile.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            deleted_at__isnull=True
        ).select_related('user').prefetch_related('practice_areas', 'qualifications')
        
        # Apply search filter
        search_form = LawyerProfileSearchForm(self.request.GET, request=self.request)
        if search_form.is_valid():
            cleaned_data = search_form.cleaned_data
            
            # Text search
            search_query = cleaned_data.get('search')
            if search_query:
                queryset = queryset.filter(
                    Q(user__first_name__icontains=search_query) |
                    Q(user__last_name__icontains=search_query) |
                    Q(user__email__icontains=search_query) |
                    Q(bar_number__icontains=search_query) |
                    Q(law_school__icontains=search_query) |
                    Q(specializations__icontains=search_query)
                )
            
            # Experience level filter
            experience_levels = cleaned_data.get('experience_level')
            if experience_levels:
                queryset = queryset.filter(experience_level__in=experience_levels)
            
            # Practice areas filter
            practice_areas = cleaned_data.get('practice_areas')
            if practice_areas:
                queryset = queryset.filter(practice_areas__in=practice_areas).distinct()
            
            # Billing method filter
            billing_methods = cleaned_data.get('billing_method')
            if billing_methods:
                queryset = queryset.filter(billing_method__in=billing_methods)
            
            # Availability filter
            is_available = cleaned_data.get('is_available')
            if is_available:
                queryset = queryset.filter(is_available=True)
            
            # Experience range filter
            min_experience = cleaned_data.get('min_experience')
            max_experience = cleaned_data.get('max_experience')
            if min_experience is not None:
                queryset = queryset.filter(years_of_experience__gte=min_experience)
            if max_experience is not None:
                queryset = queryset.filter(years_of_experience__lte=max_experience)
            
            # Qualifications filter
            has_qualifications = cleaned_data.get('has_qualifications')
            if has_qualifications:
                queryset = queryset.filter(qualifications__isnull=False).distinct()
        
        return queryset.order_by('user__last_name', 'user__first_name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = LawyerProfileSearchForm(self.request.GET, request=self.request)
        context['total_profiles'] = self.get_queryset().count()
        return context


class LawyerProfileDetailView(LawyerPanelRequiredMixin, DetailView):
    """Detail view for lawyer profiles."""
    model = LawyerProfile
    template_name = 'lawyer_panel/lawyer_profile_detail.html'
    context_object_name = 'lawyer_profile'
    
    def get_queryset(self):
        return LawyerProfile.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            deleted_at__isnull=True
        ).select_related('user').prefetch_related('practice_areas', 'qualifications')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        lawyer_profile = self.get_object()
        
        # Get related cases
        from cases.models import Case
        context['recent_cases'] = Case.objects.filter(
            assigned_lawyers=lawyer_profile.user,
            tenant=self.request.tenant,  # type: ignore
            deleted_at__isnull=True
        ).order_by('-updated_at')[:5]
        
        # Calculate statistics
        context['profile_completion'] = lawyer_profile.get_profile_completion_percentage()  # type: ignore
        context['availability_percentage'] = lawyer_profile.availability_percentage  # type: ignore
        
        return context


class LawyerProfileCreateView(LawyerPanelRequiredMixin, CreateView):
    """Create view for new lawyer profiles."""
    model = LawyerProfile
    form_class = LawyerProfileForm
    template_name = 'lawyer_panel/lawyer_profile_form.html'
    success_url = reverse_lazy('lawyer_panel:lawyer_profile_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs
    
    def form_valid(self, form):
        form.instance.tenant = self.request.tenant
        form.instance.user = self.request.user
        messages.success(self.request, f'Lawyer profile for {form.instance.user.get_full_name()} has been created successfully.')  # type: ignore
        return super().form_valid(form)
    
    def dispatch(self, request, *args, **kwargs):
        # Check if user already has a profile
        if hasattr(request.user, 'lawyer_profile'):
            messages.warning(request, 'You already have a lawyer profile. You can edit it instead.')
            return redirect('lawyer_panel:lawyer_profile_detail', pk=request.user.lawyer_profile.pk)  # type: ignore
        return super().dispatch(request, *args, **kwargs)


class LawyerProfileUpdateView(LawyerPanelRequiredMixin, UpdateView):
    """Update view for existing lawyer profiles."""
    model = LawyerProfile
    form_class = LawyerProfileForm
    template_name = 'lawyer_panel/lawyer_profile_form.html'
    success_url = reverse_lazy('lawyer_panel:lawyer_profile_list')
    
    def get_queryset(self):
        return LawyerProfile.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            deleted_at__isnull=True
        )
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs
    
    def form_valid(self, form):
        messages.success(self.request, f'Lawyer profile for {form.instance.user.get_full_name()} has been updated successfully.')
        return super().form_valid(form)


# Practice Area Views

class PracticeAreaListView(LawyerPanelRequiredMixin, ListView):
    """List view for practice areas."""
    model = PracticeArea
    template_name = 'lawyer_panel/practice_area_list.html'
    context_object_name = 'practice_areas'
    paginate_by = 20
    
    def get_queryset(self):
        return PracticeArea.objects.filter(
            tenant=self.request.tenant
        ).order_by('name')


class PracticeAreaCreateView(LawyerPanelRequiredMixin, CreateView):
    """Create view for new practice areas."""
    model = PracticeArea
    form_class = PracticeAreaForm
    template_name = 'lawyer_panel/practice_area_form.html'
    success_url = reverse_lazy('lawyer_panel:practice_area_list')
    
    def form_valid(self, form):
        form.instance.tenant = self.request.tenant  # type: ignore
        messages.success(self.request, f'Practice area "{form.instance.name}" has been created successfully.')
        return super().form_valid(form)


class PracticeAreaUpdateView(LawyerPanelRequiredMixin, UpdateView):
    """Update view for existing practice areas."""
    model = PracticeArea
    form_class = PracticeAreaForm
    template_name = 'lawyer_panel/practice_area_form.html'
    success_url = reverse_lazy('lawyer_panel:practice_area_list')
    
    def get_queryset(self):
        return PracticeArea.objects.filter(tenant=self.request.tenant)  # type: ignore
    
    def form_valid(self, form):
        messages.success(self.request, f'Practice area "{form.instance.name}" has been updated successfully.')
        return super().form_valid(form)


# Lawyer Qualification Views

class LawyerQualificationListView(LawyerPanelRequiredMixin, ListView):
    """List view for lawyer qualifications."""
    model = LawyerQualification
    template_name = 'lawyer_panel/lawyer_qualification_list.html'
    context_object_name = 'qualifications'
    paginate_by = 20
    
    def get_queryset(self):
        lawyer_profile_id = self.kwargs.get('lawyer_profile_id')
        if lawyer_profile_id:
            return LawyerQualification.objects.filter(
                lawyer_profile_id=lawyer_profile_id,
                tenant=self.request.tenant
            ).select_related('lawyer_profile__user')
        else:
            return LawyerQualification.objects.filter(
                tenant=self.request.tenant
            ).select_related('lawyer_profile__user')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        lawyer_profile_id = self.kwargs.get('lawyer_profile_id')
        if lawyer_profile_id:
            try:
                context['lawyer_profile'] = LawyerProfile.objects.get(
                    pk=lawyer_profile_id,
                    tenant=self.request.tenant
                )
            except LawyerProfile.DoesNotExist:
                pass
        return context


class LawyerQualificationCreateView(LawyerPanelRequiredMixin, CreateView):
    """Create view for new lawyer qualifications."""
    model = LawyerQualification
    form_class = LawyerQualificationForm
    template_name = 'lawyer_panel/lawyer_qualification_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        lawyer_profile_id = self.kwargs.get('lawyer_profile_id')
        if lawyer_profile_id:
            try:
                kwargs['lawyer_profile'] = LawyerProfile.objects.get(
                    pk=lawyer_profile_id,
                    tenant=self.request.tenant
                )
            except LawyerProfile.DoesNotExist:
                pass
        return kwargs
    
    def get_success_url(self):
        lawyer_profile_id = self.kwargs.get('lawyer_profile_id')
        if lawyer_profile_id:
            return reverse_lazy('lawyer_panel:lawyer_qualification_list', kwargs={'lawyer_profile_id': lawyer_profile_id})
        return reverse_lazy('lawyer_panel:lawyer_qualification_list')
    
    def form_valid(self, form):
        messages.success(self.request, f'Qualification "{form.instance.title}" has been added successfully.')
        return super().form_valid(form)


class LawyerQualificationUpdateView(LawyerPanelRequiredMixin, UpdateView):
    """Update view for existing lawyer qualifications."""
    model = LawyerQualification
    form_class = LawyerQualificationForm
    template_name = 'lawyer_panel/lawyer_qualification_form.html'
    
    def get_queryset(self):
        return LawyerQualification.objects.filter(tenant=self.request.tenant)  # type: ignore
    
    def get_success_url(self):
        return reverse_lazy('lawyer_panel:lawyer_qualification_list', kwargs={
            'lawyer_profile_id': self.object.lawyer_profile.pk
        })
    
    def form_valid(self, form):
        messages.success(self.request, f'Qualification "{form.instance.title}" has been updated successfully.')
        return super().form_valid(form)


# Availability Management Views

class LawyerAvailabilityUpdateView(LawyerPanelRequiredMixin, UpdateView):
    """Update view for lawyer availability settings."""
    model = LawyerProfile
    form_class = LawyerAvailabilityForm
    template_name = 'lawyer_panel/lawyer_availability_form.html'
    
    def get_queryset(self):
        return LawyerProfile.objects.filter(
            tenant=self.request.tenant,
            deleted_at__isnull=True
        )
    
    def get_success_url(self):
        return reverse_lazy('lawyer_panel:lawyer_profile_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        messages.success(self.request, 'Availability settings have been updated successfully.')
        return super().form_valid(form)


# Export Views

@login_required
def export_lawyer_profiles(request: TenantHttpRequest):
    """Export lawyer profiles to CSV."""
    if not hasattr(request.user, 'role') or request.user.role.lower() not in ['lawyer', 'admin']:  # type: ignore
        return HttpResponseForbidden()
    
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="lawyer_profiles.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Name', 'Email', 'Bar Number', 'Law School', 'Graduation Year',
        'Experience Level', 'Years of Experience', 'Practice Areas',
        'Billing Method', 'Hourly Rate', 'Is Available', 'Max Cases',
        'Current Case Load', 'Profile Completion %'
    ])
    
    lawyer_profiles = LawyerProfile.objects.filter(
        tenant=request.tenant,
        deleted_at__isnull=True
    ).select_related('user').prefetch_related('practice_areas')
    
    for profile in lawyer_profiles:
        practice_areas = ', '.join([pa.name for pa in profile.practice_areas.all()])
        writer.writerow([
            profile.full_name,
            profile.user.email,
            profile.bar_number or '',
            profile.law_school or '',
            profile.graduation_year or '',
            profile.get_experience_level_display() or '',
            profile.years_of_experience or '',
            practice_areas,
            profile.get_billing_method_display() or '',
            profile.hourly_rate or '',
            profile.is_available,
            profile.max_cases,
            profile.current_case_load,
            profile.get_profile_completion_percentage()
        ])
    
    return response


@login_required
def update_case_load(request: TenantHttpRequest, lawyer_profile_id: int):
    """Update case load for a specific lawyer profile."""
    if not hasattr(request.user, 'role') or request.user.role.lower() not in ['lawyer', 'admin']:  # type: ignore
        return HttpResponseForbidden()
    
    lawyer_profile = get_object_or_404(
        LawyerProfile,
        pk=lawyer_profile_id,
        tenant=request.tenant,
        deleted_at__isnull=True
    )
    
    lawyer_profile.update_case_load()
    messages.success(request, f'Case load for {lawyer_profile.full_name} has been updated.')
    
    return redirect('lawyer_panel:lawyer_profile_detail', pk=lawyer_profile.pk)


# Invoice Views

class InvoiceListView(LawyerPanelRequiredMixin, ListView):
    """List view for invoices."""
    model = Invoice
    template_name = 'lawyer_panel/invoice_list.html'
    context_object_name = 'invoices'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Invoice.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            deleted_at__isnull=True
        )
        
        # Apply filters
        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        client_filter = self.request.GET.get('client')
        if client_filter:
            queryset = queryset.filter(client_id=client_filter)
        
        date_from = self.request.GET.get('date_from')
        if date_from:
            queryset = queryset.filter(issue_date__gte=date_from)
        
        date_to = self.request.GET.get('date_to')
        if date_to:
            queryset = queryset.filter(issue_date__lte=date_to)
        
        return queryset.order_by('-issue_date', '-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'status_choices': Invoice.STATUS_CHOICES,
            'clients': Client.objects.filter(
                tenant=self.request.tenant,  # type: ignore
                deleted_at__isnull=True
            ),
            'total_amount': self.get_queryset().aggregate(
                total=Sum('total_amount')
            )['total'] or 0,
        })
        return context


class InvoiceDetailView(LawyerPanelRequiredMixin, DetailView):
    """Detail view for a specific invoice."""
    model = Invoice
    template_name = 'lawyer_panel/invoice_detail.html'
    context_object_name = 'invoice'
    
    def get_queryset(self):
        return Invoice.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            deleted_at__isnull=True
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        invoice = self.get_object()
        
        context.update({
            'items': invoice.items.filter(deleted_at__isnull=True),  # type: ignore
            'payments': invoice.payments.filter(deleted_at__isnull=True),  # type: ignore
            'total_paid': sum(p.amount for p in invoice.payments.filter(deleted_at__isnull=True)),  # type: ignore
        })
        return context


class InvoiceCreateView(LawyerPanelRequiredMixin, CreateView):
    """Create view for new invoices."""
    model = Invoice
    template_name = 'lawyer_panel/invoice_form.html'
    success_url = reverse_lazy('lawyer_panel:invoice_list')
    fields = ['client', 'case', 'issue_date', 'due_date', 'tax_rate', 'notes']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create New Invoice'
        context['clients'] = Client.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            deleted_at__isnull=True
        )
        context['cases'] = Case.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            assigned_lawyers=self.request.user,
            deleted_at__isnull=True
        )
        return context
    
    def form_valid(self, form):
        form.instance.tenant = self.request.tenant  # type: ignore
        form.instance.created_by = self.request.user
        
        # Generate invoice number
        from datetime import datetime
        today = datetime.now()
        invoice_count = Invoice.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            created_at__year=today.year,
            created_at__month=today.month
        ).count() + 1
        form.instance.invoice_number = f"INV-{today.strftime('%Y%m')}-{invoice_count:04d}"
        
        messages.success(self.request, f'Invoice "{form.instance.invoice_number}" has been created successfully.')
        return super().form_valid(form)


# Payment Views

class PaymentListView(LawyerPanelRequiredMixin, ListView):
    """List view for payments."""
    model = Payment
    template_name = 'lawyer_panel/payment_list.html'
    context_object_name = 'payments'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Payment.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            deleted_at__isnull=True
        )
        
        # Apply filters
        invoice_filter = self.request.GET.get('invoice')
        if invoice_filter:
            queryset = queryset.filter(invoice_id=invoice_filter)
        
        payment_method_filter = self.request.GET.get('payment_method')
        if payment_method_filter:
            queryset = queryset.filter(payment_method=payment_method_filter)
        
        date_from = self.request.GET.get('date_from')
        if date_from:
            queryset = queryset.filter(payment_date__gte=date_from)
        
        date_to = self.request.GET.get('date_to')
        if date_to:
            queryset = queryset.filter(payment_date__lte=date_to)
        
        return queryset.order_by('-payment_date', '-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'payment_method_choices': Payment.PAYMENT_METHOD_CHOICES,
            'invoices': Invoice.objects.filter(
                tenant=self.request.tenant,  # type: ignore
                deleted_at__isnull=True
            ),
            'total_amount': self.get_queryset().aggregate(
                total=Sum('amount')
            )['total'] or 0,
        })
        return context


class PaymentDetailView(LawyerPanelRequiredMixin, DetailView):
    """Detail view for a specific payment."""
    model = Payment
    template_name = 'lawyer_panel/payment_detail.html'
    context_object_name = 'payment'
    
    def get_queryset(self):
        return Payment.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            deleted_at__isnull=True
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        payment = self.get_object()
        
        context.update({
            'invoice': payment.invoice,  # type: ignore
            'remaining_balance': payment.remaining_balance,  # type: ignore
        })
        return context


class PaymentCreateView(LawyerPanelRequiredMixin, CreateView):
    """Create view for new payments."""
    model = Payment
    template_name = 'lawyer_panel/payment_form.html'
    success_url = reverse_lazy('lawyer_panel:payment_list')
    fields = ['invoice', 'amount', 'payment_date', 'payment_method', 'reference', 'notes']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Record Payment'
        context['invoices'] = Invoice.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            deleted_at__isnull=True,
            status__in=['draft', 'sent', 'overdue']
        )
        return context
    
    def form_valid(self, form):
        form.instance.tenant = self.request.tenant  # type: ignore
        form.instance.created_by = self.request.user
        messages.success(self.request, f'Payment of ${form.instance.amount} has been recorded successfully.')
        return super().form_valid(form)


@login_required
def generate_invoice(request: TenantHttpRequest):
    """Generate an invoice from unbilled time entries and expenses."""
    if not hasattr(request.user, 'role') or request.user.role.lower() not in ['lawyer', 'admin']:  # type: ignore
        return HttpResponseForbidden()
    
    if request.method == 'POST':
        client_id = request.POST.get('client')
        case_id = request.POST.get('case')
        
        if not client_id:
            messages.error(request, 'Please select a client.')
            return redirect('lawyer_panel:generate_invoice')
        
        client = get_object_or_404(
            Client,
            pk=client_id,
            tenant=request.tenant,
            deleted_at__isnull=True
        )
        
        case = None
        if case_id:
            case = get_object_or_404(
                Case,
                pk=case_id,
                tenant=request.tenant,
                deleted_at__isnull=True
            )
        
        # Create invoice
        from datetime import datetime, timedelta
        today = datetime.now()
        due_date = today + timedelta(days=30)
        
        invoice_count = Invoice.objects.filter(
            tenant=request.tenant,
            created_at__year=today.year,
            created_at__month=today.month
        ).count() + 1
        
        invoice = Invoice.objects.create(
            invoice_number=f"INV-{today.strftime('%Y%m')}-{invoice_count:04d}",
            client=client,
            case=case,
            issue_date=today.date(),
            due_date=due_date.date(),
            tenant=request.tenant,
            created_by=request.user
        )
        
        # Add unbilled time entries
        unbilled_time_entries = TimeEntry.objects.filter(
            tenant=request.tenant,
            lawyer=request.user,
            is_billable=True,
            deleted_at__isnull=True
        ).exclude(
            invoice_items__isnull=False
        )
        
        for time_entry in unbilled_time_entries:
            InvoiceItem.objects.create(
                invoice=invoice,
                description=f"Time entry: {time_entry.description}",
                quantity=time_entry.hours,
                rate=time_entry.rate,
                time_entry=time_entry,
                tenant=request.tenant
            )
        
        # Add unbilled expenses
        unbilled_expenses = Expense.objects.filter(
            tenant=request.tenant,
            created_by=request.user,
            is_reimbursable=True,
            deleted_at__isnull=True
        ).exclude(
            invoice_items__isnull=False
        )
        
        for expense in unbilled_expenses:
            InvoiceItem.objects.create(
                invoice=invoice,
                description=f"Expense: {expense.description}",
                quantity=1,
                rate=expense.amount,
                expense=expense,
                tenant=request.tenant
            )
        
        # Calculate totals
        invoice.calculate_totals()
        
        messages.success(
            request,
            f'Invoice {invoice.invoice_number} has been generated with {unbilled_time_entries.count()} time entries and {unbilled_expenses.count()} expenses.'
        )
        return redirect('lawyer_panel:invoice_detail', pk=invoice.pk)
    
    # GET request
    context = {
        'clients': Client.objects.filter(
            tenant=request.tenant,
            deleted_at__isnull=True
        ),
        'cases': Case.objects.filter(
            tenant=request.tenant,
            assigned_lawyers=request.user,
            deleted_at__isnull=True
        ),
        'title': 'Generate Invoice'
    }
    
    return render(request, 'lawyer_panel/generate_invoice.html', context)


# ============================================================================
# DELETE VIEWS - Complete CRUD Implementation
# ============================================================================

class ClientDeleteView(LawyerPanelRequiredMixin, DeleteView):
    """Soft delete view for clients."""
    model = Client
    template_name = 'lawyer_panel/client_confirm_delete.html'
    success_url = reverse_lazy('lawyer_panel:client_list')
    
    def get_queryset(self):
        return Client.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            deleted_at__isnull=True
        )
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.soft_delete()
        messages.success(request, f'Client "{self.object.full_name}" has been deleted successfully.')
        return redirect(self.success_url)


class CaseDeleteView(LawyerPanelRequiredMixin, DeleteView):
    """Soft delete view for cases."""
    model = Case
    template_name = 'lawyer_panel/case_confirm_delete.html'
    success_url = reverse_lazy('lawyer_panel:case_list')
    
    def get_queryset(self):
        return Case.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            assigned_lawyers=self.request.user,
            deleted_at__isnull=True
        )
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.soft_delete()
        messages.success(request, f'Case "{self.object.title}" has been deleted successfully.')
        return redirect(self.success_url)


class DocumentDeleteView(LawyerPanelRequiredMixin, DeleteView):
    """Soft delete view for documents."""
    model = Document
    template_name = 'lawyer_panel/document_confirm_delete.html'
    success_url = reverse_lazy('lawyer_panel:document_list')
    
    def get_queryset(self):
        return Document.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            deleted_at__isnull=True
        )
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.soft_delete()
        messages.success(request, f'Document "{self.object.title}" has been deleted successfully.')
        return redirect(self.success_url)


class TimeEntryDeleteView(LawyerPanelRequiredMixin, DeleteView):
    """Soft delete view for time entries."""
    model = TimeEntry
    template_name = 'lawyer_panel/time_entry_confirm_delete.html'
    success_url = reverse_lazy('lawyer_panel:time_entry_list')
    
    def get_queryset(self):
        return TimeEntry.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            lawyer=self.request.user,
            deleted_at__isnull=True
        )
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        # Check if already billed
        if self.object.is_billed:
            messages.error(request, 'Cannot delete a time entry that has been billed.')
            return redirect('lawyer_panel:time_entry_list')
        self.object.soft_delete()
        messages.success(request, 'Time entry has been deleted successfully.')
        return redirect(self.success_url)


class ExpenseDeleteView(LawyerPanelRequiredMixin, DeleteView):
    """Soft delete view for expenses."""
    model = Expense
    template_name = 'lawyer_panel/expense_confirm_delete.html'
    success_url = reverse_lazy('lawyer_panel:expense_list')
    
    def get_queryset(self):
        return Expense.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            created_by=self.request.user,
            deleted_at__isnull=True
        )
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        # Check if already billed
        if self.object.is_billed:
            messages.error(request, 'Cannot delete an expense that has been billed.')
            return redirect('lawyer_panel:expense_list')
        self.object.soft_delete()
        messages.success(request, 'Expense has been deleted successfully.')
        return redirect(self.success_url)


class InvoiceDeleteView(LawyerPanelRequiredMixin, DeleteView):
    """Soft delete view for invoices."""
    model = Invoice
    template_name = 'lawyer_panel/invoice_confirm_delete.html'
    success_url = reverse_lazy('lawyer_panel:invoice_list')
    
    def get_queryset(self):
        return Invoice.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            deleted_at__isnull=True
        )
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        # Only allow deletion of draft invoices
        if self.object.status != 'draft':
            messages.error(request, 'Only draft invoices can be deleted.')
            return redirect('lawyer_panel:invoice_list')
        self.object.soft_delete()
        messages.success(request, f'Invoice "{self.object.invoice_number}" has been deleted successfully.')
        return redirect(self.success_url)


class PaymentDeleteView(LawyerPanelRequiredMixin, DeleteView):
    """Soft delete view for payments."""
    model = Payment
    template_name = 'lawyer_panel/payment_confirm_delete.html'
    success_url = reverse_lazy('lawyer_panel:payment_list')
    
    def get_queryset(self):
        return Payment.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            deleted_at__isnull=True
        )
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.soft_delete()
        messages.success(request, f'Payment has been deleted successfully.')
        return redirect(self.success_url)


class LawyerProfileDeleteView(LawyerPanelRequiredMixin, DeleteView):
    """Soft delete view for lawyer profiles."""
    model = LawyerProfile
    template_name = 'lawyer_panel/lawyer_profile_confirm_delete.html'
    success_url = reverse_lazy('lawyer_panel:lawyer_profile_list')
    
    def get_queryset(self):
        return LawyerProfile.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            deleted_at__isnull=True
        )
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.soft_delete()
        messages.success(request, f'Lawyer profile for {self.object.full_name} has been deleted successfully.')
        return redirect(self.success_url)


class PracticeAreaDeleteView(LawyerPanelRequiredMixin, DeleteView):
    """Delete view for practice areas."""
    model = PracticeArea
    template_name = 'lawyer_panel/practice_area_confirm_delete.html'
    success_url = reverse_lazy('lawyer_panel:practice_area_list')
    
    def get_queryset(self):
        return PracticeArea.objects.filter(tenant=self.request.tenant)  # type: ignore
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        # Check if practice area is in use
        if self.object.lawyers.exists():
            messages.error(request, f'Cannot delete practice area "{self.object.name}" because it is assigned to lawyers.')
            return redirect('lawyer_panel:practice_area_list')
        self.object.delete()
        messages.success(request, f'Practice area "{self.object.name}" has been deleted successfully.')
        return redirect(self.success_url)


class LawyerQualificationDeleteView(LawyerPanelRequiredMixin, DeleteView):
    """Delete view for lawyer qualifications."""
    model = LawyerQualification
    template_name = 'lawyer_panel/lawyer_qualification_confirm_delete.html'
    
    def get_queryset(self):
        return LawyerQualification.objects.filter(tenant=self.request.tenant)  # type: ignore
    
    def get_success_url(self):
        return reverse_lazy('lawyer_panel:lawyer_qualification_list', kwargs={
            'lawyer_profile_id': self.object.lawyer_profile.pk
        })
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        messages.success(request, f'Qualification "{self.object.title}" has been deleted successfully.')
        return redirect(self.get_success_url())


# ============================================================================
# UPDATE VIEWS - Complete CRUD Implementation
# ============================================================================

class DocumentUpdateView(LawyerPanelRequiredMixin, UpdateView):
    """Update view for documents."""
    model = Document
    form_class = DocumentForm
    template_name = 'lawyer_panel/document_form.html'
    success_url = reverse_lazy('lawyer_panel:document_list')
    
    def get_queryset(self):
        return Document.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            deleted_at__isnull=True
        )
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs
    
    def form_valid(self, form):
        messages.success(self.request, f'Document "{form.instance.title}" has been updated successfully.')
        return super().form_valid(form)


class TimeEntryUpdateView(LawyerPanelRequiredMixin, UpdateView):
    """Update view for time entries."""
    model = TimeEntry
    form_class = TimeEntryForm
    template_name = 'lawyer_panel/time_entry_form.html'
    success_url = reverse_lazy('lawyer_panel:time_entry_list')
    
    def get_queryset(self):
        return TimeEntry.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            lawyer=self.request.user,
            deleted_at__isnull=True
        )
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs
    
    def form_valid(self, form):
        # Check if already billed
        if self.object.is_billed:
            messages.error(self.request, 'Cannot edit a time entry that has been billed.')
            return redirect('lawyer_panel:time_entry_list')
        messages.success(self.request, 'Time entry has been updated successfully.')
        return super().form_valid(form)


class ExpenseUpdateView(LawyerPanelRequiredMixin, UpdateView):
    """Update view for expenses."""
    model = Expense
    form_class = ExpenseForm
    template_name = 'lawyer_panel/expense_form.html'
    success_url = reverse_lazy('lawyer_panel:expense_list')
    
    def get_queryset(self):
        return Expense.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            created_by=self.request.user,
            deleted_at__isnull=True
        )
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs
    
    def form_valid(self, form):
        # Check if already billed
        if self.object.is_billed:
            messages.error(self.request, 'Cannot edit an expense that has been billed.')
            return redirect('lawyer_panel:expense_list')
        messages.success(self.request, 'Expense has been updated successfully.')
        return super().form_valid(form)


class InvoiceUpdateView(LawyerPanelRequiredMixin, UpdateView):
    """Update view for invoices."""
    model = Invoice
    template_name = 'lawyer_panel/invoice_form.html'
    fields = ['client', 'case', 'issue_date', 'due_date', 'tax_rate', 'notes', 'status']
    
    def get_queryset(self):
        return Invoice.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            deleted_at__isnull=True
        )
    
    def get_success_url(self):
        return reverse_lazy('lawyer_panel:invoice_detail', kwargs={'pk': self.object.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Edit Invoice'
        context['clients'] = Client.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            deleted_at__isnull=True
        )
        context['cases'] = Case.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            assigned_lawyers=self.request.user,
            deleted_at__isnull=True
        )
        return context
    
    def form_valid(self, form):
        messages.success(self.request, f'Invoice "{form.instance.invoice_number}" has been updated successfully.')
        return super().form_valid(form)


class PaymentUpdateView(LawyerPanelRequiredMixin, UpdateView):
    """Update view for payments."""
    model = Payment
    template_name = 'lawyer_panel/payment_form.html'
    fields = ['invoice', 'amount', 'payment_date', 'payment_method', 'reference', 'notes']
    
    def get_queryset(self):
        return Payment.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            deleted_at__isnull=True
        )
    
    def get_success_url(self):
        return reverse_lazy('lawyer_panel:payment_detail', kwargs={'pk': self.object.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Edit Payment'
        context['invoices'] = Invoice.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            deleted_at__isnull=True
        )
        return context
    
    def form_valid(self, form):
        messages.success(self.request, 'Payment has been updated successfully.')
        return super().form_valid(form)


class CaseEventUpdateView(LawyerPanelRequiredMixin, UpdateView):
    """Update view for case events."""
    model = CaseEvent
    form_class = CaseEventForm
    template_name = 'lawyer_panel/case_event_form.html'
    
    def get_queryset(self):
        return CaseEvent.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            case__assigned_lawyers=self.request.user
        )
    
    def get_success_url(self):
        return reverse_lazy('lawyer_panel:case_detail', kwargs={'pk': self.object.case.pk})
    
    def form_valid(self, form):
        messages.success(self.request, f'Event "{form.instance.title}" has been updated successfully.')
        return super().form_valid(form)


class CaseEventDeleteView(LawyerPanelRequiredMixin, DeleteView):
    """Delete view for case events."""
    model = CaseEvent
    template_name = 'lawyer_panel/case_event_confirm_delete.html'
    
    def get_queryset(self):
        return CaseEvent.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            case__assigned_lawyers=self.request.user
        )
    
    def get_success_url(self):
        return reverse_lazy('lawyer_panel:case_detail', kwargs={'pk': self.object.case.pk})
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        messages.success(request, f'Event "{self.object.title}" has been deleted successfully.')
        return redirect(self.get_success_url())


# ============================================================================
# HTMX AJAX VIEWS - Dynamic Interactions
# ============================================================================

@login_required
@require_http_methods(["DELETE"])
def htmx_delete_client(request: TenantHttpRequest, pk: int):
    """HTMX endpoint for deleting clients."""
    if not hasattr(request.user, 'role') or request.user.role.lower() not in ['lawyer', 'admin']:  # type: ignore
        return HttpResponseForbidden()
    
    client = get_object_or_404(
        Client,
        pk=pk,
        tenant=request.tenant,
        deleted_at__isnull=True
    )
    
    client.soft_delete()
    
    from django.http import HttpResponse
    return HttpResponse(
        status=200,
        headers={'HX-Trigger': 'clientDeleted'}
    )


@login_required
def htmx_client_row(request: TenantHttpRequest, pk: int):
    """HTMX endpoint for rendering a single client row."""
    if not hasattr(request.user, 'role') or request.user.role.lower() not in ['lawyer', 'admin']:  # type: ignore
        return HttpResponseForbidden()
    
    client = get_object_or_404(
        Client,
        pk=pk,
        tenant=request.tenant,
        deleted_at__isnull=True
    )
    
    return render(request, 'lawyer_panel/partials/client_row.html', {'client': client})


@login_required
def htmx_case_events(request: TenantHttpRequest, case_id: int):
    """HTMX endpoint for loading case events."""
    if not hasattr(request.user, 'role') or request.user.role.lower() not in ['lawyer', 'admin']:  # type: ignore
        return HttpResponseForbidden()
    
    case = get_object_or_404(
        Case,
        pk=case_id,
        tenant=request.tenant,
        assigned_lawyers=request.user,
        deleted_at__isnull=True
    )
    
    events = case.events.order_by('-event_date')  # type: ignore
    
    return render(request, 'lawyer_panel/partials/case_events.html', {
        'case': case,
        'events': events
    })
