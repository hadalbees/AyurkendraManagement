from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.paginator import Paginator
from patientmgmt.models import Patient
from .models import PatientReport

# ---------- Home Page ----------
from django.db.models import Q
from django.utils.timezone import now, timedelta

class ReportHomeView(LoginRequiredMixin, View):
    def get(self, request):
        search = request.GET.get("search", "").strip()
        report_type = request.GET.get("type", "")
        start_date = request.GET.get("start", "")
        end_date = request.GET.get("end", "")

        reports = PatientReport.objects.select_related("patient").order_by("-created_at")

        # Filtering
        if search:
            reports = reports.filter(
                Q(patient__patient_name__icontains=search) |
                Q(report_title__icontains=search)
            )

        if report_type:
            reports = reports.filter(report_type=report_type)

        if start_date:
            reports = reports.filter(report_date__gte=start_date)

        if end_date:
            reports = reports.filter(report_date__lte=end_date)

        # Recent uploads (last 7 days)
        recent = PatientReport.objects.order_by("-created_at")[:5]

        return render(request, "reportmgmt/reporthome.html", {
            "reports": reports,
            "recent": recent,
            "search": search,
            "report_type": report_type,
            "start_date": start_date,
            "end_date": end_date,
        })


# ---------- All Reports ----------
# class AllReportsListView(LoginRequiredMixin, View):
#     def get(self, request):
#         reports = PatientReport.objects.select_related("patient").order_by("-created_at")
#         return render(request, "reportmgmt/reportlist.html", {"reports": reports})
    
#     from patientmgmt.models import Patient

class AllReportsListView(LoginRequiredMixin, View):
    def get(self, request):
        q = request.GET.get("q", "")
        ptype = request.GET.get("type", "")

        patients = Patient.objects.filter(is_active=True)

        if q:
            patients = patients.filter(
                patient_name__icontains=q
            ) | patients.filter(phone__icontains=q)

        if ptype:
            patients = patients.filter(patient_type=ptype)

        patients = patients.order_by("-created_at")

        paginator = Paginator(patients, 10)  # 10 per page
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        context = {
            "patients": page_obj,
            "page_obj": page_obj,
            "is_paginated": page_obj.has_other_pages(),
            "q": q,
            "type": ptype,
        }
        return render(request, "reportmgmt/reportlist.html", context)



# ---------- Patient Specific ----------
class PatientReportListView(LoginRequiredMixin, View):
    template_name = "reportmgmt/patientreports.html"

    def get(self, request, pk):
        patient = get_object_or_404(Patient, pk=pk)

        report_qs = patient.reports.order_by("-report_date")
        paginator = Paginator(report_qs, 10)  # 10 per page

        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        return render(request, self.template_name, {
            "patient": patient,
            "reports": page_obj,
            "page_obj": page_obj
        })


class PatientReportCreateView(LoginRequiredMixin, View):
    template_name = "reportmgmt/addreport.html"

    def get(self, request, pk):
        patient = get_object_or_404(Patient, pk=pk)
        return render(request, self.template_name, {"patient": patient})

    def post(self, request, pk):
        patient = get_object_or_404(Patient, pk=pk)

        PatientReport.objects.create(
            patient=patient,
            report_title=request.POST.get("report_title"),
            report_type=request.POST.get("report_type"),
            report_date=request.POST.get("report_date"),
            uploaded_file=request.FILES.get("uploaded_file"),
            notes=request.POST.get("notes"),
            uploaded_by=request.user
        )

        messages.success(request, "Report uploaded successfully.")
        return redirect("reportmgmt:patientreports", pk=pk)


# reportmgmt/views.py
import os
from django.shortcuts import render, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import PatientReport

from django.http import FileResponse

class ViewReportDetail(LoginRequiredMixin, View):
    def get(self, request, report_id):
        report = get_object_or_404(PatientReport, pk=report_id)

        _, ext = os.path.splitext(report.uploaded_file.name)
        extension = ext.lower()

        if extension in [".png", ".jpg", ".jpeg", ".webp"]:
            file_type = "image"
        elif extension == ".pdf":
            file_type = "pdf"
        else:
            file_type = "other"

        return render(request, "reportmgmt/viewreport.html", {
            "report": report,
            "file_type": file_type,
            "extension": extension,
        })


class DeleteReportView(LoginRequiredMixin, View):
    def post(self, request, report_id):
        report = get_object_or_404(PatientReport, pk=report_id)
        pid = report.patient.pk
        report.delete()
        messages.success(request, "Report deleted.")
        return redirect("reportmgmt:patientreports", pk=pid)
    
class EditReportView(LoginRequiredMixin, View):
    template_name = "reportmgmt/editreport.html"

    def get(self, request, report_id):
        report = get_object_or_404(PatientReport, pk=report_id)

        # send field choices to template
        report_types = PatientReport._meta.get_field("report_type").choices 

        return render(request, self.template_name, {
            "report": report,
            "report_types": report_types
        })

    def post(self, request, report_id):
        report = get_object_or_404(PatientReport, pk=report_id)

        report.report_title = request.POST.get("report_title")
        report.report_type = request.POST.get("report_type")
        report.report_date = request.POST.get("report_date")
        report.notes = request.POST.get("notes")

        new_file = request.FILES.get("uploaded_file")
        if new_file:
            report.uploaded_file = new_file

        report.save()
        messages.success(request, "Report updated successfully.")

        return redirect("reportmgmt:viewreport", report_id=report_id)

