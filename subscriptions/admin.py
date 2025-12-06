from django.contrib import admin
from .models import (
    SubscriptionPlan, SubscriptionFeature, PlanFeature, PaymentMethod,
    TenantSubscription, Invoice, Payment, UsageRecord, SubscriptionEvent
)


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'billing_cycle', 'max_users', 'max_storage_mb', 'is_active', 'created_at')
    list_filter = ('billing_cycle', 'is_active', 'created_at')
    search_fields = ('name', 'description')
    ordering = ('price',)
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'plan_type')
        }),
        ('Pricing', {
            'fields': ('price', 'billing_cycle', 'setup_fee', 'trial_days')
        }),
        ('Limits', {
            'fields': ('max_users', 'max_storage_mb')
        }),
        ('Settings', {
            'fields': ('is_active', 'is_public', 'sort_order')
        }),
    )


@admin.register(SubscriptionFeature)
class SubscriptionFeatureAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'description', 'created_at')
    search_fields = ('name', 'code', 'description')
    ordering = ('name',)
    readonly_fields = ('created_at',)


class PlanFeatureInline(admin.TabularInline):
    model = PlanFeature
    extra = 1


# Re-register SubscriptionPlan with inline
admin.site.unregister(SubscriptionPlan)
@admin.register(SubscriptionPlan)
class SubscriptionPlanWithFeaturesAdmin(SubscriptionPlanAdmin):
    inlines = [PlanFeatureInline]


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'method_type', 'is_default', 'created_at')
    list_filter = ('method_type', 'is_default', 'created_at')
    search_fields = ('tenant__name',)
    ordering = ('-is_default', '-created_at')
    readonly_fields = ('created_at', 'updated_at')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if hasattr(request.user, 'tenant') and request.user.tenant:
            return qs.filter(tenant=request.user.tenant)
        return qs
    
    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(self.readonly_fields)
        if obj and obj.pk:
            readonly_fields.extend(['method_type', 'provider_id'])
        return readonly_fields


@admin.register(TenantSubscription)
class TenantSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'plan', 'status', 'start_date', 'end_date', 'auto_renew', 'created_at')
    list_filter = ('status', 'auto_renew', 'created_at')
    search_fields = ('tenant__name', 'plan__name')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if hasattr(request.user, 'tenant') and request.user.tenant:
            return qs.filter(tenant=request.user.tenant)
        return qs


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ('payment_method', 'amount', 'status', 'payment_date', 'transaction_id')


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'tenant', 'subscription', 'total_amount', 'status', 'due_date', 'created_at')
    list_filter = ('status', 'invoice_type', 'created_at')
    search_fields = ('invoice_number', 'tenant__name', 'description')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    inlines = [PaymentInline]
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if hasattr(request.user, 'tenant') and request.user.tenant:
            return qs.filter(tenant=request.user.tenant)
        return qs


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'amount', 'payment_method', 'status', 'payment_date', 'created_at')
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('invoice__invoice_number', 'provider_transaction_id')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if hasattr(request.user, 'tenant') and request.user.tenant:
            return qs.filter(invoice__tenant=request.user.tenant)
        return qs


@admin.register(UsageRecord)
class UsageRecordAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'feature', 'current_usage', 'limit', 'period_start', 'period_end', 'created_at')
    list_filter = ('feature', 'period_start', 'created_at')
    search_fields = ('tenant__name', 'feature__name')
    ordering = ('-period_start', 'tenant', 'feature')
    readonly_fields = ('created_at', 'updated_at')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if hasattr(request.user, 'tenant') and request.user.tenant:
            return qs.filter(tenant=request.user.tenant)
        return qs


@admin.register(SubscriptionEvent)
class SubscriptionEventAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'subscription', 'event_type', 'description', 'created_at')
    list_filter = ('event_type', 'created_at')
    search_fields = ('tenant__name', 'description')
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if hasattr(request.user, 'tenant') and request.user.tenant:
            return qs.filter(tenant=request.user.tenant)
        return qs
