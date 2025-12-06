from django.urls import path
from . import views

app_name = 'permissions'

urlpatterns = [
    # Role URLs
    path('roles/', views.RoleListView.as_view(), name='role_list'),
    path('roles/create/', views.RoleCreateView.as_view(), name='role_create'),
    path('roles/<int:pk>/update/', views.RoleUpdateView.as_view(), name='role_update'),
    path('roles/<int:pk>/delete/', views.RoleDeleteView.as_view(), name='role_delete'),
    path('roles/<int:role_id>/users/', views.role_users_view, name='role_users'),
    path('roles/<int:role_id>/users/<int:user_role_id>/remove/', 
         views.remove_user_role_view, name='remove_user_role'),
    
    # User permission URLs
    path('users/', views.user_permissions_view, name='user_permissions'),
    path('users/<int:user_id>/', views.user_permissions_view, name='user_permissions_detail'),
    path('bulk-assignment/', views.BulkRoleAssignmentView.as_view(), name='bulk_role_assignment'),
    
    # Permission URLs
    path('permissions/', views.PermissionListView.as_view(), name='permission_list'),
    path('permission-matrix/', views.permission_matrix_view, name='permission_matrix'),
]