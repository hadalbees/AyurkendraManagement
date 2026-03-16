from django.shortcuts import render
from django.urls import path
from . import views

app_name = "billingmgmt"

urlpatterns = [
    path("inpatient_billing/", views.inpatient_billing_view, name="inpatientbilling"),
    path("print-inpatient/<str:bill_no>/", views.print_inpatient_bill, name="print_inpatient_bill"),
    path("outpatient_billing/", views.outpatient_billing_view, name="outpatientbilling"),
    path("print-outpatient/<str:bill_no>/", views.print_outpatient_bill, name="print_outpatient_bill"),
    path('medicalbilling/', views.medical_billing_view, name='medicalbilling'),
    path('get-patient/', views.get_patient, name='get_patient'),
    path('print/<str:bill_no>/', views.print_bill, name='print_bill'),
    path("get-prescription/", views.get_patient_prescription, name="get_prescription"),
    
    path("therapy_billing/", views.therapy_billing_view, name="therapybilling"),
    path('therapy-bill-print/<str:bill_no>/', views.therapy_bill_print_view, name='therapy_bill_print'),
     path('get_patient_suggestions/', views.get_patient_suggestions, name='get_patient_suggestions'),
     path("patient/<int:patient_id>/bills/download/", views.download_all_bills_pdf,name="download_all_bills"),
     
     # ===== BILLING HISTORY DASHBOARD =====
    path("billing-history/", views.billing_history_home, name="billing_history"),

    # ===== BILLING LIST PAGES =====
    path("billing-history/medical/", views.medical_billing_list, name="medical_billing_list"),
    path("medical/ajax/", views.medical_bill_ajax, name="medical_bill_ajax"),
     path(
        "medical/print-all/",
        views.print_all_medical_bills,
        name="print_all_medical_bills"
    ),

    path("billing-history/therapy/", views.therapy_billing_list, name="therapy_billing_list"),
    path("billing-history/inpatient/", views.inpatient_billing_list, name="inpatient_billing_list"),
    path("billing-history/outpatient/", views.outpatient_billing_list, name="outpatient_billing_list"),
    
    path("billing/filter/<str:bill_type>/", views.billing_filter_ajax, name="billing_filter_ajax"),
    path("billing/print-all/<str:bill_type>/", views.print_all_bills, name="print_all_bills"),
    path("get_patient_suggestions/", views.get_patient_suggestions),

    
    # ===== VIEW PAGES =====
    path("billing-history/medical/view/<int:pk>/", views.medical_bill_view, name="medical_bill_view"),
    path("billing-history/therapy/view/<int:pk>/", views.therapy_bill_view, name="therapy_bill_view"),
    path("billing-history/inpatient/view/<int:pk>/", views.inpatient_bill_view, name="inpatient_bill_view"),
    path("billing-history/outpatient/view/<int:pk>/", views.outpatient_bill_view, name="outpatient_bill_view"),
    
    
    
    path("billing/combined/", views.combined_billing_view,name="combined_billing_view"),

    path("billing/combined/filter/",views.combined_billing_filter_ajax,name="combined_billing_filter_ajax"),

    path("billing/combined/print/",views.combined_billing_print,name="combined_billing_print"),


]