from django.urls import path
from . import views
from .views import (
    DepartmentListView,
    DepartmentCreateView,
    DepartmentUpdateView,
    DepartmentDeleteView,
)

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
    
    # DEPARTMENT
    path("departments/", DepartmentListView.as_view(), name="department_list"),
    path("departments/add/", DepartmentCreateView.as_view(), name="department_add"),
    path("departments/edit/<int:pk>/", DepartmentUpdateView.as_view(), name="department_edit"),
    path("departments/delete/<int:pk>/", DepartmentDeleteView.as_view(), name="department_delete"),
    
    #APPOINMENT TYPE
    path("appointment-types/", views.appointment_type_list, name="appointment_type_list"),
    path("appointment-types/add/", views.appointment_type_add, name="appointment_type_add"),
    path("appointment-types/edit/<int:pk>/", views.appointment_type_edit, name="appointment_type_edit"),
    path("appointment-types/delete/<int:pk>/", views.appointment_type_delete, name="appointment_type_delete"),
    
    #IPOTHERCHARGES
    path("ip-othercharges/",views.ip_othercharge_list,name="ip_othercharge_list",),
    path("ip-othercharges/add/",views.ip_othercharge_add,name="ip_othercharge_add",),
    path("ip-othercharges/edit/<int:pk>/",views.ip_othercharge_edit,name="ip_othercharge_edit",),
    path("ip-othercharges/delete/<int:pk>/",views.ip_othercharge_delete,name="ip_othercharge_delete",),
    
    #ADJUVANT
    path("adjuvant/", views.adjuvant_list, name="adjuvant_list"),
    path("adjuvant/add/", views.adjuvant_add, name="adjuvant_add"),
    path("adjuvant/edit/<int:id>/", views.adjuvant_edit, name="adjuvant_edit"),
    path("adjuvant/delete/<int:id>/", views.adjuvant_delete, name="adjuvant_delete"),
    

    path(
        "room-types/",
        views.room_type_list,
        name="room_type_list"
    ),

    path(
        "room-types/add/",
        views.room_type_add,
        name="room_type_add"
    ),

    path(
        "room-types/edit/<int:id>/",
        views.room_type_edit,
        name="room_type_edit"
    ),

    path(
        "room-types/delete/<int:id>/",
        views.room_type_delete,
        name="room_type_delete"
    ),
]
