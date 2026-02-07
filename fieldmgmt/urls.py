from django.urls import path
from . import views

app_name = "fieldmgmt"

urlpatterns = [
    path("therapy_list/", views.therapy_list, name="therapy_list"),
    path("therapy_add/", views.therapy_add, name="therapy_add"),
    path("therapy_edit/<int:id>/", views.therapy_edit, name="therapy_edit"),
    path("therapy_delete/<int:id>/", views.therapy_delete, name="therapy_delete"),
    
    
    path('ayurvedic_list/', views.ayurvedic_list, name='ayurvedic_list'),
    path('ayurvedic_add/', views.ayurvedic_add, name='ayurvedic_add'),
    path('ayurvedic_edit/<int:id>/', views.ayurvedic_edit, name='ayurvedic_edit'),
    path('ayurvedic_delete/<int:id>/', views.ayurvedic_delete, name='ayurvedic_delete'),
    
    
    # SUPPLIER
    path('suppliers/', views.supplier_list, name="supplier_list"),
    path('suppliers/add/', views.supplier_add, name="supplier_add"),
    path('suppliers/edit/<int:pk>/', views.supplier_edit, name="supplier_edit"),
    path('suppliers/delete/<int:pk>/', views.supplier_delete, name="supplier_delete"),

    # MANUFACTURER
    path('manufacturers/', views.manufacturer_list, name="manufacturer_list"),
    path('manufacturers/add/', views.manufacturer_add, name="manufacturer_add"),
    path('manufacturers/edit/<int:pk>/', views.manufacturer_edit, name="manufacturer_edit"),
    path('manufacturers/delete/<int:pk>/', views.manufacturer_delete, name="manufacturer_delete"),
]
