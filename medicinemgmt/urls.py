from django.shortcuts import render
from django.urls import path
from . import views

app_name = "medicinemgmt"

urlpatterns = [
    path('medicinehome/', views.medicinehome, name='medicinehome'),
    path("home/", views.MedicineDashboardView.as_view(), name="medicine_home"),

    # Medicine CRUD
    path("medicines/", views.MedicineListView.as_view(), name="medicine_list"),
    path("medicines/add/", views.MedicineCreateView.as_view(), name="medicine_add"),
    path("medicines/<int:pk>/edit/", views.MedicineEditView.as_view(), name="medicine_edit"),
    path("medicines/<int:pk>/delete/", views.MedicineDeleteView.as_view(), name="medicine_delete"),
    path("medicines/<int:pk>/detail/", views.MedicineDetailView.as_view(), name="medicine_detail"),

    # Batch
    path("batches/", views.BatchListView.as_view(), name="batch_list"),
    path("batches/<int:pk>/adjust/", views.BatchAdjustView.as_view(), name="batch_adjust"),

    # Purchases
    path("purchases/", views.PurchaseListView.as_view(), name="purchase_list"),
    path("purchases/add/", views.PurchaseCreateView.as_view(), name="purchase_add"),
    path("purchases/<int:pk>/view/", views.PurchaseDetailView.as_view(), name="purchase_detail"),

    # Sales / Billing
    path("sales/", views.SaleListView.as_view(), name="sale_list"),
    path("sales/add/", views.SaleCreateView.as_view(), name="sale_add"),
    path("sales/<int:pk>/view/", views.SaleDetailView.as_view(), name="sale_detail"),
    path("sales/<int:pk>/void/", views.SaleVoidView.as_view(), name="sale_void"),

    # Exports and API
    path("export/medicines/csv/", views.ExportMedicinesCSV.as_view(), name="export_medicines_csv"),
    path("api/live_counts/", views.LiveCountsView.as_view(), name="live_counts"),
]
