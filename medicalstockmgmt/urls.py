from django.shortcuts import render
from django.urls import path
from . import views

app_name = "medicalstockmgmt"

urlpatterns = [
    path('list/', views.medicalstockhome, name='medicalstockhome'),
    path('add/', views.addstock, name='addstock'),
    path("get-stock/", views.get_stock_details, name="get_stock"),
    
    # Edit/Update/Delete
    path('edit/<int:id>/', views.edit_stock, name='editstock'),
    path('update/<int:id>/', views.update_stock, name='updatestock'),
    path('delete/<int:id>/', views.delete_stock, name='deletestock'),
]