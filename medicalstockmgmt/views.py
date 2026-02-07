from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from django.contrib import messages
from stockmgmt.models import Medicine, Stock
from medicalstockmgmt.models import MedicalStock   # new medical stock table

def get_stock_details(request):
    medicine_id = request.GET.get("medicine_id")

    if not medicine_id:
        return JsonResponse({"error": "No medicine selected"}, status=400)

    try:
        stock = Stock.objects.filter(medicine_id=medicine_id).order_by('-expiry_date').first()
        # You can also choose nearest expiry or highest qty
    except Stock.DoesNotExist:
        return JsonResponse({"error": "No stock found"}, status=404)

    return JsonResponse({
        "batch_number": stock.batch_number,
        "selling_price": float(stock.selling_price),
        "quantity": float(stock.quantity),
        "manufacture_date": stock.manufacture_date,
        "expiry_date": stock.expiry_date,
    })
def medicalstockhome(request):
    stocks = MedicalStock.objects.all().order_by("-created_at")
    return render(request, 'medicalstockmgmt/medicalstockhome.html', {
        "stocks": stocks,
        "today": timezone.localdate(),
    })

def addstock(request):
    if request.method == "POST":

        medicine_id = request.POST.get("medicine")
        batch = request.POST.get("batch")
        qty = request.POST.get("quantity")
        selling_price = request.POST.get("selling_price")
        mfg_date = request.POST.get("manufacture_date")
        exp_date = request.POST.get("expiry_date")

        # Validate medicine
        try:
            medicine = Medicine.objects.get(id=medicine_id)
        except Medicine.DoesNotExist:
            messages.error(request, "Invalid medicine selection.")
            return redirect("medicalstockmgmt:add_stock")

        # Save NEW medical stock entry
        MedicalStock.objects.create(
            medicine=medicine,
            batch_number=batch,
            quantity=qty,
            selling_price=selling_price,
            manufacture_date=mfg_date,
            expiry_date=exp_date,
        )

        messages.success(request, "Medical stock added successfully.")
        return redirect("medicalstockmgmt:medicalstockhome")

    medicines = Medicine.objects.all()

    return render(request, "medicalstockmgmt/add_stock.html", {
        "medicines": medicines,
        "today": timezone.localdate(),
    })
    # ============================
#  EDIT MEDICAL STOCK
# ============================
def edit_stock(request, id):
    stock = get_object_or_404(MedicalStock, id=id)
    return render(request, "medicalstockmgmt/edit_stock.html", {"stock": stock})


# ============================
#  UPDATE MEDICAL STOCK
# ============================
def update_stock(request, id):
    stock = get_object_or_404(MedicalStock, id=id)

    if request.method == "POST":
        stock.quantity = request.POST.get("quantity")
        stock.save()

        messages.success(request, "Stock updated successfully!")
        return redirect("medicalstockmgmt:medicalstockhome")

    return redirect("medicalstockmgmt:medicalstockhome")


# ============================
#  DELETE MEDICAL STOCK
# ============================
def delete_stock(request, id):
    stock = get_object_or_404(MedicalStock, id=id)
    stock.delete()
    messages.success(request, "Stock deleted successfully!")
    return redirect("medicalstockmgmt:medicalstockhome")