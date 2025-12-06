from django.urls import path
from . import views

app_name = 'subscriptions'

urlpatterns = [
    # Plan selection and comparison
    path('plans/', views.PlanSelectionView.as_view(), name='plan_selection'),
    path('plans/<int:pk>/', views.PlanDetailView.as_view(), name='plan_detail'),
    
    # Subscription management
    path('subscribe/', views.SubscriptionCreateView.as_view(), name='subscribe'),
    path('subscription/<int:pk>/', views.BillingDashboardView.as_view(), name='subscription_detail'),
    path('subscription/<int:pk>/update/', views.SubscriptionUpdateView.as_view(), name='subscription_update'),
    path('subscription/<int:pk>/cancel/', views.SubscriptionCancelView.as_view(), name='subscription_cancel'),
    
    # Billing and payments
    path('billing/', views.BillingDashboardView.as_view(), name='billing_dashboard'),
    path('invoices/', views.InvoiceListView.as_view(), name='invoice_list'),
    path('invoices/<int:pk>/', views.InvoiceDetailView.as_view(), name='invoice_detail'),
    path('invoices/<int:pk>/pay/', views.PaymentCreateView.as_view(), name='invoice_payment'),
    path('payments/', views.InvoiceListView.as_view(), name='payment_list'),
    
    # Payment methods
    path('payment-methods/', views.PaymentMethodListView.as_view(), name='payment_method_list'),
    path('payment-methods/add/', views.PaymentMethodCreateView.as_view(), name='payment_method_create'),
    path('payment-methods/<int:pk>/update/', views.PaymentMethodUpdateView.as_view(), name='payment_method_update'),
    path('payment-methods/<int:pk>/delete/', views.PaymentMethodDeleteView.as_view(), name='payment_method_delete'),
    path('payment-methods/<int:pk>/set-default/', views.PaymentMethodCreateView.as_view(), name='payment_method_set_default'),
    
    # Usage tracking
    path('usage/', views.UsageDashboardView.as_view(), name='usage_dashboard'),
    
    # Webhooks for payment providers
    # path('webhooks/stripe/', views.stripe_webhook, name='stripe_webhook'),
]