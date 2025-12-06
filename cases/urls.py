from django.urls import path
from . import views

app_name = 'cases'

urlpatterns = [
    # Case URLs
    path('', views.CaseListView.as_view(), name='list'),
    path('create/', views.CaseCreateView.as_view(), name='create'),
    path('<int:pk>/', views.CaseDetailView.as_view(), name='detail'),
    path('<int:pk>/update/', views.CaseUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.CaseDeleteView.as_view(), name='delete'),
    
    # Case Event URLs
    path('event/create/<int:case_pk>/', views.CaseEventCreateView.as_view(), name='event_create'),
    path('event/<int:pk>/update/', views.CaseEventUpdateView.as_view(), name='event_update'),
    path('event/<int:pk>/delete/', views.CaseEventDeleteView.as_view(), name='event_delete'),
]