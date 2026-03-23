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
from fieldmgmt.models import Adjuvant

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

        stock_ids = request.POST.getlist("stock_id[]")
        medicine_names = request.POST.getlist("medicine_name[]")
        dosages = request.POST.getlist("dosage[]")
        durations = request.POST.getlist("duration[]")
        quantities = request.POST.getlist("quantity[]")
        food_timings = request.POST.getlist("food_timing[]")
        adjuvants = request.POST.getlist("adjuvant[]")

        if not patient_id:
            messages.error(request, "Patient ID required.")
            return redirect("dashboard")

        try:
            patient = Patient.objects.get(patient_unique_id=patient_id)
        except Patient.DoesNotExist:
            messages.error(request, "Invalid Patient ID.")
            return redirect("dashboard")

        # Create prescription
        prescription = Prescription.objects.create(
            prescription_no=pres_no,
            patient=patient,
            doctor=request.user,
            notes=notes,
            next_visit=next_visit,
        )

        # Save medicines
        for sid, med, dose, dur, qty, food, adj in zip(
            stock_ids,
            medicine_names,
            dosages,
            durations,
            quantities,
            food_timings,
            adjuvants
        ):

            if not med:
                continue

            adjuvant_obj = None
            if adj:
                try:
                    adjuvant_obj = Adjuvant.objects.get(id=adj)
                except Adjuvant.DoesNotExist:
                    pass

            PrescriptionItem.objects.create(
                prescription=prescription,
                stock_id=sid if sid else None,
                medicine_name=med,
                dosage=dose or "",
                duration_days=int(dur or 0),
                quantity=Decimal(qty or "0"),
                food_timing=food or "",
                adjuvant=adjuvant_obj
            )

        messages.success(request, "Prescription saved successfully!")
        return redirect("dashboard")

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
