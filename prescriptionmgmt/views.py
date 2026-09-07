# prescription/views.py
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from prescriptionmgmt.models import Prescription, PrescriptionItem, TreatmentPlanItem
from stockmgmt.models import Stock
from patientmgmt.models import Patient
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from fieldmgmt.models import Adjuvant, ActivityHistory
from billingmgmt.models import HospitalSetting

def generate_prescription_no():
    last = Prescription.objects.order_by('-id').first()
    if last and last.prescription_no.startswith("PR"):
        try:
            n = int(last.prescription_no.replace("PR", ""))
        except Exception:
            n = 0
        return f"PR{n+1:04d}"
    return "PR0001"

@login_required
def create_prescription(request):
    if request.method == "POST":
        pres_no = request.POST.get("prescription_no")
        patient_id = request.POST.get("patient_id")
        notes = request.POST.get("notes", "")
        next_visit = request.POST.get("next_visit") or None

        # Case Sheet Clinical Fields
        occupation = request.POST.get("occupation", "").strip()
        presenting_complaints = request.POST.get("presenting_complaints", "").strip()
        associated_complaints = request.POST.get("associated_complaints", "").strip()
        history_present_illness = request.POST.get("history_present_illness", "").strip()
        history_past_illness = request.POST.get("history_past_illness", "").strip()

        # Co-morbidities & Current Meds
        comorbid_diabetes = request.POST.get("comorbid_diabetes") in ["on", "true", True]
        comorbid_hypertension = request.POST.get("comorbid_hypertension") in ["on", "true", True]
        comorbid_thyroid = request.POST.get("comorbid_thyroid") in ["on", "true", True]
        comorbid_cardiac = request.POST.get("comorbid_cardiac") in ["on", "true", True]
        comorbid_kidney = request.POST.get("comorbid_kidney") in ["on", "true", True]
        comorbid_others = request.POST.get("comorbid_others", "").strip()
        current_medications = request.POST.get("current_medications", "").strip()

        # Vitals / Examination Grid (16 fields)
        exam_malam = request.POST.get("exam_malam", "").strip()
        exam_nadi = request.POST.get("exam_nadi", "").strip()
        exam_jivha = request.POST.get("exam_jivha", "").strip()
        exam_akri = request.POST.get("exam_akri", "").strip()

        exam_diet_habit = request.POST.get("exam_diet_habit", "").strip()
        exam_mutr = request.POST.get("exam_mutr", "").strip()
        exam_shabda = request.POST.get("exam_shabda", "").strip()
        exam_bp = request.POST.get("exam_bp", "").strip()

        exam_addiction = request.POST.get("exam_addiction", "").strip()
        exam_lmp = request.POST.get("exam_lmp", "").strip()
        exam_sharira = request.POST.get("exam_sharira", "").strip()
        exam_sparsha = request.POST.get("exam_sparsha", "").strip()

        exam_allergies = request.POST.get("exam_allergies", "").strip()
        exam_pulse = request.POST.get("exam_pulse", "").strip()
        exam_shir = request.POST.get("exam_shir", "").strip()
        exam_nakha = request.POST.get("exam_nakha", "").strip()

        # Medicine Allocations
        stock_ids = request.POST.getlist("stock_id[]")
        medicine_names = request.POST.getlist("medicine_name[]")
        dosages = request.POST.getlist("dosage[]")
        custom_dosages = request.POST.getlist("custom_dosage[]")
        durations = request.POST.getlist("duration[]")
        quantities = request.POST.getlist("quantity[]")
        food_timings = request.POST.getlist("food_timing[]")
        adjuvants = request.POST.getlist("adjuvant[]")

        # Treatment Plan
        treatment_names = request.POST.getlist("treatment_name[]")
        tailams = request.POST.getlist("tailam[]")
        treatment_instructions = request.POST.getlist("treatment_instructions[]")

        if not patient_id:
            messages.error(request, "Patient ID required.")
            return redirect("dashboard")

        try:
            patient = Patient.objects.get(patient_unique_id=patient_id)
        except Patient.DoesNotExist:
            messages.error(request, "Invalid Patient ID.")
            return redirect("dashboard")

        # Check if updating an existing prescription or creating new
        prescription = None
        if pres_no:
            prescription = Prescription.objects.filter(prescription_no=pres_no).first()

        action_type = "UPDATE" if prescription else "CREATE"

        if not prescription:
            prescription = Prescription(prescription_no=pres_no or generate_prescription_no())

        prescription.patient = patient
        prescription.doctor = request.user
        prescription.notes = notes
        prescription.next_visit = next_visit
        prescription.occupation = occupation
        prescription.presenting_complaints = presenting_complaints
        prescription.associated_complaints = associated_complaints
        prescription.history_present_illness = history_present_illness
        prescription.history_past_illness = history_past_illness

        prescription.comorbid_diabetes = comorbid_diabetes
        prescription.comorbid_hypertension = comorbid_hypertension
        prescription.comorbid_thyroid = comorbid_thyroid
        prescription.comorbid_cardiac = comorbid_cardiac
        prescription.comorbid_kidney = comorbid_kidney
        prescription.comorbid_others = comorbid_others
        prescription.current_medications = current_medications

        prescription.exam_malam = exam_malam
        prescription.exam_nadi = exam_nadi
        prescription.exam_jivha = exam_jivha
        prescription.exam_akri = exam_akri
        prescription.exam_diet_habit = exam_diet_habit
        prescription.exam_mutr = exam_mutr
        prescription.exam_shabda = exam_shabda
        prescription.exam_bp = exam_bp
        prescription.exam_addiction = exam_addiction
        prescription.exam_lmp = exam_lmp
        prescription.exam_sharira = exam_sharira
        prescription.exam_sparsha = exam_sparsha
        prescription.exam_allergies = exam_allergies
        prescription.exam_pulse = exam_pulse
        prescription.exam_shir = exam_shir
        prescription.exam_nakha = exam_nakha

        prescription.save()

        ActivityHistory.objects.create(
            user=request.user,
            action=action_type,
            module="PRESCRIPTION",
            record_id=prescription.id,
            description=f"Case Sheet / Prescription #{prescription.prescription_no} {action_type.lower()}d by {request.user}"
        )

        # Re-create medicine items
        prescription.items.all().delete()
        for idx in range(max(len(medicine_names), len(stock_ids))):
            med = medicine_names[idx] if idx < len(medicine_names) else ""
            sid = stock_ids[idx] if idx < len(stock_ids) else None
            dose = dosages[idx] if idx < len(dosages) else ""
            custom_dose = custom_dosages[idx] if idx < len(custom_dosages) else ""
            if dose == "Other" and custom_dose:
                final_dose = custom_dose
            else:
                final_dose = dose
            dur = durations[idx] if idx < len(durations) else 0
            qty = quantities[idx] if idx < len(quantities) else 0
            food = food_timings[idx] if idx < len(food_timings) else ""
            adj = adjuvants[idx] if idx < len(adjuvants) else None

            if not med:
                continue

            adjuvant_obj = None
            if adj:
                try:
                    adjuvant_obj = Adjuvant.objects.get(id=adj)
                except (Adjuvant.DoesNotExist, ValueError):
                    pass

            PrescriptionItem.objects.create(
                prescription=prescription,
                stock_id=sid if sid else None,
                medicine_name=med,
                dosage=final_dose or "",
                duration_days=int(dur or 0),
                quantity=Decimal(str(qty or 0)),
                food_timing=food or "",
                adjuvant=adjuvant_obj
            )

        # Re-create treatment plan items
        prescription.treatment_items.all().delete()
        for idx in range(len(treatment_names)):
            t_name = treatment_names[idx].strip()
            if not t_name:
                continue
            tailam = tailams[idx].strip() if idx < len(tailams) else ""
            t_inst = treatment_instructions[idx].strip() if idx < len(treatment_instructions) else ""

            TreatmentPlanItem.objects.create(
                prescription=prescription,
                treatment_name=t_name,
                tailam=tailam,
                instructions=t_inst
            )

        return redirect("prescriptionmgmt:print", prescription_no=prescription.prescription_no)

    return redirect("dashboard")

@login_required
def ajax_get_patient(request):
    patient_id = request.GET.get("patient_id")
    patient_name = request.GET.get("patient_name")
    try:
        if patient_id:
            p = Patient.objects.get(patient_unique_id=patient_id)
        elif patient_name:
            p = Patient.objects.get(patient_name=patient_name)
        else:
            return JsonResponse({"error": "no parameter provided"})
    except Patient.DoesNotExist:
        return JsonResponse({"error": "patient not found"})

    return JsonResponse({
        "patient_unique_id": p.patient_unique_id,
        "patient_name": p.patient_name,
        "age": p.age,
        "gender": p.gender,
        "phone": p.phone or "",
        "address": p.address or "",
    })

@login_required
def ajax_get_patient_history(request):
    patient_id = request.GET.get("patient_id")
    patient_name = request.GET.get("patient_name")

    patient = None
    if patient_id:
        patient = Patient.objects.filter(patient_unique_id=patient_id).first()
    elif patient_name:
        patient = Patient.objects.filter(patient_name=patient_name).first()

    if not patient:
        return JsonResponse({"history": []})

    prescriptions = Prescription.objects.filter(patient=patient).select_related("doctor").order_by("-created_at")
    history = []
    for p in prescriptions:
        doctor_name = p.doctor.get_full_name() if p.doctor else (p.doctor.username if p.doctor else "")
        history.append({
            "id": p.id,
            "prescription_no": p.prescription_no,
            "date": p.created_at.strftime("%d-%m-%Y"),
            "date_iso": p.created_at.strftime("%Y-%m-%d"),
            "doctor": doctor_name,
            "complaints": p.presenting_complaints or "",
            "notes": p.notes or "",
        })
    return JsonResponse({"history": history, "patient_unique_id": patient.patient_unique_id})

@login_required
def ajax_get_prescription_details(request):
    prescription_no = request.GET.get("prescription_no")
    prescription_id = request.GET.get("prescription_id")

    pres = None
    if prescription_no:
        pres = Prescription.objects.filter(prescription_no=prescription_no).select_related("patient", "doctor").first()
    elif prescription_id:
        pres = Prescription.objects.filter(id=prescription_id).select_related("patient", "doctor").first()

    if not pres:
        return JsonResponse({"error": "Prescription / Case sheet record not found"}, status=404)

    items = []
    for item in pres.items.select_related("adjuvant", "stock").all():
        items.append({
            "stock_id": item.stock_id or "",
            "medicine_name": item.medicine_name,
            "dosage": item.dosage,
            "duration_days": item.duration_days,
            "quantity": str(item.quantity),
            "food_timing": item.food_timing or "",
            "adjuvant_id": item.adjuvant_id or "",
            "adjuvant_name": item.adjuvant.name if item.adjuvant else "",
        })

    treatments = []
    for t in pres.treatment_items.all():
        treatments.append({
            "treatment_name": t.treatment_name,
            "tailam": t.tailam or "",
            "instructions": t.instructions or "",
        })

    doctor_name = pres.doctor.get_full_name() if pres.doctor else (pres.doctor.username if pres.doctor else "")

    return JsonResponse({
        "prescription_no": pres.prescription_no,
        "created_at": pres.created_at.strftime("%Y-%m-%d"),
        "created_at_display": pres.created_at.strftime("%d-%m-%Y %H:%M"),
        "doctor_name": doctor_name,
        "patient": {
            "unique_id": pres.patient.patient_unique_id,
            "name": pres.patient.patient_name,
            "age": pres.patient.age,
            "gender": pres.patient.gender,
            "gender_display": pres.patient.get_gender_display(),
            "phone": pres.patient.phone or "",
            "address": pres.patient.address or "",
        },
        "occupation": pres.occupation or "",
        "presenting_complaints": pres.presenting_complaints or "",
        "associated_complaints": pres.associated_complaints or "",
        "history_present_illness": pres.history_present_illness or "",
        "history_past_illness": pres.history_past_illness or "",
        "comorbidities": {
            "diabetes": pres.comorbid_diabetes,
            "hypertension": pres.comorbid_hypertension,
            "thyroid": pres.comorbid_thyroid,
            "cardiac": pres.comorbid_cardiac,
            "kidney": pres.comorbid_kidney,
            "others": pres.comorbid_others or "",
        },
        "current_medications": pres.current_medications or "",
        "examination": {
            "malam": pres.exam_malam or "",
            "nadi": pres.exam_nadi or "",
            "jivha": pres.exam_jivha or "",
            "akri": pres.exam_akri or "",
            "diet_habit": pres.exam_diet_habit or "",
            "mutr": pres.exam_mutr or "",
            "shabda": pres.exam_shabda or "",
            "bp": pres.exam_bp or "",
            "addiction": pres.exam_addiction or "",
            "lmp": pres.exam_lmp or "",
            "sharira": pres.exam_sharira or "",
            "sparsha": pres.exam_sparsha or "",
            "allergies": pres.exam_allergies or "",
            "pulse": pres.exam_pulse or "",
            "shir": pres.exam_shir or "",
            "nakha": pres.exam_nakha or "",
        },
        "items": items,
        "treatment_plan": treatments,
        "notes": pres.notes or "",
        "next_visit": pres.next_visit.strftime("%Y-%m-%d") if pres.next_visit else "",
    })

@login_required
def ajax_get_stock(request):
    stock_id = request.GET.get("stock_id")
    q = request.GET.get("q")
    if stock_id:
        try:
            s = Stock.objects.select_related("medicine").get(id=stock_id)
        except Stock.DoesNotExist:
            return JsonResponse({"error": "stock not found"}, status=404)
        return JsonResponse({
            "id": s.id,
            "medicine_name": s.medicine.name,
            "batch": s.batch_number,
            "selling_price": str(s.selling_price),
            "quantity": str(s.quantity),
        })
    if q:
        qs = Stock.objects.select_related("medicine").filter(medicine__name__icontains=q, quantity__gt=0)[:20]
        out = []
        for s in qs:
            out.append({
                "id": s.id,
                "medicine_name": s.medicine.name,
                "batch": s.batch_number,
                "selling_price": str(s.selling_price),
                "quantity": str(s.quantity),
            })
        return JsonResponse({"results": out})
    return JsonResponse({"error": "no parameters"}, status=400)

@login_required
def print_prescription(request, prescription_no):
    pres = get_object_or_404(Prescription.objects.select_related("patient", "doctor"), prescription_no=prescription_no)
    items = pres.items.select_related("adjuvant", "stock").all()
    treatment_items = pres.treatment_items.all()
    settings = HospitalSetting.objects.first()

    return render(
        request,
        "prescriptionmgmt/print_prescription.html",
        {
            "prescription": pres,
            "items": items,
            "treatment_items": treatment_items,
            "settings": settings
        }
    )