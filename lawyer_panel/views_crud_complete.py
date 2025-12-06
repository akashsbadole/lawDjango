"""
Complete CRUD Views for Lawyer Panel with HTMX Support
Implements all missing DELETE and UPDATE operations
"""
from typing import TYPE_CHECKING
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import DeleteView, UpdateView
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from clients.models import Client
from cases.models import Case, CaseEvent
from documents.models import Document
from billing.models import TimeEntry, Expense, Invoice, Payment
from .models import LawyerProfile, PracticeArea, LawyerQualification
from .forms import (
    DocumentForm, TimeEntryForm, ExpenseForm, CaseEventForm
)

if TYPE_CHECKING:
    from core.types import TenantHttpRequest

# Import the base mixin
from lawyer_panel.views import LawyerPanelRequiredMixin


# ============================================================================
# DELETE VIEWS - Soft Delete Implementation
# ============================================================================

class ClientDeleteView(LawyerPanelRequiredMixin, DeleteView):
    """Soft delete view for clients with HTMX support."""
    model = Client
    template_name = 'lawyer_panel/confirm_delete.html'
    success_url = reverse_lazy('lawyer_panel:client_list')
    
    def get_queryset(self):
        return Client.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            deleted_at__isnull=True
        )
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        
        # Soft delete
        self.object.soft_delete()
        
        messages.success(request, f'Client "{self.object.full_name}" has been deleted successfully.')
        
        # HTMX support
        if request.headers.get('HX-Request'):
            return HttpResponse(status=204, headers={'HX-Redirect': success_url})
        
        return redirect(success_url)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['object_type'] = 'Client'
        context['object_name'] = self.object.full_name
        return context


class CaseDeleteView(LawyerPanelRequiredMixin, DeleteView):
    """Soft delete view for cases with HTMX support."""
    model = Case
    template_name = 'lawyer_panel/confirm_delete.html'
    success_url = reverse_lazy('lawyer_panel:case_list')
    
    def get_queryset(self):
        return Case.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            assigned_lawyers=self.request.user,
            deleted_at__isnull=True
        )
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        
        # Soft delete
        self.object.soft_delete()
        
        messages.success(request, f'Case "{self.object.title}" has been deleted successfully.')
        
        # HTMX support
        if request.headers.get('HX-Request'):
            return HttpResponse(status=204, headers={'HX-Redirect': success_url})
        
        return redirect(success_url)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['object_type'] = 'Case'
        context['object_name'] = self.object.title
        return context


class DocumentDeleteView(LawyerPanelRequiredMixin, DeleteView):
    """Soft delete view for documents with HTMX support."""
    model = Document
    template_name = 'lawyer_panel/confirm_delete.html'
    success_url = reverse_lazy('lawyer_panel:document_list')
    
    def get_queryset(self):
        return Document.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            deleted_at__isnull=True
        )
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        
        # Soft delete
        self.object.soft_delete()
        
        messages.success(request, f'Document "{self.object.title}" has been deleted successfully.')
        
        # HTMX support
        if request.headers.get('HX-Request'):
            return HttpResponse(status=204, headers={'HX-Redirect': success_url})
        
        return redirect(success_url)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['object_type'] = 'Document'
        context['object_name'] = self.object.title
        return context


class TimeEntryDeleteView(LawyerPanelRequiredMixin, DeleteView):
    """Soft delete view for time entries with HTMX support."""
    model = TimeEntry
    template_name = 'lawyer_panel/confirm_delete.html'
    success_url = reverse_lazy('lawyer_panel:time_entry_list')
    
    def get_queryset(self):
        return TimeEntry.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            lawyer=self.request.user,
            deleted_at__isnull=True
        )
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        
        # Soft delete
        self.object.soft_delete()
        
        messages.success(request, f'Time entry has been deleted successfully.')
        
        # HTMX support
        if request.headers.get('HX-Request'):
            return HttpResponse(status=204, headers={'HX-Redirect': success_url})
        
        return redirect(success_url)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['object_type'] = 'Time Entry'
        context['object_name'] = f"{self.object.hours} hours on {self.object.date}"
        return context


class ExpenseDeleteView(LawyerPanelRequiredMixin, DeleteView):
    """Soft delete view for expenses with HTMX support."""
    model = Expense
    template_name = 'lawyer_panel/confirm_delete.html'
    success_url = reverse_lazy('lawyer_panel:expense_list')
    
    def get_queryset(self):
        return Expense.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            created_by=self.request.user,
            deleted_at__isnull=True
        )
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        
        # Soft delete
        self.object.soft_delete()
        
        messages.success(request, f'Expense "{self.object.description}" has been deleted successfully.')
        
        # HTMX support
        if request.headers.get('HX-Request'):
            return HttpResponse(status=204, headers={'HX-Redirect': success_url})
        
        return redirect(success_url)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['object_type'] = 'Expense'
        context['object_name'] = self.object.description
        return context


class InvoiceDeleteView(LawyerPanelRequiredMixin, DeleteView):
    """Soft delete view for invoices with HTMX support."""
    model = Invoice
    template_name = 'lawyer_panel/confirm_delete.html'
    success_url = reverse_lazy('lawyer_panel:invoice_list')
    
    def get_queryset(self):
        return Invoice.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            deleted_at__isnull=True
        )
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        
        # Only allow deletion of draft invoices
        if self.object.status != 'draft':
            messages.error(request, 'Only draft invoices can be deleted.')
            return redirect('lawyer_panel:invoice_detail', pk=self.object.pk)
        
        # Soft delete
        self.object.soft_delete()
        
        messages.success(request, f'Invoice "{self.object.invoice_number}" has been deleted successfully.')
        
        # HTMX support
        if request.headers.get('HX-Request'):
            return HttpResponse(status=204, headers={'HX-Redirect': success_url})
        
        return redirect(success_url)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['object_type'] = 'Invoice'
        context['object_name'] = self.object.invoice_number
        return context


class PaymentDeleteView(LawyerPanelRequiredMixin, DeleteView):
    """Soft delete view for payments with HTMX support."""
    model = Payment
    template_name = 'lawyer_panel/confirm_delete.html'
    success_url = reverse_lazy('lawyer_panel:payment_list')
    
    def get_queryset(self):
        return Payment.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            deleted_at__isnull=True
        )
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        
        # Soft delete
        self.object.soft_delete()
        
        messages.success(request, f'Payment has been deleted successfully.')
        
        # HTMX support
        if request.headers.get('HX-Request'):
            return HttpResponse(status=204, headers={'HX-Redirect': success_url})
        
        return redirect(success_url)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['object_type'] = 'Payment'
        context['object_name'] = f"${self.object.amount} on {self.object.payment_date}"
        return context


class LawyerProfileDeleteView(LawyerPanelRequiredMixin, DeleteView):
    """Soft delete view for lawyer profiles with HTMX support."""
    model = LawyerProfile
    template_name = 'lawyer_panel/confirm_delete.html'
    success_url = reverse_lazy('lawyer_panel:lawyer_profile_list')
    
    def get_queryset(self):
        return LawyerProfile.objects.filter(
            tenant=self.request.tenant,  # type: ignore
            deleted_at__isnull=True
        )
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        
        # Soft delete
        self.object.soft_delete()
        
        messages.success(request, f'Lawyer profile for "{self.object.full_name}" has been deleted successfully.')
        
        # HTMX support
        if request.headers.get('HX-Request'):
            return HttpResponse(status=204, headers={'HX-Redirect': success_url})
        
        return redirect(success_url)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['object_type'] = 'Lawyer Profile'
        context['object_name'] = self.object.full_name
        return context


class PracticeAreaDeleteView(LawyerPanelRequiredMixin, DeleteView):
    """Delete view for practice areas with HTMX support."""
    model = PracticeArea
    template_name = 'lawyer_panel/confirm_delete.html'
    success_url = reverse_lazy('lawyer_panel:practice_area_list')
    
    def get_queryset(self):
        return PracticeArea.objects.filter(tenant=self.request.tenant)  # type: ignore
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        
        # Hard delete for practice areas (or deactivate)
        self.object.is_active = False
        self.object.save()
        
        messages.success(request, f'Practice area "{self.object.name}" has been deactivated.')
        
        # HTMX support
        if request.headers.get('HX-Request'):
            return HttpResponse(status=204, headers={'HX-Redirect': success_url})
        
        return redirect(success_url)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['object_type'] = 'Practice Area'
        context['object_name'] = self.object.name
        return context


class LawyerQualificationDeleteView(LawyerPanelRequiredMixin, DeleteView):
    """Delete view for lawyer qualifications with HTMX support."""
    model = LawyerQualification
    template_name = 'lawyer_panel/confirm_delete.html'
    
    def get_queryset(self):
        return LawyerQualification.objects.filter(tenant=self.request.tenant)  # type: ignore
    
    def get_success_url(self):
        return reverse_lazy('lawyer_panel:lawyer_qualification_list', kwargs={
            'lawyer_profile_id': self.object.lawyer_profile.pk
        })
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        
        # Hard delete
        self.object.delete()
        
        messages.success(request, f'Qualification "{self.object.title}" has been deleted successfully.')
        
        # HTMX support
        if request.headers.get('HX-Request'):
            return HttpResponse(status=204, headers={'HX-Redirect': success_url})
        
        return redirect(success_url)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['object_type'] = 'Qualification'
        context['object_name'] = self.object.title
        return context


class CaseEventDeleteView(LawyerPanelRequiredMixin, DeleteView):
    """Delete view for case events with HTMX support."""
    model = CaseEvent
    template_name = 'lawyer_panel/confirm_delete.html'
    
    def get_queryset(self):
        return CaseEvent.objects.filter(tenant=self.request.tenant)  # type: ignore
    
    def get_success_url(self):
        return reverse_lazy('lawyer_panel:case_detail', kwargs={'pk': self.object.case.pk})
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        
        # Hard delete
        self.object.delete()
        
        messages.success(request, f'Case event "{self.object.title}" has been deleted successfully.')
        
        # HTMX support
        if request.headers.get('HX-Request'):
            return HttpResponse(status=204, headers={'HX-Redirect': success_url})
        
        return redirect(success_url)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['object_type'] = 'Case Event'
        context['object_name'] = self.object.title
        return context


# ============================================================================
# UPDATE VIEWS - Missing Update Operations
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
        messages.success(self.request, f'Expense "{form.instance.description}" has been updated successfully.')
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
    
    def form_valid(self, form):
        messages.success(self.request, 'Payment has been updated successfully.')
        return super().form_valid(form)


class CaseEventUpdateView(LawyerPanelRequiredMixin, UpdateView):
    """Update view for case events."""
    model = CaseEvent
    form_class = CaseEventForm
    template_name = 'lawyer_panel/case_event_form.html'
    
    def get_queryset(self):
        return CaseEvent.objects.filter(tenant=self.request.tenant)  # type: ignore
    
    def get_success_url(self):
        return reverse_lazy('lawyer_panel:case_detail', kwargs={'pk': self.object.case.pk})
    
    def form_valid(self, form):
        messages.success(self.request, f'Case event "{form.instance.title}" has been updated successfully.')
        return super().form_valid(form)


# ============================================================================
# HTMX AJAX VIEWS
# ============================================================================

@login_required
@require_http_methods(["POST"])
def toggle_case_status(request: 'TenantHttpRequest', pk: int):
    """Toggle case status via HTMX."""
    case = get_object_or_404(
        Case,
        pk=pk,
        tenant=request.tenant,
        assigned_lawyers=request.user,
        deleted_at__isnull=True
    )
    
    # Toggle between open and closed
    if case.status == 'open':
        case.status = 'closed'
    else:
        case.status = 'open'
    
    case.save()
    
    return JsonResponse({
        'status': case.status,
        'status_display': case.get_status_display()
    })


@login_required
@require_http_methods(["GET"])
def case_quick_view(request: 'TenantHttpRequest', pk: int):
    """Quick view of case details via HTMX."""
    case = get_object_or_404(
        Case,
        pk=pk,
        tenant=request.tenant,
        assigned_lawyers=request.user,
        deleted_at__isnull=True
    )
    
    return render(request, 'lawyer_panel/partials/case_quick_view.html', {
        'case': case
    })


@login_required
@require_http_methods(["GET"])
def client_quick_view(request: 'TenantHttpRequest', pk: int):
    """Quick view of client details via HTMX."""
    client = get_object_or_404(
        Client,
        pk=pk,
        tenant=request.tenant,
        deleted_at__isnull=True
    )
    
    return render(request, 'lawyer_panel/partials/client_quick_view.html', {
        'client': client
    })


@login_required
@require_http_methods(["POST"])
def restore_deleted_item(request: 'TenantHttpRequest'):
    """Restore a soft-deleted item via HTMX."""
    model_type = request.POST.get('model_type')
    item_id = request.POST.get('item_id')
    
    model_map = {
        'client': Client,
        'case': Case,
        'document': Document,
        'time_entry': TimeEntry,
        'expense': Expense,
        'invoice': Invoice,
        'payment': Payment,
        'lawyer_profile': LawyerProfile,
    }
    
    if model_type not in model_map:
        return JsonResponse({'error': 'Invalid model type'}, status=400)
    
    model = model_map[model_type]
    try:
        item = model.objects.get(pk=item_id, tenant=request.tenant)
        item.restore()
        return JsonResponse({'success': True, 'message': f'{model_type.replace("_", " ").title()} restored successfully'})
    except model.DoesNotExist:
        return JsonResponse({'error': 'Item not found'}, status=404)
