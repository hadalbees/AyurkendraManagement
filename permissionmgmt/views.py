from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from rolemgmt.models import Role
from authentication.models import CustomUser
from django.views import View
from django.http import JsonResponse
# from django.contrib.auth.decorators import login_required

# @login_required
def permissionhome(request):
    staff_qs = CustomUser.objects.filter(
        is_superuser=False,
        is_staff=False
    ).order_by("id")

    paginator = Paginator(staff_qs, 10)   # ✅ 10 records per page
    page_number = request.GET.get("page")
    staffs = paginator.get_page(page_number)

    return render(
        request,
        "permissionmgmt/permissionhome.html",
        {"staffs": staffs}
    )
def staffaddform(request):
    roles = Role.objects.all()

    if request.method == "POST":
        username = request.POST.get("name")
        email = request.POST.get("email")
        mobile_number = request.POST.get("mobile_number")
        gender = request.POST.get("gender")
        role_id = request.POST.get("role")
        password = request.POST.get("password")
        permissions = request.POST.getlist("permission")

        permission_str = ",".join(permissions)

        role = Role.objects.get(id=role_id) if role_id else None

        if username:
            # ✅ Use create() instead of create_user()
            user = CustomUser.objects.create(
                username=username,
                email=email,
                mobile_number=mobile_number,
                gender=gender,
                role=role,
                menu_permission=permission_str,
            )
            user.set_password(password)  # ✅ hash password properly
            user.save()

            messages.success(request, f"Staff '{username}' added successfully!")
            return redirect("permissionhome")
        else:
            messages.error(request, "Please enter a valid name.")

    return render(request, "permissionmgmt/staffaddform.html", {"roles": roles})

def staffeditform(request, pk):
    staff = get_object_or_404(CustomUser, pk=pk)
    roles = Role.objects.all()

    # Selected permissions as list
    selected_permissions = staff.menu_permission.split(",") if staff.menu_permission else []

    # Full permissions list
    PERMISSIONS_LIST = [
        "dashboard","medicalbilling","inpatientbilling","outpatientbilling",
        "reportsdashboard","allreports","rolemanagement","staffmanagement",
        "attendancemanagement","stockmanagement","patientdashboard","registerpatient",
        "appoinments","therapy","ayurvedictype","suppliers","manufacturers",'prescription','accountmanagement','sendmessage'
    ]

    # Display-friendly permissions (tuple: value, label)
    PERMISSIONS_DISPLAY = [(p, p.replace("_"," ").title()) for p in PERMISSIONS_LIST]

    if request.method == "POST":
        staff.username = request.POST.get("name")
        staff.email = request.POST.get("email")
        staff.mobile_number = request.POST.get("mobile_number")
        staff.gender = request.POST.get("gender")
        staff.role_id = request.POST.get("role")

        password = request.POST.get("password")
        if password:
            staff.set_password(password)

        permissions = request.POST.getlist("permission")
        staff.menu_permission = ",".join(permissions)

        staff.save()
        messages.success(request, f"Staff '{staff.username}' updated successfully!")
        return redirect("permissionhome")

    return render(request, "permissionmgmt/staffeditform.html", {
        "roles": roles,
        "staff": staff,
        "selected_permissions": selected_permissions,
        "permissions_list": PERMISSIONS_DISPLAY
    })
def staff_delete_view(request, pk):
    staff = get_object_or_404(CustomUser, pk=pk)
    staff.is_active = False   # ✅ Use built-in field
    staff.save()
    messages.success(request, f"Staff '{staff.username}' deleted successfully!")
    return redirect("permissionhome")


def toggle_staff_status(request, pk):
    if request.method == "POST":
        staff = get_object_or_404(CustomUser, pk=pk)
        # Toggle the status
        staff.is_active = not staff.is_active
        staff.save()
        return JsonResponse({"success": True, "is_active": staff.is_active})
    return JsonResponse({"success": False}, status=400)