from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Custom login view that handles role-based redirects
    path('login/', views.CustomLoginView.as_view(), name='login'),
]