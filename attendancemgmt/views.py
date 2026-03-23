from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponse
from django.utils import timezone
from django.db import IntegrityError, transaction
from django.core.paginator import Paginator
from django.urls import reverse
from django.db.models import Count, Q
from django.contrib import messages
import csv
from decimal import Decimal
from django.core.paginator import Paginator

from django.conf import settings
User = settings.AUTH_USER_MODEL
from django.contrib.auth import get_user_model
CustomUser = get_user_model()

from .models import Attendance
from datetime import date
from fieldmgmt.models import ActivityHistory

# Helper: today
def today_date():
    return timezone.localdate()


# =====================================================
# ATTENDANCE LIST
# =====================================================
@login_required
def attendance_list(request):
    if not (request.user.is_staff or request.user.has_perm('attendancemgmt.view_attendance')):
        messages.error(request, "You do not have permission to view attendance.")
        return redirect("ahmsapp:dashboard")

    employees_qs = CustomUser.objects.filter(
        is_active=True,
        is_superuser=False
    ).order_by('username')

    # 🔹 Pagination
    paginator = Paginator(employees_qs, 10)
    page_number = request.GET.get("page")
    employees = paginator.get_page(page_number)

    t = today_date()

    qdate = request.GET.get('date')
    if qdate:
        try:
            qdate_parsed = date.fromisoformat(qdate)
        except Exception:
            qdate_parsed = t
            messages.warning(request, "Invalid date selected. Showing today.")
    else:
        qdate_parsed = t

    todays = Attendance.objects.filter(date=qdate_parsed)
    todays_map = {a.user_id: a for a in todays}

    return render(request, "attendancemgmt/attendance_list.html", {
        "employees": employees,
        "todays_map": todays_map,
        "today": t,
        "qdate": qdate_parsed,
    })

# =====================================================
# EMPLOYEE SELF MARK ATTENDANCE
# =====================================================
@login_required
def employee_mark(request):
    if request.method != "POST":
        messages.error(request, "Invalid request method.")
        return HttpResponseBadRequest("Use POST")

    user = request.user
    status = request.POST.get('status') or 'Present'
    the_date = request.POST.get('date')

    try:
        the_date = date.fromisoformat(the_date) if the_date else today_date()
    except Exception:
        the_date = today_date()

    try:
        with transaction.atomic():
            obj, created = Attendance.objects.update_or_create(
                user=user,
                date=the_date,
                defaults={
                    'status': status,
                    'marked_by': request.user
                }
            )
            # Activity History
            ActivityHistory.objects.create(
                user=request.user,
                action="CREATE" if created else "UPDATE",
                module="ATTENDANCE",
                record_id=obj.id,
                description=f"{request.user.username} marked attendance as {status} for {the_date}"
            )

    except IntegrityError:
        messages.error(request, "Could not save attendance. Please try again.")
        return JsonResponse({"error": "Could not save attendance"}, status=500)

    messages.success(request, f"Attendance marked as {obj.status} for {obj.date}")
    return JsonResponse({"ok": True, "status": obj.status, "date": str(obj.date)})


# =====================================================
# ADMIN MARK USER ATTENDANCE
# =====================================================
@login_required
def admin_mark_user(request, user_id):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Invalid request"})

    status = request.POST.get("status")
    date_val = request.POST.get("date")

    try:
        date_val = date.fromisoformat(date_val)
    except Exception:
        date_val = timezone.localdate()

    user = get_object_or_404(CustomUser, id=user_id)

    obj, created = Attendance.objects.update_or_create(
        user=user,
        date=date_val,
        defaults={
            "status": status,
            "marked_by": request.user,
        }
    )
     # Activity History
    ActivityHistory.objects.create(
        user=request.user,
        action="CREATE" if created else "UPDATE",
        module="ATTENDANCE",
        record_id=obj.id,
        description=f"Admin {request.user.username} marked {user.username}'s attendance as {status} for {date_val}"
    )
    return JsonResponse({
        "ok": True,
        "status": status,
        "marked_by": request.user.username,
        "created": created,
    })

# =====================================================
# ATTENDANCE REPORTS
# =====================================================
@login_required
def attendance_reports(request):
    user = request.user
    start = request.GET.get('start')
    end = request.GET.get('end')
    emp_id = request.GET.get('employee')

    today = today_date()
    if not start:
        start = (today - timezone.timedelta(days=30)).isoformat()
    if not end:
        end = today.isoformat()

    try:
        start_d = date.fromisoformat(start)
        end_d = date.fromisoformat(end)
    except Exception:
        start_d = today - timezone.timedelta(days=30)
        end_d = today
        messages.warning(request, "Invalid date range. Showing last 30 days.")

    qs = Attendance.objects.filter(
        date__range=(start_d, end_d)
    ).select_related('user').order_by('-date', 'user__username')

    if emp_id:
        qs = qs.filter(user__id=emp_id)

    if not (user.is_staff or user.has_perm('attendancemgmt.view_attendance')):
        qs = qs.filter(user=user)

    # -------- SUMMARY --------
    summary_qs = qs.values('user__id', 'user__username').annotate(
        present_count=Count('id', filter=Q(status='Present')),
        absent_count=Count('id', filter=Q(status='Absent')),
        total_days=Count('id')
    ).order_by('user__username')

    summary_paginator = Paginator(summary_qs, 10)
    summary_page = request.GET.get('summary_page')
    summary = summary_paginator.get_page(summary_page)

    # -------- RECORDS --------
    records_paginator = Paginator(qs, 10)
    records_page = request.GET.get('records_page')
    records = records_paginator.get_page(records_page)

    employees = CustomUser.objects.filter(
        is_active=True, is_superuser=False
    ).order_by('username')

    context = {
        "summary": summary,
        "records": records,
        "employees": employees,
        "start": start_d,
        "end": end_d,
        "selected_employee": int(emp_id) if emp_id else None,
    }
    return render(request, "attendancemgmt/attendance_reports.html", context)


# =====================================================
# CSV EXPORT
# =====================================================
@login_required
def export_attendance_csv(request):
    user = request.user
    start = request.GET.get('start')
    end = request.GET.get('end')
    emp_id = request.GET.get('employee')

    today = today_date()
    if not start:
        start = (today - timezone.timedelta(days=30)).isoformat()
    if not end:
        end = today.isoformat()

    try:
        start_d = date.fromisoformat(start)
        end_d = date.fromisoformat(end)
    except Exception:
        start_d = today - timezone.timedelta(days=30)
        end_d = today

    qs = Attendance.objects.filter(
        date__range=(start_d, end_d)
    ).select_related('user').order_by('-date', 'user__username')

    if emp_id:
        qs = qs.filter(user__id=emp_id)

    if not (user.is_staff or user.has_perm('attendancemgmt.view_attendance')):
        qs = qs.filter(user=user)

    messages.info(
        request,
        f"Attendance CSV exported from {start_d} to {end_d}"
    )

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        f'attachment; filename="attendance_{start_d}_{end_d}.csv"'
    )

    writer = csv.writer(response)
    writer.writerow([
        'User ID', 'Username', 'Full Name',
        'Date', 'Status', 'Marked By', 'Marked At'
    ])

    for a in qs:
        writer.writerow([
            a.user.id,
            a.user.username,
            a.user.get_full_name() or a.user.username,
            a.date.isoformat(),
            a.status,
            a.marked_by.username if a.marked_by else '',
            a.marked_at.isoformat() if a.marked_at else '',
        ])

    return response
