from django.urls import path
from . import views
from . import views_crud_complete as crud_views

app_name = 'lawyer_panel'

urlpatterns = [
    # Dashboard
    path('', views.DashboardView.as_view(), name='dashboard'),
    
    # Cases - Full CRUD
    path('cases/', views.CaseListView.as_view(), name='case_list'),
    path('cases/<int:pk>/', views.CaseDetailView.as_view(), name='case_detail'),
    path('cases/create/', views.CaseCreateView.as_view(), name='case_create'),
    path('cases/<int:pk>/edit/', views.CaseUpdateView.as_view(), name='case_update'),
    path('cases/<int:pk>/delete/', crud_views.CaseDeleteView.as_view(), name='case_delete'),
    path('cases/<int:case_id>/event/', views.add_case_event, name='add_case_event'),
    
    # Case Events - Full CRUD
    path('case-events/<int:pk>/edit/', crud_views.CaseEventUpdateView.as_view(), name='case_event_update'),
    path('case-events/<int:pk>/delete/', crud_views.CaseEventDeleteView.as_view(), name='case_event_delete'),
    
    # Clients - Full CRUD
    path('clients/', views.ClientListView.as_view(), name='client_list'),
    path('clients/<int:pk>/', views.ClientDetailView.as_view(), name='client_detail'),
    path('clients/create/', views.ClientCreateView.as_view(), name='client_create'),
    path('clients/<int:pk>/edit/', views.ClientUpdateView.as_view(), name='client_update'),
    path('clients/<int:pk>/delete/', crud_views.ClientDeleteView.as_view(), name='client_delete'),
    
    # Documents - Full CRUD
    path('documents/', views.DocumentListView.as_view(), name='document_list'),
    path('documents/<int:pk>/', views.DocumentDetailView.as_view(), name='document_detail'),
    path('documents/create/', views.DocumentCreateView.as_view(), name='document_create'),
    path('documents/<int:pk>/edit/', crud_views.DocumentUpdateView.as_view(), name='document_update'),
    path('documents/<int:pk>/delete/', crud_views.DocumentDeleteView.as_view(), name='document_delete'),
    
    # Time Entries - Full CRUD
    path('time-entries/', views.TimeEntryListView.as_view(), name='time_entry_list'),
    path('time-entries/create/', views.TimeEntryCreateView.as_view(), name='time_entry_create'),
    path('time-entries/<int:pk>/edit/', crud_views.TimeEntryUpdateView.as_view(), name='time_entry_update'),
    path('time-entries/<int:pk>/delete/', crud_views.TimeEntryDeleteView.as_view(), name='time_entry_delete'),
    
    # Expenses - Full CRUD
    path('expenses/', views.ExpenseListView.as_view(), name='expense_list'),
    path('expenses/create/', views.ExpenseCreateView.as_view(), name='expense_create'),
    path('expenses/<int:pk>/edit/', crud_views.ExpenseUpdateView.as_view(), name='expense_update'),
    path('expenses/<int:pk>/delete/', crud_views.ExpenseDeleteView.as_view(), name='expense_delete'),
    
    # Billing Dashboard
    path('billing/', views.BillingDashboardView.as_view(), name='billing_dashboard'),
    
    # Invoices - Full CRUD
    path('billing/invoices/', views.InvoiceListView.as_view(), name='invoice_list'),
    path('billing/invoices/<int:pk>/', views.InvoiceDetailView.as_view(), name='invoice_detail'),
    path('billing/invoices/create/', views.InvoiceCreateView.as_view(), name='invoice_create'),
    path('billing/invoices/<int:pk>/edit/', crud_views.InvoiceUpdateView.as_view(), name='invoice_update'),
    path('billing/invoices/<int:pk>/delete/', crud_views.InvoiceDeleteView.as_view(), name='invoice_delete'),
    path('billing/generate-invoice/', views.generate_invoice, name='generate_invoice'),
    
    # Payments - Full CRUD
    path('billing/payments/', views.PaymentListView.as_view(), name='payment_list'),
    path('billing/payments/<int:pk>/', views.PaymentDetailView.as_view(), name='payment_detail'),
    path('billing/payments/create/', views.PaymentCreateView.as_view(), name='payment_create'),
    path('billing/payments/<int:pk>/edit/', crud_views.PaymentUpdateView.as_view(), name='payment_update'),
    path('billing/payments/<int:pk>/delete/', crud_views.PaymentDeleteView.as_view(), name='payment_delete'),
    
    # Search
    path('search/', views.quick_search, name='quick_search'),
    
    # Lawyer Profiles - Full CRUD
    path('lawyers/', views.LawyerProfileListView.as_view(), name='lawyer_profile_list'),
    path('lawyers/<int:pk>/', views.LawyerProfileDetailView.as_view(), name='lawyer_profile_detail'),
    path('lawyers/create/', views.LawyerProfileCreateView.as_view(), name='lawyer_profile_create'),
    path('lawyers/<int:pk>/edit/', views.LawyerProfileUpdateView.as_view(), name='lawyer_profile_update'),
    path('lawyers/<int:pk>/delete/', crud_views.LawyerProfileDeleteView.as_view(), name='lawyer_profile_delete'),
    path('lawyers/<int:pk>/availability/', views.LawyerAvailabilityUpdateView.as_view(), name='lawyer_availability_update'),
    path('lawyers/<int:lawyer_profile_id>/update-case-load/', views.update_case_load, name='lawyer_update_case_load'),
    path('lawyers/export/', views.export_lawyer_profiles, name='lawyer_profile_export'),
    
    # Practice Areas - Full CRUD
    path('practice-areas/', views.PracticeAreaListView.as_view(), name='practice_area_list'),
    path('practice-areas/create/', views.PracticeAreaCreateView.as_view(), name='practice_area_create'),
    path('practice-areas/<int:pk>/edit/', views.PracticeAreaUpdateView.as_view(), name='practice_area_update'),
    path('practice-areas/<int:pk>/delete/', crud_views.PracticeAreaDeleteView.as_view(), name='practice_area_delete'),
    
    # Lawyer Qualifications - Full CRUD
    path('qualifications/', views.LawyerQualificationListView.as_view(), name='lawyer_qualification_list'),
    path('qualifications/create/', views.LawyerQualificationCreateView.as_view(), name='lawyer_qualification_create'),
    path('qualifications/<int:pk>/edit/', views.LawyerQualificationUpdateView.as_view(), name='lawyer_qualification_update'),
    path('qualifications/<int:pk>/delete/', crud_views.LawyerQualificationDeleteView.as_view(), name='lawyer_qualification_delete'),
    path('lawyers/<int:lawyer_profile_id>/qualifications/', views.LawyerQualificationListView.as_view(), name='lawyer_qualification_list'),
    path('lawyers/<int:lawyer_profile_id>/qualifications/create/', views.LawyerQualificationCreateView.as_view(), name='lawyer_qualification_create'),
    
    # HTMX AJAX Endpoints
    path('ajax/case/<int:pk>/toggle-status/', crud_views.toggle_case_status, name='ajax_toggle_case_status'),
    path('ajax/case/<int:pk>/quick-view/', crud_views.case_quick_view, name='ajax_case_quick_view'),
    path('ajax/client/<int:pk>/quick-view/', crud_views.client_quick_view, name='ajax_client_quick_view'),
    path('ajax/restore/', crud_views.restore_deleted_item, name='ajax_restore_item'),
]