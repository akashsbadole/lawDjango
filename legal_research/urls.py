from django.urls import path
from . import views

app_name = 'legal_research'

urlpatterns = [
    # Dashboard
    path('dashboard/', views.research_dashboard, name='dashboard'),
    
    # Research Queries
    path('', views.LegalResearchQueryListView.as_view(), name='query_list'),
    path('query/<int:pk>/', views.LegalResearchQueryDetailView.as_view(), name='query_detail'),
    path('query/create/', views.LegalResearchQueryCreateView.as_view(), name='query_create'),
    path('query/<int:pk>/process/', views.process_research_query, name='query_process'),
    path('query/<int:pk>/feedback/', views.submit_feedback, name='query_feedback'),
    path('query/<int:pk>/export/', views.export_research_results, name='query_export'),
    
    # Quick Research
    path('quick/', views.quick_research, name='quick_research'),
    
    # Document Analysis
    path('document-analysis/', views.document_analysis, name='document_analysis'),
    
    # Research Sessions
    path('sessions/', views.ResearchSessionListView.as_view(), name='session_list'),
    path('session/<int:pk>/', views.ResearchSessionDetailView.as_view(), name='session_detail'),
    path('session/create/', views.ResearchSessionCreateView.as_view(), name='session_create'),
]
