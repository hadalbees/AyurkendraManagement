from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse, HttpResponseBadRequest,Http404
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
import datetime
import re
from billingmgmt.models import MedicalBill, MedicineItem
from fieldmgmt.models import TherapyMaster
from prescriptionmgmt.models import Prescription, PrescriptionItem
from stockmgmt.models import Medicine, Stock
from .models import InpatientBill, InpatientItem, TherapyBill, TherapyBillItem
from medicalstockmgmt.models import MedicalStock
from patientmgmt.models import Patient
from .models import InpatientBill, InpatientItem
from patientmgmt.models import Patient
from .models import OutpatientBill, OutpatientItem
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from django.template.loader import render_to_string
from django.http import JsonResponse
from django.db.models import Value, CharField
from datetime import date



UNIT_CONVERTER = {
    "KG": Decimal("1000"),   # 1 kg = 1000 g
    "G": Decimal("1"),
    "MG": Decimal("0.001"),
    "L": Decimal("1000"),    # 1 l = 1000 ml
    "ML": Decimal("1"),
    "UNIT": Decimal("1")      # for 'unit'
}
UNIT_TO_BASE = {
    "KG": Decimal("1000"),   # 1 kg = 1000 g
    "G":  Decimal("1"),      # gram is base
    "MG": Decimal("0.001"),  # 1 mg = 0.001 g

    "L":  Decimal("1000"),   # 1 L = 1000 ml
    "ML": Decimal("1"),      # ml is base

    "UNIT": Decimal("1"),    # pieces
}
def outpatient_billing_view(request):
    return render(request, "billingmgmt/outpatientbill.html")


# ----------------------------
# BILL NUMBER GENERATOR
# ----------------------------
def generate_medical_bill_number():
    last_bill = MedicalBill.objects.order_by('-id').first()
    if last_bill:
        number = int(last_bill.bill_no.replace("MED", ""))
        return f"MED{number + 1:03d}"
    return "MED001"


# ----------------------------
# GET PATIENT (AJAX)
# ----------------------------
# def get_patient(request):
#     patient_id = request.GET.get("patient_id")
#     patient_name = request.GET.get("patient_name")

#     try:
#         if patient_id:
#             patient = Patient.objects.get(patient_unique_id=patient_id)

#         elif patient_name:
#             patient = Patient.objects.get(patient_name__iexact=patient_name)

#         else:
#             return JsonResponse({"error": "No data"})

#     except Patient.DoesNotExist:
#         return JsonResponse({"error": "Patient not found"})

#     return JsonResponse({
#         "id": patient.patient_unique_id,
#         "patient_name": patient.patient_name,
#         "age": patient.age,
#         "gender": patient.gender
#     })

# def get_patient(request):
#     query = request.GET.get("patient_id") or request.GET.get("patient_name")

#     if not query:
#         return JsonResponse({"error": "No query provided"}, status=400)

#     try:
#         # Try ID format first (e.g., PID001)
#         patient = Patient.objects.filter(patient_unique_id__iexact=query).first()

#         # If not match, try name search
#         if not patient:
#             patient = Patient.objects.filter(patient_name__icontains=query).first()

#         if not patient:
#             raise Patient.DoesNotExist

#     except Patient.DoesNotExist:
#         return JsonResponse({"error": "Patient not found"}, status=404)

#     return JsonResponse({
#         "patient_unique_id": patient.patient_unique_id,
#         "patient_name": patient.patient_name,
#         "age": patient.age,
#         "gender": patient.gender,
#         "last_doctor": patient.consultant_doctor
#     })

def get_patient_prescription(request):
    patient_id = request.GET.get("patient_id")

    if not patient_id:
        return JsonResponse({"error": "Missing patient_id"})

    try:
        # Get latest prescription
        pres = Prescription.objects.filter(patient__patient_unique_id=patient_id).order_by('-created_at').first()
        if not pres:
            return JsonResponse({"error": "No prescription found"})

        items = PrescriptionItem.objects.filter(prescription=pres)

        data = {
            "prescription_no": pres.prescription_no,
            "created_at": pres.created_at,
            "items": []
        }

        for i in items:
            data["items"].append({
                "medicine_name": i.medicine_name,
                "quantity": float(i.quantity),
                "dosage": i.dosage,
                "duration": i.duration_days,
                "instructions": i.instructions or "",
                "food_timing": i.food_timing or "",
            })

        return JsonResponse(data)

    except Exception as e:
        return JsonResponse({"error": str(e)})
# ----------------------------
# MEDICAL BILLING
# ----------------------------
@transaction.atomic
def medical_billing_view(request):
    patients = Patient.objects.filter(is_active=True)
    bill_no = generate_medical_bill_number()
    medicines = Stock.objects.select_related("medicine").all()
    today = timezone.localdate()

    if request.method == "POST":
        try:
            # -------- BILL DATA --------
            doctor_name = request.POST.get("doctor_name", "").strip()
            bill_date = request.POST.get("bill_date") or today
            subtotal = Decimal(request.POST.get("subtotal", "0") or "0")
            tax = Decimal(request.POST.get("tax", "0") or "0")
            total = Decimal(request.POST.get("total", "0") or "0")
            payment_mode = request.POST.get("payment_mode") or "Cash"
            payment_status = request.POST.get("payment_status") or "Pending"
            remarks = request.POST.get("remarks", "")

            # 🔹 NEW: customer type
            customer_type = request.POST.get("customer_type", "patient")
            patient = None

            if customer_type == "patient":
                patient_id = request.POST.get("patient_id")
                if not patient_id:
                    return redirect("billingmgmt:medicalbilling")

                patient = get_object_or_404(
                    Patient,
                    patient_unique_id=patient_id,
                    is_active=True
                )
            # 🔹 else: walk-in customer → patient stays None

            # -------- MEDICINE DATA ARRAYS (from form) --------
            stock_ids = request.POST.getlist("stock_id[]")
            units = request.POST.getlist("unit[]")
            qtys = request.POST.getlist("quantity[]")
            subs_vals = request.POST.getlist("subtotal[]")

            if not stock_ids:
                return redirect("billingmgmt:medicalbilling")

            # Helper: check if MedicineItem has 'unit' field
            mi_field_names = [f.name for f in MedicineItem._meta.fields]

            with transaction.atomic():

                # CREATE BILL
                bill = MedicalBill.objects.create(
                    bill_no=bill_no,
                    patient=patient,  # ✅ patient OR None (walk-in)
                    doctor_name=doctor_name,
                    bill_date=bill_date,
                    subtotal=subtotal,
                    tax=tax,
                    total=total,
                    payment_mode=payment_mode,
                    payment_status=payment_status,
                    remarks=remarks,
                )

                # iterate by index to ensure we use the matching unit for each row
                for idx in range(len(stock_ids)):
                    sid = stock_ids[idx] if idx < len(stock_ids) else None
                    user_unit = units[idx] if idx < len(units) else None
                    qty_str = qtys[idx] if idx < len(qtys) else None
                    sub_str = subs_vals[idx] if idx < len(subs_vals) else "0"

                    if not sid or not qty_str:
                        continue

                    try:
                        stock = Stock.objects.select_for_update().get(id=sid)
                    except Stock.DoesNotExist:
                        continue

                    try:
                        qty_decimal = Decimal(qty_str)
                    except (InvalidOperation, TypeError):
                        continue

                    try:
                        subtotal_decimal = Decimal(sub_str or "0")
                    except (InvalidOperation, TypeError):
                        subtotal_decimal = Decimal("0")

                    if qty_decimal <= 0:
                        continue

                    # --- Determine conversions to base units ---
                    user_unit_norm = (user_unit or "").strip().upper()
                    stock_unit_norm = (stock.unit or "").strip().upper()

                    user_base_mul = UNIT_TO_BASE.get(user_unit_norm, UNIT_TO_BASE["UNIT"])
                    stock_base_mul = UNIT_TO_BASE.get(stock_unit_norm, UNIT_TO_BASE["UNIT"])

                    qty_base = qty_decimal * user_base_mul
                    stock_base_qty = stock.quantity * stock_base_mul

                    if qty_base <= stock_base_qty:
                        amount_to_deduct_stock_units = (qty_base / stock_base_mul).quantize(Decimal("0.0001"))
                    else:
                        amount_to_deduct_stock_units = (stock_base_qty / stock_base_mul).quantize(Decimal("0.0001"))

                    if amount_to_deduct_stock_units < 0:
                        amount_to_deduct_stock_units = Decimal("0")

                    mi_kwargs = {
                        "bill": bill,
                        "medicine_name": stock.medicine.name,
                        "unit_price": stock.selling_price,
                        "quantity": int(qty_decimal),
                        "subtotal": subtotal_decimal,
                    }

                    if "unit" in mi_field_names:
                        mi_kwargs["unit"] = user_unit_norm or stock_unit_norm or "UNIT"

                    MedicineItem.objects.create(**mi_kwargs)

                    new_stock_qty = (stock.quantity - amount_to_deduct_stock_units).quantize(Decimal("0.0001"))
                    if new_stock_qty < 0:
                        new_stock_qty = Decimal("0")

                    stock.quantity = new_stock_qty
                    stock.save()

            return redirect("billingmgmt:print_bill", bill_no=bill.bill_no)

        except Exception:
            return redirect("billingmgmt:medicalbilling")

    # GET request
    return render(request, "billingmgmt/medicalbill.html", {
        "patients": patients,
        "bill_no": bill_no,
        "today": today,
        "medicines": medicines,
    })

def print_bill(request, bill_no):
    bill = get_object_or_404(MedicalBill, bill_no=bill_no)
    items = bill.items.all()
    return render(request, "billingmgmt/printbill.html", {
        "bill": bill,
        "items": items,
    })
def generate_ip_bill_number():
    """Generate a unique InpatientBill number safely."""
    last = InpatientBill.objects.order_by('-id').first()
    prefix = "IP"

    if not last or not last.bill_no:
        return f"{prefix}001"

    # Extract trailing digits
    match = re.search(r'(\d+)$', last.bill_no)
    if match:
        num = int(match.group(1)) + 1
    else:
        num = 1  # fallback if no number found

    return f"{prefix}{num:03d}"


def inpatient_billing_view(request):

    if request.method == "GET":
        bill_no = generate_ip_bill_number()
        patients = Patient.objects.filter(is_active=True)
        medicines = MedicalStock.objects.filter(quantity__gt=0).select_related('medicine')[:1000]
        therapies = TherapyMaster.objects.all()

        return render(request, "billingmgmt/inpatientbill.html", {
            "bill_no": bill_no,
            "patients": patients,
            "medicines": medicines,
            "therapies": therapies,
            "today": timezone.localdate(),
        })

    # ---------------- POST ----------------
    if request.method == "POST":

        bill_no = request.POST.get("bill_no")
        patient_id = request.POST.get("patient_id")
        doctor_name = request.POST.get("doctor_name") or ""
        admit_date = request.POST.get("admit_date") or None
        discharge_date = request.POST.get("discharge_date") or None

        discount = Decimal(request.POST.get("discount") or "0")
        tax = Decimal(request.POST.get("tax") or "0")
        total = Decimal(request.POST.get("total") or "0")
        payment_mode = request.POST.get("payment_mode") or "Cash"
        payment_status = request.POST.get("payment_status") or "Pending"
        remarks = request.POST.get("remarks") or ""

        # ---- validate patient ----
        try:
            patient = Patient.objects.get(patient_unique_id=patient_id)
        except Patient.DoesNotExist:
            return HttpResponseBadRequest("Invalid Patient ID")

        # ---- NEW REGISTRATION CHARGE ----
        registration_fee = Decimal("0.00")
        if patient.created_at.date() == timezone.localdate():
            registration_fee = Decimal("50.00")

        # ---- items ----
        item_names = request.POST.getlist("item_name[]")
        item_rates = request.POST.getlist("item_rate[]")
        item_qtys = request.POST.getlist("item_qty[]")
        item_types = request.POST.getlist("item_type[]")
        item_stock_ids = request.POST.getlist("item_stock_id[]")

        calculated_subtotal = Decimal("0.00")

        with transaction.atomic():

            bill = InpatientBill.objects.create(
                bill_no=bill_no,
                patient=patient,
                doctor_name=doctor_name,
                admit_date=admit_date,
                discharge_date=discharge_date,
                subtotal=Decimal("0.00"),  # temp
                discount=discount,
                tax=tax,
                total=total,
                payment_mode=payment_mode,
                payment_status=payment_status,
                remarks=remarks,
                created_by=request.user
            )

            for name, rate, qty, itype, stock_id in zip(
                item_names, item_rates, item_qtys, item_types, item_stock_ids
            ):
                if not name:
                    continue

                rate_d = Decimal(rate or "0")
                qty_d = Decimal(qty or "0")
                sub = (rate_d * qty_d).quantize(Decimal("0.01"))
                calculated_subtotal += sub

                stock_obj = None
                if itype == "medicine" and stock_id:
                    stock_obj = MedicalStock.objects.select_for_update().get(id=stock_id)
                    if Decimal(stock_obj.quantity) < qty_d:
                        raise ValueError("Not enough stock")
                    stock_obj.quantity -= qty_d
                    stock_obj.save()

                InpatientItem.objects.create(
                    bill=bill,
                    item_type=itype,
                    item_name=name,
                    unit_price=rate_d,
                    quantity=qty_d,
                    subtotal=sub,
                    medical_stock=stock_obj
                )

            # ---- FINAL SUBTOTAL WITH REGISTRATION CHARGE ----
            final_subtotal = calculated_subtotal + registration_fee
            bill.subtotal = final_subtotal
            bill.save()

        return redirect("billingmgmt:print_inpatient_bill", bill_no=bill.bill_no)


# AJAX patient lookup (by id or name)
def get_patient(request):
    patient_id = request.GET.get("patient_id")
    patient_name = request.GET.get("patient_name")

    try:
        if patient_id:
            p = Patient.objects.get(patient_unique_id=patient_id)

        elif patient_name:
            p = Patient.objects.get(patient_name=patient_name)

        else:
            return JsonResponse({"error": "no parameter provided"}, status=400)

    except Patient.DoesNotExist:
        return JsonResponse({"error": "patient not found"}, status=404)

    # 🔥 THIS IS THE IMPORTANT PART
    is_new_patient = (p.created_at.date() == timezone.localdate())

    return JsonResponse({
        "patient_unique_id": p.patient_unique_id,
        "patient_name": p.patient_name,
        "age": p.age,
        "gender": p.gender,

        # ✅ REQUIRED FOR REGISTRATION FEE LOGIC
        "is_new": is_new_patient
    })


# AJAX stock lookup by id (optional helper used by JS)
def get_stock(request):
    stock_id = request.GET.get("stock_id")
    try:
        stock = MedicalStock.objects.select_related('medicine').get(id=stock_id)
    except MedicalStock.DoesNotExist:
        return JsonResponse({"error":"stock not found"})
    return JsonResponse({
        "id": stock.id,
        "medicine_name": stock.medicine.name,
        "batch_number": stock.batch_number,
        "selling_price": str(stock.selling_price),
        "quantity": str(stock.quantity),
        "manufacture_date": stock.manufacture_date.isoformat() if stock.manufacture_date else "",
        "expiry_date": stock.expiry_date.isoformat() if stock.expiry_date else "",
    })


def print_inpatient_bill(request, bill_no):
    bill = get_object_or_404(InpatientBill, bill_no=bill_no)
    items = bill.items.all()

    room_items = items.filter(item_type='room')
    other_items = items.exclude(item_type='room')

    # ✅ CHECK NEW REGISTRATION
    is_new_patient = bill.patient.created_at.date() == bill.created_at.date()
    registration_fee = Decimal("50.00") if is_new_patient else Decimal("0.00")

    # ✅ UPDATED TOTALS FOR PRINT
    printable_subtotal = bill.subtotal + registration_fee
    printable_tax = (printable_subtotal * Decimal("0.05")).quantize(Decimal("0.01"))
    printable_total = printable_subtotal + printable_tax - bill.discount

    return render(request, "billingmgmt/print_inpatientbill.html", {
        "bill": bill,
        "room_items": room_items,
        "other_items": other_items,

        # 👇 NEW CONTEXT
        "is_new_patient": is_new_patient,
        "registration_fee": registration_fee,

        # 👇 PRINT TOTALS
        "printable_subtotal": printable_subtotal,
        "printable_tax": printable_tax,
        "printable_total": printable_total,
    })
    
def generate_op_bill_no():
    last = OutpatientBill.objects.order_by("-id").first()
    if last:
        num = int(last.bill_no.replace("OP", ""))
        return f"OP{num+1:03d}"
    return "OP001"
def outpatient_billing_view(request):
    therapies = TherapyMaster.objects.all()

    # ---------- GET ----------
    if request.method == "GET":
        return render(request, "billingmgmt/outpatientbill.html", {
            "bill_no": generate_op_bill_no(),
            "today": timezone.localdate(),
            "therapies": therapies
        })

    # ---------- POST ----------
    bill_no = request.POST.get("bill_no")
    patient_id = request.POST.get("patient_id")
    doctor_name = request.POST.get("doctor_name") or ""
    visit_date = request.POST.get("visit_date") or timezone.localdate()
    payment_mode = request.POST.get("payment_mode") or "Cash"
    payment_status = request.POST.get("payment_status") or "Pending"
    subtotal = Decimal(request.POST.get("subtotal") or "0")
    discount = Decimal(request.POST.get("discount") or "0")
    tax = Decimal(request.POST.get("tax") or "0")
    total = Decimal(request.POST.get("total") or "0")

    try:
        patient = Patient.objects.get(id=patient_id)
    except (Patient.DoesNotExist, ValueError, TypeError):
        return HttpResponseBadRequest("Invalid Patient")

    # ✅ CHECK NEW PATIENT
    is_new_patient = patient.created_at.date() == timezone.localdate()
    registration_fee = Decimal("50.00") if is_new_patient else Decimal("0.00")

    # ✅ ADD REGISTRATION FEE TO SUBTOTAL
    subtotal = subtotal + registration_fee

    # ✅ RECALCULATE TAX & TOTAL
    tax = (subtotal * Decimal("0.05")).quantize(Decimal("0.01"))
    total = subtotal + tax - discount

    item_names = request.POST.getlist("item_name[]")
    item_rates = request.POST.getlist("item_rate[]")
    item_qtys = request.POST.getlist("item_qty[]")

    with transaction.atomic():

        bill = OutpatientBill.objects.create(
            bill_no=bill_no,
            patient=patient,
            doctor_name=doctor_name,
            visit_date=visit_date,
            subtotal=subtotal,
            discount=discount,
            tax=tax,
            payment_mode=payment_mode,
            payment_status=payment_status,
            total=total,
            created_by=request.user,
        )

        # ✅ SAVE NORMAL ITEMS
        for name, rate, qty in zip(item_names, item_rates, item_qtys):
            if not name:
                continue

            rate_d = Decimal(rate or "0")
            qty_d = Decimal(qty or "0")
            sub = rate_d * qty_d

            OutpatientItem.objects.create(
                bill=bill,
                item_name=name,
                unit_price=rate_d,
                quantity=qty_d,
                subtotal=sub
            )

        # ✅ SAVE REGISTRATION FEE AS ITEM (ONLY IF NEW)
        if registration_fee > 0:
            OutpatientItem.objects.create(
                bill=bill,
                item_name="New Registration Fee",
                unit_price=registration_fee,
                quantity=1,
                subtotal=registration_fee
            )

    return redirect("billingmgmt:print_outpatient_bill", bill_no=bill.bill_no)

def print_outpatient_bill(request, bill_no):
    bill = get_object_or_404(OutpatientBill, bill_no=bill_no)
    items = bill.items.all()
    return render(request, "billingmgmt/print_outpatientbill.html", {
        "bill": bill,
        "items": items
    })
def generate_therapy_bill_number():
    last = TherapyBill.objects.order_by("-id").first()
    if last and last.bill_no.startswith("TB"):
        try:
            n = int(last.bill_no.replace("TB", ""))
        except:
            n = 0
        return f"TB{n+1:03d}"
    return "TB001"

# Therapy billing page
def therapy_billing_view(request):
    patient_id = request.POST.get("patient_id") or request.GET.get("patient_id")

    if request.method == "POST":

        bill_no = request.POST.get("bill_no") or generate_therapy_bill_number()
        bill_date = request.POST.get("bill_date") or timezone.localdate()
        payment_mode = request.POST.get("payment_mode") or "Cash"

        subtotal = Decimal(request.POST.get("subtotal") or 0)
        discount = Decimal(request.POST.get("discount") or 0)
        tax = Decimal(request.POST.get("tax") or 0)
        total = Decimal(request.POST.get("total") or 0)

        payment_status = request.POST.get("payment_status") or "Pending"
        remarks = request.POST.get("remarks", "")

        therapy_ids = request.POST.getlist("therapy_id[]")
        quantities = request.POST.getlist("quantity[]")
        unit_prices = request.POST.getlist("unit_price[]")
        subtotals = request.POST.getlist("subtotal[]")

        with transaction.atomic():
            patient = Patient.objects.get(id=patient_id)

            bill = TherapyBill.objects.create(
                patient=patient,
                bill_no=bill_no,
                bill_date=bill_date,
                subtotal=subtotal,
                discount=discount,
                tax=tax,
                total=total,
                payment_mode=payment_mode,
                payment_status=payment_status,
                remarks=remarks
            )

            for t_id, qty, price, sub in zip(therapy_ids, quantities, unit_prices, subtotals):
                therapy = TherapyMaster.objects.get(id=t_id)
                TherapyBillItem.objects.create(
                    bill=bill,
                    therapy=therapy,
                    unit_price=Decimal(price),
                    quantity=int(qty),
                    subtotal=Decimal(sub)
                )

        return redirect("billingmgmt:therapy_bill_print", bill_no=bill.bill_no)

    patients = Patient.objects.filter(is_active=True)
    therapies = TherapyMaster.objects.filter(status=True)
    bill_no = generate_therapy_bill_number()

    return render(request, "billingmgmt/therapybill.html", {
        "patients": patients,
        "therapies": therapies,
        "bill_no": bill_no,
        "today": timezone.localdate(),
    })

# Print bill
def therapy_bill_print_view(request, bill_no):
    bill = TherapyBill.objects.get(bill_no=bill_no)
    return render(request, "billingmgmt/print_therapybill.html", {"bill": bill})   
    
    
def get_patient_suggestions(request):
    query = request.GET.get('q', '').strip()

    if not query:
        return JsonResponse([], safe=False)

    # Search by patient name or phone
    patients = Patient.objects.filter(
        patient_name__icontains=query
    ).order_by('patient_name')[:10]  # limit results
    results = []
    for p in patients:
        is_new_patient = (p.created_at.date() == timezone.localdate())
        results.append({
            'id': p.id,
            'name': p.patient_name,
            'patient_unique_id': p.patient_unique_id,
            'phone': p.phone,
            'age': p.age,
            'gender': p.get_gender_display(),
            'is_new_patient':is_new_patient
        })

    return JsonResponse(results, safe=False)

def download_all_bills_pdf(request, patient_id):
    try:
        patient = Patient.objects.get(id=patient_id)
    except Patient.DoesNotExist:
        raise Http404("Patient not found")

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="{patient.patient_name}_all_bills.pdf"'
    )

    c = canvas.Canvas(response, pagesize=A4)
    width, height = A4
    y = height - 50

    # ---- HEADER ----
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, y, "Patient Billing Summary")
    y -= 30

    c.setFont("Helvetica", 11)
    c.drawString(50, y, f"Patient Name: {patient.patient_name}")
    y -= 15
    c.drawString(50, y, f"Patient ID: {patient.id}")
    y -= 25

    # helper
    def section(title):
        nonlocal y
        if y < 100:
            c.showPage()
            y = height - 50
        c.setFont("Helvetica-Bold", 13)
        c.drawString(50, y, title)
        y -= 20
        c.setFont("Helvetica", 10)

    def row(label, value):
        nonlocal y
        c.drawString(50, y, label)
        c.drawRightString(width - 50, y, f"₹ {value}")
        y -= 15

    # ---- MEDICAL ----
    medical = MedicalBill.objects.filter(patient=patient)
    if medical.exists():
        section("Medical Bills")
        for b in medical:
            row(f"{b.bill_no} ({b.bill_date})", b.total)
        y -= 10

    # ---- INPATIENT ----
    inpatient = InpatientBill.objects.filter(patient=patient)
    if inpatient.exists():
        section("Inpatient Bills")
        for b in inpatient:
            row(f"{b.bill_no} ({b.admit_date})", b.total)
        y -= 10

    # ---- OUTPATIENT ----
    outpatient = OutpatientBill.objects.filter(patient=patient)
    if outpatient.exists():
        section("Outpatient Bills")
        for b in outpatient:
            row(f"{b.bill_no} ({b.visit_date})", b.total)
        y -= 10

    # ---- THERAPY ----
    therapy = TherapyBill.objects.filter(patient=patient)
    if therapy.exists():
        section("Therapy Bills")
        for b in therapy:
            row(f"{b.bill_no} ({b.bill_date})", b.total)
        y -= 10

    # ---- GRAND TOTAL ----
    grand_total = (
        sum(b.total for b in medical) +
        sum(b.total for b in inpatient) +
        sum(b.total for b in outpatient) +
        sum(b.total for b in therapy)
    )

    y -= 20
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(width - 50, y, f"GRAND TOTAL: ₹ {grand_total}")

    c.showPage()
    c.save()
    return response

# =====================================================
# BILLING HISTORY HOME
# =====================================================
def billing_history_home(request):
    context = {
        "medical_count": MedicalBill.objects.count(),
        "therapy_count": TherapyBill.objects.count(),
        "inpatient_count": InpatientBill.objects.count(),
        "outpatient_count": OutpatientBill.objects.count(),
    }
    return render(request, "billingmgmt/billing_history.html", context)

# =====================================================
# MEDICAL BILLING LIST
# =====================================================
def medical_billing_list(request):
    bills = MedicalBill.objects.select_related("patient").order_by("-id")
    return render(request, "billingmgmt/billing_history_medical.html", {
        "bills": bills,
        "title": "Medical Billing History"
    })


def medical_bill_ajax(request):
    patient_id = request.GET.get("patient_id")
    status = request.GET.get("status")

    bills = MedicalBill.objects.select_related("patient")

    if patient_id:
        bills = bills.filter(patient__patient_unique_id=patient_id)

    if status:
        bills = bills.filter(payment_status=status)

    html = render_to_string(
        "billingmgmt/partials/bill_rows.html",
        {"bills": bills.order_by("-id")}
    )
    return HttpResponse(html)


def print_all_medical_bills(request):
    patient_id = request.GET.get("patient_id")
    status = request.GET.get("status")

    bills = MedicalBill.objects.select_related("patient").prefetch_related("items")

    if patient_id:
        bills = bills.filter(patient__patient_unique_id=patient_id)

    if status:
        bills = bills.filter(payment_status=status)

    combined_items = []
    subtotal = Decimal("0")
    discount = Decimal("0")
    tax = Decimal("0")
    total = Decimal("0")

    for bill in bills:
        subtotal += bill.subtotal
        discount += bill.discount
        tax += bill.tax
        total += bill.total

        for item in bill.items.all():   # ✅ FIXED
            combined_items.append(item)

    return render(request, "billingmgmt/print_all_medical.html", {
        "bills": bills,
        "items": combined_items,
        "subtotal": subtotal,
        "discount": discount,
        "tax": tax,
        "total": total,
    })
# =====================================================
# THERAPY BILLING LIST
# =====================================================
def therapy_billing_list(request):
    bills = TherapyBill.objects.select_related("patient").order_by("-id")
    return render(request, "billingmgmt/billing_history_therapy.html", {
        "bills": bills,
        "title": "Therapy Billing History"
    })


# =====================================================
# INPATIENT BILLING LIST
# =====================================================
def inpatient_billing_list(request):
    bills = InpatientBill.objects.select_related("patient").order_by("-id")
    return render(request, "billingmgmt/billing_history_inpatient.html", {
        "bills": bills,
        "title": "Inpatient Billing History"
    })


# =====================================================
# OUTPATIENT BILLING LIST
# =====================================================
def outpatient_billing_list(request):
    bills = OutpatientBill.objects.select_related("patient").order_by("-id")
    return render(request, "billingmgmt/billing_history_outpatient.html", {
        "bills": bills,
        "title": "Outpatient Billing History"
    })
    
def billing_filter_ajax(request, bill_type):
    patient_id = request.GET.get("patient_id")
    status = request.GET.get("status")

    MODEL_MAP = {
        "therapy": TherapyBill,
        "inpatient": InpatientBill,
        "outpatient": OutpatientBill,
    }

    model = MODEL_MAP[bill_type]

    bills = model.objects.select_related("patient")

    if patient_id:
        bills = bills.filter(patient__patient_unique_id=patient_id)

    if status:
        bills = bills.filter(payment_status=status)

    html = render_to_string(
        f"billingmgmt/partials/{bill_type}_rows.html",
        {"bills": bills.order_by("-id")},
        request=request
    )

    return HttpResponse(html)

def print_all_bills(request, bill_type):
    patient_id = request.GET.get("patient_id")
    status = request.GET.get("status")

    MODEL_MAP = {
        "therapy": TherapyBill,
        "inpatient": InpatientBill,
        "outpatient": OutpatientBill,
    }

    model = MODEL_MAP[bill_type]
    bills = model.objects.select_related("patient")

    if patient_id:
        bills = bills.filter(patient__patient_unique_id=patient_id)

    if status:
        bills = bills.filter(payment_status=status)

    bills = bills.order_by("created_at")

    total = sum([b.total for b in bills], Decimal("0"))

    return render(request, f"billingmgmt/print_all_{bill_type}.html", {
        "bills": bills,
        "total": total,
    })
    
# =====================================================
# VIEW PAGES (DETAIL)
# =====================================================
def medical_bill_view(request, pk):
    bill = get_object_or_404(MedicalBill, pk=pk)
    return render(request, "billingmgmt/view_medical_bill.html", {"bill": bill})

def therapy_bill_view(request, pk):
    bill = get_object_or_404(TherapyBill, pk=pk)
    return render(request, "billingmgmt/view_therapy_bill.html", {"bill": bill})

def inpatient_bill_view(request, pk):
    bill = get_object_or_404(InpatientBill, pk=pk)
    return render(request, "billingmgmt/view_inpatient_bill.html", {"bill": bill})

def outpatient_bill_view(request, pk):
    bill = get_object_or_404(OutpatientBill, pk=pk)
    return render(request, "billingmgmt/view_outpatient_bill.html", {"bill": bill})    


def combined_billing_view(request):
    patients = Patient.objects.filter(is_active=True)

    return render(request, "billingmgmt/combined_billing.html", {
        "patients": patients
    })
    
def combined_billing_filter_ajax(request):
    patient_id = request.GET.get("patient_id")
    status = request.GET.get("payment_status")
    mode = request.GET.get("payment_mode")
    bill_types = request.GET.getlist("bill_types[]")
    start = request.GET.get("start_date")
    end = request.GET.get("end_date")

    records = []

    def apply_filters(qs):
        if patient_id:
            qs = qs.filter(patient__patient_unique_id=patient_id)
        if status:
            qs = qs.filter(payment_status=status)
        if mode:
            qs = qs.filter(payment_mode=mode)
        return qs

    # ---------- MEDICAL ----------
    if "medical" in bill_types:
        qs = apply_filters(MedicalBill.objects.all())
        if start and end:
            qs = qs.filter(bill_date__range=[start, end])

        for b in qs:
            records.append({
                "bill_no": b.bill_no,
                "date": b.bill_date,   # date
                "total": b.total,
                "type_label": "Medical",
            })

    # ---------- THERAPY ----------
    if "therapy" in bill_types:
        qs = apply_filters(TherapyBill.objects.all())
        if start and end:
            qs = qs.filter(bill_date__range=[start, end])

        for b in qs:
            records.append({
                "bill_no": b.bill_no,
                "date": b.bill_date,   # date
                "total": b.total,
                "type_label": "Therapy",
            })

    # ---------- INPATIENT ----------
    if "inpatient" in bill_types:
        qs = apply_filters(InpatientBill.objects.all())
        if start and end:
            qs = qs.filter(created_at__date__range=[start, end])

        for b in qs:
            records.append({
                "bill_no": b.bill_no,
                "date": b.created_at.date(),  # 🔥 FORCE DATE
                "total": b.total,
                "type_label": "Inpatient",
            })

    # ---------- OUTPATIENT ----------
    if "outpatient" in bill_types:
        qs = apply_filters(OutpatientBill.objects.all())
        if start and end:
            qs = qs.filter(visit_date__range=[start, end])

        for b in qs:
            records.append({
                "bill_no": b.bill_no,
                "date": b.visit_date,  # date
                "total": b.total,
                "type_label": "Outpatient",
            })

    # ✅ SAFE SORT (all are date objects now)
    records.sort(key=lambda x: x["date"], reverse=True)

    html = render_to_string(
        "billingmgmt/partials/combined_rows.html",
        {"records": records},
        request=request
    )

    return JsonResponse({"html": html})



def combined_billing_print(request):
    patient_id = request.GET.get("patient_id")
    start = request.GET.get("start_date")
    end = request.GET.get("end_date")
    status = request.GET.get("payment_status")
    mode = request.GET.get("payment_mode")

    rows = []
    subtotal = discount = tax = total = Decimal("0.00")
    patient = None

    def apply_filters(qs, date_field):
        nonlocal patient
        if patient_id:
            qs = qs.filter(patient__patient_unique_id=patient_id)
            patient = qs.first().patient if qs.exists() else patient
        if status:
            qs = qs.filter(payment_status=status)
        if mode:
            qs = qs.filter(payment_mode=mode)
        if start and end:
            qs = qs.filter(**{f"{date_field}__range": [start, end]})
        return qs

    # ---------------- MEDICAL ----------------
    medical = apply_filters(MedicalBill.objects.all(), "bill_date")
    for b in medical:
        rows.append({
            "date": b.bill_date,
            "bill_no": b.bill_no,
            "type": "Medical",
            "amount": b.total
        })
        subtotal += b.subtotal
        discount += b.discount
        tax += b.tax
        total += b.total

    # ---------------- THERAPY ----------------
    therapy = apply_filters(TherapyBill.objects.all(), "bill_date")
    for b in therapy:
        rows.append({
            "date": b.bill_date,
            "bill_no": b.bill_no,
            "type": "Therapy",
            "amount": b.total
        })
        subtotal += b.subtotal
        discount += b.discount
        tax += b.tax
        total += b.total

    # ---------------- INPATIENT ----------------
    inpatient = apply_filters(InpatientBill.objects.all(), "created_at")
    for b in inpatient:
        rows.append({
            "date": b.created_at.date(),
            "bill_no": b.bill_no,
            "type": "Inpatient",
            "amount": b.total
        })
        subtotal += b.subtotal
        discount += b.discount
        tax += b.tax
        total += b.total

    # ---------------- OUTPATIENT ----------------
    outpatient = apply_filters(OutpatientBill.objects.all(), "visit_date")
    for b in outpatient:
        rows.append({
            "date": b.visit_date,
            "bill_no": b.bill_no,
            "type": "Outpatient",
            "amount": b.total
        })
        subtotal += b.subtotal
        discount += b.discount
        tax += b.tax
        total += b.total

    rows = sorted(rows, key=lambda x: x["date"])

    return render(request, "billingmgmt/combined_print.html", {
        "patient": patient,
        "rows": rows,
        "subtotal": subtotal,
        "discount": discount,
        "tax": tax,
        "total": total,
        "start": start,
        "end": end,
    })