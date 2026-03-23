from django.shortcuts import render,redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.db.models import Value, DecimalField
from django.db.models.functions import Cast
from django.db.models import Sum
from django.contrib import messages
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from django.core.paginator import Paginator
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from itertools import chain
from collections import defaultdict
import calendar
from datetime import date
from itertools import chain
from billingmgmt.models import (
    MedicalBill,
    TherapyBill,
    InpatientBill,
    OutpatientBill
)
from accountmgmt.models import Expense
from fieldmgmt.models import ActivityHistory

from billingmgmt.models import MedicalBill, InpatientBill, OutpatientBill, TherapyBill
# from accountmgmt.models import Expense  # create this model if not exists

@login_required
def account_dashboard(request):
    today = date.today()

    # ---- Income ----
    medical_income = MedicalBill.objects.aggregate(
        total=Sum("total")
    )["total"] or 0

    inpatient_income = InpatientBill.objects.aggregate(
        total=Sum("total")
    )["total"] or 0

    outpatient_income = OutpatientBill.objects.aggregate(
        total=Sum("total")
    )["total"] or 0

    therapy_income = TherapyBill.objects.aggregate(
        total=Sum("total")
    )["total"] or 0

    # Convert to whole numbers
    medical_income = int(round(medical_income))
    inpatient_income = int(round(inpatient_income))
    outpatient_income = int(round(outpatient_income))
    therapy_income = int(round(therapy_income))

    total_income = (
        medical_income +
        inpatient_income +
        outpatient_income +
        therapy_income
    )

    # ---- Expenses (DYNAMIC) ----
    total_expense = Expense.objects.aggregate(
        total=Sum("amount")
    )["total"] or 0

    total_expense = int(round(total_expense))

    # ---- Profit ----
    profit = total_income - total_expense

    context = {
        "medical_income": medical_income,
        "inpatient_income": inpatient_income,
        "outpatient_income": outpatient_income,
        "therapy_income": therapy_income,
        "total_income": total_income,
        "total_expense": total_expense,
        "profit": profit,
    }

    return render(
        request,
        "accountmgmt/account_dashboard.html",
        context
    )

def income_list(request):

    medical_bills = MedicalBill.objects.all()
    inpatient_bills = InpatientBill.objects.all()
    outpatient_bills = OutpatientBill.objects.all()
    therapy_bills = TherapyBill.objects.all()

    # ===== TOTALS =====
    total_medical = medical_bills.aggregate(total=Sum('total'))['total'] or 0
    total_inpatient = inpatient_bills.aggregate(total=Sum('total'))['total'] or 0
    total_outpatient = outpatient_bills.aggregate(total=Sum('total'))['total'] or 0
    total_therapy = therapy_bills.aggregate(total=Sum('total'))['total'] or 0

    # ===== NORMALIZE BILL TYPE + DATE (FIX) =====
    for b in medical_bills:
        b.bill_type = "Medical"
        b.display_date = b.bill_date

    for b in inpatient_bills:
        b.bill_type = "Inpatient"
        b.display_date = b.admit_date

    for b in outpatient_bills:
        b.bill_type = "Outpatient"
        b.display_date = b.visit_date

    for b in therapy_bills:
        b.bill_type = "Therapy"
        b.display_date = b.bill_date

    # ===== MERGE ALL =====
    all_bills = list(chain(
        medical_bills,
        inpatient_bills,
        outpatient_bills,
        therapy_bills
    ))

    all_bills.sort(key=lambda x: x.display_date, reverse=True)

    paginator = Paginator(all_bills, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    # ===== MONTHLY SUMMARY =====
    monthly_data = defaultdict(float)

    def add_monthly(queryset, date_field):
        for row in queryset.annotate(month=TruncMonth(date_field)) \
                           .values("month") \
                           .annotate(total=Sum("total")):
            if row["month"]:
                m = calendar.month_abbr[row["month"].month]
                monthly_data[m] += float(row["total"] or 0)

    add_monthly(medical_bills, "bill_date")
    add_monthly(inpatient_bills, "admit_date")
    add_monthly(outpatient_bills, "visit_date")
    add_monthly(therapy_bills, "bill_date")

    months = list(calendar.month_abbr)[1:]
    monthly_income = [monthly_data[m] for m in months]

    return render(request, "accountmgmt/income_list.html", {
        "page_obj": page_obj,
        "total_medical": total_medical,
        "total_inpatient": total_inpatient,
        "total_outpatient": total_outpatient,
        "total_therapy": total_therapy,
        "months": months,
        "monthly_income": monthly_income,
    })

def expense_list(request):

    expenses = Expense.objects.all().order_by("-expense_date")

    from_date = request.GET.get("from_date")
    to_date = request.GET.get("to_date")
    category = request.GET.get("category")

    # ===== FILTERS =====
    if from_date and to_date:
        expenses = expenses.filter(expense_date__range=[from_date, to_date])

    if category:
        expenses = expenses.filter(category=category)

    # ===== TOTAL =====
    total_expense = expenses.aggregate(total=Sum("amount"))["total"] or 0
    total_expense = int(round(total_expense))

    # ===== PDF EXPORT =====
    if "export_pdf" in request.GET:
        return export_expense_pdf(expenses, from_date, to_date, total_expense)

    # ===== PAGINATION =====
    paginator = Paginator(expenses, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # ===== MONTHLY EXPENSE CHART =====
    monthly_map = defaultdict(float)

    for row in Expense.objects.annotate(
        month=TruncMonth("expense_date")
    ).values("month").annotate(total=Sum("amount")):
        if row["month"]:
            m = calendar.month_abbr[row["month"].month]
            monthly_map[m] += float(row["total"] or 0)

    months = list(calendar.month_abbr)[1:]
    monthly_expense = [monthly_map[m] for m in months]

    context = {
        "page_obj": page_obj,
        "total_expense": total_expense,
        "from_date": from_date,
        "to_date": to_date,
        "category": category,
        "category_choices": Expense.CATEGORY_CHOICES,
        "months": months,
        "monthly_expense": monthly_expense,
    }

    return render(request, "accountmgmt/expense_list.html", context)


def export_expense_pdf(expenses, from_date, to_date, total_expense):
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="Expense_List.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    y = height - 40

    # ---- Title ----
    p.setFont("Helvetica-Bold", 14)
    p.drawString(40, y, "Expense Report")
    y -= 20

    p.setFont("Helvetica", 10)
    if from_date and to_date:
        p.drawString(40, y, f"Period: {from_date} to {to_date}")
        y -= 20

    # ---- Table Header ----
    p.setFont("Helvetica-Bold", 10)
    p.drawString(40, y, "Date")
    p.drawString(120, y, "Category")
    p.drawString(260, y, "Description")
    p.drawString(470, y, "Amount")
    y -= 15

    p.line(40, y, 550, y)
    y -= 15

    # ---- Table Rows ----
    p.setFont("Helvetica", 10)
    for exp in expenses:
        if y < 60:
            p.showPage()
            y = height - 40

        p.drawString(40, y, exp.expense_date.strftime("%d-%m-%Y"))
        p.drawString(120, y, str(exp.category or ""))
        p.drawString(260, y, exp.description[:40])
        p.drawRightString(530, y, f"{exp.amount}")
        y -= 15

    # ---- Total ----
    y -= 10
    p.line(350, y, 550, y)
    y -= 15
    p.setFont("Helvetica-Bold", 11)
    p.drawRightString(530, y, f"Total : ₹ {total_expense}")

    p.showPage()
    p.save()
    return response


def expense_add(request):
    if request.method == "POST":
        expense = Expense.objects.create(
            expense_date=request.POST.get("expense_date"),
            category=request.POST.get("category"),
            description=request.POST.get("description"),
            amount=request.POST.get("amount"),
            attachment=request.FILES.get("attachment"),
            payment_mode=request.POST.get("payment_mode"),
            paid_by=request.user,
        )
        # Save Activity History
        ActivityHistory.objects.create(
            user=request.user,
            action="CREATE",
            module="EXPENSE",
            record_id=expense.id,
            description=f"Expense #{expense.id} created by {request.user}"
        )
        messages.success(request,"Expense added successfully")
        return redirect("accountmgmt:expense_list")

    return render(request, "accountmgmt/expense_add.html")



def ledger_list(request):
    from_date = request.GET.get("from_date")
    to_date = request.GET.get("to_date")

    ledger = []

    # ---------- MEDICAL BILL (CREDIT) ----------
    qs = MedicalBill.objects.all()
    if from_date and to_date:
        qs = qs.filter(bill_date__range=[from_date, to_date])

    for b in qs:
        ledger.append({
            "date": b.bill_date,
            "particulars": f"Medical Bill - {b.bill_no}",
            "debit": 0,
            "credit": b.total,
            "payment_mode": b.payment_mode or "—",
        })

    # ---------- THERAPY BILL (CREDIT) ----------
    qs = TherapyBill.objects.all()
    if from_date and to_date:
        qs = qs.filter(bill_date__range=[from_date, to_date])

    for b in qs:
        ledger.append({
            "date": b.bill_date,
            "particulars": f"Therapy Bill - {b.bill_no}",
            "debit": 0,
            "credit": b.total,
            "payment_mode": b.payment_mode or "—",
        })

    # ---------- INPATIENT BILL (CREDIT) ----------
    qs = InpatientBill.objects.exclude(admit_date__isnull=True)
    if from_date and to_date:
        qs = qs.filter(admit_date__range=[from_date, to_date])

    for b in qs:
        ledger.append({
            "date": b.admit_date,
            "particulars": f"Inpatient Bill - {b.bill_no}",
            "debit": 0,
            "credit": b.total,
            "payment_mode": b.payment_mode or "—",
        })

    # ---------- OUTPATIENT BILL (CREDIT) ----------
    qs = OutpatientBill.objects.all()
    if from_date and to_date:
        qs = qs.filter(visit_date__range=[from_date, to_date])

    for b in qs:
        ledger.append({
            "date": b.visit_date,
            "particulars": f"Outpatient Bill - {b.bill_no}",
            "debit": 0,
            "credit": b.total,
            "payment_mode": b.payment_mode or "—",
        })

    # ---------- EXPENSE (DEBIT) ----------
    qs = Expense.objects.all()
    if from_date and to_date:
        qs = qs.filter(expense_date__range=[from_date, to_date])

    for e in qs:
        ledger.append({
            "date": e.expense_date,
            "particulars": f"Expense - {e.description}",
            "debit": e.amount,
            "credit": 0,
            "payment_mode": e.payment_mode or "—",
        })

    # ---------- SORT ----------
    ledger.sort(key=lambda x: x["date"])

    # ---------- CLOSING BALANCE ----------
    closing_balance = 0
    for row in ledger:
        closing_balance += row["credit"]
        closing_balance -= row["debit"]

    closing_balance_type = "Credit" if closing_balance >= 0 else "Debit"
    closing_balance_value = abs(closing_balance)

    # ---------- PDF ----------
    if "export_pdf" in request.GET:
        return ledger_pdf(
            ledger,
            closing_balance_type,
            closing_balance_value,
            from_date,
            to_date
        )

    return render(request, "accountmgmt/ledger_list.html", {
        "ledger": ledger,
        "from_date": from_date,
        "to_date": to_date,
        "closing_balance_type": closing_balance_type,
        "closing_balance_value": closing_balance_value,
    })



# ================= PDF =================

def ledger_pdf(ledger, balance_type, balance_value, from_date, to_date):
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="Ledger_Report.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4
    y = height - 40

    p.setFont("Helvetica-Bold", 14)
    p.drawString(40, y, "Ledger Report")
    y -= 20

    if from_date and to_date:
        p.setFont("Helvetica", 10)
        p.drawString(40, y, f"Period : {from_date} to {to_date}")
        y -= 20

    # Header
    p.setFont("Helvetica-Bold", 10)
    p.drawString(40, y, "Date")
    p.drawString(110, y, "Particulars")
    p.drawString(360, y, "Debit")
    p.drawString(450, y, "Credit")
    y -= 10
    p.line(40, y, 550, y)
    y -= 15

    p.setFont("Helvetica", 10)
    for row in ledger:
        if y < 80:
            p.showPage()
            y = height - 40

        p.drawString(40, y, row["date"].strftime("%d-%m-%Y"))
        p.drawString(110, y, row["particulars"][:35])
        p.drawRightString(400, y, str(row["debit"]) if row["debit"] else "-")
        p.drawRightString(500, y, str(row["credit"]) if row["credit"] else "-")
        y -= 15

    # Closing Balance
    y -= 10
    p.line(300, y, 550, y)
    y -= 15
    p.setFont("Helvetica-Bold", 11)
    p.drawRightString(
        550,
        y,
        f"Closing Balance ({balance_type}) : {balance_value}"
    )

    p.showPage()
    p.save()
    return response


def account_reports(request):
    from_date = request.GET.get("from_date")
    to_date = request.GET.get("to_date")

    # ---------------- INCOME ----------------
    medical_total = MedicalBill.objects.aggregate(total=Sum("total"))["total"] or 0
    therapy_total = TherapyBill.objects.aggregate(total=Sum("total"))["total"] or 0
    inpatient_total = InpatientBill.objects.aggregate(total=Sum("total"))["total"] or 0
    outpatient_total = OutpatientBill.objects.aggregate(total=Sum("total"))["total"] or 0

    if from_date and to_date:
        medical_total = MedicalBill.objects.filter(
            bill_date__range=[from_date, to_date]
        ).aggregate(total=Sum("total"))["total"] or 0

        therapy_total = TherapyBill.objects.filter(
            bill_date__range=[from_date, to_date]
        ).aggregate(total=Sum("total"))["total"] or 0

        inpatient_total = InpatientBill.objects.filter(
            admit_date__range=[from_date, to_date]
        ).aggregate(total=Sum("total"))["total"] or 0

        outpatient_total = OutpatientBill.objects.filter(
            visit_date__range=[from_date, to_date]
        ).aggregate(total=Sum("total"))["total"] or 0

    total_income = int(
        medical_total +
        therapy_total +
        inpatient_total +
        outpatient_total
    )

    # ---------------- EXPENSE ----------------
    expense_qs = Expense.objects.all()
    if from_date and to_date:
        expense_qs = expense_qs.filter(expense_date__range=[from_date, to_date])

    total_expense = int(expense_qs.aggregate(total=Sum("amount"))["total"] or 0)

    # ---------------- PROFIT / LOSS ----------------
    profit = total_income - total_expense
    profit_type = "Profit" if profit >= 0 else "Loss"
    profit_value = abs(profit)

    context = {
        "from_date": from_date,
        "to_date": to_date,

        "medical_total": int(medical_total),
        "therapy_total": int(therapy_total),
        "inpatient_total": int(inpatient_total),
        "outpatient_total": int(outpatient_total),

        "total_income": total_income,
        "total_expense": total_expense,
        "profit_type": profit_type,
        "profit_value": profit_value,
    }

    return render(request, "accountmgmt/account_reports.html", context)