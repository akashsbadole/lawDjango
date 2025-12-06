from django.urls import path
from . import views

app_name = 'lawyer_panel'

urlpatterns = [
    # Dashboard
    path('', views.DashboardView.as_view(), name='dashboard'),
    
    # Cases
    path('cases/', views.CaseListView.as_view(), name='case_list'),
    path('cases/<int:pk>/', views.CaseDetailView.as_view(), name='case_detail'),
    path('cases/create/', views.CaseCreateView.as_view(), name='case_create'),
    path('cases/<int:pk>/edit/', views.CaseUpdateView.as_view(), name='case_update'),
    path('cases/<int:case_id>/event/', views.add_case_event, name='add_case_event'),
    
    # Clients
    path('clients/', views.ClientListView.as_view(), name='client_list'),
    path('clients/<int:pk>/', views.ClientDetailView.as_view(), name='client_detail'),
    path('clients/create/', views.ClientCreateView.as_view(), name='client_create'),
    path('clients/<int:pk>/edit/', views.ClientUpdateView.as_view(), name='client_update'),
    
    # Documents
    path('documents/', views.DocumentListView.as_view(), name='document_list'),
    path('documents/<int:pk>/', views.DocumentDetailView.as_view(), name='document_detail'),
    path('documents/create/', views.DocumentCreateView.as_view(), name='document_create'),
    
    # Time Entries
    path('time-entries/', views.TimeEntryListView.as_view(), name='time_entry_list'),
    path('time-entries/create/', views.TimeEntryCreateView.as_view(), name='time_entry_create'),
    
    # Expenses
    path('expenses/', views.ExpenseListView.as_view(), name='expense_list'),
    path('expenses/create/', views.ExpenseCreateView.as_view(), name='expense_create'),
    
    # Billing Dashboard
    path('billing/', views.BillingDashboardView.as_view(), name='billing_dashboard'),
    
    # Search
    path('search/', views.quick_search, name='quick_search'),
]