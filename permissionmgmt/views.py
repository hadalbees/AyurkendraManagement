from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from rolemgmt.models import Role
from authentication.models import CustomUser
from django.views import View
from django.http import JsonResponse
from django.http import HttpResponse
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer, Image
)
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Table
from reportlab.platypus import SimpleDocTemplate
from django.utils.timezone import now
import os
from billingmgmt.models import HospitalSetting
from reportlab.lib.utils import ImageReader
from fieldmgmt.models import ActivityHistory
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

        # ✅ Fix: consistent permission format
        permission_str = ",".join(set(permissions))

        role = Role.objects.filter(id=role_id).first()

        if not username:
            messages.error(request, "Please enter a valid name.")
            return redirect("permissionhome")

        if not password:
            messages.error(request, "Password is required.")
            return redirect("permissionhome")

        user = CustomUser.objects.create(
            username=username,
            email=email,
            mobile_number=mobile_number,
            gender=gender,
            role=role,
            menu_permission=permission_str,
        )

        user.set_password(password)
        user.save()

        ActivityHistory.objects.create(
            user=request.user,
            action="CREATE",
            module="STAFF",
            record_id=user.id,
            description=f"Staff #{user.id} created by {request.user}"
        )

        messages.success(request, f"Staff '{username}' added successfully!")
        return redirect("permissionhome")

    return render(request, "permissionmgmt/staffaddform.html", {"roles": roles})

def staffeditform(request, pk):
    staff = get_object_or_404(CustomUser, pk=pk)
    roles = Role.objects.all()

    # ✅ Convert string → list
    selected_permissions = staff.menu_permission.split(",") if staff.menu_permission else []

    if request.method == "POST":
        staff.username = request.POST.get("name")
        staff.email = request.POST.get("email")
        staff.mobile_number = request.POST.get("mobile_number")
        staff.gender = request.POST.get("gender")

        role_id = request.POST.get("role")
        staff.role = Role.objects.filter(id=role_id).first()

        password = request.POST.get("password")
        if password:
            staff.set_password(password)

        permissions = request.POST.getlist("permission")

        # ✅ remove duplicates
        staff.menu_permission = ",".join(set(permissions))

        staff.save()

        ActivityHistory.objects.create(
            user=request.user,
            action="UPDATE",
            module="STAFF",
            record_id=staff.id,
            description=f"Staff #{staff.id} updated by {request.user}"
        )

        messages.success(request, f"Staff '{staff.username}' updated successfully!")
        return redirect("permissionhome")

    return render(request, "permissionmgmt/staffeditform.html", {
        "roles": roles,
        "staff": staff,
        "selected_permissions": selected_permissions
    })
def staff_delete_view(request, pk):
    if request.method == "POST":
        staff = get_object_or_404(CustomUser, pk=pk)

        if staff.is_superuser:
            messages.error(request, "Cannot delete admin user")
            return redirect("permissionhome")

        staff.delete()

        ActivityHistory.objects.create(
            user=request.user,
            action="DELETE",
            module="STAFF",
            record_id=pk,
            description=f"Staff #{pk} deleted by {request.user}"
        )

        messages.success(request, "Staff deleted successfully!")

    return redirect("permissionhome")


def toggle_staff_status(request, pk):
    if request.method == "POST":
        staff = get_object_or_404(CustomUser, pk=pk)
        # Toggle the status
        staff.is_active = not staff.is_active
        staff.save()
        return JsonResponse({"success": True, "is_active": staff.is_active})
    return JsonResponse({"success": False}, status=400)


def staff_export_pdf(request):

    hospital = HospitalSetting.objects.first()

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="staff_list.pdf"'

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

    # ================= TITLE CENTER =================

    title_style = ParagraphStyle(
        name="TitleCenter",
        parent=styles["Heading1"],
        alignment=1,  # Center
        fontSize=20,
        spaceAfter=6,
    )

    date_style = ParagraphStyle(
        name="DateSmallCenter",
        parent=styles["Normal"],
        alignment=1,  # Center
        fontSize=9,
        textColor=colors.grey,
    )

    generated_date = now().strftime("%d %B %Y %I:%M %p")

    elements.append(Paragraph("Staff Report", title_style))
    elements.append(Paragraph(f"{generated_date}", date_style))
    elements.append(Spacer(1, 0.5 * inch))

    # ================= TABLE =================

    staffs = CustomUser.objects.filter(
        is_superuser=False,
        is_staff=False
    ).order_by("id")

    data = [["#", "Name", "Email", "Mobile", "Role", "Gender"]]

    for i, s in enumerate(staffs, start=1):
        data.append([
            str(i),
            s.username,
            s.email,
            s.mobile_number or "",
            s.role.role_name if s.role else "No Role",
            s.gender or "",
        ])

    col_widths = [
        usable_width * 0.07,
        usable_width * 0.18,
        usable_width * 0.30,
        usable_width * 0.15,
        usable_width * 0.15,
        usable_width * 0.15,
    ]

    table = Table(data, colWidths=col_widths, repeatRows=1)

    table_style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1f2937")),
        ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BOTTOMPADDING', (0,0), (-1,0), 10),
    ])

    # Zebra Striping
    for row in range(1, len(data)):
        if row % 2 == 0:
            table_style.add('BACKGROUND', (0,row), (-1,row), colors.whitesmoke)

    table.setStyle(table_style)
    elements.append(table)

    # ================= FOOTER + LOGO WATERMARK =================

    def add_footer_and_watermark(canvas, doc):

        # Page number
        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(
            page_width - 40,
            20,
            f"Page {doc.page}"
        )

        # Center Logo Watermark
        if hospital and hospital.hospital_logo:

            logo_path = hospital.hospital_logo.path
            watermark = ImageReader(logo_path)

            canvas.saveState()

            # Very light opacity
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

def check_email(request):
    email = request.GET.get('email')
    exists = CustomUser.objects.filter(email=email).exists()
    return JsonResponse({'exists': exists})
