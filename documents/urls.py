from django.urls import path
from . import views

app_name = 'documents'

urlpatterns = [
    # Document list and search
    path('', views.DocumentListView.as_view(), name='list'),
    
    # Document CRUD operations
    path('upload/', views.DocumentCreateView.as_view(), name='upload'),
    path('<int:pk>/', views.DocumentDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.DocumentUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.DocumentDeleteView.as_view(), name='delete'),
    path('<int:pk>/download/', views.document_download, name='download'),
    
    # Document versioning
    path('<int:pk>/version/', views.DocumentVersionCreateView.as_view(), name='add_version'),
    
    # AJAX endpoints
    path('<int:pk>/toggle-star/', views.document_toggle_star, name='toggle_star'),
    path('stats/', views.document_stats, name='stats'),
]