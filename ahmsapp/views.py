from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import Sum
from django.utils import timezone
from django.contrib import messages
from patientmgmt.models import Patient
from prescriptionmgmt.models import Prescription
from stockmgmt.models import Stock
from patientmgmt.models import Patient
from attendancemgmt.models import Attendance
from billingmgmt.models import MedicalBill, InpatientBill, OutpatientBill, TherapyBill
from stockmgmt.models import Stock
from django.utils.timesince import timesince
from datetime import datetime
from fieldmgmt.models import Adjuvant
# @login_required
# def dashboardview(request):
#     # For now, let’s simulate user_permissions manually.
#     # Later this will come from the Permission model.
#     if request.user.is_superuser:
#         user_permissions = ['patientmgmt', 'attendancemgmt', 'stockmgmt', 'permissionmgmt', 'reportmgmt']
#     else:
#         # Example: limited access
#         user_permissions = ['patientmgmt', 'reportmgmt']

#     return render(request, "ahmsapp/dashboard.html", {
#         "user_permissions": user_permissions
#     })
def generate_prescription_no():
    last = Prescription.objects.order_by('-id').first()
    if last and last.prescription_no.startswith("PR"):
        try:
            n = int(last.prescription_no.replace("PR", ""))
        except Exception:
            n = 0
        return f"PR{n+1:04d}"
    return "PR0001"


def dashboardview(request):

    user_permissions = []
    if request.user.is_authenticated and request.user.menu_permission:
        user_permissions = request.user.menu_permission.split(",")

    today = timezone.localdate()
    adjuvants = Adjuvant.objects.filter(status=True).order_by("name")
    # -------------------------
    # TODAY'S PATIENTS
    # -------------------------
    todays_patients = Patient.objects.filter(created_at__date=today)
    total_today_patients = todays_patients.count()

    # -------------------------
    # ATTENDANCE SUMMARY
    # -------------------------
    todays_attendance = Attendance.objects.filter(date=today)
    total_attendance = todays_attendance.count()
    attended_count = todays_attendance.filter(status='present').count()

    attendance_percentage = 0
    if total_attendance > 0:
        attendance_percentage = round((attended_count / total_attendance) * 100)

    # -------------------------
    # TODAY REVENUE
    # -------------------------
    revenue_medical = MedicalBill.objects.filter(bill_date=today).aggregate(total=Sum('total'))['total'] or 0
    revenue_inpatient = InpatientBill.objects.filter(created_at__date=today).aggregate(total=Sum('total'))['total'] or 0
    revenue_outpatient = OutpatientBill.objects.filter(visit_date=today).aggregate(total=Sum('total'))['total'] or 0
    revenue_therapy = TherapyBill.objects.filter(bill_date=today).aggregate(total=Sum('total'))['total'] or 0

    today_revenue = revenue_medical + revenue_inpatient + revenue_outpatient + revenue_therapy

    # -------------------------
    # STOCK ALERT
    # -------------------------
    low_stock_count = Stock.objects.filter(total_base_quantity__lte=5).count()

    # -------------------------
    # RECENT ACTIVITY (DYNAMIC)
    # -------------------------
    activities = []

    # Latest Patient
    latest_patient = Patient.objects.order_by('-created_at').first()
    if latest_patient:
        activities.append({
            "title": "New Patient Registered",
            "description": latest_patient.patient_name,
            "time": timesince(latest_patient.created_at) + " ago",
            "icon": "person_add",
            "color": "primary",
            "created_at": latest_patient.created_at
        })

    # Latest Medical Bill (bill_date is DATE → convert to datetime)
    latest_medical_bill = MedicalBill.objects.order_by('-bill_date').first()
    if latest_medical_bill:
        bill_datetime = datetime.combine(
            latest_medical_bill.bill_date,
            datetime.min.time()
        )
        bill_datetime = timezone.make_aware(bill_datetime)

        activities.append({
            "title": "Medical Bill Generated",
            "description": f"Invoice #{latest_medical_bill.bill_no}",
            "time": timesince(bill_datetime) + " ago",
            "icon": "receipt_long",
            "color": "success",
            "created_at": bill_datetime
        })

    # Latest Inpatient Bill
    latest_inpatient_bill = InpatientBill.objects.order_by('-created_at').first()
    if latest_inpatient_bill:
        activities.append({
            "title": "Inpatient Bill Generated",
            "description": f"Invoice #{latest_inpatient_bill.bill_no}",
            "time": timesince(latest_inpatient_bill.created_at) + " ago",
            "icon": "receipt_long",
            "color": "info",
            "created_at": latest_inpatient_bill.created_at
        })

    # Low Stock Alert
    low_stock_item = Stock.objects.filter(total_base_quantity__lte=5).select_related("medicine").first()
    if low_stock_item:
        activities.append({
            "title": "Stock Alert",
            "description": f"{low_stock_item.medicine.name} running low",
            "time": "Check inventory",
            "icon": "warning",
            "color": "warning",
            "created_at": timezone.now()
        })

    # Sort safely
    activities = sorted(activities, key=lambda x: x["created_at"], reverse=True)

    # Limit
    activities = activities[:5]

    # -------------------------
    # OTHER DATA
    # -------------------------
    prescription_no = generate_prescription_no()
    patients = Patient.objects.filter(is_active=True)
    stocks = Stock.objects.filter(
    total_base_quantity__gt=0
    ).select_related("medicine").order_by("medicine__name")

    # -------------------------
    # CONTEXT
    # -------------------------
    context = {
        "user_permissions": user_permissions,
        "todays_patients": todays_patients,
        "total_today_patients": total_today_patients,
        "attendance_percentage": attendance_percentage,
        "today_revenue": today_revenue,
        "low_stock_count": low_stock_count,
        "prescription_no": prescription_no,
        "stocks": stocks,
        "patients": patients,
        "activities": activities,
        "adjuvants": adjuvants

    }

    return render(request, "ahmsapp/dashboard.html", context)