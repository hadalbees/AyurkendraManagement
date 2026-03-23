from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseBadRequest
from django.contrib import messages
from django.core.paginator import Paginator
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Department
from django.views import View
from .models import AppointmentType,IPOtherCharge
from .models import Adjuvant

from .models import (
    AyurvedicType,
    ManufacturerMaster,
    SupplierMaster,
    TherapyMaster,
    ActivityHistory
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

        therapy=TherapyMaster.objects.create(
            name=name,
            description=description,
            charges=charges,
            status=status,
        )
        ActivityHistory.objects.create(
            user=request.user,
            action="CREATE",
            module="THERAPY",
            record_id=therapy.id,
            description=f"Therapy #{therapy.id} created by {request.user}"
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
        ActivityHistory.objects.create(
            user=request.user,
            action="UPDATE",
            module="THERAPY",
            record_id=therapy.id,
            description=f"Therapy #{therapy.id} updated by {request.user}"
        )
        messages.success(request, f"Therapy '{therapy.name}' updated successfully.")
        return redirect("fieldmgmt:therapy_list")

    return render(request, "fieldmgmt/therapyedit.html", {
        "therapy": therapy
    })


def therapy_delete(request, id):
    therapy = get_object_or_404(TherapyMaster, id=id)
    therapy.delete()
    ActivityHistory.objects.create(
        user=request.user,
        action="DELETE",
        module="THERAPY",
        record_id=therapy.id,
        description=f"Therapy #{therapy.id} deleted by {request.user}"
    )
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

        ayurvedic=AyurvedicType.objects.create(
            name=name,
            description=description,
            status=status
        )
        ActivityHistory.objects.create(
            user=request.user,
            action="CREATE",
            module="AYURVEDIC TYPE",
            record_id=ayurvedic.id,
            description=f"Ayurvedic type #{ayurvedic.id} created by {request.user}"
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
        ActivityHistory.objects.create(
            user=request.user,
            action="UPDATE",
            module="AYURVEDIC TYPE",
            record_id=obj.id,
            description=f"Ayurvedic type #{obj.id} updated by {request.user}"
        )
        messages.success(request, f"Ayurvedic type '{obj.name}' updated successfully.")
        return redirect("fieldmgmt:ayurvedic_list")

    return render(request, "fieldmgmt/ayurvedic_edit.html", {
        "type": obj
    })


def ayurvedic_delete(request, id):
    obj = get_object_or_404(AyurvedicType, id=id)
    obj.delete()
    ActivityHistory.objects.create(
        user=request.user,
        action="DELETE",
        module="AYURVEDIC TYPE",
        record_id=obj.id,
        description=f"Ayurvedic type #{obj.id} deleted by {request.user}"
    )
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
        supplier = SupplierMaster.objects.create(
            name=request.POST.get("name"),
            phone=request.POST.get("phone"),
            email=request.POST.get("email"),
            address=request.POST.get("address")
        )
        ActivityHistory.objects.create(
            user=request.user,
            action="CREATE",
            module="SUPPLIER",
            record_id=supplier.id,
            description=f"Supplier #{supplier.id} created by {request.user}"
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
        ActivityHistory.objects.create(
            user=request.user,
            action="UPDATE",
            module="SUPPLIER",
            record_id=supplier.id,
            description=f"Supplier #{supplier.id} updated by {request.user}"
        )

        messages.success(request, "Supplier updated successfully.")
        return redirect("fieldmgmt:supplier_list")

    return render(request, "fieldmgmt/supplier_form.html", {
        "supplier": supplier,
        "title": "Edit Supplier"
    })


def supplier_delete(request, pk):
    supplier = get_object_or_404(SupplierMaster, id=pk)
    supplier.delete()
    ActivityHistory.objects.create(
        user=request.user,
        action="DELETE",
        module="SUPPLIER",
        record_id=supplier.id,
        description=f"Supplier type #{supplier.id} deleted by {request.user}"
    )
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
        manufacturer = ManufacturerMaster.objects.create(
            name=request.POST.get("name"),
            phone=request.POST.get("phone"),
            email=request.POST.get("email"),
            address=request.POST.get("address")
        )
        ActivityHistory.objects.create(
            user=request.user,
            action="CREATE",
            module="MANUFACTURER",
            record_id=manufacturer.id,
            description=f"Manufacturer #{manufacturer.id} created by {request.user}"
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
        ActivityHistory.objects.create(
            user=request.user,
            action="UPDATE",
            module="MANUFACTURER",
            record_id=manufacturer.id,
            description=f"Manufacturer #{manufacturer.id} updated by {request.user}"
        )
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


# ==========================
# LIST VIEW
# ==========================
class DepartmentListView(LoginRequiredMixin, View):
    template_name = "fieldmgmt/department_list.html"

    def get(self, request):
        departments = Department.objects.all().order_by("-created_at")
        return render(request, self.template_name, {
            "departments": departments
        })


# ==========================
# ADD VIEW
# ==========================
class DepartmentCreateView(LoginRequiredMixin, View):
    template_name = "fieldmgmt/department_add.html"

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        name = request.POST.get("department_name")
        description = request.POST.get("description")

        if Department.objects.filter(department_name=name).exists():
            messages.error(request, "Department already exists!")
            return redirect("fieldmgmt:department_add")

        department = Department.objects.create(
            department_name=name,
            description=description,
            created_by=request.user
        )
        ActivityHistory.objects.create(
            user=request.user,
            action="CREATE",
            module="DEPARTMENT",
            record_id=department.id,
            description=f"Department #{department.id} created by {request.user}"
        )

        messages.success(request, "Department added successfully!")
        return redirect("fieldmgmt:department_list")


# ==========================
# EDIT VIEW
# ==========================
class DepartmentUpdateView(LoginRequiredMixin, View):
    template_name = "fieldmgmt/department_edit.html"

    def get(self, request, pk):
        department = get_object_or_404(Department, pk=pk)
        return render(request, self.template_name, {
            "department": department
        })

    def post(self, request, pk):
        department = get_object_or_404(Department, pk=pk)

        department.department_name = request.POST.get("department_name")
        department.description = request.POST.get("description")
        department.status = request.POST.get("status") == "on"
        department.save()
        ActivityHistory.objects.create(
            user=request.user,
            action="UPDATE",
            module="DEPARTMENT",
            record_id=department.id,
            description=f"Department #{department.id} updated by {request.user}"
        )

        messages.success(request, "Department updated successfully!")
        return redirect("fieldmgmt:department_list")


# ==========================
# DELETE VIEW
# ==========================
class DepartmentDeleteView(LoginRequiredMixin, View):

    def post(self, request, pk):
        department = get_object_or_404(Department, pk=pk)
        department.delete()
        ActivityHistory.objects.create(
            user=request.user,
            action="DELETE",
            module="DEPARTMENT",
            record_id=department.id,
            description=f"Department #{department.id} deleted by {request.user}"
        )
        messages.success(request, "Department deleted successfully!")
        return redirect("fieldmgmt:department_list")
    
    
def appointment_type_list(request):
    types = AppointmentType.objects.all().order_by("-id")
    return render(request, "fieldmgmt/appointment_type_list.html", {"types": types})


def appointment_type_add(request):
    if request.method == "POST":
        name = request.POST.get("appointment_type_name")
        description = request.POST.get("description")
        duration = request.POST.get("duration_minutes")

        appoinment = AppointmentType.objects.create(
            name=name,
            description=description,
            duration_minutes=duration
        )
        ActivityHistory.objects.create(
            user=request.user,
            action="CREATE",
            module="APPOINMENT",
            record_id=appoinment.id,
            description=f"Appoinment #{appoinment.id} created by {request.user}"
        )

        messages.success(request, "Appointment type added successfully.")
        return redirect("fieldmgmt:appointment_type_list")

    return render(request, "fieldmgmt/appointment_type_form.html")


def appointment_type_edit(request, pk):
    obj = get_object_or_404(AppointmentType, pk=pk)

    if request.method == "POST":
        obj.name = request.POST.get("appointment_type_name")
        obj.description = request.POST.get("description")
        obj.duration_minutes = request.POST.get("duration_minutes")
        obj.status = True if request.POST.get("status") else False
        obj.save()
        ActivityHistory.objects.create(
            user=request.user,
            action="CREATE",
            module="APPOINMENT",
            record_id=obj.id,
            description=f"Appoinment #{obj.id} updated by {request.user}"
        )

        messages.success(request, "Appointment type updated.")
        return redirect("fieldmgmt:appointment_type_list")

    return render(request, "fieldmgmt/appointment_type_form.html", {"obj": obj})


def appointment_type_delete(request, pk):
    obj = get_object_or_404(AppointmentType, pk=pk)
    obj.delete()
    ActivityHistory.objects.create(
            user=request.user,
            action="DELETE",
            module="APPOINMENT",
            record_id=obj.id,
            description=f"Appoinment #{obj.id} deleted by {request.user}"
        )
    messages.success(request, "Appointment type deleted.")
    return redirect("fieldmgmt:appointment_type_list")


def ip_othercharge_list(request):

    items = IPOtherCharge.objects.all().order_by("-id")

    paginator = Paginator(items, 10)
    page = request.GET.get("page")

    items = paginator.get_page(page)

    return render(
        request,
        "fieldmgmt/ip_othercharge_list.html",
        {"items": items},
    )


def ip_othercharge_add(request):

    if request.method == "POST":

        name = request.POST.get("name")
        type = request.POST.get("type")
        price = request.POST.get("unit_price")
        description = request.POST.get("description")
        status = True if request.POST.get("status") else False

        ipotherCharge = IPOtherCharge.objects.create(
            name=name,
            type=type,
            unit_price=price,
            description=description,
            status=status,
        )
        ActivityHistory.objects.create(
            user=request.user,
            action="CREATE",
            module="IP-OTHER CHARGE",
            record_id=ipotherCharge.id,
            description=f"IPOtherCharge #{ipotherCharge.id} created by {request.user}"
        )

        messages.success(request, "Other Charge added successfully")

        return redirect("fieldmgmt:ip_othercharge_list")

    return render(request, "fieldmgmt/ip_othercharge_form.html")


def ip_othercharge_edit(request, pk):

    obj = get_object_or_404(IPOtherCharge, pk=pk)

    if request.method == "POST":

        obj.name = request.POST.get("name")
        obj.type = request.POST.get("type")
        obj.unit_price = request.POST.get("unit_price")
        obj.description = request.POST.get("description")
        obj.status = True if request.POST.get("status") else False

        obj.save()
        ActivityHistory.objects.create(
            user=request.user,
            action="UPDATE",
            module="IP-OTHER CHARGE",
            record_id=obj.id,
            description=f"IPOtherCharge #{obj.id} updated by {request.user}"
        )

        messages.success(request, "Other Charge updated successfully")

        return redirect("fieldmgmt:ip_othercharge_list")

    return render(
        request,
        "fieldmgmt/ip_othercharge_form.html",
        {"obj": obj},
    )


def ip_othercharge_delete(request, pk):

    obj = get_object_or_404(IPOtherCharge, pk=pk)
    obj.delete()
    ActivityHistory.objects.create(
        user=request.user,
        action="DELETE",
        module="IP-OTHER CHARGE",
        record_id=obj.id,
        description=f"IPOtherCharge #{obj.id} deleted by {request.user}"
    )
    messages.success(request, "Other Charge deleted successfully")

    return redirect("fieldmgmt:ip_othercharge_list")


def adjuvant_list(request):
    adjuvants = Adjuvant.objects.all()
    return render(request, "fieldmgmt/adjuvant_list.html", {"adjuvants": adjuvants})


def adjuvant_add(request):
    if request.method == "POST":
        name = request.POST.get("name")
        description = request.POST.get("description")

        adjuvant= Adjuvant.objects.create(
            name=name,
            description=description
        )
        ActivityHistory.objects.create(
            user=request.user,
            action="CREATE",
            module="ADJUVANT",
            record_id=adjuvant.id,
            description=f"Adjuvant #{adjuvant.id} created by {request.user}"
        )
        return redirect("fieldmgmt:adjuvant_list")

    return render(request, "fieldmgmt/adjuvant_form.html")


def adjuvant_edit(request, id):
    adjuvant = get_object_or_404(Adjuvant, id=id)

    if request.method == "POST":
        adjuvant.name = request.POST.get("name")
        adjuvant.description = request.POST.get("description")
        adjuvant.save()
        ActivityHistory.objects.create(
            user=request.user,
            action="UPDATE",
            module="ADJUVANT",
            record_id=adjuvant.id,
            description=f"Adjuvant #{adjuvant.id} updated by {request.user}"
        )

        return redirect("fieldmgmt:adjuvant_list")

    return render(request, "fieldmgmt/adjuvant_form.html", {"adjuvant": adjuvant})


def adjuvant_delete(request, id):
    adjuvant = get_object_or_404(Adjuvant, id=id)
    adjuvant.delete()
    ActivityHistory.objects.create(
        user=request.user,
        action="DELETE",
        module="ADJUVANT",
        record_id=adjuvant.id,
        description=f"Adjuvant #{adjuvant.id} deleted by {request.user}"
    )
    return redirect("fieldmgmt:adjuvant_list")