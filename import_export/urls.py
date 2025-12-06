from django.urls import path
from . import views

app_name = 'import_export'

urlpatterns = [
    # Import Job URLs
    path('imports/', views.ImportJobListView.as_view(), name='import_job_list'),
    path('imports/create/', views.ImportJobCreateView.as_view(), name='import_job_create'),
    path('imports/<int:pk>/', views.ImportJobDetailView.as_view(), name='import_job_detail'),
    path('imports/<int:pk>/cancel/', views.cancel_import_job, name='import_job_cancel'),
    path('imports/<int:pk>/status/', views.import_job_status, name='import_job_status'),
    
    # Export Job URLs
    path('exports/', views.ExportJobListView.as_view(), name='export_job_list'),
    path('exports/create/', views.ExportJobCreateView.as_view(), name='export_job_create'),
    path('exports/<int:pk>/', views.ExportJobDetailView.as_view(), name='export_job_detail'),
    path('exports/<int:pk>/cancel/', views.cancel_export_job, name='export_job_cancel'),
    path('exports/<int:pk>/status/', views.export_job_status, name='export_job_status'),
    path('exports/<int:pk>/download/', views.download_export_file, name='export_job_download'),
    
    # Import Template URLs
    path('templates/', views.ImportTemplateListView.as_view(), name='import_template_list'),
    path('templates/create/', views.ImportTemplateCreateView.as_view(), name='import_template_create'),
    path('templates/<int:pk>/', views.ImportTemplateDetailView.as_view(), name='import_template_detail'),
    
    # AJAX URLs
    path('ajax/preview-import/', views.preview_import_file, name='preview_import_file'),
    path('ajax/export-filters/', views.get_export_filters, name='get_export_filters'),
    path('ajax/model-fields/', views.get_model_fields, name='get_model_fields'),
]