# prescription/urls.py
from django.urls import path
from . import views

app_name = "prescriptionmgmt"

urlpatterns = [
    path("create/", views.create_prescription, name="create"),
    path("get-patient/", views.ajax_get_patient, name="get_patient"),
    path("get-patient-history/", views.ajax_get_patient_history, name="get_patient_history"),
    path("get-prescription-details/", views.ajax_get_prescription_details, name="get_prescription_details"),
    path("get-stock/", views.ajax_get_stock, name="get_stock"),
    path("print/<str:prescription_no>/", views.print_prescription, name="print"),
]

