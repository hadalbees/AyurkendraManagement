from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.paginator import Paginator
from patientmgmt.models import Patient
from .models import PatientReport
from prescriptionmgmt.models import Prescription, PrescriptionItem
from fieldmgmt.models import ActivityHistory

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

        q = request.GET.get("q", "").strip()
        ptype = request.GET.get("type", "").strip()

        # Base queryset
        patients = Patient.objects.filter(is_active=True)

        # 🔎 Search filter
        if q:
            patients = patients.filter(
                Q(patient_name__icontains=q) |
                Q(phone__icontains=q)
            )

        # 🏥 Type filter
        if ptype:
            patients = patients.filter(patient_type=ptype)

        # 🚀 IMPORTANT: Remove duplicates
        patients = patients.distinct().order_by("-created_at")

        # ⚡ Performance optimization
        patients = patients.prefetch_related("reports")

        paginator = Paginator(patients, 10)
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

        report_title = request.POST.get("report_title")
        report_type = request.POST.get("report_type")
        report_date = request.POST.get("report_date")
        uploaded_file = request.FILES.get("uploaded_file")
        notes = request.POST.get("notes")

        # ✅ Basic validation
        if not uploaded_file:
            messages.error(request, "Please select a file to upload")
            return redirect(request.path)

        try:
            patientreport = PatientReport.objects.create(
                patient=patient,
                report_title=report_title,
                report_type=report_type,
                report_date=report_date,
                uploaded_file=uploaded_file,  # 👉 S3 will handle this automatically
                notes=notes,
                uploaded_by=request.user
            )

            # ✅ Activity log
            ActivityHistory.objects.create(
                user=request.user,
                action="CREATE",
                module="PATIENT REPORT",
                record_id=patientreport.id,
                description=f"Patient report #{patientreport.id} created by {request.user}"
            )

            # ✅ Debug (VERY USEFUL)
            print("S3 FILE URL:", patientreport.uploaded_file.url)
            print("Saved file path:", patientreport.uploaded_file.name)
            print("File URL:", patientreport.uploaded_file.url)
            messages.success(request, "Report uploaded successfully")

        except Exception as e:
            print("UPLOAD ERROR:", e)
            messages.error(request, "File upload failed")

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
        ActivityHistory.objects.create(
            user=request.user,
            action="DELETE",
            module="PATIENT REPORT",
            record_id=report.id,
            description=f"Patient report #{report.id} deleted by {request.user}"
        )
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
        ActivityHistory.objects.create(
            user=request.user,
            action="UPDATE",
            module="PATIENT REPORT",
            record_id=report.id,
            description=f"Patient report #{report.id} updated by {request.user}"
        )
        messages.success(request, "Report updated successfully.")

        return redirect("reportmgmt:viewreport", report_id=report_id)

# ================================
# LIST
# ================================
def prescription_list(request):
    prescriptions = Prescription.objects.select_related(
        "patient", "doctor"
    ).prefetch_related("items", "treatment_items").order_by("-created_at")

    paginator = Paginator(prescriptions, 10)
    page = request.GET.get("page")
    prescriptions = paginator.get_page(page)

    return render(request, "reportmgmt/prescription_list.html", {
        "prescriptions": prescriptions
    })


# ================================
# VIEW
# ================================
def prescription_view(request, pk):
    prescription = get_object_or_404(
        Prescription.objects.select_related("patient", "doctor")
        .prefetch_related("items", "treatment_items"),
        pk=pk
    )

    return render(request, "reportmgmt/prescription_view.html", {
        "prescription": prescription
    })


# ================================
# EDIT
# ================================
def prescription_edit(request, pk):
    prescription = get_object_or_404(
        Prescription.objects.select_related("patient", "doctor")
        .prefetch_related("items", "treatment_items"),
        pk=pk
    )

    if request.method == "POST":
        # --- Update main & Case Sheet fields ---
        prescription.occupation = request.POST.get("occupation", "").strip()
        prescription.presenting_complaints = request.POST.get("presenting_complaints", "").strip()
        prescription.associated_complaints = request.POST.get("associated_complaints", "").strip()
        prescription.history_present_illness = request.POST.get("history_present_illness", "").strip()
        prescription.history_past_illness = request.POST.get("history_past_illness", "").strip()

        prescription.comorbid_diabetes = request.POST.get("comorbid_diabetes") in ["on", "true", True]
        prescription.comorbid_hypertension = request.POST.get("comorbid_hypertension") in ["on", "true", True]
        prescription.comorbid_thyroid = request.POST.get("comorbid_thyroid") in ["on", "true", True]
        prescription.comorbid_cardiac = request.POST.get("comorbid_cardiac") in ["on", "true", True]
        prescription.comorbid_kidney = request.POST.get("comorbid_kidney") in ["on", "true", True]
        prescription.comorbid_others = request.POST.get("comorbid_others", "").strip()
        prescription.current_medications = request.POST.get("current_medications", "").strip()

        # Vitals / Examination Grid
        prescription.exam_malam = request.POST.get("exam_malam", "").strip()
        prescription.exam_nadi = request.POST.get("exam_nadi", "").strip()
        prescription.exam_jivha = request.POST.get("exam_jivha", "").strip()
        prescription.exam_akri = request.POST.get("exam_akri", "").strip()
        prescription.exam_diet_habit = request.POST.get("exam_diet_habit", "").strip()
        prescription.exam_mutr = request.POST.get("exam_mutr", "").strip()
        prescription.exam_shabda = request.POST.get("exam_shabda", "").strip()
        prescription.exam_bp = request.POST.get("exam_bp", "").strip()
        prescription.exam_addiction = request.POST.get("exam_addiction", "").strip()
        prescription.exam_lmp = request.POST.get("exam_lmp", "").strip()
        prescription.exam_sharira = request.POST.get("exam_sharira", "").strip()
        prescription.exam_sparsha = request.POST.get("exam_sparsha", "").strip()
        prescription.exam_allergies = request.POST.get("exam_allergies", "").strip()
        prescription.exam_pulse = request.POST.get("exam_pulse", "").strip()
        prescription.exam_shir = request.POST.get("exam_shir", "").strip()
        prescription.exam_nakha = request.POST.get("exam_nakha", "").strip()

        prescription.notes = request.POST.get("notes")
        prescription.next_visit = request.POST.get("next_visit") or None
        prescription.save()

        ActivityHistory.objects.create(
            user=request.user,
            action="UPDATE",
            module="PRESCRIPTION",
            record_id=prescription.id,
            description=f"prescription #{prescription.prescription_no} updated by {request.user}"
        )

        # --- Re-create medicine items ---
        prescription.items.all().delete()
        medicine_names = request.POST.getlist("medicine_name[]")
        dosages = request.POST.getlist("dosage[]")
        durations = request.POST.getlist("duration_days[]")
        quantities = request.POST.getlist("quantity[]")
        instructions = request.POST.getlist("instructions[]")
        food_timings = request.POST.getlist("food_timing[]")

        for idx in range(len(medicine_names)):
            name = medicine_names[idx].strip()
            if not name:
                continue
            dosage = dosages[idx] if idx < len(dosages) else ""
            dur = durations[idx] if idx < len(durations) else 0
            qty = quantities[idx] if idx < len(quantities) else 0
            inst = instructions[idx] if idx < len(instructions) else ""
            food = food_timings[idx] if idx < len(food_timings) else ""

            from prescriptionmgmt.models import PrescriptionItem
            PrescriptionItem.objects.create(
                prescription=prescription,
                medicine_name=name,
                dosage=dosage,
                duration_days=int(dur or 0),
                quantity=Decimal(str(qty or 0)),
                instructions=inst,
                food_timing=food
            )

        # --- Re-create treatment plan items ---
        prescription.treatment_items.all().delete()
        treatment_names = request.POST.getlist("treatment_name[]")
        tailams = request.POST.getlist("tailam[]")
        t_instructions = request.POST.getlist("treatment_instructions[]")

        for idx in range(len(treatment_names)):
            t_name = treatment_names[idx].strip()
            if not t_name:
                continue
            tailam = tailams[idx].strip() if idx < len(tailams) else ""
            t_inst = t_instructions[idx].strip() if idx < len(t_instructions) else ""

            from prescriptionmgmt.models import TreatmentPlanItem
            TreatmentPlanItem.objects.create(
                prescription=prescription,
                treatment_name=t_name,
                tailam=tailam,
                instructions=t_inst
            )

        return redirect("reportmgmt:prescription_list")

    from fieldmgmt.models import Adjuvant
    adjuvants = Adjuvant.objects.filter(status=True).order_by("name")
    return render(request, "reportmgmt/prescription_edit.html", {
        "prescription": prescription,
        "adjuvants": adjuvants
    })



# ================================
# DELETE
# ================================
def prescription_delete(request, pk):

    prescription = get_object_or_404(Prescription, pk=pk)
    prescription.delete()
    ActivityHistory.objects.create(
            user=request.user,
            action="DELETE",
            module="PRESCRIPTION",
            record_id=prescription.id,
            description=f"prescription #{prescription.id} deleted by {request.user}"
        )
    return redirect("reportmgmt:prescription_list")