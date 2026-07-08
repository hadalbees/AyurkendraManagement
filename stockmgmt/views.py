from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, View
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.mixins import LoginRequiredMixin
from decimal import Decimal, InvalidOperation
from decimal import Decimal, ROUND_HALF_UP
from django.http import JsonResponse
from django.db import models

from fieldmgmt.models import AyurvedicType, ManufacturerMaster, SupplierMaster,ActivityHistory
from .models import Stock, Medicine, StockTransaction
import pandas as pd
from django.db import transaction
from django.db.models.functions import Coalesce
from django.db.models import DecimalField,Value
from django.db.models import (
    Sum,
    Min,
    Max,
    Count,
    Q,
    F,
    DecimalField,
    Value,
)


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

    template_name = "stockmgmt/stockhome.html"
    context_object_name = "stocks"
    paginate_by = 10

    def get_queryset(self):
        # Base queryset of all medicines
        queryset = Medicine.objects.all()

        # Get query parameters
        q = self.request.GET.get("q", "").strip()
        category = self.request.GET.get("category", "").strip()
        supplier = self.request.GET.get("supplier", "").strip()
        manufacturer = self.request.GET.get("manufacturer", "").strip()
        quick_filter = self.request.GET.get("quick_filter", "").strip()
        sort_by = self.request.GET.get("sort_by", "").strip()

        # 1. Apply basic search query
        if q:
            queryset = queryset.filter(
                Q(name__icontains=q) |
                Q(hsn_code__icontains=q) |
                Q(stocks__batch_number__icontains=q)
            ).distinct()

        # 2. Apply Category filter
        if category:
            queryset = queryset.filter(ayurvedic_type_id=category)

        # 3. Apply Supplier filter
        if supplier:
            queryset = queryset.filter(stocks__supplier_id=supplier)

        # 4. Apply Manufacturer filter
        if manufacturer:
            queryset = queryset.filter(stocks__manufacturer_id=manufacturer)

        # Annotate required aggregation fields
        from django.db.models import Case, When, Value, CharField
        today = timezone.localdate()

        queryset = queryset.annotate(
            medicine_id=F("id"),
            medicine__name=F("name"),
            medicine__form_type=F("form_type"),
            medicine__gst_percentage=F("gst_percentage"),
            medicine__reorder_level=F("reorder_level"),
            medicine__hsn_code=F("hsn_code"),
            total_qty=Coalesce(
                Sum("stocks__total_base_quantity"),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2))
            ),
            total_batches=Count("stocks"),
            purchase_price=Coalesce(
                Max("stocks__unit_price"),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2))
            ),
            selling_price=Coalesce(
                Max("stocks__selling_price"),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2))
            ),
            nearest_expiry=Min("stocks__expiry_date"),
            category_name=Coalesce(F("ayurvedic_type__name"), Value("Unassigned"), output_field=CharField()),
            base_unit=Coalesce(
                Max("stocks__base_unit"),
                Case(
                    When(form_type="LIQUID", then=Value("ml")),
                    When(form_type="POWDER", then=Value("g")),
                    default=Value("piece"),
                    output_field=CharField()
                )
            )
        )

        # 5. Apply Quick Filters
        if quick_filter == "low_stock":
            queryset = queryset.filter(
                total_qty__lte=F("reorder_level"),
                total_qty__gt=0
            )
        elif quick_filter == "near_expiry":
            queryset = queryset.filter(
                nearest_expiry__isnull=False,
                nearest_expiry__lte=today + timezone.timedelta(days=30),
                nearest_expiry__gte=today
            )
        elif quick_filter == "expired":
            queryset = queryset.filter(
                nearest_expiry__lt=today
            )
        elif quick_filter == "zero_stock":
            queryset = queryset.filter(
                total_qty=0
            )

        # 6. Apply Sorting
        if sort_by == "name_desc":
            queryset = queryset.order_by("-name")
        elif sort_by == "stock_asc":
            queryset = queryset.order_by("total_qty")
        elif sort_by == "stock_desc":
            queryset = queryset.order_by("-total_qty")
        elif sort_by == "expiry_asc":
            queryset = queryset.order_by(F("nearest_expiry").asc(nulls_last=True))
        else:
            # Default sorting: Name A-Z
            queryset = queryset.order_by("name")

        # Select the values as expected by templates and existing logic
        return queryset.values(
            "medicine_id",
            "medicine__name",
            "medicine__hsn_code",
            "medicine__form_type",
            "medicine__gst_percentage",
            "medicine__reorder_level",
            "total_qty",
            "total_batches",
            "purchase_price",
            "selling_price",
            "nearest_expiry",
            "base_unit",
            "category_name",
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        stock = Stock.objects.all()
        today = timezone.localdate()

        context["total_medicines"] = Medicine.objects.count()
        context["total_batches"] = stock.count()
        context["total_stock"] = stock.aggregate(
            total=Coalesce(
                Sum("total_base_quantity"),
                Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )["total"]

        context["low_stock_count"] = Medicine.objects.annotate(
            total_qty=Coalesce(
                Sum("stocks__total_base_quantity"),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2))
            )
        ).filter(
            total_qty__lte=F("reorder_level"),
            total_qty__gt=0
        ).count()

        context["near_expiry_count"] = Medicine.objects.filter(
            stocks__expiry_date__isnull=False,
            stocks__expiry_date__lte=today + timezone.timedelta(days=30),
            stocks__expiry_date__gte=today,
        ).distinct().count()

        context["expired_count"] = Medicine.objects.filter(
            stocks__expiry_date__lt=today
        ).distinct().count()

        context["zero_stock_count"] = Medicine.objects.annotate(
            total_qty=Coalesce(
                Sum("stocks__total_base_quantity"),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2))
            )
        ).filter(total_qty=0).count()

        # Pass active filter values back to context
        context["q"] = self.request.GET.get("q", "")
        context["category"] = self.request.GET.get("category", "")
        context["supplier"] = self.request.GET.get("supplier", "")
        context["manufacturer"] = self.request.GET.get("manufacturer", "")
        context["quick_filter"] = self.request.GET.get("quick_filter", "all")
        context["sort_by"] = self.request.GET.get("sort_by", "name_asc")

        context["suppliers"] = SupplierMaster.objects.filter(status=True)
        context["manufacturers"] = ManufacturerMaster.objects.filter(status=True)
        context["forms"] = AyurvedicType.objects.filter(status=True)

        # Build url parameters for keeping filter state in pagination links
        params = self.request.GET.copy()
        if "page" in params:
            del params["page"]
        context["query_params"] = params.urlencode()

        return context
def stock_details(request, medicine_id):

    medicine = get_object_or_404(

        Medicine,

        id=medicine_id

    )

    stocks = (

        Stock.objects

        .filter(

            medicine=medicine

        )

        .select_related(

            "supplier",

            "manufacturer"

        )

        .order_by(

            "expiry_date"

        )

    )

    summary = stocks.aggregate(

        total_qty=Coalesce(
            Sum("total_base_quantity"),
            Value(0),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        ),

        total_packs=Coalesce(
            Sum("number_of_packs"),
            Value(0),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        ),

        total_purchase=Coalesce(
            Sum(F("number_of_packs") * F("unit_price")),
            Value(0),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        ),

        total_selling=Coalesce(
            Sum(F("number_of_packs") * F("selling_price")),
            Value(0),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        ),

        batches=Count("id"),

    )

    nearest = (

        stocks

        .exclude(

            expiry_date=None

        )

        .order_by(

            "expiry_date"

        )

        .first()

    )

    estimated_profit = (summary.get('total_selling') or 0) - (summary.get('total_purchase') or 0)

    first_stock = stocks.first()
    if first_stock and first_stock.base_unit:
        base_unit = first_stock.base_unit
    else:
        if medicine.form_type == 'LIQUID':
            base_unit = 'ml'
        elif medicine.form_type == 'POWDER':
            base_unit = 'g'
        else:
            base_unit = 'piece'

    context = {
        "medicine": medicine,
        "stocks": stocks,
        "summary": summary,
        "nearest_expiry": nearest.expiry_date if nearest else None,
        "nearest_stock": nearest,
        "estimated_profit": estimated_profit,
        "base_unit": base_unit,
        "today": timezone.localdate(),
    }

    return render(

        request,

        "stockmgmt/stock_details.html",

        context,

    )
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
def calculate_stock_values(
    pack_size,
    number_of_packs,
    unit_price,
    gst_percentage,
    selling_price,
):
    """
    Calculate stock quantities and pricing.

    unit_price = Purchase Price per Pack (GST Included)
    """

    pack_size = Decimal(str(pack_size or 0))
    number_of_packs = Decimal(str(number_of_packs or 0))
    unit_price = Decimal(str(unit_price or 0))
    gst_percentage = Decimal(str(gst_percentage or 0))
    selling_price = Decimal(str(selling_price or 0))

    # ---------------------------------------
    # Total Quantity
    # Example:
    # 450ml × 4 = 1800ml
    # ---------------------------------------

    total_base_quantity = pack_size * number_of_packs

    # ---------------------------------------
    # Extract GST from Purchase Price
    # ---------------------------------------

    gst_amount = Decimal("0.00")

    if gst_percentage > 0:

        gst_amount = (
            unit_price * gst_percentage
        ) / (Decimal("100") + gst_percentage)

    # ---------------------------------------
    # Default Selling Price
    # ---------------------------------------

    if selling_price <= 0:
        selling_price = unit_price

    # ---------------------------------------
    # Price Per Base Unit
    # Example
    # ₹100 / 450ml
    # = ₹0.222222
    # ---------------------------------------

    if pack_size > 0:

        price_per_base_unit = (
            selling_price / pack_size
        )

    else:

        price_per_base_unit = Decimal("0")

    return (

        total_base_quantity.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        ),

        gst_amount.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        ),

        selling_price.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        ),

        price_per_base_unit.quantize(
            Decimal("0.000001"),
            rounding=ROUND_HALF_UP
        ),

    )
# --------------------------------------------------
# Stock Create View
# --------------------------------------------------
class StockCreateView(LoginRequiredMixin, View):

    template_name = "stockmgmt/stockform.html"
    success_url = reverse_lazy("stockmgmt:stock_list")

    # ---------------------------------------------------
    # GET
    # ---------------------------------------------------

    def get(self, request):

        medicines = (
            Medicine.objects.annotate(
                stock_total=Coalesce(
                    Sum("stocks__total_base_quantity"),
                    Value(0),
                    output_field=DecimalField(
                        max_digits=12,
                        decimal_places=2
                    )
                )
            ).order_by("name")
        )

        context = {

            "medicines": medicines,

            "suppliers": SupplierMaster.objects.filter(status=True),

            "manufacturers": ManufacturerMaster.objects.filter(status=True),

        }

        return render(
            request,
            self.template_name,
            context
        )

    # ---------------------------------------------------
    # POST
    # ---------------------------------------------------

    @transaction.atomic
    def post(self, request):

        try:

            medicine = Medicine.objects.get(
                id=request.POST.get("medicine")
            )

            supplier = None
            supplier_id = request.POST.get("supplier")

            if supplier_id:
                supplier = SupplierMaster.objects.get(id=supplier_id)

            manufacturer = None
            manufacturer_id = request.POST.get("manufacturer")

            if manufacturer_id:
                manufacturer = ManufacturerMaster.objects.get(id=manufacturer_id)

            batch_number = request.POST.get("batch_number")

            base_unit = request.POST.get("base_unit")

            pack_size = Decimal(
                request.POST.get("pack_size") or 0
            )

            number_of_packs = Decimal(
                request.POST.get("number_of_packs") or 0
            )

            unit_price = Decimal(
                request.POST.get("unit_price") or 0
            )

            selling_price = Decimal(
                request.POST.get("selling_price") or 0
            )

            manufacture_date = request.POST.get("manufacture_date") or None

            expiry_date = request.POST.get("expiry_date") or None

            # -----------------------------------------
            # Duplicate Batch
            # -----------------------------------------

            if Stock.objects.filter(

                medicine=medicine,

                batch_number__iexact=batch_number

            ).exists():

                messages.error(
                    request,
                    "Batch already exists for this medicine."
                )

                return redirect(request.path)

            # -----------------------------------------
            # Calculate Values
            # -----------------------------------------

            (
                total_base_quantity,
                gst_amount,
                selling_price,
                price_per_base_unit,
            ) = calculate_stock_values(

                pack_size,

                number_of_packs,

                unit_price,

                medicine.gst_percentage,

                selling_price,

            )

            # -----------------------------------------
            # Save Stock
            # -----------------------------------------

            stock = Stock.objects.create(

                medicine=medicine,

                batch_number=batch_number,

                base_unit=base_unit,

                unit_price=unit_price,

                selling_price=selling_price,

                gst_amount=gst_amount,

                pack_size=pack_size,

                number_of_packs=number_of_packs,

                total_base_quantity=total_base_quantity,

                price_per_base_unit=price_per_base_unit,

                manufacture_date=manufacture_date,

                expiry_date=expiry_date,

                supplier=supplier,

                manufacturer=manufacturer,

                last_updated_by=request.user,

            )

            # -----------------------------------------
            # Stock Transaction
            # -----------------------------------------

            StockTransaction.objects.create(

                stock_item=stock,

                transaction_type="PURCHASE",

                quantity_change=total_base_quantity,

                recorded_by=request.user,

                notes="Opening Stock"

            )

            # -----------------------------------------
            # Activity History
            # -----------------------------------------

            ActivityHistory.objects.create(

                user=request.user,

                action="CREATE",

                module="STOCK",

                record_id=stock.id,

                description=f"{medicine.name} ({batch_number}) Stock Added"

            )

            messages.success(

                request,

                "Medicine Stock Added Successfully."

            )

            return redirect(self.success_url)

        except Exception as e:

            print(e)

            messages.error(

                request,

                str(e)

            )

            return redirect(request.path)
# --------------------------------------------------
# Stock Update View
# --------------------------------------------------
class StockUpdateView(LoginRequiredMixin, View):

    template_name = "stockmgmt/stockform.html"
    success_url = reverse_lazy("stockmgmt:stock_list")

    def get(self, request, pk):

        stock = get_object_or_404(Stock, pk=pk)

        medicines = (
            Medicine.objects.annotate(
                stock_total=Coalesce(
                    Sum("stocks__total_base_quantity"),
                    Value(0),
                    output_field=DecimalField(
                        max_digits=12,
                        decimal_places=2,
                    ),
                )
            ).order_by("name")
        )

        context = {
            "object": stock,
            "medicines": medicines,
            "suppliers": SupplierMaster.objects.filter(status=True),
            "manufacturers": ManufacturerMaster.objects.filter(status=True),
        }

        return render(request, self.template_name, context)

    @transaction.atomic
    def post(self, request, pk):
        
        stock = get_object_or_404(Stock, pk=pk)
        print("PK:", pk)
        print("Stock before:", stock.id, stock.batch_number)

        try:

            medicine = get_object_or_404(
                Medicine,
                pk=request.POST.get("medicine"),
            )

            supplier = None
            supplier_id = request.POST.get("supplier")

            if supplier_id:
                supplier = SupplierMaster.objects.filter(
                    pk=supplier_id
                ).first()

            manufacturer = None
            manufacturer_id = request.POST.get("manufacturer")

            if manufacturer_id:
                manufacturer = ManufacturerMaster.objects.filter(
                    pk=manufacturer_id
                ).first()

            batch_number = request.POST.get(
                "batch_number", ""
            ).strip()

            duplicate = (
                Stock.objects.filter(
                    medicine=medicine,
                    batch_number__iexact=batch_number,
                )
                .exclude(pk=stock.pk)
                .exists()
            )

            if duplicate:

                messages.error(
                    request,
                    "Batch number already exists."
                )
        
                return redirect(request.path)

            stock.medicine = medicine
            stock.batch_number = batch_number
            stock.base_unit = request.POST.get("base_unit")

            stock.pack_size = Decimal(
                request.POST.get("pack_size") or "0"
            )

            stock.number_of_packs = Decimal(
                request.POST.get("number_of_packs") or "0"
            )

            stock.unit_price = Decimal(
                request.POST.get("unit_price") or "0"
            )

            stock.selling_price = Decimal(
                request.POST.get("selling_price") or "0"
            )

            stock.manufacture_date = (
                request.POST.get("manufacture_date") or None
            )

            stock.expiry_date = (
                request.POST.get("expiry_date") or None
            )

            stock.supplier = supplier
            stock.manufacturer = manufacturer

            (
                stock.total_base_quantity,
                stock.gst_amount,
                stock.selling_price,
                stock.price_per_base_unit,
            ) = calculate_stock_values(
                stock.pack_size,
                stock.number_of_packs,
                stock.unit_price,
                medicine.gst_percentage,
                stock.selling_price,
            )

            stock.last_updated_by = request.user

            stock.save(update_fields=[
                "medicine",
                "batch_number",
                "base_unit",
                "pack_size",
                "number_of_packs",
                "unit_price",
                "selling_price",
                "gst_amount",
                "total_base_quantity",
                "price_per_base_unit",
                "manufacture_date",
                "expiry_date",
                "supplier",
                "manufacturer",
                "last_updated_by",
            ])
            stock.refresh_from_db()

            print("==============")
            print("Updated Successfully")
            print("ID :", stock.id)
            print("Medicine :", stock.medicine.name)
            print("Batch :", stock.batch_number)
            print("Pack :", stock.pack_size)
            print("Qty :", stock.number_of_packs)
            print("Purchase :", stock.unit_price)
            print("Selling :", stock.selling_price)
            print("Total Qty :", stock.total_base_quantity)
            print("==============")

            transaction, created = StockTransaction.objects.get_or_create(
                stock_item=stock,
                transaction_type="PURCHASE",
                defaults={
                    "quantity_change": stock.total_base_quantity,
                    "recorded_by": request.user,
                    "notes": "Opening Stock",
                },
            )

            if not created:
                transaction.quantity_change = stock.total_base_quantity
                transaction.recorded_by = request.user
                transaction.notes = "Opening Stock Updated"
                transaction.save()

            ActivityHistory.objects.create(
                user=request.user,
                action="UPDATE",
                module="STOCK",
                record_id=stock.pk,
                description=f"{stock.medicine.name} ({stock.batch_number}) Updated",
            )

            messages.success(
                request,
                "Stock updated successfully."
            )

            return redirect(self.success_url)

        except Exception as e:

            import traceback
            traceback.print_exc()

            messages.error(request, str(e))

            return render(
                request,
                self.template_name,
                {
                    "object": stock,
                    "medicines": Medicine.objects.annotate(
                        stock_total=Coalesce(
                            Sum("stocks__total_base_quantity"),
                            Value(0),
                            output_field=DecimalField(
                                max_digits=12,
                                decimal_places=2,
                            ),
                        )
                    ).order_by("name"),
                    "suppliers": SupplierMaster.objects.filter(status=True),
                    "manufacturers": ManufacturerMaster.objects.filter(status=True),
                },
            )
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

        if Decimal(stock.total_base_quantity) < qty_dec:
            messages.error(
                request,
                f"Insufficient stock. Available quantity: {stock.total_base_quantity}"
            )
            return redirect(reverse_lazy("stockmgmt:stock_list"))

        stock.total_base_quantity -= qty_dec
        if stock.pack_size > 0:
            stock.number_of_packs = stock.total_base_quantity / stock.pack_size
        else:
            stock.number_of_packs = Decimal("0.00")
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
            return Decimal("0")

        if isinstance(val, pd.Timestamp):
            return Decimal(str(val.day))

        # Check if it can be represented as float/decimal
        return Decimal(str(val))
    except:
        return Decimal("0")


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

        if hasattr(val, "date"):
            return val.date()

        # Handle 4-digit year integers (e.g., 2027 -> 2027-12-31)
        val_str = str(val).strip()
        if val_str.isdigit() and len(val_str) == 4:
            return datetime(int(val_str), 12, 31).date()

        if isinstance(val, str):
            try:
                return datetime.strptime(val_str, "%b-%y").date()
            except:
                return pd.to_datetime(val_str).date()

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
                if not medicine_name or medicine_name.lower() in ["nan", "none"]:
                    skipped += 1
                    continue

                # ✅ Category rows: price, manufacturer, and quantity are null
                is_category = pd.isna(row.get("price")) and pd.isna(row.get("manufacturer")) and pd.isna(row.get("quantity"))
                if is_category:
                    current_type, _ = AyurvedicType.objects.get_or_create(
                        name=medicine_name.title()
                    )
                    continue

                # -------------------------
                # FIELDS
                # -------------------------
                batch_val = row.get("batch_no")
                if pd.isna(batch_val) or str(batch_val).strip().lower() in ["", "nan", "none"]:
                    batch_number = "NO-BATCH"
                else:
                    batch_number = str(batch_val).strip()

                manufacturer_name = str(row.get("manufacturer", "")).strip()

                pack_size = safe_decimal(row.get("package"))
                number_of_packs = fix_quantity(row.get("quantity"))
                selling_price = safe_decimal(row.get("price"))
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
                if manufacturer_name and manufacturer_name.lower() not in ["nan", "none"]:
                    manufacturer, _ = ManufacturerMaster.objects.get_or_create(
                        name=manufacturer_name
                    )

                # -------------------------
                # MEDICINE
                # -------------------------
                # Parse clean HSN code without trailing float decimals (.0)
                hsn_val = row.get("hsn_code")
                if pd.isna(hsn_val) or str(hsn_val).strip().lower() in ["nan", "none"]:
                    hsn_code = ""
                else:
                    try:
                        hsn_float = float(hsn_val)
                        if hsn_float.is_integer():
                            hsn_code = str(int(hsn_float))
                        else:
                            hsn_code = str(hsn_val)
                    except:
                        hsn_code = str(hsn_val)

                medicine, created_medicine = Medicine.objects.get_or_create(
                    name__iexact=medicine_name,
                    defaults={
                        "name": medicine_name,
                        "hsn_code": hsn_code,
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


# ==============================================================================
# INVENTORY EXPORT VIEWS
# ==============================================================================

class BaseExportStockView(LoginRequiredMixin, View):
    def get_filtered_stocks(self, request):
        queryset = Medicine.objects.all()

        # Get query parameters
        q = request.GET.get("q", "").strip()
        category = request.GET.get("category", "").strip()
        supplier = request.GET.get("supplier", "").strip()
        manufacturer = request.GET.get("manufacturer", "").strip()
        quick_filter = request.GET.get("quick_filter", "").strip()
        sort_by = request.GET.get("sort_by", "").strip()

        # 1. Apply basic search query
        if q:
            queryset = queryset.filter(
                Q(name__icontains=q) |
                Q(hsn_code__icontains=q) |
                Q(stocks__batch_number__icontains=q)
            ).distinct()

        # 2. Apply Category filter
        if category:
            queryset = queryset.filter(ayurvedic_type_id=category)

        # 3. Apply Supplier filter
        if supplier:
            queryset = queryset.filter(stocks__supplier_id=supplier)

        # 4. Apply Manufacturer filter
        if manufacturer:
            queryset = queryset.filter(stocks__manufacturer_id=manufacturer)

        # Annotate required aggregation fields
        from django.db.models import Case, When, Value, CharField
        today = timezone.localdate()

        queryset = queryset.annotate(
            medicine_id=F("id"),
            medicine__name=F("name"),
            medicine__form_type=F("form_type"),
            medicine__gst_percentage=F("gst_percentage"),
            medicine__reorder_level=F("reorder_level"),
            medicine__hsn_code=F("hsn_code"),
            total_qty=Coalesce(
                Sum("stocks__total_base_quantity"),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2))
            ),
            total_batches=Count("stocks"),
            purchase_price=Coalesce(
                Max("stocks__unit_price"),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2))
            ),
            selling_price=Coalesce(
                Max("stocks__selling_price"),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2))
            ),
            nearest_expiry=Min("stocks__expiry_date"),
            category_name=Coalesce(F("ayurvedic_type__name"), Value("Unassigned"), output_field=CharField()),
            base_unit=Coalesce(
                Max("stocks__base_unit"),
                Case(
                    When(form_type="LIQUID", then=Value("ml")),
                    When(form_type="POWDER", then=Value("g")),
                    default=Value("piece"),
                    output_field=CharField()
                )
            )
        )

        # 5. Apply Quick Filters
        if quick_filter == "low_stock":
            queryset = queryset.filter(
                total_qty__lte=F("reorder_level"),
                total_qty__gt=0
            )
        elif quick_filter == "near_expiry":
            queryset = queryset.filter(
                nearest_expiry__isnull=False,
                nearest_expiry__lte=today + timezone.timedelta(days=30),
                nearest_expiry__gte=today
            )
        elif quick_filter == "expired":
            queryset = queryset.filter(
                nearest_expiry__lt=today
            )
        elif quick_filter == "zero_stock":
            queryset = queryset.filter(
                total_qty=0
            )

        # 6. Apply Sorting
        if sort_by == "name_desc":
            queryset = queryset.order_by("-name")
        elif sort_by == "stock_asc":
            queryset = queryset.order_by("total_qty")
        elif sort_by == "stock_desc":
            queryset = queryset.order_by("-total_qty")
        elif sort_by == "expiry_asc":
            queryset = queryset.order_by(F("nearest_expiry").asc(nulls_last=True))
        else:
            queryset = queryset.order_by("name")

        return queryset.values(
            "medicine_id",
            "medicine__name",
            "medicine__hsn_code",
            "medicine__form_type",
            "medicine__gst_percentage",
            "medicine__reorder_level",
            "total_qty",
            "total_batches",
            "purchase_price",
            "selling_price",
            "nearest_expiry",
            "base_unit",
            "category_name",
        )


class ExportStockExcelView(BaseExportStockView):
    def get(self, request):
        import io
        from django.http import HttpResponse

        stocks = self.get_filtered_stocks(request)
        today = timezone.localdate()

        data = []
        for index, item in enumerate(stocks, 1):
            expiry_str = "-"
            if item["nearest_expiry"]:
                expiry_str = item["nearest_expiry"].strftime("%d-%m-%Y")

            status = "Available"
            if item["nearest_expiry"] and item["nearest_expiry"] < today:
                status = "Expired"
            elif item["total_qty"] == 0:
                status = "Zero Stock"
            elif item["total_qty"] <= item["medicine__reorder_level"]:
                status = "Low Stock"

            data.append({
                "S.No": index,
                "Medicine Name": item["medicine__name"],
                "HSN Code": item["medicine__hsn_code"] or "-",
                "GST %": f"{item['medicine__gst_percentage']}%",
                "Stock Quantity": float(item["total_qty"]),
                "Unit": item["base_unit"],
                "Purchase Price (Max)": float(item["purchase_price"]),
                "Selling Price (Max)": float(item["selling_price"]),
                "Nearest Expiry": expiry_str,
                "Status": status
            })

        df = pd.DataFrame(data)

        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="stock_inventory_{today.strftime("%Y-%m-%d")}.xlsx"'

        with io.BytesIO() as b:
            with pd.ExcelWriter(b, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name="Stock Inventory", index=False)
            response.write(b.getvalue())

        return response


class StockPrintView(BaseExportStockView):
    def get(self, request):
        stocks = self.get_filtered_stocks(request)
        today = timezone.localdate()

        context = {
            "stocks": stocks,
            "today": today,
        }
        return render(request, "stockmgmt/stock_print.html", context)
