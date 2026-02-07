from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseBadRequest
from django.contrib import messages
from django.core.paginator import Paginator

from .models import (
    AyurvedicType,
    ManufacturerMaster,
    SupplierMaster,
    TherapyMaster
)

# ==================================================
# THERAPY
# ==================================================

def therapy_list(request):
    qs = TherapyMaster.objects.all().order_by('-id')

    paginator = Paginator(qs, 10)  # 10 per page
    page_number = request.GET.get("page")
    therapies = paginator.get_page(page_number)

    return render(request, "fieldmgmt/therapylist.html", {
        "therapies": therapies
    })


def therapy_add(request):
    if request.method == "POST":
        name = request.POST.get("name")
        description = request.POST.get("description")
        charges = request.POST.get("charges")
        status = request.POST.get("status") == "on"

        if not name or not charges:
            messages.error(request, "Therapy name and charges are required.")
            return redirect("fieldmgmt:therapy_add")

        TherapyMaster.objects.create(
            name=name,
            description=description,
            charges=charges,
            status=status,
        )

        messages.success(request, f"Therapy '{name}' added successfully.")
        return redirect("fieldmgmt:therapy_list")

    return render(request, "fieldmgmt/therapyadd.html")



def therapy_edit(request, id):
    therapy = get_object_or_404(TherapyMaster, id=id)

    if request.method == "POST":
        therapy.name = request.POST.get("name")
        therapy.description = request.POST.get("description")
        therapy.charges = request.POST.get("charges")
        therapy.status = request.POST.get("status") == "on"
        therapy.save()

        messages.success(request, f"Therapy '{therapy.name}' updated successfully.")
        return redirect("fieldmgmt:therapy_list")

    return render(request, "fieldmgmt/therapyedit.html", {
        "therapy": therapy
    })


def therapy_delete(request, id):
    therapy = get_object_or_404(TherapyMaster, id=id)
    therapy.delete()

    messages.success(request, "Therapy deleted successfully.")
    return redirect("fieldmgmt:therapy_list")


# ==================================================
# AYURVEDIC TYPE
# ==================================================

def ayurvedic_list(request):
    qs = AyurvedicType.objects.all().order_by('-id')

    paginator = Paginator(qs, 10)  # 10 per page
    page_number = request.GET.get("page")
    types = paginator.get_page(page_number)

    return render(request, "fieldmgmt/ayurvedic_list.html", {
        "types": types
    })


def ayurvedic_add(request):
    if request.method == "POST":
        name = request.POST.get("name")
        description = request.POST.get("description")
        status = request.POST.get("status") == "on"

        if not name:
            messages.error(request, "Ayurvedic type name is required.")
            return redirect("fieldmgmt:ayurvedic_add")

        if AyurvedicType.objects.filter(name=name).exists():
            messages.error(request, "This Ayurvedic type already exists.")
            return redirect("fieldmgmt:ayurvedic_add")

        AyurvedicType.objects.create(
            name=name,
            description=description,
            status=status
        )

        messages.success(request, f"Ayurvedic type '{name}' added successfully.")
        return redirect("fieldmgmt:ayurvedic_list")

    return render(request, "fieldmgmt/ayurvedic_add.html")


def ayurvedic_edit(request, id):
    obj = get_object_or_404(AyurvedicType, id=id)

    if request.method == "POST":
        obj.name = request.POST.get("name")
        obj.description = request.POST.get("description")
        obj.status = request.POST.get("status") == "on"
        obj.save()

        messages.success(request, f"Ayurvedic type '{obj.name}' updated successfully.")
        return redirect("fieldmgmt:ayurvedic_list")

    return render(request, "fieldmgmt/ayurvedic_edit.html", {
        "type": obj
    })


def ayurvedic_delete(request, id):
    obj = get_object_or_404(AyurvedicType, id=id)
    obj.delete()

    messages.success(request, "Ayurvedic type deleted successfully.")
    return redirect("fieldmgmt:ayurvedic_list")


# ==================================================
# SUPPLIER
# ==================================================

def supplier_list(request):
    qs = SupplierMaster.objects.all().order_by('-id')

    paginator = Paginator(qs, 10)  # 10 suppliers per page
    page_number = request.GET.get("page")
    suppliers = paginator.get_page(page_number)

    return render(request, "fieldmgmt/supplier_list.html", {
        "suppliers": suppliers
    })

def supplier_add(request):
    if request.method == "POST":
        SupplierMaster.objects.create(
            name=request.POST.get("name"),
            phone=request.POST.get("phone"),
            email=request.POST.get("email"),
            address=request.POST.get("address")
        )

        messages.success(request, "Supplier added successfully.")
        return redirect("fieldmgmt:supplier_list")

    return render(request, "fieldmgmt/supplier_form.html", {
        "title": "Add Supplier"
    })


def supplier_edit(request, pk):
    supplier = get_object_or_404(SupplierMaster, id=pk)

    if request.method == "POST":
        supplier.name = request.POST.get("name")
        supplier.phone = request.POST.get("phone")
        supplier.email = request.POST.get("email")
        supplier.address = request.POST.get("address")
        supplier.save()

        messages.success(request, "Supplier updated successfully.")
        return redirect("fieldmgmt:supplier_list")

    return render(request, "fieldmgmt/supplier_form.html", {
        "supplier": supplier,
        "title": "Edit Supplier"
    })


def supplier_delete(request, pk):
    supplier = get_object_or_404(SupplierMaster, id=pk)
    supplier.delete()

    messages.success(request, "Supplier deleted successfully.")
    return redirect("fieldmgmt:supplier_list")


# ==================================================
# MANUFACTURER
# ==================================================

def manufacturer_list(request):
    qs = ManufacturerMaster.objects.all().order_by('-id')

    paginator = Paginator(qs, 10)  # 10 manufacturers per page
    page_number = request.GET.get("page")
    manufacturers = paginator.get_page(page_number)

    return render(request, "fieldmgmt/manufacturer_list.html", {
        "manufacturers": manufacturers
    })


def manufacturer_add(request):
    if request.method == "POST":
        ManufacturerMaster.objects.create(
            name=request.POST.get("name"),
            phone=request.POST.get("phone"),
            email=request.POST.get("email"),
            address=request.POST.get("address")
        )

        messages.success(request, "Manufacturer added successfully.")
        return redirect("fieldmgmt:manufacturer_list")

    return render(request, "fieldmgmt/manufacturer_form.html", {
        "title": "Add Manufacturer"
    })


def manufacturer_edit(request, pk):
    manufacturer = get_object_or_404(ManufacturerMaster, id=pk)

    if request.method == "POST":
        manufacturer.name = request.POST.get("name")
        manufacturer.phone = request.POST.get("phone")
        manufacturer.email = request.POST.get("email")
        manufacturer.address = request.POST.get("address")
        manufacturer.save()

        messages.success(request, "Manufacturer updated successfully.")
        return redirect("fieldmgmt:manufacturer_list")

    return render(request, "fieldmgmt/manufacturer_form.html", {
        "manufacturer": manufacturer,
        "title": "Edit Manufacturer"
    })


def manufacturer_delete(request, pk):
    manufacturer = get_object_or_404(ManufacturerMaster, id=pk)
    manufacturer.delete()

    messages.success(request, "Manufacturer deleted successfully.")
    return redirect("fieldmgmt:manufacturer_list")
