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

    # Today's patients
    todays_patients = Patient.objects.filter(created_at__date=today)
    total_today_patients = todays_patients.count()

    # Attendance Summary
    todays_attendance = Attendance.objects.filter(date=today)
    total_attendance = todays_attendance.count()
    attended_count = todays_attendance.filter(status='present').count()
    attendance_percentage = 0
    if total_attendance > 0:
        attendance_percentage = round((attended_count / total_attendance) * 100)

    # Today's Revenue
    revenue_medical = MedicalBill.objects.filter(bill_date=today).aggregate(total=Sum('total'))['total'] or 0
    revenue_inpatient = InpatientBill.objects.filter(created_at__date=today).aggregate(total=Sum('total'))['total'] or 0
    revenue_outpatient = OutpatientBill.objects.filter(visit_date=today).aggregate(total=Sum('total'))['total'] or 0
    revenue_therapy = TherapyBill.objects.filter(bill_date=today).aggregate(total=Sum('total'))['total'] or 0

    today_revenue = revenue_medical + revenue_inpatient + revenue_outpatient + revenue_therapy

    # Stock Alert
    low_stock_count = Stock.objects.filter(quantity__lte=5).count()

    prescription_no = generate_prescription_no()
    patients = Patient.objects.filter(is_active=True)
    stocks = Stock.objects.filter(quantity__gt=0).select_related("medicine").order_by("medicine__name")

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
    }

    # ✅ WELCOME TOAST MESSAGE (ONLY IF USER IS LOGGED IN)
    # if request.user.is_authenticated:
    #     messages.success(
    #         request,
    #         f"Welcome back, {request.user.get_full_name() or request.user.username} 👋"
    #     )

    return render(request, "ahmsapp/dashboard.html", context)