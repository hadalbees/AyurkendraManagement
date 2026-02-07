# prescription/views.py
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from prescriptionmgmt.models import Prescription, PrescriptionItem
from stockmgmt.models import Stock
from patientmgmt.models import Patient
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods

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

        # Arrays from form
        stock_ids = request.POST.getlist("stock_id[]")
        medicine_names = request.POST.getlist("medicine_name[]")
        dosages = request.POST.getlist("dosage[]")
        custom_dosages = request.POST.getlist("custom_dosage[]")
        durations = request.POST.getlist("duration[]")
        quantities = request.POST.getlist("quantity[]")
        food_timings = request.POST.getlist("food_timing[]")

        # ✅ Validate patient
        try:
            patient = Patient.objects.get(patient_unique_id=patient_id)
        except Patient.DoesNotExist:
            messages.error(request, "Invalid patient ID.")
            return redirect("prescriptionmgmt:create_prescription")

        try:
            with transaction.atomic():

                pres, created = Prescription.objects.get_or_create(
                    prescription_no=pres_no,
                    defaults={
                        "patient": patient,
                        "doctor": request.user,
                        "notes": notes,
                        "next_visit": next_visit,
                    }
                )

                if not created:
                    pres.patient = patient
                    pres.doctor = request.user
                    pres.notes = notes
                    pres.next_visit = next_visit
                    pres.save()

                # ✅ ONLY SAVE DATA (NO STOCK CHANGES)
                for sid, med_name, dose, custom_dose, dur, qty, food in zip(
                    stock_ids, medicine_names, dosages,
                    custom_dosages, durations, quantities, food_timings
                ):

                    if not med_name:
                        continue

                    final_dose = custom_dose if (dose == "Other" and custom_dose) else dose

                    stock_obj = None
                    if sid:
                        try:
                            stock_obj = Stock.objects.get(id=sid)
                        except Stock.DoesNotExist:
                            stock_obj = None

                    PrescriptionItem.objects.create(
                        prescription=pres,
                        stock=stock_obj,
                        medicine_name=med_name,
                        dosage=final_dose or "",
                        duration_days=int(dur or 0),
                        quantity=Decimal(qty or "0"),   # ✅ SAVE AS USER ENTERED
                        food_timing=food or "",
                    )

        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            return redirect("dashboard")

        messages.success(request, f"Prescription {pres.prescription_no} saved successfully!")
        return redirect("dashboard")

    # -------- GET REQUEST --------

    prescription_no = generate_prescription_no()

    stocks = Stock.objects.filter(
        quantity__gt=0
    ).select_related("medicine").order_by("medicine__name")

    patients = Patient.objects.filter(is_active=True)

    return render(request, "prescriptionmgmt/create_prescription.html", {
        "prescription_no": prescription_no,
        "stocks": stocks,
        "patients": patients,
        "today": timezone.localdate(),
    })

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
    })

@login_required
def ajax_get_stock(request):
    """
    Return JSON for a stock id or a search query.
    If stock_id provided -> return details.
    If q provided -> return first 20 matches (name, id, selling price, qty, batch)
    """
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
    pres = get_object_or_404(Prescription, prescription_no=prescription_no)
    items = pres.items.all()
    return render(request, "prescriptionmgmt/print_prescription.html", {
        "prescription": pres,
        "items": items,
    })
