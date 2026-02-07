from django.urls import path
from . import views

app_name = "reportmgmt"

urlpatterns = [
    path("", views.ReportHomeView.as_view(), name="reporthome"),
    path("list/", views.AllReportsListView.as_view(), name="reportlist"),

    # Patient Specific
    path("<int:pk>/reports/", views.PatientReportListView.as_view(), name="patientreports"),
    path("<int:pk>/reports/add/", views.PatientReportCreateView.as_view(), name="addreport"),

    path("view/<int:report_id>/", views.ViewReportDetail.as_view(), name="viewreport"),
    path("delete/<int:report_id>/", views.DeleteReportView.as_view(), name="deletereport"),
    path("edit/<int:report_id>/", views.EditReportView.as_view(), name="editreport"),

]
