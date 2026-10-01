# patientmgmt/urls.py
from django.urls import path
from . import views

app_name = "patientmgmt"

urlpatterns = [
    # Dashboard & register
    path("dashboard/", views.PatientDashboardView.as_view(), name="patient_dashboard"),
    path("register/", views.PatientRegistrationView.as_view(), name="patient_register"),

    # Patient list, detail, edit, deactivate
    path("patients/", views.PatientListView.as_view(), name="patient_list"),
    path("<int:pk>/detail/", views.PatientDetailView.as_view(), name="patient_detail"),
    path("<int:pk>/history/print/", views.PatientFullHistoryPrintView.as_view(), name="patient_history_print"),
    path("<int:pk>/edit/", views.PatientEditView.as_view(), name="patient_edit"),
    path("<int:pk>/deactivate/", views.PatientDeactivateView.as_view(), name="patient_deactivate"),

    # Visit (consultation)
    path("<int:pk>/consult/", views.ConsultationCreateView.as_view(), name="consultation_create"),
    path("<int:pk>/consult/<int:visit_pk>/edit/", views.ConsultationEditView.as_view(), name="consultation_edit"),
    path("<int:pk>/consult/<int:visit_pk>/invalidate/", views.ConsultationInvalidateView.as_view(), name="consultation_invalidate"),

    # Admission
    path("admissions/", views.AdmissionListView.as_view(), name="admission_list"),
    path("<int:pk>/admit/", views.AdmissionCreateView.as_view(), name="admission_create"),
    path("<int:pk>/admit/<int:admission_pk>/edit/", views.AdmissionEditView.as_view(), name="admission_edit"),
    path("<int:pk>/admit/<int:admission_pk>/discharge/", views.DischargeAdmissionView.as_view(), name="admission_discharge"),

    # Billing
    path("billing/", views.BillingListView.as_view(), name="billing_list"),
    path("<int:pk>/bill/", views.BillingInvoiceCreateView.as_view(), name="billing_create"),
    path("<int:pk>/bill/<int:invoice_pk>/edit/", views.BillingInvoiceEditView.as_view(), name="billing_edit"),
    path("<int:pk>/bill/<int:invoice_pk>/void/", views.BillingInvoiceVoidView.as_view(), name="billing_void"),

    # Exports
    path("billing/export/csv/", views.BillingExportCSVView.as_view(), name="billing_export_csv"),
    path("billing/export/xlsx/", views.BillingExportXLSXView.as_view(), name="billing_export_xlsx"),
    path("billing/export/pdf/", views.BillingExportPDFView.as_view(), name="billing_export_pdf"),

    # Live counts
    path("api/live_counts/", views.LiveCountsView.as_view(), name="live_counts"),
    
    # Appointments
    path('appointments/', views.appointment_list, name='appointment_list'),
    path('appointments/add/', views.appointment_add, name='appointment_add'),
    path('appointments/edit/<int:pk>/', views.appointment_edit, name='appointment_edit'),
    path('appointments/delete/<int:pk>/', views.appointment_delete, name='appointment_delete'),
    path('appointments/search/', views.appointment_live_search, name='appointment_live_search'),
    
    
    #Alert whatsapp
    path("send-tomorrow-whatsapp/", views.send_tomorrow_whatsapp, name="send_tomorrow_whatsapp"),

    path('get_patient_suggestions/', views.get_patient_suggestions, name='get_patient_suggestions'),
    
    path("booked-slots/", views.booked_slots, name="booked_slots"),
    
    path("whatsapp/send/", views.whatsapp_broadcast_view, name="whatsapp_send"),
    path("whatsapp/logs/", views.whatsapp_logs_view, name="whatsapp_logs"),
    
    path(
    "get-doctors-by-role/",
    views.get_doctors_by_role,
    name="get_doctors_by_role"
    ),
    
    path("check-availability/", views.check_availability, name="check_availability"),
    path("patients/export/pdf/",views.patient_export_pdf,name="patient_export_pdf"),

    # Discharge Summaries
    path("discharge-summaries/", views.DischargeSummaryListView.as_view(), name="discharge_summary_list"),
    path("discharge-summary/add/", views.DischargeSummaryCreateView.as_view(), name="discharge_summary_create"),
    path("discharge-summary/add/<int:patient_id>/", views.DischargeSummaryCreateView.as_view(), name="discharge_summary_create_patient"),
    path("discharge-summary/<int:pk>/detail/", views.DischargeSummaryDetailView.as_view(), name="discharge_summary_detail"),
    path("discharge-summary/<int:pk>/edit/", views.DischargeSummaryEditView.as_view(), name="discharge_summary_edit"),
    path("discharge-summary/<int:pk>/print/", views.DischargeSummaryPrintView.as_view(), name="discharge_summary_print"),
]

