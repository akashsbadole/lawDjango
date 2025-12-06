from django.urls import path
from . import views

app_name = 'client_requests'

urlpatterns = [
    # Client Request CRUD operations
    path('', views.ClientRequestListView.as_view(), name='list'),
    path('create/', views.ClientRequestCreateView.as_view(), name='create'),
    path('<int:pk>/', views.ClientRequestDetailView.as_view(), name='detail'),
    path('<int:pk>/update/', views.ClientRequestUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.ClientRequestDeleteView.as_view(), name='delete'),
    
    # Workflow actions
    path('<int:pk>/add-note/', views.add_note, name='add_note'),
    path('<int:pk>/assign/', views.assign_lawyer, name='assign_lawyer'),
    path('<int:pk>/review/', views.review_request, name='review_request'),
    path('<int:pk>/submit-for-review/', views.submit_for_review, name='submit_for_review'),
]