# patientmgmt/views.py
from decimal import Decimal, InvalidOperation
import io, csv, datetime
from django.db.models import Q
from django.core.paginator import Paginator

from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import TemplateView, DetailView, ListView
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError, transaction, models
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.utils.encoding import smart_str
from datetime import date, timedelta
from django.shortcuts import redirect
from authentication.models import CustomUser
from billingmgmt.models import InpatientBill, MedicalBill, OutpatientBill, TherapyBill
from patientmgmt.models import Patient
from utils.whatsapp import send_whatsapp_template, format_phone
from fieldmgmt.models import TherapyMaster,ActivityHistory
from rolemgmt.models import Role
from fieldmgmt.models import Department
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from django.utils.timezone import now
from billingmgmt.models import HospitalSetting
from fieldmgmt.models import AppointmentType
from django.db.models import Q
from django.utils.dateparse import parse_date, parse_time

from .models import (
    Appointment,
    Patient,
    PatientVisit,
    InpatientAdmission,
    BillingInvoice,
    InvoiceItem,
    WhatsAppLog,
)
from utils.whatsapp import (
    send_whatsapp_text,
    send_whatsapp_image,
    send_whatsapp_document,
    format_phone
)
# optional libs
try:
    import openpyxl
except Exception:
    openpyxl = None

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
except Exception:
    canvas = None


# -----------------------------
# DASHBOARD
# -----------------------------
class PatientDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "patientmgmt/patienthome.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["total_patients"] = Patient.objects.filter(is_active=True).count()
        ctx["inpatients"] = Patient.objects.filter(is_active=True, patient_type="IP").count()
        ctx["outpatients"] = Patient.objects.filter(is_active=True, patient_type="OP").count()
        ctx["discharged"] = InpatientAdmission.objects.filter(discharge_date__isnull=False).count()
        ctx["patients"] = Patient.objects.filter(is_active=True).order_by('-id')[:10]
        ctx["billings"] = BillingInvoice.objects.filter(is_void=False).order_by('-id')[:5]
        ctx["pending_invoices"] = BillingInvoice.objects.filter(is_void=False, payment_status="PENDING").count()
        ctx["total_invoices_amount"] = BillingInvoice.objects.filter(is_void=False).aggregate(total=models.Sum('total_amount'))['total'] or 0
        return ctx


# -----------------------------
# PATIENT CRUD (create, list is below)
# -----------------------------
def generate_patient_id():
    """
    Generate a unique patient ID safely.
    Format: PAT0001, PAT0002, ...
    Uses select_for_update to prevent race conditions.
    """
    with transaction.atomic():
        # Lock the last patient row to prevent duplicate ID
        last_patient = Patient.objects.select_for_update().order_by('-id').first()
        if last_patient and last_patient.patient_unique_id:
            try:
                num = int(last_patient.patient_unique_id.replace("PAT", ""))
                return f"PAT{num + 1:04d}"
            except ValueError:
                pass
        return "PAT0001"

class PatientRegistrationView(LoginRequiredMixin, View):
    template_name = "patientmgmt/addpatient.html"

    # ==========================
    # GET METHOD
    # ==========================
    def get(self, request, *args, **kwargs):

        current_time = timezone.localtime().strftime("%I:%M %p")

        doctors = CustomUser.objects.filter(
                    Q(role__role_name__icontains="Doctor") |
                    Q(role__role_name__icontains="Consultant") |
                    Q(role__role_name__icontains="Surgeon"),
                    is_active=True
                ).select_related('role').order_by('username').distinct()
        
        # ✅ Get Active Departments
        departments = Department.objects.filter(status=True).order_by("department_name")

        # Active patients (for referred_by dropdown if needed)
        patients = Patient.objects.filter(is_active=True)

        return render(request, self.template_name, {
            "current_time": current_time,
            "doctors": doctors,
            "patients": patients,
            "departments": departments
        })

    # ==========================
    # POST METHOD
    # ==========================
    def post(self, request, *args, **kwargs):

        new_patient_id = generate_patient_id()

        # ------------------------
        # REFERRED BY (SAFE)
        # ------------------------
        referred_by_id = request.POST.get("refered_by", "").strip()

        if referred_by_id in ("", "undefined", "null"):
            referred_by_patient = None
        elif referred_by_id.isdigit():
            referred_by_patient = Patient.objects.filter(
                id=int(referred_by_id)
            ).first()
        else:
            referred_by_patient = None

        # ------------------------
        # CONSULTANT & ASSIGNED DOCTOR
        # ------------------------
        consultant_id = request.POST.get("consultant_doctor")
        assigned_id = request.POST.get("assigned_doctor")

        consultant_user = CustomUser.objects.filter(
            id=consultant_id
        ).first() if consultant_id else None

        assigned_user = CustomUser.objects.filter(
            id=assigned_id
        ).first() if assigned_id else None

        # ------------------------
        # CREATE PATIENT
        # ------------------------
        patient = Patient.objects.create(
            patient_unique_id=new_patient_id,

            consultant_doctor=consultant_user,
            assigned_doctor=assigned_user,
            department=request.POST.get("department"),

            prefix=request.POST.get("prefix"),
            patient_name=request.POST.get("patient_name"),

            age=int(request.POST.get("age") or 0),
            gender=request.POST.get("gender"),
            dob=request.POST.get("dob") or None,

            phone=request.POST.get("phone"),
            email=request.POST.get("email"),
            address=request.POST.get("address"),

            id_card=request.POST.get("id_card"),
            id_card_image=request.FILES.get("id_card_image"),

            emergency_contact=request.POST.get("emergency_contact"),

            patient_type=request.POST.get("patient_type"),
            visit_date=request.POST.get("visit_date") or timezone.localdate(),

            notes=request.POST.get("notes"),

            refered_by=referred_by_patient,

            registered_by=request.user
        )
        ActivityHistory.objects.create(
            user=request.user,
            action="CREATE",
            module="PATIENT",
            record_id=patient.id,
            description=f"Patient #{patient.id} created by {request.user}"
        )

        messages.success(
            request,
            f"Patient registered successfully. Patient ID: {new_patient_id}"
        )

        return redirect("patientmgmt:patient_list")


class PatientEditView(LoginRequiredMixin, View):
    template_name = "patientmgmt/editpatient.html"

    def get(self, request, pk):
        patient = get_object_or_404(Patient, pk=pk)
        return render(request, self.template_name, {"patient": patient})

    def post(self, request, pk):
        patient = get_object_or_404(Patient, pk=pk)
        patient.consultant_doctor = request.POST.get("consultant_doctor")
        patient.department = request.POST.get("department")
        patient.prefix = request.POST.get("prefix")
        patient.patient_name = request.POST.get("patient_name")
        patient.age = int(request.POST.get("age") or 0)
        patient.gender = request.POST.get("gender")

        patient.phone = request.POST.get("phone")
        patient.email = request.POST.get("email")
        patient.address = request.POST.get("address")

        patient.patient_type = request.POST.get("patient_type")
        patient.visit_date = request.POST.get("visit_date") or patient.visit_date

        patient.assigned_doctor = request.POST.get("assigned_doctor")
        patient.notes = request.POST.get("notes")

        patient.save()
        ActivityHistory.objects.create(
            user=request.user,
            action="UPDATE",
            module="PATIENT",
            record_id=patient.id,
            description=f"Patient #{patient.id} updated by {request.user}"
        )
        messages.success(request, "Patient updated successfully.")
        return redirect("patientmgmt:patient_detail", pk=patient.pk)


class PatientDeactivateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        patient = get_object_or_404(Patient, pk=pk)
        patient.is_active = False
        patient.save()
        ActivityHistory.objects.create(
            user=request.user,
            action="DEACTIVATE",
            module="PATIENT",
            record_id=patient.id,
            description=f"Patient #{patient.id} deactivated by {request.user}"
        )
        messages.success(request, "Patient deactivated (record preserved).")
        return redirect("patientmgmt:patient_list")


class PatientDetailView(LoginRequiredMixin, DetailView):
    model = Patient
    template_name = "patientmgmt/patientdetail.html"
    context_object_name = "patient"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        patient = self.object

        bills = []
        # ---- Medical Bills ----
        for b in MedicalBill.objects.filter(patient=patient):
            bills.append({
                "type": "Medical",
                "bill_no": b.bill_no,
                "date": b.bill_date,
                "total": b.total,
                "status": b.payment_status,
                "pdf_url": "billingmgmt:print_bill",
                "ref": b.bill_no,
            })

        # ---- Inpatient Bills ----
        for b in InpatientBill.objects.filter(patient=patient):
            bills.append({
                "type": "Inpatient",
                "bill_no": b.bill_no,
                "date": b.admit_date,
                "total": b.total,
                "status": b.payment_status,
                "pdf_url": "billingmgmt:print_inpatient_bill",
                "ref": b.bill_no,
            })

        # ---- Outpatient Bills ----
        for b in OutpatientBill.objects.filter(patient=patient):
            bills.append({
                "type": "Outpatient",
                "bill_no": b.bill_no,
                "date": b.visit_date,
                "total": b.total,
                "status": "Paid",
                "pdf_url": "billingmgmt:print_outpatient_bill",
                "ref": b.bill_no,
            })

        # ---- Therapy Bills ----
        for b in TherapyBill.objects.filter(patient=patient):
            bills.append({
                "type": "Therapy",
                "bill_no": b.bill_no,
                "date": b.bill_date,
                "total": b.total,
                "status": b.payment_status,
                "pdf_url": "billingmgmt:therapy_bill_print",
                "ref": b.bill_no,
            })

        # sort by date desc
        bills.sort(key=lambda x: x["date"] or "", reverse=True)

        ctx["all_bills"] = bills
        return ctx


# -----------------------------
# VISITS
# -----------------------------
class ConsultationCreateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        patient = get_object_or_404(Patient, pk=pk, is_active=True)
        visit = PatientVisit(
            patient=patient,
            diagnosis=request.POST.get("diagnosis"),
            prescription_notes=request.POST.get("prescription_notes"),
            visit_date=request.POST.get("visit_date") or timezone.now()
        )
        visit.save()
        messages.success(request, "Consultation recorded.")
        return redirect("patientmgmt:patient_detail", pk=pk)


class ConsultationEditView(LoginRequiredMixin, View):
    template_name = "patientmgmt/editvisit.html"

    def get(self, request, pk, visit_pk):
        visit = get_object_or_404(PatientVisit, pk=visit_pk)
        return render(request, self.template_name, {"visit": visit})

    def post(self, request, pk, visit_pk):
        visit = get_object_or_404(PatientVisit, pk=visit_pk)
        visit.diagnosis = request.POST.get("diagnosis")
        visit.prescription_notes = request.POST.get("prescription_notes")
        vdate = request.POST.get("visit_date")
        if vdate:
            visit.visit_date = vdate
        visit.save()
        messages.success(request, "Visit updated.")
        return redirect("patientmgmt:patient_detail", pk=pk)


class ConsultationInvalidateView(LoginRequiredMixin, View):
    def post(self, request, pk, visit_pk):
        visit = get_object_or_404(PatientVisit, pk=visit_pk)
        visit.is_valid = False
        visit.save()
        messages.success(request, "Visit marked invalid.")
        return redirect("patientmgmt:patient_detail", pk=pk)


# -----------------------------
# ADMISSIONS
# -----------------------------
class AdmissionCreateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        patient = get_object_or_404(Patient, pk=pk, is_active=True)
        admission = InpatientAdmission(
            patient=patient,
            room_number=request.POST.get("room_number"),
            bed_id=request.POST.get("bed_id"),
            admission_date=request.POST.get("admission_date") or timezone.now()
        )
        admission.save()
        messages.success(request, "Patient admitted.")
        return redirect("patientmgmt:patient_detail", pk=pk)


class AdmissionEditView(LoginRequiredMixin, View):
    template_name = "patientmgmt/editadmission.html"

    def get(self, request, pk, admission_pk):
        admission = get_object_or_404(InpatientAdmission, pk=admission_pk)
        return render(request, self.template_name, {"admission": admission})

    def post(self, request, pk, admission_pk):
        admission = get_object_or_404(InpatientAdmission, pk=admission_pk)
        admission.room_number = request.POST.get("room_number")
        admission.bed_id = request.POST.get("bed_id")
        adate = request.POST.get("admission_date")
        if adate:
            admission.admission_date = adate
        admission.save()
        messages.success(request, "Admission updated.")
        return redirect("patientmgmt:patient_detail", pk=pk)


class DischargeAdmissionView(LoginRequiredMixin, View):
    def post(self, request, pk, admission_pk):
        admission = get_object_or_404(InpatientAdmission, pk=admission_pk)
        admission.current_status = 'DISCHARGED'
        admission.discharge_date = timezone.now()
        admission.save()
        messages.success(request, "Patient discharged.")
        return redirect("patientmgmt:patient_detail", pk=pk)


# -----------------------------
# BILLING
# -----------------------------
class BillingInvoiceCreateView(LoginRequiredMixin, View):
    template_name = "patientmgmt/invoiceform.html"

    def get(self, request, pk):
        patient = get_object_or_404(Patient, pk=pk, is_active=True)
        return render(request, self.template_name, {"patient": patient})

    def post(self, request, pk):
        patient = get_object_or_404(Patient, pk=pk, is_active=True)
        items_count = int(request.POST.get("items_count", 0))
        payment_status = request.POST.get("payment_status", "PENDING")

        if items_count <= 0:
            messages.error(request, "Add at least one invoice item.")
            return render(request, self.template_name, {"patient": patient})

        total = Decimal("0.00")
        with transaction.atomic():
            invoice = BillingInvoice.objects.create(
                patient=patient,
                payment_status=payment_status,
                generated_by=request.user,
            )
            created_any = False
            for i in range(items_count):
                desc = request.POST.get(f"item_desc_{i}", "").strip()
                qty_raw = request.POST.get(f"item_qty_{i}", "0").strip()
                unit_raw = request.POST.get(f"item_unit_{i}", "0").strip()
                if not desc:
                    continue
                try:
                    qty = Decimal(qty_raw)
                except InvalidOperation:
                    qty = Decimal("0.00")
                try:
                    unit_price = Decimal(unit_raw)
                except InvalidOperation:
                    unit_price = Decimal("0.00")
                line_total = (qty * unit_price).quantize(Decimal('0.01'))
                InvoiceItem.objects.create(
                    invoice=invoice,
                    description=desc,
                    quantity=qty,
                    unit_price=unit_price,
                    line_total=line_total
                )
                total += line_total
                created_any = True

            if not created_any:
                transaction.set_rollback(True)
                messages.error(request, "No valid invoice items provided.")
                return render(request, self.template_name, {"patient": patient})

            invoice.total_amount = total
            invoice.save()

        messages.success(request, f"Invoice created (ID: {invoice.pk}) — total ₹{invoice.total_amount}")
        return redirect("patientmgmt:patient_detail", pk=pk)


class BillingInvoiceEditView(LoginRequiredMixin, View):
    template_name = "patientmgmt/editinvoice.html"

    def get(self, request, pk, invoice_pk):
        invoice = get_object_or_404(BillingInvoice, pk=invoice_pk)
        if invoice.is_void:
            messages.error(request, "Cannot edit a voided invoice.")
            return redirect("patientmgmt:patient_detail", pk=pk)
        return render(request, self.template_name, {"invoice": invoice})

    def post(self, request, pk, invoice_pk):
        invoice = get_object_or_404(BillingInvoice, pk=invoice_pk)
        if invoice.is_void:
            messages.error(request, "Cannot edit a voided invoice.")
            return redirect("patientmgmt:patient_detail", pk=pk)

        items_count = int(request.POST.get("items_count", 0))
        payment_status = request.POST.get("payment_status", invoice.payment_status)

        if items_count <= 0:
            messages.error(request, "Add at least one invoice item.")
            return render(request, self.template_name, {"invoice": invoice})

        total = Decimal("0.00")
        with transaction.atomic():
            invoice.items.all().delete()
            for i in range(items_count):
                desc = request.POST.get(f"item_desc_{i}", "").strip()
                qty_raw = request.POST.get(f"item_qty_{i}", "0").strip()
                unit_raw = request.POST.get(f"item_unit_{i}", "0").strip()
                if not desc:
                    continue
                try:
                    qty = Decimal(qty_raw)
                except InvalidOperation:
                    qty = Decimal("0.00")
                try:
                    unit_price = Decimal(unit_raw)
                except InvalidOperation:
                    unit_price = Decimal("0.00")
                line_total = (qty * unit_price).quantize(Decimal('0.01'))
                InvoiceItem.objects.create(
                    invoice=invoice,
                    description=desc,
                    quantity=qty,
                    unit_price=unit_price,
                    line_total=line_total
                )
                total += line_total

            invoice.total_amount = total
            invoice.payment_status = payment_status
            invoice.save()

        messages.success(request, "Invoice updated.")
        return redirect("patientmgmt:patient_detail", pk=pk)


class BillingInvoiceVoidView(LoginRequiredMixin, View):
    def post(self, request, pk, invoice_pk):
        invoice = get_object_or_404(BillingInvoice, pk=invoice_pk)
        invoice.is_void = True
        invoice.save()
        messages.success(request, "Invoice voided (preserved for history).")
        return redirect("patientmgmt:patient_detail", pk=pk)


# -----------------------------
# LISTS with search / pagination
# -----------------------------
class PatientListView(LoginRequiredMixin, ListView):
    model = Patient
    template_name = "patientmgmt/patientlist.html"
    context_object_name = "patients"
    paginate_by = 15

    def get_queryset(self):
        qs = Patient.objects.filter(is_active=True).order_by('-created_at')
        q = self.request.GET.get('q', '').strip()
        ptype = self.request.GET.get('type', '').strip()
        phone = self.request.GET.get('phone', '').strip()

        if q:
            qs = qs.filter(
                models.Q(patient_name__icontains=q) |
                models.Q(consultant_doctor__icontains=q) |
                models.Q(department__icontains=q)
            )
        if phone:
            qs = qs.filter(phone__icontains=phone)
        if ptype in ('OP', 'IP'):
            qs = qs.filter(patient_type=ptype)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["total_patients"] = Patient.objects.filter(is_active=True).count()
        ctx["inpatients"] = Patient.objects.filter(is_active=True, patient_type="IP").count()
        ctx["outpatients"] = Patient.objects.filter(is_active=True, patient_type="OP").count()
        ctx["discharged"] = InpatientAdmission.objects.filter(discharge_date__isnull=False).count()
        ctx["patients"] = Patient.objects.filter(is_active=True).order_by('-id')[:10]
        ctx["billings"] = BillingInvoice.objects.filter(is_void=False).order_by('-id')[:5]
        ctx["pending_invoices"] = BillingInvoice.objects.filter(is_void=False, payment_status="PENDING").count()
        ctx["total_invoices_amount"] = BillingInvoice.objects.filter(is_void=False).aggregate(total=models.Sum('total_amount'))['total'] or 0
        ctx['q'] = self.request.GET.get('q', '')
        ctx['phone'] = self.request.GET.get('phone', '')
        ctx['type'] = self.request.GET.get('type', '')
        return ctx


class AdmissionListView(LoginRequiredMixin, ListView):
    model = InpatientAdmission
    template_name = "patientmgmt/admissionlist.html"
    context_object_name = "admissions"
    paginate_by = 20

    def get_queryset(self):
        qs = InpatientAdmission.objects.select_related('patient').order_by('-admission_date')
        status = self.request.GET.get('status', '').upper()
        if status in ('ACTIVE', 'DISCHARGED'):
            qs = qs.filter(current_status=status)
        return qs


class BillingListView(LoginRequiredMixin, ListView):
    model = BillingInvoice
    template_name = "patientmgmt/billinglist.html"
    context_object_name = "invoices"
    paginate_by = 20

    def get_queryset(self):
        qs = BillingInvoice.objects.select_related('patient').order_by('-invoice_date')
        q = self.request.GET.get('q', '').strip()
        status = self.request.GET.get('status', '').upper()
        if q:
            qs = qs.filter(models.Q(patient__patient_name__icontains=q) | models.Q(pk__icontains=q))
        if status == 'VOID':
            qs = qs.filter(is_void=True)
        elif status in ('PENDING', 'PAID', 'PARTIAL'):
            qs = qs.filter(payment_status=status, is_void=False)
        else:
            qs = qs.filter(is_void=False)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        ctx['status'] = self.request.GET.get('status', '')
        return ctx


# -----------------------------
# EXPORTS & LIVE COUNTS
# -----------------------------
class BillingExportCSVView(LoginRequiredMixin, View):
    def get(self, request):
        invoices = BillingInvoice.objects.select_related('patient').order_by('-invoice_date')
        start = request.GET.get('start'); end = request.GET.get('end')
        if start:
            invoices = invoices.filter(invoice_date__gte=start)
        if end:
            invoices = invoices.filter(invoice_date__lte=end)

        response = HttpResponse(content_type='text/csv')
        filename = f"billing_{datetime.date.today().isoformat()}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        writer = csv.writer(response)
        writer.writerow(['Invoice ID', 'Patient', 'Invoice Date', 'Total Amount', 'Payment Status', 'Is Void'])
        for inv in invoices:
            writer.writerow([inv.pk, smart_str(inv.patient.patient_name), inv.invoice_date.isoformat(), str(inv.total_amount), inv.payment_status, inv.is_void])
        return response


class BillingExportXLSXView(LoginRequiredMixin, View):
    def get(self, request):
        if openpyxl is None:
            return HttpResponse("openpyxl not installed", status=500)

        invoices = BillingInvoice.objects.select_related('patient').order_by('-invoice_date')
        start = request.GET.get('start'); end = request.GET.get('end')
        if start: invoices = invoices.filter(invoice_date__gte=start)
        if end: invoices = invoices.filter(invoice_date__lte=end)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Billing"
        ws.append(['Invoice ID', 'Patient', 'Invoice Date', 'Total Amount', 'Payment Status', 'Is Void'])
        for inv in invoices:
            ws.append([inv.pk, inv.patient.patient_name, inv.invoice_date.isoformat(), float(inv.total_amount), inv.payment_status, str(inv.is_void)])

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        response = HttpResponse(output.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        filename = f"billing_{datetime.date.today().isoformat()}.xlsx"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class BillingExportPDFView(LoginRequiredMixin, View):
    def get(self, request):
        if canvas is None:
            return HttpResponse("reportlab not installed", status=500)

        invoices = BillingInvoice.objects.select_related('patient').order_by('-invoice_date')[:500]
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        x_margin = 40
        y = height - 40
        p.setFont("Helvetica-Bold", 14)
        p.drawString(x_margin, y, "Billing Report")
        p.setFont("Helvetica", 10)
        y -= 25
        p.drawString(x_margin, y, f"Generated: {datetime.datetime.now().isoformat()}")
        y -= 20

        p.setFont("Helvetica-Bold", 9)
        p.drawString(x_margin, y, "ID")
        p.drawString(x_margin+40, y, "Patient")
        p.drawString(x_margin+240, y, "Date")
        p.drawString(x_margin+320, y, "Amount")
        p.drawString(x_margin+400, y, "Status")
        y -= 12
        p.setFont("Helvetica", 9)

        for inv in invoices:
            if y < 60:
                p.showPage()
                y = height - 40
            p.drawString(x_margin, y, str(inv.pk))
            p.drawString(x_margin+40, y, inv.patient.patient_name[:28])
            p.drawString(x_margin+240, y, inv.invoice_date.isoformat())
            p.drawString(x_margin+320, y, f"{inv.total_amount}")
            p.drawString(x_margin+400, y, inv.payment_status if not inv.is_void else "VOID")
            y -= 14

        p.showPage()
        p.save()
        buffer.seek(0)
        return HttpResponse(buffer, content_type='application/pdf', headers={
            'Content-Disposition': f'attachment; filename="billing_{datetime.date.today().isoformat()}.pdf"'
        })


class LiveCountsView(LoginRequiredMixin, View):
    def get(self, request):
        total_patients = Patient.objects.filter(is_active=True).count()
        inpatients = Patient.objects.filter(is_active=True, patient_type="IP").count()
        outpatients = Patient.objects.filter(is_active=True, patient_type="OP").count()
        pending_invoices = BillingInvoice.objects.filter(is_void=False, payment_status="PENDING").count()
        total_invoices_amount = BillingInvoice.objects.filter(is_void=False).aggregate(total=models.Sum('total_amount'))['total'] or 0
        data = {
            "total_patients": total_patients,
            "inpatients": inpatients,
            "outpatients": outpatients,
            "pending_invoices": pending_invoices,
            "total_invoices_amount": float(total_invoices_amount),
        }
        return JsonResponse(data)

# APPOINMENT LIST + FILTER
def appointment_list(request):

    status = request.GET.get('status', '')
    date = request.GET.get('date', '')
    search = request.GET.get('search', '')

    appointments = Appointment.objects.select_related(
        'patient', 'therapy'
    ).order_by('-id')

    if status:
        appointments = appointments.filter(status=status)

    if date:
        appointments = appointments.filter(appointment_date=date)

    if search:
        appointments = appointments.filter(
            Q(patient__patient_name__icontains=search) |
            Q(patient__phone__icontains=search) |
            Q(patient__patient_unique_id__icontains=search) |
            Q(patient__address__icontains=search)
        )

    paginator = Paginator(appointments, 10)  # ✅ 10 per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, "patientmgmt/appointment_list.html", {
        "appointments": page_obj,
        "page_obj": page_obj,
        "status": status,
        "date": date,
        "search": search
    })



# APPOINMENT ADD
def appointment_add(request):
    therapies = TherapyMaster.objects.filter(status=True)
    appointment_types = AppointmentType.objects.filter(status=True)

    if request.method == "POST":
        # Patient details
        name   = request.POST.get("name").strip()
        age    = int(request.POST.get("age") or 0)
        phone  = request.POST.get("phone").strip()
        place  = request.POST.get("place").strip()
        gender = request.POST.get("gender")

        # Appointment details
        appt_type_id = request.POST.get("appointment_type")
        therapy_id = request.POST.get("therapy")
        appt_type = AppointmentType.objects.filter(id=appt_type_id).first()
        date  = request.POST.get("appointment_date")
        time  = request.POST.get("appointment_time")
        notes = request.POST.get("notes")
        
        doctor_id = request.POST.get("doctor")
        therapist_id = request.POST.get("therapist")

        doctor = None
        therapist = None

        if doctor_id:
            doctor = CustomUser.objects.filter(id=doctor_id).first()

        if therapist_id:
            therapist = CustomUser.objects.filter(id=therapist_id).first()


        # ✅ Find existing patient by combination (Name+Age+Phone+Place)
        patient = Patient.objects.filter(
            patient_name=name,
            age=age,
            phone=phone,
            address=place,
            is_active=True
        ).first()

        # ✅ Create new patient if not found
        if not patient:
            created = False
            while not created:
                try:
                    patient = Patient.objects.create(
                        patient_unique_id=generate_patient_id(),
                        patient_name=name,
                        age=age,
                        phone=phone,
                        address=place,
                        gender=gender,
                        patient_type='OP',
                        visit_date=timezone.now().date()
                    )
                    created = True
                except IntegrityError:
                    # Rare case: generated ID already exists, retry
                    continue

        # ✅ Therapy selection
        therapy = None
        if appt_type and appt_type.name in ['Therapy', 'Both'] and therapy_id:
            therapy = TherapyMaster.objects.get(id=therapy_id)

        # ✅ Create Appointment
        appoinment = Appointment.objects.create(
            patient=patient,
            appointment_type=appt_type,
            therapy=therapy,
            doctor=doctor,
            therapist=therapist,
            appointment_date=date,
            appointment_time=time,
            notes=notes,
            status="PENDING"
        )
        ActivityHistory.objects.create(
            user=request.user,
            action="CREATE",
             module="PATIENT APPOINMENT",
            record_id=appoinment.id,
            description=f"Appoinment #{appoinment.id} created by {request.user}"
        )

        return redirect("patientmgmt:appointment_list")

    return render(request, "patientmgmt/appointment_add.html", {
        "therapies": therapies,
        "appointment_types":appointment_types
    })


# APPOINMENT EDIT
def appointment_edit(request, pk):
    appt = get_object_or_404(Appointment, id=pk)
    therapies = TherapyMaster.objects.filter(status=True)
    appointment_types = AppointmentType.objects.filter(status=True)

    if request.method == "POST":
        # Get POST data
        appointment_type_id = request.POST.get("appointment_type")
        appointment_date = request.POST.get("appointment_date")
        appointment_time = request.POST.get("appointment_time")
        status = request.POST.get("status")
        notes = request.POST.get("notes")
        therapy_id = request.POST.get("therapy")

        # ✅ Fetch AppointmentType instance
        appointment_type = get_object_or_404(
            AppointmentType, id=appointment_type_id
        )
        appt.appointment_type = appointment_type

        # ✅ Convert and assign date & time
        appt.appointment_date = parse_date(appointment_date)
        appt.appointment_time = parse_time(appointment_time)

        appt.status = status
        appt.notes = notes

        # ✅ Assign Therapy based on Appointment Type
        if appointment_type.name.upper() in ["THERAPY", "BOTH"] and therapy_id:
            appt.therapy = get_object_or_404(TherapyMaster, id=therapy_id)
        else:
            appt.therapy = None

        # Save the appointment
        appt.save()

        # Log activity
        ActivityHistory.objects.create(
            user=request.user,
            action="UPDATE",
            module="PATIENT APPOINTMENT",
            record_id=appt.id,
            description=f"Appointment #{appt.id} updated by {request.user}"
        )

        return redirect("patientmgmt:appointment_list")

    return render(request, "patientmgmt/appointment_edit.html", {
        "appt": appt,
        "therapies": therapies,
        "appointment_types": appointment_types
    })
# APPOINMENT DELETE
def appointment_delete(request, pk):
    appt = get_object_or_404(Appointment, id=pk)
    appt.delete()
    ActivityHistory.objects.create(
        user=request.user,
        action="DELETE",
            module="PATIENT APPOINMENT",
        record_id=appt.id,
        description=f"Appoinment #{appt.id} deleted by {request.user}"
    )
    return redirect("patientmgmt:appointment_list")


# APPOINMENT LIVE SEARCH AJAX
def appointment_live_search(request):
    query = request.GET.get("q","")

    appointments = Appointment.objects.select_related('patient', 'therapy').filter(
        Q(patient__patient_name__icontains=query) |
        Q(patient__phone__icontains=query) |
        Q(patient__address__icontains=query)
    )[:20]

    data = []

    for a in appointments:
        data.append({
            "id": a.id,
            "name": a.patient.patient_name,
            "phone": a.patient.phone or "-",
            "appointment_type": a.appointment_type or "-",
            "therapy": a.therapy.name if a.therapy else "-",
            "date": a.appointment_date.strftime("%Y-%m-%d") if a.appointment_date else "-",
            "time": a.appointment_time.strftime("%H:%M") if a.appointment_time else "-",
            "status": a.status or "-",
        })

    return JsonResponse({"results": data})


#alert whatsapp
def send_tomorrow_whatsapp(request):
    if request.method == "POST":

        message_text = request.POST.get("message")
        tomorrow = date.today() + timedelta(days=1)

        patients = Patient.objects.filter(visit_date=tomorrow)

        if not patients.exists():
            messages.error(request, "No patients scheduled for tomorrow.")
            return redirect("patientmgmt:patient_list")

        for patient in patients:
            phone = format_phone(patient.phone)
            if not phone:
                continue

            template_name = "jaspers_market_plain_text_v1"
            template_params = [{"type": "text", "text": message_text}]

            send_whatsapp_template(phone, template_name, template_params)

        messages.success(request, "WhatsApp reminders sent to all tomorrow's patients!")
        return redirect("patientmgmt:patient_list")

    return redirect("patientmgmt:patient_list")

def get_patient_suggestions(request):
    q = request.GET.get("q", "")
    patients = Patient.objects.filter(patient_name__icontains=q)[:10]
    data = []
    for p in patients:
        data.append({
            "id": p.id,
            "patient_name": p.patient_name,
            "age": p.age,
            "gender": p.gender,
            "phone": p.phone,
            "email": p.email,
            "address": p.address,
            "patient_type": p.patient_type,
        })
    return JsonResponse(data, safe=False)


def booked_slots(request):
    date = request.GET.get("date")
    doctor_id = request.GET.get("doctor")
    therapist_id = request.GET.get("therapist")
    exclude_id = request.GET.get("exclude_id")

    if not date:
        return JsonResponse({"booked": []})

    appointments = Appointment.objects.filter(
        appointment_date=date,
        status__in=["PENDING", "CONFIRMED"]
    )

    if doctor_id:
        appointments = appointments.filter(doctor_id=doctor_id)

    if therapist_id:
        appointments = appointments.filter(therapist_id=therapist_id)

    if exclude_id:
        appointments = appointments.exclude(id=exclude_id)

    booked_times = appointments.values_list("appointment_time", flat=True)

    return JsonResponse({
        "booked": [t.strftime("%H:%M") for t in booked_times]
    })

def get_doctors_by_role(request):
    role_name = request.GET.get("role", "").lower()

    if role_name == "doctor":
        users = CustomUser.objects.filter(
            Q(role__role_name__icontains="doctor") |
            Q(role__role_name__icontains="consultant") |
            Q(role__role_name__icontains="surgeon"),
            is_active=True
        )

    elif role_name == "therapist":
        users = CustomUser.objects.filter(
            role__role_name__icontains="therapist",
            is_active=True
        )

    else:
        users = CustomUser.objects.none()

    data = [
        {
            "id": user.id,
            "name": f"{user.get_full_name() or user.username} ({user.role.role_name})"
        }
        for user in users
    ]

    return JsonResponse({"doctors": data})

def check_availability(request):

    date = request.GET.get("date")
    time = request.GET.get("time")
    doctor_id = request.GET.get("doctor")
    therapist_id = request.GET.get("therapist")

    if not date or not time:
        return JsonResponse({
            "available": False,
            "message": "Invalid date or time"
        })

    # Only consider active appointments
    appointments = Appointment.objects.filter(
        appointment_date=date,
        appointment_time=time,
        status__in=["PENDING", "CONFIRMED"]  # ignore cancelled
    )

    # ✅ Doctor check
    if doctor_id:
        if appointments.filter(doctor_id=doctor_id).exists():
            return JsonResponse({
                "available": False,
                "message": "Doctor already booked at this time."
            })

    # ✅ Therapist check
    if therapist_id:
        if appointments.filter(therapist_id=therapist_id).exists():
            return JsonResponse({
                "available": False,
                "message": "Therapist already booked at this time."
            })

    return JsonResponse({"available": True})

def whatsapp_broadcast_view(request):
    patients = Patient.objects.filter(is_active=True)

    if request.method == "POST":
        message = request.POST.get("message")
        send_all = request.POST.get("send_all")
        selected_ids = request.POST.getlist("patients")
        manual_numbers = request.POST.get("manual_numbers", "")

        image = request.FILES.get("image")
        document = request.FILES.get("document")

        phone_numbers = []

        if send_all:
            phone_numbers = list(patients.values_list("phone", flat=True))
        elif selected_ids:
            phone_numbers = list(
                Patient.objects.filter(id__in=selected_ids)
                .values_list("phone", flat=True)
            )
        elif manual_numbers:
            phone_numbers = [n.strip() for n in manual_numbers.split(",")]
        else:
            messages.error(request, "Select at least one recipient")
            return redirect("patientmgmt:whatsapp_send")

        sent = 0

        for phone in phone_numbers:
            phone_fmt = format_phone(phone)
            if not phone_fmt:
                continue

            log = WhatsAppLog.objects.create(
                phone=phone_fmt,
                message=message,
                image=image,
                document=document,
                status="pending"
            )

            try:
                res = send_whatsapp_text(phone_fmt, message)

                if res.get("error"):
                    raise Exception(res["error"]["message"])

                if image:
                    image_url = request.build_absolute_uri(image.file.url)
                    send_whatsapp_image(phone_fmt, image_url)

                if document:
                    doc_url = request.build_absolute_uri(document.file.url)
                    send_whatsapp_document(phone_fmt, doc_url, document.name)

                log.status = "sent"
                sent += 1

            except Exception as e:
                log.status = "failed"
                log.error_message = str(e)

            log.save()

        messages.success(request, f"WhatsApp sent to {sent} users")
        return redirect("patientmgmt:whatsapp_send")

    return render(request, "patientmgmt/whatsapp_send.html", {
        "patients": patients
    })
    
def whatsapp_logs_view(request):
    logs = WhatsAppLog.objects.order_by("-created_at")
    return render(request, "patientmgmt/whatsapp_logs.html", {
        "logs": logs
    })
    
def patient_export_pdf(request):

    hospital = HospitalSetting.objects.first()

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="patient_list.pdf"'

    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=60,
        bottomMargin=40
    )

    elements = []
    styles = getSampleStyleSheet()

    page_width, page_height = A4
    usable_width = page_width - doc.leftMargin - doc.rightMargin

    # ================= TITLE =================

    title_style = ParagraphStyle(
        name="TitleCenter",
        parent=styles["Heading1"],
        alignment=1,
        fontSize=20,
        spaceAfter=6,
    )

    date_style = ParagraphStyle(
        name="DateSmallCenter",
        parent=styles["Normal"],
        alignment=1,
        fontSize=9,
        textColor=colors.grey,
    )

    generated_date = now().strftime("%d %B %Y %I:%M %p")

    elements.append(Paragraph("Patient Management Report", title_style))
    elements.append(Paragraph(f"Generated on: {generated_date}", date_style))
    elements.append(Spacer(1, 0.5 * inch))

    # ================= TABLE DATA =================

    patients = Patient.objects.filter(is_active=True).order_by("-created_at")

    data = [[
        "#",
        "Patient",
        "Gender",
        "Type",
        "Phone",
        "Referred By",
        "Registered"
    ]]

    for i, p in enumerate(patients, start=1):

        referred = "-"
        if p.refered_by:
            referred = f"{p.refered_by.patient_name}"

        data.append([
            str(i),
            f"{p.patient_name}\n{p.patient_unique_id}",
            p.get_gender_display(),
            p.get_patient_type_display(),
            p.phone,
            referred,
            p.created_at.strftime("%d %b %Y")
        ])

    col_widths = [
        usable_width * 0.06,
        usable_width * 0.22,
        usable_width * 0.10,
        usable_width * 0.10,
        usable_width * 0.15,
        usable_width * 0.17,
        usable_width * 0.20,
    ]

    table = Table(data, colWidths=col_widths, repeatRows=1)

    table_style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1f2937")),
        ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,0), 10),
    ])

    # Zebra rows
    for row in range(1, len(data)):
        if row % 2 == 0:
            table_style.add('BACKGROUND', (0,row), (-1,row), colors.whitesmoke)

    table.setStyle(table_style)
    elements.append(table)

    # ================= FOOTER + WATERMARK =================

    def add_footer_and_watermark(canvas, doc):

        # Page number
        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(
            page_width - 40,
            20,
            f"Page {doc.page}"
        )

        # Logo watermark
        if hospital and hospital.hospital_logo:

            logo_path = hospital.hospital_logo.path
            watermark = ImageReader(logo_path)

            canvas.saveState()
            canvas.setFillAlpha(0.07)

            wm_width = page_width * 0.5
            wm_height = wm_width

            canvas.drawImage(
                watermark,
                (page_width - wm_width) / 2,
                (page_height - wm_height) / 2,
                width=wm_width,
                height=wm_height,
                preserveAspectRatio=True,
                mask='auto'
            )

            canvas.restoreState()

    doc.build(
        elements,
        onFirstPage=add_footer_and_watermark,
        onLaterPages=add_footer_and_watermark
    )

    return response