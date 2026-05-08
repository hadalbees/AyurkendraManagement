from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, View
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.contrib.auth.mixins import LoginRequiredMixin
from decimal import Decimal, InvalidOperation

from django.http import JsonResponse
from django.db import models

from fieldmgmt.models import AyurvedicType, ManufacturerMaster, SupplierMaster,ActivityHistory
from .models import Stock, Medicine, StockTransaction
import pandas as pd
from django.db import transaction


# --------------------------------------------------
# Helper: calculate price per single unit
# --------------------------------------------------
def calculate_price_per_single(selling_price, quantity, unit):
    """
    Calculates price per smallest base unit (g/ml/unit)
    """

    try:
        selling_price = Decimal(str(selling_price).replace(",", "").strip())
        quantity = Decimal(str(quantity).replace(",", "").strip())
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")

    unit = (unit or "").strip().lower()

    # Convert everything into smallest base unit
    conversions = {
        "kg": Decimal("1000"),   # 1 kg = 1000 g
        "g": Decimal("1"),
        "mg": Decimal("0.001"),
        "l": Decimal("1000"),    # 1 L = 1000 ml
        "ml": Decimal("1"),
        "unit": Decimal("1"),
    }

    factor = conversions.get(unit, Decimal("1"))

    total_base_quantity = quantity * factor

    if total_base_quantity <= 0:
        return Decimal("0")

    return selling_price / total_base_quantity


# --------------------------------------------------
# Stock List View
# --------------------------------------------------
class StockListView(LoginRequiredMixin, ListView):
    model = Stock
    template_name = "stockmgmt/stockhome.html"
    context_object_name = "stocks"
    paginate_by = 50

    def get_queryset(self):

        qs = super().get_queryset().select_related(
            "medicine",
            "supplier",
            "manufacturer"
        )

        q_name = self.request.GET.get("q", "").strip()
        low_stock = self.request.GET.get("low_stock")
        near_expiry = self.request.GET.get("near_expiry")

        # -----------------------------
        # Search
        # -----------------------------
        if q_name:
            qs = qs.filter(
                Q(medicine__name__icontains=q_name) |
                Q(batch_number__icontains=q_name)
            )

        # -----------------------------
        # Low Stock
        # -----------------------------
        if low_stock:
            qs = qs.filter(
                total_base_quantity__lte=models.F(
                    "medicine__reorder_level"
                )
            )

        # -----------------------------
        # Near Expiry
        # -----------------------------
        if near_expiry:
            today = timezone.localdate()

            qs = qs.filter(
                expiry_date__isnull=False,
                expiry_date__lte=today + timezone.timedelta(days=30)
            )

        return qs.order_by("medicine__name")

    def get_context_data(self, **kwargs):

        ctx = super().get_context_data(**kwargs)

        ctx["q"] = self.request.GET.get("q", "")
        ctx["low_stock"] = bool(
            self.request.GET.get("low_stock")
        )
        ctx["near_expiry"] = bool(
            self.request.GET.get("near_expiry")
        )

        ctx["ayurvedic_forms"] = AyurvedicType.objects.filter(
            status=True
        )

        ctx["suppliers"] = SupplierMaster.objects.filter(
            status=True
        )

        ctx["manufacturers"] = ManufacturerMaster.objects.filter(
            status=True
        )

        return ctx


def stock_delete(request, pk):

    stock = get_object_or_404(Stock, pk=pk)

    medicine_name = stock.medicine.name
    batch_no = stock.batch_number

    stock.delete()

    messages.success(
        request,
        f"Stock deleted successfully. ({medicine_name} - {batch_no})"
    )

    return redirect("stockmgmt:stock_list")
# --------------------------------------------------
# Add Medicine (AJAX)
# --------------------------------------------------
def add_medicine_ajax(request):

    if request.method != "POST":
        messages.error(request, "Invalid request method.")
        return redirect("stockmgmt:stock_list")

    # -----------------------
    # Get Form Data
    # -----------------------
    name = request.POST.get("name")
    hsn_code = request.POST.get("hsn_code")
    form_type = request.POST.get("form_type")
    ayurvedic_type_id = request.POST.get("ayurvedic_type")
    description = request.POST.get("description")

    gst_percentage = request.POST.get("gst_percentage")
    reorder_level = request.POST.get("reorder_level")
    expiry_days_alert = request.POST.get("expiry_days_alert")

    # -----------------------
    # Clean Values
    # -----------------------
    name = name.strip().title() if name else ""   # Auto Capitalize
    hsn_code = hsn_code.strip() if hsn_code else ""
    form_type = form_type.strip() if form_type else ""
    description = description.strip() if description else ""

    # -----------------------
    # Validation
    # -----------------------
    if not name:
        messages.error(request, "Medicine name is required.")
        return redirect("stockmgmt:stock_list")

    if not form_type:
        messages.error(request, "Form type is required.")
        return redirect("stockmgmt:stock_list")

    # -----------------------
    # Duplicate Check (case insensitive)
    # -----------------------
    if Medicine.objects.filter(name__iexact=name).exists():
        messages.error(request, f"{name} already exists.")
        return redirect("stockmgmt:stock_list")

    # -----------------------
    # Convert Numbers
    # -----------------------
    try:
        gst_percentage = Decimal(gst_percentage) if gst_percentage else Decimal("0")
    except:
        gst_percentage = Decimal("0")

    try:
        reorder_level = int(reorder_level) if reorder_level else 0
    except:
        reorder_level = 0

    try:
        expiry_days_alert = int(expiry_days_alert) if expiry_days_alert else 30
    except:
        expiry_days_alert = 30

    # -----------------------
    # Ayurvedic Type
    # -----------------------
    ayurvedic_type = None
    if ayurvedic_type_id:
        try:
            ayurvedic_type = AyurvedicType.objects.get(id=ayurvedic_type_id)
        except AyurvedicType.DoesNotExist:
            ayurvedic_type = None

    # -----------------------
    # Create Medicine
    # -----------------------
    medicine = Medicine.objects.create(
        name=name,
        hsn_code=hsn_code,
        form_type=form_type,
        ayurvedic_type=ayurvedic_type,
        description=description,
        gst_percentage=gst_percentage,
        reorder_level=reorder_level,
        expiry_days_alert=expiry_days_alert,
    )

    # -----------------------
    # Activity Log
    # -----------------------
    ActivityHistory.objects.create(
        user=request.user,
        action="CREATE",
        module="MEDICINE",
        record_id=medicine.id,
        description=f"Medicine '{medicine.name}' created by {request.user}"
    )

    messages.success(request, f"{medicine.name} added successfully.")
    return redirect("stockmgmt:stock_list")

def update_medicine(request):
    if request.method == "POST":
        medicine = get_object_or_404(Medicine, id=request.POST.get("medicine_id"))

        medicine.name = request.POST.get("name")
        medicine.hsn_code = request.POST.get("hsn_code")
        medicine.form_type = request.POST.get("form_type")
        medicine.gst_percentage = request.POST.get("gst_percentage")
        medicine.reorder_level = request.POST.get("reorder_level") or 0
        medicine.expiry_days_alert = request.POST.get("expiry_days_alert") or 30
        medicine.description = request.POST.get("description")

        medicine.save()
        ActivityHistory.objects.create(
            user=request.user,
            action="update",
            module="MEDICINE",
            record_id=medicine.id,
            description=f"medicine #{medicine.id} updated by {request.user}"
        )
        messages.success(request, "Medicine updated successfully.")

    return redirect("stockmgmt:stock_list")

def calculate_stock_values(pack_size, number_of_packs, unit_price, gst_percentage, selling_price):

    pack_size = Decimal(pack_size or 0)
    number_of_packs = Decimal(number_of_packs or 0)
    unit_price = Decimal(unit_price or 0)
    gst_percentage = Decimal(gst_percentage or 0)

    total_base_quantity = pack_size * number_of_packs

    # GST INCLUDED extraction formula
    if gst_percentage > 0:
        gst_amount = (unit_price * gst_percentage) / (Decimal("100") + gst_percentage)
    else:
        gst_amount = Decimal("0")

    # Selling price auto if empty
    if not selling_price or Decimal(selling_price) == 0:
        selling_price = unit_price
    else:
        selling_price = Decimal(selling_price)

    if total_base_quantity > 0:
        price_per_base_unit = selling_price / total_base_quantity
    else:
        price_per_base_unit = Decimal("0")

    return total_base_quantity, gst_amount, selling_price, price_per_base_unit

# --------------------------------------------------
# Stock Create View
# --------------------------------------------------
class StockCreateView(LoginRequiredMixin, CreateView):
    model = Stock
    fields = [
        "medicine",
        "batch_number",
        "base_unit",
        "pack_size",
        "number_of_packs",
        "unit_price",
        "selling_price",
        "manufacture_date",
        "expiry_date",
        "supplier",
        "manufacturer",
    ]
    template_name = "stockmgmt/stockform.html"
    success_url = reverse_lazy("stockmgmt:stock_list")

    def form_valid(self, form):
        obj = form.save(commit=False)

        gst_percentage = obj.medicine.gst_percentage

        total_qty, gst_amount, selling_price, price_per_base = calculate_stock_values(
            obj.pack_size,
            obj.number_of_packs,
            obj.unit_price,
            gst_percentage,
            obj.selling_price
        )

        obj.total_base_quantity = total_qty
        obj.gst_amount = gst_amount
        obj.selling_price = selling_price
        obj.price_per_base_unit = price_per_base
        obj.last_updated_by = self.request.user

        obj.save()
        ActivityHistory.objects.create(
            user=self.request.user,
            action="CREATE",
            module="STOCK",
            record_id=obj.id,
            description=f"Stock #{obj.id} created by {self.request.user}"
        )

        messages.success(self.request, "Stock added successfully.")
        return super().form_valid(form)


# --------------------------------------------------
# Stock Update View
# --------------------------------------------------
class StockUpdateView(LoginRequiredMixin, UpdateView):
    model = Stock
    fields = [
        "medicine",
        "batch_number",
        "base_unit",
        "pack_size",
        "number_of_packs",
        "unit_price",
        "selling_price",
        "manufacture_date",
        "expiry_date",
        "supplier",
        "manufacturer",
    ]
    template_name = "stockmgmt/stockform.html"
    success_url = reverse_lazy("stockmgmt:stock_list")

    def form_valid(self, form):
        obj = form.save(commit=False)

        gst_percentage = obj.medicine.gst_percentage

        total_qty, gst_amount, selling_price, price_per_base = calculate_stock_values(
            obj.pack_size,
            obj.number_of_packs,
            obj.unit_price,
            gst_percentage,
            obj.selling_price
        )

        obj.total_base_quantity = total_qty
        obj.gst_amount = gst_amount
        obj.selling_price = selling_price
        obj.price_per_base_unit = price_per_base
        obj.last_updated_by = self.request.user

        obj.save()
        ActivityHistory.objects.create(
            user=self.request.user,
            action="UPDATE",
            module="STOCK",
            record_id=obj.id,
            description=f"Stock #{obj.id} updated by {self.request.user}"
        )
        messages.success(self.request, "Stock updated successfully.")
        return super().form_valid(form)


# --------------------------------------------------
# Stock Dispense View
# --------------------------------------------------
class StockDispenseView(LoginRequiredMixin, View):

    def post(self, request, *args, **kwargs):
        stock_id = request.POST.get("stock_id")
        qty = request.POST.get("quantity")
        notes = request.POST.get("notes", "").strip()

        if not stock_id or not qty:
            messages.error(request, "Stock and quantity are required.")
            return redirect(reverse_lazy("stockmgmt:stock_list"))

        stock = get_object_or_404(Stock, pk=stock_id)

        try:
            qty_dec = Decimal(qty)
            if qty_dec <= 0:
                raise ValueError
        except Exception:
            messages.error(request, "Enter a valid positive quantity.")
            return redirect(reverse_lazy("stockmgmt:stock_list"))

        if Decimal(stock.quantity) < qty_dec:
            messages.error(
                request,
                f"Insufficient stock. Available quantity: {stock.quantity}"
            )
            return redirect(reverse_lazy("stockmgmt:stock_list"))

        stock.quantity -= qty_dec
        stock.last_updated_by = request.user
        stock.save()

        StockTransaction.objects.create(
            stock_item=stock,
            transaction_type="DISPENSE",
            quantity_change=-qty_dec,
            recorded_by=request.user,
            transaction_date=timezone.now(),
            notes=notes or "Dispensed from stock",
        )

        messages.success(
            request,
            f"{qty_dec} units dispensed from {stock.medicine.name} "
            f"(Batch {stock.batch_number})"
        )

        return redirect(reverse_lazy("stockmgmt:stock_list"))


REQUIRED_COLUMNS = [
    "medicine_name",
    "batch_number",
    "base_unit",
    "pack_size",
    "number_of_packs",
    "unit_price",
    "selling_price",
]


from datetime import datetime
# -----------------------------
# SAFE DECIMAL
# -----------------------------
def safe_decimal(val, default=0):
    try:
        if pd.isna(val):
            return Decimal(default)
        return Decimal(str(val).replace("₹", "").strip())
    except:
        return Decimal(default)


# -----------------------------
# FIX QUANTITY (handles date issue like 4-Jan)
# -----------------------------
def fix_quantity(val):
    try:
        if pd.isna(val):
            return 0

        if isinstance(val, pd.Timestamp):
            return val.day

        return int(val)
    except:
        return 0


# -----------------------------
# FORM TYPE + BASE UNIT
# -----------------------------
def detect_form_and_unit(name):
    name = name.lower()

    if "ml" in name:
        return "LIQUID", "ml"

    elif "gm" in name or " g " in name or "gms" in name:
        return "POWDER", "g"

    else:
        return "PIECE", "piece"   # 🔥 IMPORTANT FIX


# -----------------------------
# EXPIRY PARSER (FIX ERROR)
# -----------------------------
def parse_expiry(val):
    try:
        if pd.isna(val):
            return None

        if isinstance(val, pd.Timestamp):
            return val.date()

        if isinstance(val, str):
            try:
                return datetime.strptime(val, "%b-%y").date()
            except:
                return pd.to_datetime(val).date()

        return None
    except:
        return None


# =============================
# MAIN BULK IMPORT
# =============================
def bulk_import_stock(request):

    if request.method != "POST":
        return redirect("stockmgmt:stock_list")

    file = request.FILES.get("file")
    if not file:
        messages.error(request, "No file uploaded.")
        return redirect("stockmgmt:stock_list")

    try:
        df = pd.read_excel(file)

        df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

        created = 0
        updated = 0
        skipped = 0

        current_type = None

        with transaction.atomic():

            for _, row in df.iterrows():

                medicine_name = str(row.get("medicine_name", "")).strip()

                # ✅ Skip ONLY empty medicine name
                if not medicine_name:
                    skipped += 1
                    continue

                # ✅ Category rows
                if medicine_name.isupper():
                    current_type, _ = AyurvedicType.objects.get_or_create(
                        name=medicine_name.title()
                    )
                    continue

                # -------------------------
                # FIELDS
                # -------------------------
                batch_number = str(row.get("batch_no", "")).strip()

                # 🔥 FIX: allow empty batch
                if not batch_number:
                    batch_number = f"NO-BATCH-{_}"

                manufacturer_name = str(row.get("manufacturer", "")).strip()

                pack_size = safe_decimal(row.get("package"))
                number_of_packs = fix_quantity(row.get("quantity"))
                selling_price = safe_decimal(row.get("total_price"))
                unitprice_excel = safe_decimal(row.get("unit_price"))

                # 🔥 ALLOW ZERO VALUES
                if pack_size < 0:
                    pack_size = Decimal("0")

                if number_of_packs < 0:
                    number_of_packs = Decimal("0")

                if selling_price < 0:
                    selling_price = Decimal("0")

                unit_price = selling_price
                total_qty = pack_size * number_of_packs
                if total_qty > 0:
                    price_per_base_unit = selling_price / total_qty
                else:
                    price_per_base_unit = Decimal("0")

                expiry_date = parse_expiry(row.get("expiry"))

                # -------------------------
                # FORM TYPE
                # -------------------------
                form_type, base_unit = detect_form_and_unit(medicine_name)

                # -------------------------
                # MANUFACTURER
                # -------------------------
                manufacturer = None
                if manufacturer_name:
                    manufacturer, _ = ManufacturerMaster.objects.get_or_create(
                        name=manufacturer_name
                    )

                # -------------------------
                # MEDICINE
                # -------------------------
                medicine, created_medicine = Medicine.objects.get_or_create(
                    name__iexact=medicine_name,
                    defaults={
                        "name": medicine_name,
                        "hsn_code": str(row.get("hsn_code", "")),
                        "form_type": form_type,
                        "ayurvedic_type": current_type,
                        "gst_percentage": Decimal("0"),
                        "reorder_level": 0,
                        "expiry_days_alert": 30,
                        "description": "",
                    }
                )

                # -------------------------
                # STOCK
                # -------------------------
                # -------------------------
                # STOCK
                # -------------------------

                stock = Stock.objects.filter(
                    medicine=medicine,
                    batch_number=batch_number
                ).first()

                gst_percentage = medicine.gst_percentage or Decimal("0")

                # SAME LOGIC AS CREATE VIEW
                total_qty, gst_amount, selling_price_final, price_per_base = calculate_stock_values(
                    pack_size,
                    number_of_packs,
                    unit_price,
                    gst_percentage,
                    selling_price
                )

                if stock:

                    stock.pack_size = pack_size

                    stock.number_of_packs += number_of_packs

                    stock.total_base_quantity += total_qty

                    stock.unit_price = unit_price

                    stock.selling_price = selling_price_final

                    stock.gst_amount = gst_amount

                    stock.price_per_base_unit = unitprice_excel

                    stock.base_unit = base_unit

                    stock.manufacturer = manufacturer

                    stock.expiry_date = expiry_date

                    stock.updated_at = timezone.now()

                    stock.last_updated_by = request.user

                    stock.save()

                    # STOCK TRANSACTION
                    StockTransaction.objects.create(
                        stock_item=stock,
                        transaction_type="ADJUSTMENT",
                        quantity_change=total_qty,
                        recorded_by=request.user,
                        notes="Bulk import stock update"
                    )

                    # ACTIVITY
                    ActivityHistory.objects.create(
                        user=request.user,
                        action="UPDATE",
                        module="STOCK",
                        record_id=stock.id,
                        description=f"Stock #{stock.id} updated via bulk import"
                    )

                    updated += 1

                else:

                    stock = Stock.objects.create(

                        medicine=medicine,

                        batch_number=batch_number,

                        base_unit=base_unit,

                        pack_size=pack_size,

                        number_of_packs=number_of_packs,

                        total_base_quantity=total_qty,

                        unit_price=unit_price,

                        selling_price=selling_price_final,

                        gst_amount=gst_amount,

                        price_per_base_unit=unitprice_excel,

                        manufacture_date=None,

                        expiry_date=expiry_date,

                        supplier=None,

                        manufacturer=manufacturer,

                        last_updated_by=request.user,

                    )

                    # STOCK TRANSACTION
                    StockTransaction.objects.create(
                        stock_item=stock,
                        transaction_type="PURCHASE",
                        quantity_change=total_qty,
                        recorded_by=request.user,
                        notes="Bulk import new stock"
                    )

                    # ACTIVITY
                    ActivityHistory.objects.create(
                        user=request.user,
                        action="CREATE",
                        module="STOCK",
                        record_id=stock.id,
                        description=f"Stock #{stock.id} created via bulk import"
                    )

                    created += 1

        messages.success(
            request,
            f"✔ Import Done → Created: {created}, Updated: {updated}, Skipped: {skipped}"
        )

    except Exception as e:
        messages.error(request, f"Import failed: {str(e)}")

    return redirect("stockmgmt:stock_list")

def medicine_check(request):

    q = request.GET.get("q","")

    medicines = Medicine.objects.filter(
        name__icontains=q
    ).values("name")[:10]

    return JsonResponse(list(medicines), safe=False)
