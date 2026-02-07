from django.urls import path
from . import views

urlpatterns = [
    path('', views.roledashboardview, name='roledashboard'),
    path('add/', views.RoleFormView.as_view(), name='roleaddform'),
    path('edit/<int:pk>/', views.roleeditform, name='roleeditform'),
    path('delete/<int:pk>/', views.roledelete, name='roledelete'),
    path('toggle-status/<int:pk>/', views.toggle_role_status, name='toggle_role_status'),

]
