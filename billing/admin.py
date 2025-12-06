from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    BillingRate, Invoice, InvoiceItem, TimeEntry, 
    Expense, Payment
)


@admin.register(BillingRate)
class BillingRateAdmin(admin.ModelAdmin):
    list_display = ['role', 'default_rate', 'effective_date', 'description', 'tenant', 'created_at']
    list_filter = ['role', 'effective_date', 'tenant']
    search_fields = ['role', 'description']
    ordering = ['-effective_date', 'role']
    readonly_fields = ['created_at', 'updated_at', 'created_by']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Filter by tenant for non-superusers
        if hasattr(request.user, 'tenant'):
            return qs.filter(tenant=request.user.tenant)
        return qs.none()
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if not request.user.is_superuser and hasattr(request.user, 'tenant'):
            # Filter tenant field for non-superusers
            if 'tenant' in form.base_fields:
                form.base_fields['tenant'].queryset = form.base_fields['tenant'].queryset.filter(
                    id=request.user.tenant.id
                )
                form.base_fields['tenant'].initial = request.user.tenant
        return form
    
    def save_model(self, request, obj, form, change):
        if not change and hasattr(request.user, 'tenant'):
            obj.tenant = request.user.tenant
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1
    readonly_fields = ['created_at', 'updated_at']
    fields = ['description', 'quantity', 'rate', 'amount', 'time_entry', 'expense']


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'client', 'case', 'issue_date', 'due_date', 'total_amount', 'status', 'is_overdue', 'tenant']
    list_filter = ['status', 'issue_date', 'due_date', 'tenant']
    search_fields = ['invoice_number', 'client__first_name', 'client__last_name', 'client__company']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at', 'created_by', 'subtotal', 'tax_amount', 'total_amount']
    inlines = [InvoiceItemInline]
    
    def is_overdue(self, obj):
        if obj.is_overdue:
            return format_html('<span style="color: red;">Overdue</span>')
        return format_html('<span style="color: green;">Not Overdue</span>')
    is_overdue.short_description = 'Overdue Status'
    is_overdue.admin_order_field = 'due_date'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Filter by tenant for non-superusers
        if hasattr(request.user, 'tenant'):
            return qs.filter(tenant=request.user.tenant)
        return qs.none()
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if not request.user.is_superuser and hasattr(request.user, 'tenant'):
            # Filter tenant field for non-superusers
            if 'tenant' in form.base_fields:
                form.base_fields['tenant'].queryset = form.base_fields['tenant'].queryset.filter(
                    id=request.user.tenant.id
                )
                form.base_fields['tenant'].initial = request.user.tenant
            
            # Filter client and case by tenant
            if 'client' in form.base_fields:
                form.base_fields['client'].queryset = form.base_fields['client'].queryset.filter(
                    tenant=request.user.tenant
                )
            
            if 'case' in form.base_fields:
                form.base_fields['case'].queryset = form.base_fields['case'].queryset.filter(
                    tenant=request.user.tenant
                )
        return form
    
    def save_model(self, request, obj, form, change):
        if not change and hasattr(request.user, 'tenant'):
            obj.tenant = request.user.tenant
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    list_display = ['invoice', 'description', 'quantity', 'rate', 'amount', 'tenant']
    list_filter = ['invoice__status', 'tenant']
    search_fields = ['description', 'invoice__invoice_number']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at', 'amount']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Filter by tenant for non-superusers
        if hasattr(request.user, 'tenant'):
            return qs.filter(tenant=request.user.tenant)
        return qs.none()
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if not request.user.is_superuser and hasattr(request.user, 'tenant'):
            # Filter tenant field for non-superusers
            if 'tenant' in form.base_fields:
                form.base_fields['tenant'].queryset = form.base_fields['tenant'].queryset.filter(
                    id=request.user.tenant.id
                )
                form.base_fields['tenant'].initial = request.user.tenant
            
            # Filter invoice by tenant
            if 'invoice' in form.base_fields:
                form.base_fields['invoice'].queryset = form.base_fields['invoice'].queryset.filter(
                    tenant=request.user.tenant
                )
        return form
    
    def save_model(self, request, obj, form, change):
        if not change and hasattr(request.user, 'tenant'):
            obj.tenant = request.user.tenant
        super().save_model(request, obj, form, change)


@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    list_display = ['lawyer', 'case', 'hours', 'rate', 'amount', 'date', 'is_billable', 'is_billed', 'tenant']
    list_filter = ['is_billable', 'date', 'tenant', 'lawyer']
    search_fields = ['description', 'case__case_number', 'lawyer__first_name', 'lawyer__last_name']
    ordering = ['-date', '-created_at']
    readonly_fields = ['created_at', 'updated_at', 'created_by']
    
    def amount(self, obj):
        return f"${obj.amount:.2f}"
    amount.short_description = 'Amount'
    amount.admin_order_field = 'hours'
    
    def is_billed(self, obj):
        if obj.is_billed:
            return format_html('<span style="color: green;">Billed</span>')
        return format_html('<span style="color: orange;">Not Billed</span>')
    is_billed.short_description = 'Billed Status'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Filter by tenant for non-superusers
        if hasattr(request.user, 'tenant'):
            return qs.filter(tenant=request.user.tenant)
        return qs.none()
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if not request.user.is_superuser and hasattr(request.user, 'tenant'):
            # Filter tenant field for non-superusers
            if 'tenant' in form.base_fields:
                form.base_fields['tenant'].queryset = form.base_fields['tenant'].queryset.filter(
                    id=request.user.tenant.id
                )
                form.base_fields['tenant'].initial = request.user.tenant
            
            # Filter case and lawyer by tenant
            if 'case' in form.base_fields:
                form.base_fields['case'].queryset = form.base_fields['case'].queryset.filter(
                    tenant=request.user.tenant
                )
            
            if 'lawyer' in form.base_fields:
                form.base_fields['lawyer'].queryset = form.base_fields['lawyer'].queryset.filter(
                    tenant=request.user.tenant
                )
        return form
    
    def save_model(self, request, obj, form, change):
        if not change and hasattr(request.user, 'tenant'):
            obj.tenant = request.user.tenant
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['description', 'amount', 'category', 'date', 'is_reimbursable', 'is_billed', 'case', 'tenant']
    list_filter = ['category', 'is_reimbursable', 'date', 'tenant']
    search_fields = ['description', 'case__case_number']
    ordering = ['-date', '-created_at']
    readonly_fields = ['created_at', 'updated_at', 'created_by']
    
    def is_billed(self, obj):
        if obj.is_billed:
            return format_html('<span style="color: green;">Billed</span>')
        return format_html('<span style="color: orange;">Not Billed</span>')
    is_billed.short_description = 'Billed Status'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Filter by tenant for non-superusers
        if hasattr(request.user, 'tenant'):
            return qs.filter(tenant=request.user.tenant)
        return qs.none()
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if not request.user.is_superuser and hasattr(request.user, 'tenant'):
            # Filter tenant field for non-superusers
            if 'tenant' in form.base_fields:
                form.base_fields['tenant'].queryset = form.base_fields['tenant'].queryset.filter(
                    id=request.user.tenant.id
                )
                form.base_fields['tenant'].initial = request.user.tenant
            
            # Filter case by tenant
            if 'case' in form.base_fields:
                form.base_fields['case'].queryset = form.base_fields['case'].queryset.filter(
                    tenant=request.user.tenant
                )
        return form
    
    def save_model(self, request, obj, form, change):
        if not change and hasattr(request.user, 'tenant'):
            obj.tenant = request.user.tenant
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['invoice', 'amount', 'payment_date', 'payment_method', 'reference', 'tenant']
    list_filter = ['payment_method', 'payment_date', 'tenant']
    search_fields = ['invoice__invoice_number', 'reference']
    ordering = ['-payment_date', '-created_at']
    readonly_fields = ['created_at', 'updated_at', 'created_by']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Filter by tenant for non-superusers
        if hasattr(request.user, 'tenant'):
            return qs.filter(tenant=request.user.tenant)
        return qs.none()
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if not request.user.is_superuser and hasattr(request.user, 'tenant'):
            # Filter tenant field for non-superusers
            if 'tenant' in form.base_fields:
                form.base_fields['tenant'].queryset = form.base_fields['tenant'].queryset.filter(
                    id=request.user.tenant.id
                )
                form.base_fields['tenant'].initial = request.user.tenant
            
            # Filter invoice by tenant
            if 'invoice' in form.base_fields:
                form.base_fields['invoice'].queryset = form.base_fields['invoice'].queryset.filter(
                    tenant=request.user.tenant
                )
        return form
    
    def save_model(self, request, obj, form, change):
        if not change and hasattr(request.user, 'tenant'):
            obj.tenant = request.user.tenant
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
