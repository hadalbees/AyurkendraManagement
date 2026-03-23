from django.urls import path
from . import views

urlpatterns = [
    path('', views.permissionhome, name='permissionhome'),
    path('staff/add/', views.staffaddform, name='staffaddform'),
    path('staff/edit/<int:pk>/', views.staffeditform, name='staffeditform'),
    path('staff/delete/<int:pk>/', views.staff_delete_view, name='staff_delete'),
    path('toggle-status/<int:pk>/', views.toggle_staff_status, name='toggle_staff_status'),
    path("staff/export/pdf/",views.staff_export_pdf,name="staff_export_pdf"),

]
