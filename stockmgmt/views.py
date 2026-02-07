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

from fieldmgmt.models import AyurvedicType, ManufacturerMaster, SupplierMaster
from .models import Stock, Medicine, StockTransaction


# --------------------------------------------------
# Helper: calculate price per single unit
# --------------------------------------------------
def calculate_price_per_single(selling_price, unit):
    try:
        selling_price = Decimal(str(selling_price).replace(",", "").strip())
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")

    unit = (unit or "").strip().lower()

    conversions = {
        "kg": Decimal("1000"),
        "g":  Decimal("1000"),
        "mg": Decimal("1"),
        "l":  Decimal("1000"),
        "ml": Decimal("1"),
    }

    factor = conversions.get(unit, Decimal("1"))
    if factor <= 0:
        return Decimal("0")

    return selling_price / factor


# --------------------------------------------------
# Stock List View
# --------------------------------------------------
class StockListView(LoginRequiredMixin, ListView):
    model = Stock
    template_name = "stockmgmt/stockhome.html"
    context_object_name = "stocks"
    paginate_by = 50

    def get_queryset(self):
        qs = super().get_queryset().select_related("medicine", "supplier")

        q_name = self.request.GET.get("q", "").strip()
        low_stock = self.request.GET.get("low_stock")
        near_expiry = self.request.GET.get("near_expiry")

        if q_name:
            qs = qs.filter(
                Q(medicine__name__icontains=q_name) |
                Q(batch_number__icontains=q_name)
            )

        if low_stock:
            qs = qs.filter(quantity__lte=models.F("medicine__reorder_level"))

        if near_expiry:
            today = timezone.localdate()
            qs = qs.filter(
                expiry_date__isnull=False,
                expiry_date__lte=today + timezone.timedelta(days=30)
            )

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = self.request.GET.get("q", "")
        ctx["low_stock"] = bool(self.request.GET.get("low_stock"))
        ctx["near_expiry"] = bool(self.request.GET.get("near_expiry"))
        ctx["ayurvedic_forms"] = AyurvedicType.objects.filter(status=True)
        ctx["suppliers"] = SupplierMaster.objects.filter(status=True)
        ctx["manufacturers"] = ManufacturerMaster.objects.filter(status=True)
        return ctx


# --------------------------------------------------
# Add Medicine (AJAX)
# --------------------------------------------------
def add_medicine_ajax(request):
    if request.method != "POST":
        messages.error(request, "Invalid request method.")
        return redirect("stockmgmt:stock_list")

    name = request.POST.get("name", "").strip()
    hsn_code = request.POST.get("hsn_code", "").strip()
    ayurvedic_type_id = request.POST.get("ayurvedic_type")
    description = request.POST.get("description", "")
    reorder_level = request.POST.get("reorder_level") or 0

    if not name:
        messages.error(request, "Medicine name is required.")
        return redirect("stockmgmt:stock_list")

    ayurvedic_type = None
    if ayurvedic_type_id and ayurvedic_type_id != "0":
        try:
            ayurvedic_type = AyurvedicType.objects.get(id=ayurvedic_type_id)
        except AyurvedicType.DoesNotExist:
            messages.error(request, "Invalid Ayurvedic type selected.")
            return redirect("stockmgmt:stock_list")

    Medicine.objects.create(
        name=name,
        hsn_code=hsn_code,
        ayurvedic_type=ayurvedic_type,
        description=description,
        reorder_level=reorder_level,
    )

    messages.success(request, f"Medicine '{name}' added successfully.")
    return redirect("stockmgmt:stock_list")
# --------------------------------------------------
# Stock Create View
# --------------------------------------------------
class StockCreateView(LoginRequiredMixin, CreateView):
    model = Stock
    fields = [
        "medicine", "unit", "batch_number",
        "quantity", "unit_price", "selling_price",
        "manufacture_date", "expiry_date",
        "supplier", "manufacturer",
    ]
    template_name = "stockmgmt/stockform.html"
    success_url = reverse_lazy("stockmgmt:stock_list")

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.last_updated_by = self.request.user

        obj.price_per_single = calculate_price_per_single(
            obj.selling_price,
            obj.unit
        )

        obj.save()

        StockTransaction.objects.create(
            stock_item=obj,
            transaction_type="PURCHASE",
            quantity_change=obj.quantity,
            recorded_by=self.request.user,
            transaction_date=timezone.now(),
            notes="Initial stock creation",
        )

        messages.success(
            self.request,
            f"Stock added successfully. Price per unit: {obj.price_per_single}"
        )

        return super().form_valid(form)


# --------------------------------------------------
# Stock Update View
# --------------------------------------------------
class StockUpdateView(LoginRequiredMixin, UpdateView):
    model = Stock
    fields = [
        "medicine", "unit", "batch_number",
        "quantity", "unit_price", "selling_price",
    ]
    template_name = "stockmgmt/stockform.html"
    success_url = reverse_lazy("stockmgmt:stock_list")

    def form_valid(self, form):
        old_obj = self.get_object()
        old_qty = Decimal(old_obj.quantity)

        obj = form.save(commit=False)

        try:
            delta = Decimal(obj.quantity) - old_qty
        except Exception:
            delta = None

        obj.price_per_single = calculate_price_per_single(
            obj.selling_price,
            obj.unit
        )

        obj.last_updated_by = self.request.user
        obj.save()

        if delta and delta != 0:
            StockTransaction.objects.create(
                stock_item=obj,
                transaction_type="ADJUSTMENT",
                quantity_change=delta,
                recorded_by=self.request.user,
                transaction_date=timezone.now(),
                notes="Stock quantity updated",
            )

        messages.success(
            self.request,
            f"Stock updated successfully. New price per unit: {obj.price_per_single}"
        )

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
