from decimal import Decimal, InvalidOperation,ROUND_HALF_UP
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
from .models import HospitalSetting
from fieldmgmt.models import IPOtherCharge,ActivityHistory
from fieldmgmt.models import RoomType




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
    settings = HospitalSetting.objects.first()

    bill_no = generate_medical_bill_number()

    medicines = Stock.objects.select_related("medicine").filter(
        total_base_quantity__gt=0
    ).order_by("expiry_date")

    today = timezone.localdate()
    print("POST DATA:", request.POST)
    if request.method == "POST":

        try:

            doctor_name = request.POST.get("doctor_name", "").strip()
            bill_date = request.POST.get("bill_date") or today

            # ---------- BILL VALUES ----------

            subtotal = Decimal(
                request.POST.get("subtotal", "0") or "0"
            )

            discount_percent = Decimal(
                request.POST.get("discount_percent", "0") or "0"
            )

            # Discount Amount
            discount = (
                subtotal * discount_percent / Decimal("100")
            ).quantize(Decimal("0.01"))

            subtotal_after_discount = subtotal - discount

            # GST %
            gst_percent = Decimal(
                settings.consultation_gst or 0
            )

            tax = (
                subtotal_after_discount * gst_percent / Decimal("100")
            ).quantize(Decimal("0.01"))

            total = subtotal_after_discount + tax


            payment_mode = request.POST.get("payment_mode") or "Cash"
            payment_status = request.POST.get("payment_status") or "Pending"
            remarks = request.POST.get("remarks", "")

            # -------- CUSTOMER TYPE --------
            customer_type = request.POST.get("customer_type", "patient")

            patient = None
            customer_name = ""
            customer_age = None
            customer_gender = ""

            if customer_type == "patient":

                patient_id = request.POST.get("patient_id")

                patient = get_object_or_404(
                    Patient,
                    patient_unique_id=patient_id,
                    is_active=True
                )

            else:

                customer_name = request.POST.get("walkin_name", "").strip()

                customer_age = request.POST.get("customer_age")

                customer_gender = request.POST.get("customer_gender")

            # -------- MEDICINE DATA --------
            stock_ids = request.POST.getlist("stock_id[]")
            units = request.POST.getlist("unit[]")
            qtys = request.POST.getlist("quantity[]")
            subs = request.POST.getlist("subtotal[]")

            if not stock_ids:
                return redirect("billingmgmt:medicalbilling")

            with transaction.atomic():

                bill = MedicalBill.objects.create(

                    bill_no=bill_no,

                    patient=patient,
                    
                    customer_name=customer_name,

                    customer_age=customer_age,

                    customer_gender=customer_gender,

                    doctor_name=doctor_name,

                    bill_date=bill_date,

                    subtotal=subtotal,

                    discount_percent=discount_percent,

                    discount=discount,

                    tax=tax,

                    total=total,

                    payment_mode=payment_mode,

                    payment_status=payment_status,

                    remarks=remarks,

                )

                 # Activity History
                ActivityHistory.objects.create(
                    user=request.user,
                    action="CREATE",
                    module="MEDICAL BILL",
                    record_id=bill.id,
                    description=f"Medical Bill #{bill.id} created by {request.user}"
                )

                for i in range(len(stock_ids)):

                    sid = stock_ids[i]

                    qty = Decimal(qtys[i] or "0")

                    sub = Decimal(subs[i] or "0")

                    stock = Stock.objects.select_for_update().get(id=sid)

                    # Stock validation
                    if stock.total_base_quantity < qty:
                        raise Exception(
                            f"Insufficient stock for {stock.medicine.name}. "
                            f"Available: {stock.total_base_quantity}"
                        )

                    # Save bill item
                    MedicineItem.objects.create(
                        bill=bill,
                        medicine_name=stock.medicine.name,
                        unit_price=stock.price_per_base_unit,
                        quantity=qty,
                        subtotal=sub
                    )

                    required_qty = qty

                    stocks = (
                        Stock.objects
                        .select_for_update()
                        .filter(
                            medicine=stock.medicine,
                            total_base_quantity__gt=0
                        )
                        .order_by("expiry_date", "id")
                    )

                    for s in stocks:

                        if required_qty <= 0:
                            break

                        deduct = min(s.total_base_quantity, required_qty)

                        s.total_base_quantity -= deduct

                        s.save(update_fields=["total_base_quantity"])

                        required_qty -= deduct

                    if required_qty > 0:
                        raise Exception(
                            f"Insufficient stock for {stock.medicine.name}"
                        )
            
            return redirect("billingmgmt:print_bill", bill_no=bill.bill_no)

        # except Exception as e:
        #     print("Medical Billing Error:", e)
        #     return redirect("billingmgmt:medicalbilling")
        except Exception as e:
            print("MEDICAL BILL ERROR:", e)
            raise e

    return render(request, "billingmgmt/medicalbill.html", {
        "patients": patients,
        "bill_no": bill_no,
        "today": today,
        "medicines": medicines,
        "settings": settings,
    })
def print_bill(request, bill_no):
    bill = get_object_or_404(MedicalBill, bill_no=bill_no)
    items = bill.items.all()

    settings = HospitalSetting.objects.first()

    gst_percent = Decimal(settings.consultation_gst or 0) if settings else Decimal("0.00")
    total_gst = bill.tax or Decimal("0.00")

    # ✅ Split GST correctly
    half_gst_percent = (gst_percent / 2).quantize(Decimal("0.01"))
    cgst = (total_gst / 2).quantize(Decimal("0.01"))
    sgst = (total_gst / 2).quantize(Decimal("0.01"))

    return render(request, "billingmgmt/printbill.html", {
        "bill": bill,
        "items": items,
        "settings": settings,
        "gst_percent": gst_percent,
        "half_gst_percent": half_gst_percent,
        "cgst": cgst,
        "sgst": sgst,
    })

def edit_medical_bill_view(request, bill_no):

    bill = get_object_or_404(
        MedicalBill,
        bill_no=bill_no
    )

    patients = Patient.objects.filter(is_active=True)

    # Don't filter by stock > 0 in edit page
    medicines = Stock.objects.select_related(
        "medicine"
    ).all()

    settings = HospitalSetting.objects.first()

    items = MedicineItem.objects.filter(
        bill=bill
    )

    if request.method == "POST":

        try:

            doctor_name = request.POST.get("doctor_name", "")
            bill_date = request.POST.get("bill_date")

            subtotal = Decimal(
                request.POST.get("subtotal") or "0"
            )

            tax = Decimal(
                request.POST.get("tax") or "0"
            )

            total = Decimal(
                request.POST.get("total") or "0"
            )

            payment_mode = request.POST.get("payment_mode")
            payment_status = request.POST.get("payment_status")

            stock_ids = request.POST.getlist("stock_id[]")
            qtys = request.POST.getlist("quantity[]")
            subs = request.POST.getlist("subtotal[]")

            with transaction.atomic():

                # ======================
                # RESTORE OLD STOCK
                # ======================

                old_items = MedicineItem.objects.filter(
                    bill=bill
                )

                for old in old_items:

                    stock = Stock.objects.filter(
                        medicine__name=old.medicine_name
                    ).first()

                    if stock:

                        stock.total_base_quantity += old.quantity

                        stock.save(
                            update_fields=[
                                "total_base_quantity"
                            ]
                        )

                # ======================
                # DELETE OLD ITEMS
                # ======================

                old_items.delete()

                # ======================
                # SAVE NEW ITEMS
                # ======================

                for i in range(len(stock_ids)):

                    stock = Stock.objects.filter(
                        id=stock_ids[i]
                    ).first()

                    if not stock:
                        continue

                    qty = Decimal(qtys[i] or "0")
                    sub = Decimal(subs[i] or "0")

                    if qty > stock.total_base_quantity:

                        raise Exception(
                            f"Only {stock.total_base_quantity} "
                            f"{stock.base_unit} available "
                            f"for {stock.medicine.name}"
                        )

                    MedicineItem.objects.create(
                        bill=bill,
                        medicine_name=stock.medicine.name,
                        unit_price=stock.selling_price,
                        quantity=qty,
                        subtotal=sub
                    )

                    stock.total_base_quantity -= qty

                    stock.save(
                        update_fields=[
                            "total_base_quantity"
                        ]
                    )

                # ======================
                # UPDATE BILL
                # ======================

                bill.doctor_name = doctor_name
                bill.bill_date = bill_date
                bill.subtotal = subtotal
                bill.tax = tax
                bill.total = total
                bill.payment_mode = payment_mode
                bill.payment_status = payment_status

                bill.save()

                ActivityHistory.objects.create(
                    user=request.user,
                    action="UPDATE",
                    module="MEDICAL BILL",
                    record_id=bill.id,
                    description=f"Medical Bill #{bill.bill_no} updated by {request.user}"
                )

            return redirect(
                "billingmgmt:print_bill",
                bill_no=bill.bill_no
            )

        except Exception as e:
            print("Medical Bill Edit Error:", e)
            raise e

    return render(
        request,
        "billingmgmt/medicalbill_edit.html",
        {
            "bill": bill,
            "patients": patients,
            "medicines": medicines,
            "settings": settings,
            "today": bill.bill_date,
            "items": items,
        },
    )
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
        settings = HospitalSetting.objects.first()
        charges = IPOtherCharge.objects.filter(status=True)
        medicines = MedicalStock.objects.filter(quantity__gt=0).select_related('medicine')[:1000]
        therapies = TherapyMaster.objects.all()
        room_types = RoomType.objects.filter(is_active=True)

        return render(request, "billingmgmt/inpatientbill.html", {
            "bill_no": bill_no,
            "patients": patients,
            "medicines": medicines,
            "therapies": therapies,
            "settings": settings,
            "charges": charges,
            "room_types":room_types,
            "today": timezone.localdate(),
        })

    # ---------------- POST ----------------

    if request.method == "POST":

        bill_no = request.POST.get("bill_no")
        patient_id = request.POST.get("patient_id")
        doctor_name = request.POST.get("doctor_name") or ""
        admit_date = request.POST.get("admit_date") or None
        discharge_date = request.POST.get("discharge_date") or None

        # 🔹 Discount percent from form
        discount_percent = Decimal(request.POST.get("discount") or "0")
        advance_payment = Decimal(request.POST.get("advance_payment") or "0")
        balance_amount = Decimal(request.POST.get("balance_amount") or "0")
        payment_mode = request.POST.get("payment_mode") or "Cash"
        payment_status = request.POST.get("payment_status") or "Pending"
        remarks = request.POST.get("remarks") or ""

        # ---- validate patient ----
        try:
            patient = Patient.objects.get(patient_unique_id=patient_id)
        except Patient.DoesNotExist:
            return HttpResponseBadRequest("Invalid Patient ID")

        # ---- REGISTRATION FEE ----
        registration_fee = Decimal("50.00") if patient.created_at.date() == timezone.localdate() else Decimal("0.00")

        # ---- GST FROM SETTINGS ----
        settings = HospitalSetting.objects.first()
        gst_percent = Decimal(settings.consultation_gst or 0) if settings else Decimal("0")

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
                subtotal=Decimal("0.00"),
                discount=Decimal("0.00"),
                tax=Decimal("0.00"),
                total=Decimal("0.00"),
                advance_payment=advance_payment,
                balance_amount=balance_amount,
                payment_mode=payment_mode,
                payment_status=payment_status,
                remarks=remarks,
                discount_percent=discount_percent,
                created_by=request.user
            )
            ActivityHistory.objects.create(
                user=request.user,
                action="CREATE",
                module="INPATIENT BILL",
                record_id=bill.id,
                description=f"Inpatient Bill #{bill.id} created by {request.user}"
            )
            for name, rate, qty, itype, stock_id in zip(
                item_names, item_rates, item_qtys, item_types, item_stock_ids
            ):

                if not name:
                    continue

                rate_d = Decimal(rate or "0")
                qty_d = Decimal(qty or "0")

                subtotal = (rate_d * qty_d).quantize(Decimal("0.01"))
                calculated_subtotal += subtotal

                stock_obj = None

                # -------- MEDICINE STOCK --------
                if itype == "medicine" and stock_id:

                    stock_obj = MedicalStock.objects.select_for_update().get(id=stock_id)

                    if Decimal(stock_obj.quantity) < qty_d:
                        raise ValueError(f"Not enough stock for {name}")

                    stock_obj.quantity -= qty_d
                    stock_obj.save()

                # -------- CREATE BILL ITEM --------
                InpatientItem.objects.create(
                    bill=bill,
                    item_type=itype,
                    item_name=name,
                    unit_price=rate_d,
                    quantity=qty_d,
                    subtotal=subtotal,
                    medical_stock=stock_obj
                )

            # ---------------- FINAL CALCULATION ----------------

            # Add registration fee
            final_subtotal = calculated_subtotal + registration_fee

            # Discount calculation
            discount_amount = (final_subtotal * discount_percent / Decimal("100")).quantize(Decimal("0.01"))

            subtotal_after_discount = final_subtotal - discount_amount

            # GST calculation
            tax = (subtotal_after_discount * gst_percent / Decimal("100")).quantize(Decimal("0.01"))

            total = subtotal_after_discount + tax

            bill.subtotal = final_subtotal
            bill.discount = discount_amount
            bill.tax = tax
            bill.total = total
            bill.save()

        return redirect("billingmgmt:print_inpatient_bill", bill_no=bill.bill_no)


def edit_inpatient_bill_view(request, bill_no):

    bill = get_object_or_404(InpatientBill, bill_no=bill_no)

    patients = Patient.objects.filter(is_active=True)
    settings = HospitalSetting.objects.first()
    charges = IPOtherCharge.objects.filter(status=True)

    medicines = MedicalStock.objects.filter(
        quantity__gt=0
    ).select_related("medicine")[:1000]

    therapies = TherapyMaster.objects.all()

    items = InpatientItem.objects.filter(bill=bill)

    if request.method == "POST":

        bill.patient = Patient.objects.get(
            patient_unique_id=request.POST.get("patient_id")
        )

        bill.doctor_name = request.POST.get("doctor_name") or ""
        bill.admit_date = request.POST.get("admit_date") or None
        bill.discharge_date = request.POST.get("discharge_date") or None

        discount_percent = Decimal(request.POST.get("discount") or "0")

        payment_mode = request.POST.get("payment_mode") or "Cash"
        payment_status = request.POST.get("payment_status") or "Pending"
        remarks = request.POST.get("remarks") or ""

        item_names = request.POST.getlist("item_name[]")
        item_rates = request.POST.getlist("item_rate[]")
        item_qtys = request.POST.getlist("item_qty[]")
        item_types = request.POST.getlist("item_type[]")
        item_stock_ids = request.POST.getlist("item_stock_id[]")

        gst_percent = Decimal(settings.consultation_gst or 0)

        with transaction.atomic():

            # ---------- RESTORE OLD STOCK ----------
            for old in items:
                if old.item_type == "medicine" and old.medical_stock:
                    stock = old.medical_stock
                    stock.quantity += old.quantity
                    stock.save()

            # ---------- DELETE OLD ITEMS ----------
            items.delete()

            subtotal = Decimal("0.00")

            for name, rate, qty, itype, stock_id in zip(
                item_names,
                item_rates,
                item_qtys,
                item_types,
                item_stock_ids,
            ):

                if not name:
                    continue

                rate_d = Decimal(rate or "0")
                qty_d = Decimal(qty or "0")

                sub = (rate_d * qty_d).quantize(Decimal("0.01"))
                subtotal += sub

                stock_obj = None

                # -------- MEDICINE STOCK --------
                if itype == "medicine" and stock_id:

                    stock_obj = MedicalStock.objects.select_for_update().get(
                        id=stock_id
                    )

                    if stock_obj.quantity < qty_d:
                        raise ValueError(f"Not enough stock for {name}")

                    stock_obj.quantity -= qty_d
                    stock_obj.save()

                # -------- CREATE ITEM --------
                InpatientItem.objects.create(
                    bill=bill,
                    item_type=itype,
                    item_name=name,
                    unit_price=rate_d,
                    quantity=qty_d,
                    subtotal=sub,
                    medical_stock=stock_obj
                )
            # ---------- BILL CALCULATION ----------

            discount_amount = (
                subtotal * discount_percent / Decimal("100")
            ).quantize(Decimal("0.01"))

            subtotal_after_discount = subtotal - discount_amount

            tax = (
                subtotal_after_discount * gst_percent / Decimal("100")
            ).quantize(Decimal("0.01"))

            total = subtotal_after_discount + tax

            # ---------- ADVANCE PAYMENT LOGIC ----------

            old_advance = bill.advance_payment or Decimal("0")
            new_payment = Decimal(request.POST.get("advance_payment") or "0")

            total_advance = old_advance + new_payment

            balance_amount = total - total_advance

            if balance_amount < 0:
                balance_amount = Decimal("0.00")

            # ---------- SAVE BILL ----------

            bill.subtotal = subtotal
            bill.discount = discount_amount
            bill.tax = tax
            bill.total = total

            bill.advance_payment = total_advance
            bill.balance_amount = balance_amount

            bill.payment_mode = payment_mode
            bill.payment_status = payment_status
            bill.remarks = remarks
            bill.discount_percent = discount_percent

            bill.save()
            ActivityHistory.objects.create(
                user=request.user,
                action="UPDATE",
                module="INPATIENT BILL",
                record_id=bill.id,
                description=f"Inpatient Bill #{bill.id} updated by {request.user}"
            )
        return redirect(
            "billingmgmt:print_inpatient_bill",
            bill_no=bill.bill_no
        )

    return render(
        request,
        "billingmgmt/inpatientbill_edit.html",
        {
            "bill": bill,
            "items": items,
            "patients": patients,
            "medicines": medicines,
            "therapies": therapies,
            "charges": charges,
            "settings": settings,
        },
    )

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

    # ---- SETTINGS ----
    settings = HospitalSetting.objects.first()
    gst_percent = Decimal(settings.consultation_gst or 0).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    # ---- GST SPLIT (PERCENT) ----
    cgst_percent = (gst_percent / 2).quantize(Decimal("0.01"))
    sgst_percent = (gst_percent / 2).quantize(Decimal("0.01"))

    # ---- GST AMOUNT ----
    subtotal = bill.subtotal
    total_gst = (subtotal * gst_percent / Decimal("100")).quantize(Decimal("0.01"))
    cgst = (total_gst / 2).quantize(Decimal("0.01"))
    sgst = (total_gst / 2).quantize(Decimal("0.01"))

    grand_total = subtotal + total_gst - bill.discount

    return render(request, "billingmgmt/print_inpatientbill.html", {
        "bill": bill,
        "room_items": room_items,
        "other_items": other_items,

        # 🔹 SETTINGS
        "settings": settings,

        # 🔹 GST %
        "gst_percent": gst_percent,
        "cgst_percent": cgst_percent,
        "sgst_percent": sgst_percent,

        # 🔹 GST AMOUNTS
        "cgst": cgst,
        "sgst": sgst,
        "total_gst": total_gst,

        # 🔹 TOTALS
        "subtotal": subtotal,
        "grand_total": grand_total,
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
        settings = HospitalSetting.objects.first()

        return render(request, "billingmgmt/outpatientbill.html", {
            "bill_no": generate_op_bill_no(),
            "today": timezone.localdate(),
            "therapies": therapies,
            "settings": settings
        })

    # ---------- POST ----------

    bill_no = request.POST.get("bill_no")
    patient_id = request.POST.get("patient_id")
    doctor_name = request.POST.get("doctor_name") or ""
    visit_date = request.POST.get("visit_date") or timezone.localdate()

    payment_mode = request.POST.get("payment_mode") or "Cash"
    payment_status = request.POST.get("payment_status") or "Pending"

    subtotal = Decimal(request.POST.get("subtotal") or "0")

    discount_percent = Decimal(request.POST.get("discount") or "0")

    try:
        patient = Patient.objects.get(id=patient_id)
    except (Patient.DoesNotExist, ValueError, TypeError):
        return HttpResponseBadRequest("Invalid Patient")

    # -------- REGISTRATION FEE --------
    registration_fee = Decimal(
        request.POST.get("registration_fee") or "0"
    )

    subtotal = subtotal + registration_fee
    # -------- DISCOUNT CALCULATION --------
    discount_amount = (
        subtotal * discount_percent / Decimal("100")
    ).quantize(Decimal("0.01"))

    subtotal_after_discount = subtotal - discount_amount

    # -------- GST --------
    settings = HospitalSetting.objects.first()
    gst_percent = Decimal(settings.consultation_gst or 0) if settings else Decimal("0")

    tax = (
        subtotal_after_discount * gst_percent / Decimal("100")
    ).quantize(Decimal("0.01"))

    total = subtotal_after_discount + tax

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
            discount_percent=discount_percent,
            discount=discount_amount,
            tax=tax,
            total=total,

            payment_mode=payment_mode,
            payment_status=payment_status,
            created_by=request.user,
        )
        ActivityHistory.objects.create(
            user=request.user,
            action="CREATE",
            module="OUTPATIENT BILL",
            record_id=bill.id,
            description=f"Outpatient Bill #{bill.id} created by {request.user}"
        )
        # -------- SAVE ITEMS --------
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

        # -------- REGISTRATION ITEM --------
        if registration_fee > 0:
            OutpatientItem.objects.create(
                bill=bill,
                item_name="New Registration Fee",
                unit_price=registration_fee,
                quantity=1,
                subtotal=registration_fee
            )

    return redirect(
        "billingmgmt:print_outpatient_bill",
        bill_no=bill.bill_no
    )

def edit_outpatient_bill_view(request, bill_no):

    bill = get_object_or_404(OutpatientBill, bill_no=bill_no)

    settings = HospitalSetting.objects.first()
    therapies = TherapyMaster.objects.all()

    items = OutpatientItem.objects.filter(bill=bill)

    if request.method == "POST":

        doctor_name = request.POST.get("doctor_name") or ""
        visit_date = request.POST.get("visit_date") or timezone.localdate()

        payment_mode = request.POST.get("payment_mode") or "Cash"
        payment_status = request.POST.get("payment_status") or "Pending"

        discount_percent = Decimal(request.POST.get("discount") or "0")

        item_names = request.POST.getlist("item_name[]")
        item_rates = request.POST.getlist("item_rate[]")
        item_qtys = request.POST.getlist("item_qty[]")

        gst_percent = Decimal(settings.consultation_gst or 0) if settings else Decimal("0")

        with transaction.atomic():

            # delete old items
            items.delete()

            subtotal = Decimal("0.00")

            for name, rate, qty in zip(item_names, item_rates, item_qtys):

                if not name:
                    continue

                rate_d = Decimal(rate or "0")
                qty_d = Decimal(qty or "0")

                sub = rate_d * qty_d
                subtotal += sub

                OutpatientItem.objects.create(
                    bill=bill,
                    item_name=name,
                    unit_price=rate_d,
                    quantity=qty_d,
                    subtotal=sub
                )

            # -------- REGISTRATION FEE --------
            registration_fee = Decimal(
                request.POST.get("registration_fee") or "0"
            )

            subtotal = subtotal + registration_fee

            discount_amount = (
                subtotal * discount_percent / Decimal("100")
            ).quantize(Decimal("0.01"))

            subtotal_after_discount = subtotal - discount_amount

            tax = (
                subtotal_after_discount * gst_percent / Decimal("100")
            ).quantize(Decimal("0.01"))

            total = subtotal_after_discount + tax

            bill.doctor_name = doctor_name
            bill.visit_date = visit_date

            bill.subtotal = subtotal
            bill.discount_percent = discount_percent
            bill.discount = discount_amount
            bill.tax = tax
            bill.total = total

            bill.payment_mode = payment_mode
            bill.payment_status = payment_status

            bill.save()
            ActivityHistory.objects.create(
                user=request.user,
                action="UPDATE",
                module="INPATIENT BILL",
                record_id=bill.id,
                description=f"Inpatient Bill #{bill.id} updated by {request.user}"
            )
        return redirect(
            "billingmgmt:print_outpatient_bill",
            bill_no=bill.bill_no
        )

    return render(
        request,
        "billingmgmt/outpatientbill_edit.html",
        {
            "bill": bill,
            "items": items,
            "settings": settings,
            "therapies": therapies,
        },
    )

def print_outpatient_bill(request, bill_no):
    bill = get_object_or_404(OutpatientBill, bill_no=bill_no)
    items = bill.items.all()

    # ---- SETTINGS ----
    settings = HospitalSetting.objects.first()
    gst_percent = Decimal(settings.consultation_gst or 0).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    # ---- GST SPLIT (PERCENT) ----
    cgst_percent = (gst_percent / 2).quantize(Decimal("0.01"))
    sgst_percent = (gst_percent / 2).quantize(Decimal("0.01"))

    # ---- GST AMOUNT ----
    subtotal = bill.subtotal
    total_gst = (subtotal * gst_percent / Decimal("100")).quantize(Decimal("0.01"))
    cgst = (total_gst / 2).quantize(Decimal("0.01"))
    sgst = (total_gst / 2).quantize(Decimal("0.01"))

    grand_total = subtotal + total_gst - bill.discount

    return render(request, "billingmgmt/print_outpatientbill.html", {
        "bill": bill,
        "items": items,

        # 🔹 SETTINGS
        "settings": settings,

        # 🔹 GST %
        "gst_percent": gst_percent,
        "cgst_percent": cgst_percent,
        "sgst_percent": sgst_percent,

        # 🔹 GST AMOUNTS
        "cgst": cgst,
        "sgst": sgst,
        "total_gst": total_gst,

        # 🔹 TOTALS
        "grand_total": grand_total,
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

    if request.method == "POST":
        customer_type = request.POST.get("customer_type", "patient")

        patient_id = request.POST.get("patient_id")
        walkin_name = request.POST.get("walkin_name", "").strip()

        # REGISTERED PATIENT
        patient = None

        if customer_type == "patient":

            if not patient_id:
                messages.error(request, "Select patient")
                return redirect("billingmgmt:therapybilling")

            patient = get_object_or_404(
                Patient,
                id=patient_id
            )

        # WALKIN
        else:

            if not walkin_name:
                messages.error(request, "Enter customer name")
                return redirect("billingmgmt:therapybilling")

        bill_no = request.POST.get("bill_no") or generate_therapy_bill_number()
        bill_date = request.POST.get("bill_date") or timezone.localdate()

        payment_mode = request.POST.get("payment_mode") or "Cash"
        payment_status = request.POST.get("payment_status") or "Pending"
        remarks = request.POST.get("remarks", "")

        # ---------- TOTAL INPUT ----------
        try:
            subtotal = Decimal(request.POST.get("subtotal") or "0")
            discount_percent = Decimal(request.POST.get("discount_percent") or "0")
            advance_payment = Decimal(request.POST.get("advance_payment") or "0")
        except InvalidOperation:
            subtotal = Decimal("0")
            discount_percent = Decimal("0")
            advance_payment = Decimal("0")

        # ---------- GST ----------
        settings = HospitalSetting.objects.first()
        gst_percent = Decimal(settings.therapy_gst or 0) if settings else Decimal("0")

        tax = (subtotal * gst_percent / Decimal("100")).quantize(Decimal("0.01"))

        subtotal_with_gst = subtotal + tax

        # ---------- DISCOUNT ----------
        discount = (
            subtotal_with_gst * discount_percent / Decimal("100")
        ).quantize(Decimal("0.01"))

        # ---------- TOTAL ----------
        total = subtotal_with_gst - discount

        # ---------- BALANCE ----------
        balance_amount = total - advance_payment

        if balance_amount < 0:
            balance_amount = Decimal("0.00")

        # ---------- FORM ARRAYS ----------
        therapy_ids = request.POST.getlist("therapy_id[]")
        quantities = request.POST.getlist("quantity[]")
        unit_prices = request.POST.getlist("unit_price[]")
        subtotals = request.POST.getlist("subtotal[]")

        with transaction.atomic():

            bill = TherapyBill.objects.create(

                customer_type=customer_type,
                walkin_name=walkin_name if customer_type == "walkin" else None,

                patient=patient,

                bill_no=bill_no,
                bill_date=bill_date,

                subtotal=subtotal,
                discount_percent=discount_percent,
                discount=discount,

                tax=tax,
                total=total,

                advance_payment=advance_payment,
                balance_amount=balance_amount,

                payment_mode=payment_mode,
                payment_status=payment_status,
                remarks=remarks
            )
            ActivityHistory.objects.create(
                user=request.user,
                action="CREATE",
                module="THERAPY BILL",
                record_id=bill.id,
                description=f"Therapy Bill #{bill.id} created by {request.user}"
            )

            # ---------- SAVE ITEMS ----------
            for t_id, qty, price, sub in zip(
                therapy_ids, quantities, unit_prices, subtotals
            ):

                if not t_id:
                    continue

                try:
                    therapy = TherapyMaster.objects.get(id=t_id)
                    qty_int = int(float(qty))
                    unit_price = Decimal(price)
                    subtotal_amt = Decimal(sub)

                except (TherapyMaster.DoesNotExist, ValueError, TypeError, InvalidOperation):
                    continue

                if qty_int <= 0:
                    continue

                TherapyBillItem.objects.create(
                    bill=bill,
                    therapy=therapy,
                    unit_price=unit_price,
                    quantity=qty_int,
                    subtotal=subtotal_amt
                )

        return redirect("billingmgmt:therapy_bill_print", bill_no=bill.bill_no)

    # ---------- GET ----------
    return render(request, "billingmgmt/therapybill.html", {
        "patients": Patient.objects.filter(is_active=True),
        "therapies": TherapyMaster.objects.filter(status=True),
        "bill_no": generate_therapy_bill_number(),
        "settings": HospitalSetting.objects.first(),
        "today": timezone.localdate(),
    })
    
    
def edit_therapy_bill_view(request, bill_no):

    bill = get_object_or_404(TherapyBill, bill_no=bill_no)

    settings = HospitalSetting.objects.first()

    if request.method == "POST":
        bill.customer_type = request.POST.get(
            "customer_type",
            "patient"
        )

        bill.walkin_name = request.POST.get(
            "walkin_name",
            ""
        ).strip()

        if bill.customer_type == "patient":

            patient_id = request.POST.get("patient_id")

            if patient_id:
                bill.patient = get_object_or_404(
                    Patient,
                    id=patient_id
                )

        else:
            bill.patient = None

        subtotal = Decimal(request.POST.get("subtotal") or "0")
        discount_percent = Decimal(request.POST.get("discount_percent") or "0")

        old_advance = Decimal(request.POST.get("old_advance") or "0")
        new_payment = Decimal(request.POST.get("advance_payment") or "0")

        gst_percent = Decimal(settings.therapy_gst or 0)

        tax = (subtotal * gst_percent / Decimal("100")).quantize(Decimal("0.01"))

        subtotal_with_gst = subtotal + tax

        discount = (
            subtotal_with_gst * discount_percent / Decimal("100")
        ).quantize(Decimal("0.01"))

        total = subtotal_with_gst - discount

        # 🔹 CORRECT ADVANCE LOGIC
        total_advance = old_advance + new_payment

        balance_amount = total - total_advance

        if balance_amount < 0:
            balance_amount = Decimal("0")

        bill.subtotal = subtotal
        bill.discount_percent = discount_percent
        bill.discount = discount
        bill.tax = tax
        bill.total = total

        bill.advance_payment = total_advance
        bill.balance_amount = balance_amount

        bill.payment_mode = request.POST.get("payment_mode")
        bill.payment_status = request.POST.get("payment_status")
        bill.remarks = request.POST.get("remarks")

        bill.save()
        ActivityHistory.objects.create(
            user=request.user,
            action="UPDATE",
            module="THERAPY BILL",
            record_id=bill.id,
            description=f"Therapy Bill #{bill.id} updated by {request.user}"
        )
        return redirect("billingmgmt:therapy_bill_print", bill_no=bill.bill_no)

    return render(request, "billingmgmt/therapybill_edit.html", {
        "bill": bill,
        "patients": Patient.objects.filter(is_active=True),
        "therapies": TherapyMaster.objects.filter(status=True),
        "settings": settings,
    })
def therapy_bill_print_view(request, bill_no):
    bill = get_object_or_404(TherapyBill, bill_no=bill_no)

    # ---- SETTINGS ----
    settings = HospitalSetting.objects.first()
    gst_percent = Decimal(settings.therapy_gst or 0) if settings else Decimal("0")

    # ---- GST CALCULATION (SAME AS OUTPATIENT) ----
    gst_amount = (bill.subtotal * gst_percent / Decimal("100")).quantize(Decimal("0.01"))
    grand_total = bill.subtotal - bill.discount + gst_amount

    return render(request, "billingmgmt/print_therapybill.html", {
        "bill": bill,
        "items": bill.items.all(),   # ✅ CORRECT RELATED NAME
        "settings": settings,
        "gst_percent": gst_percent,
        "gst_amount": gst_amount,
        "grand_total": grand_total,
    })

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
    
    
    
def hospital_settings(request):
    settings = HospitalSetting.objects.first()

    if request.method == 'POST':
        if not settings:
            settings = HospitalSetting()

        settings.hospital_name = request.POST.get('hospital_name')
        settings.address = request.POST.get('address')
        settings.phone = request.POST.get('phone')
        settings.landline = request.POST.get('landline')
        settings.email = request.POST.get('email')
        settings.registration_number = request.POST.get('registration_number')
        settings.gst_number = request.POST.get('gst_number')
        settings.consultation_gst = request.POST.get('consultation_gst') or 0
        settings.therapy_gst = request.POST.get('therapy_gst') or 0

        if 'hospital_logo' in request.FILES:
            settings.hospital_logo = request.FILES['hospital_logo']

        settings.save()
        messages.success(request, 'Hospital settings updated successfully')

        return redirect('billingmgmt:hospital_settings')

    return render(request, 'billingmgmt/settings.html', {
        'settings': settings
    })
    
def medical_bill_delete(request, pk):
    bill = get_object_or_404(MedicalBill, pk=pk)

    bill_no = bill.bill_no  # store for message
    bill.delete()

    messages.success(request, f"Medical Bill {bill_no} deleted successfully.")
    return redirect('billingmgmt:medical_billing_list')  # change to your list page name


# ---------------- INPATIENT DELETE ----------------
def inpatient_bill_delete(request, pk):
    bill = get_object_or_404(InpatientBill, pk=pk)
    bill_no = bill.bill_no
    bill.delete()

    messages.success(request, f"Inpatient Bill {bill_no} deleted successfully.")
    return redirect('billingmgmt:inpatient_billing_list')


# ---------------- OUTPATIENT DELETE ----------------
def outpatient_bill_delete(request, pk):
    bill = get_object_or_404(OutpatientBill, pk=pk)
    bill_no = bill.bill_no
    bill.delete()

    messages.success(request, f"Outpatient Bill {bill_no} deleted successfully.")
    return redirect('billingmgmt:outpatient_billing_list')


# ---------------- THERAPY DELETE ----------------
def therapy_bill_delete(request, pk):
    bill = get_object_or_404(TherapyBill, pk=pk)
    bill_no = bill.bill_no
    bill.delete()

    messages.success(request, f"Therapy Bill {bill_no} deleted successfully.")
    return redirect('billingmgmt:therapy_billing_list')