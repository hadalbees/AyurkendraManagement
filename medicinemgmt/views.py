from decimal import Decimal, InvalidOperation
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import TemplateView, ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db import transaction, models
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
import csv, datetime

from .models import (
    Medicine, Supplier, Batch, StockMovement,
    Purchase, PurchaseItem,
    SaleInvoice, SaleItem,
    create_batches_from_purchase, reduce_stock_for_sale, restore_stock_for_voided_sale
)

# Dashboard
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from decimal import Decimal
from django.db import models

from .models import (
    Medicine,
    Batch,
    Purchase,
    SaleInvoice,
)
def medicinehome(request):
    return render(request, 'medicinemgmt/medicinehome.html')
class MedicineDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "medicinemgmt/medicinehome.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # Active medicines (your DB has "active", not "is_active")
        ctx['total_medicines'] = Medicine.objects.filter(active=True).count()

        # Low stock
        ctx['low_stock_count'] = Batch.objects.filter(quantity__lte=5).count()

        # Total stock value = quantity * purchase_price
        total_value = Batch.objects.aggregate(
            total=models.Sum(
                models.F('quantity') * models.F('purchase_price'),
                output_field=models.DecimalField()
            )
        )['total'] or Decimal("0.00")

        ctx['total_stock_value'] = total_value

        # Recent 6 purchases (your model = Purchase)
        ctx['recent_purchases'] = Purchase.objects.order_by('-created_at')[:6]

        # Recent 6 sales (SaleInvoice is correct)
        ctx['recent_sales'] = SaleInvoice.objects.filter(is_void=False).order_by('-created_at')[:6]

        return ctx


# Medicine CRUD
class MedicineListView(LoginRequiredMixin, ListView):
    model = Medicine
    template_name = "medicinemgmt/medicinelist.html"
    context_object_name = "medicines"
    paginate_by = 25

    def get_queryset(self):
        qs = Medicine.objects.filter(active=True).order_by('name')
        q = (self.request.GET.get('q') or "").strip()
        if q:
            qs = qs.filter(models.Q(name__icontains=q) | models.Q(code__icontains=q) | models.Q(brand__icontains=q))
        return qs


class MedicineCreateView(LoginRequiredMixin, View):
    template_name = "medicinemgmt/addmedicine.html"

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        code = request.POST.get('code','').strip()
        name = request.POST.get('name','').strip()
        brand = request.POST.get('brand','').strip()
        unit = request.POST.get('unit','strip').strip()
        mrp = request.POST.get('mrp','0').strip()
        selling = request.POST.get('selling_price','0').strip()
        purchase_price = request.POST.get('purchase_price','0').strip()
        gst = request.POST.get('gst','0').strip()
        if not code or not name:
            messages.error(request, "Code and name are required.")
            return render(request, self.template_name, {'data': request.POST})
        try:
            mrp = Decimal(mrp); selling = Decimal(selling); purchase_price = Decimal(purchase_price); gst = Decimal(gst)
        except Exception:
            messages.error(request, "Numeric fields invalid.")
            return render(request, self.template_name, {'data': request.POST})
        med = Medicine.objects.create(
            code=code, name=name, brand=brand, unit=unit,
            mrp=mrp, selling_price=selling, purchase_price=purchase_price, gst_percent=gst
        )
        messages.success(request, "Medicine created.")
        return redirect('medicinemgmt:medicine_list')


class MedicineEditView(LoginRequiredMixin, View):
    template_name = "medicinemgmt/editmedicine.html"

    def get(self, request, pk):
        med = get_object_or_404(Medicine, pk=pk)
        return render(request, self.template_name, {'medicine': med})

    def post(self, request, pk):
        med = get_object_or_404(Medicine, pk=pk)
        med.code = request.POST.get('code','').strip()
        med.name = request.POST.get('name','').strip()
        med.brand = request.POST.get('brand','').strip()
        med.unit = request.POST.get('unit','strip').strip()
        med.mrp = Decimal(request.POST.get('mrp','0') or '0')
        med.selling_price = Decimal(request.POST.get('selling_price','0') or '0')
        med.purchase_price = Decimal(request.POST.get('purchase_price','0') or '0')
        med.gst_percent = Decimal(request.POST.get('gst','0') or '0')
        med.save()
        messages.success(request, "Medicine updated.")
        return redirect('medicinemgmt:medicine_detail', pk=med.pk)


class MedicineDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        med = get_object_or_404(Medicine, pk=pk)
        med.active = False
        med.save()
        messages.success(request, "Medicine deactivated.")
        return redirect('medicinemgmt:medicine_list')


class MedicineDetailView(LoginRequiredMixin, DetailView):
    model = Medicine
    template_name = "medicinemgmt/medicinedetail.html"
    context_object_name = "medicine"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        med = self.get_object()
        ctx['batches'] = med.batches.order_by('expiry_date', 'created_at')
        ctx['purchase_items'] = PurchaseItem.objects.filter(medicine=med).order_by('-purchase__purchase_date')[:20]
        ctx['sale_items'] = SaleItem.objects.filter(medicine=med).order_by('-invoice__sale_date')[:20]
        return ctx


# Batch list and adjust
class BatchListView(LoginRequiredMixin, ListView):
    model = Batch
    template_name = "medicinemgmt/batchlist.html"
    context_object_name = "batches"
    paginate_by = 25

    def get_queryset(self):
        qs = Batch.objects.select_related('medicine').order_by('medicine__name', 'expiry_date')
        q = (self.request.GET.get('q') or "").strip()
        if q:
            qs = qs.filter(models.Q(medicine__name__icontains=q) | models.Q(batch_no__icontains=q))
        return qs


class BatchAdjustView(LoginRequiredMixin, View):
    template_name = "medicinemgmt/batchadjust.html"
    def get(self, request, pk):
        batch = get_object_or_404(Batch, pk=pk)
        return render(request, self.template_name, {'batch': batch})
    def post(self, request, pk):
        batch = get_object_or_404(Batch, pk=pk)
        try:
            qty = Decimal(request.POST.get('quantity','0') or '0')
        except Exception:
            messages.error(request, "Invalid quantity")
            return render(request, self.template_name, {'batch': batch})
        note = request.POST.get('note','Manual adjust')
        batch.quantity = qty
        batch.save()
        StockMovement.objects.create(batch=batch, movement_type="ADJUST", quantity=qty, note=note, reference=f"adjust-{batch.pk}")
        messages.success(request, "Batch adjusted")
        return redirect('medicinemgmt:batch_list')


# Purchases
class PurchaseCreateView(LoginRequiredMixin, View):
    template_name = "medicinemgmt/purchaseform.html"

    def get(self, request):
        suppliers = Supplier.objects.all()
        medicines = Medicine.objects.filter(active=True).order_by('name')
        return render(request, self.template_name, {'suppliers': suppliers, 'medicines': medicines})

    def post(self, request):
        supplier_id = request.POST.get('supplier') or None
        supplier = Supplier.objects.filter(pk=supplier_id).first() if supplier_id else None
        invoice_no = request.POST.get('invoice_no','').strip()
        items_count = int(request.POST.get('items_count') or 0)
        if items_count <= 0:
            messages.error(request, "Add at least one purchase item.")
            return redirect('medicinemgmt:purchase_add')

        with transaction.atomic():
            purchase = Purchase.objects.create(
                supplier=supplier,
                invoice_no=invoice_no,
                purchase_date=request.POST.get('purchase_date') or timezone.localdate(),
                created_by=request.user
            )
            total = Decimal('0.00')
            for i in range(items_count):
                med_id = request.POST.get(f'item_med_{i}')
                if not med_id:
                    continue
                med = get_object_or_404(Medicine, pk=int(med_id))
                qty = Decimal(request.POST.get(f'item_qty_{i}','0') or '0')
                unitp = Decimal(request.POST.get(f'item_unit_{i}','0') or '0')
                batch_no = request.POST.get(f'item_batch_{i}','').strip() or None
                expiry = request.POST.get(f'item_expiry_{i}') or None
                item = PurchaseItem.objects.create(
                    purchase=purchase, medicine=med,
                    batch_no=batch_no, expiry_date=expiry,
                    quantity=qty, unit_price=unitp
                )
                total += item.line_total
            if total <= 0:
                transaction.set_rollback(True)
                messages.error(request, "No valid items added.")
                return redirect('medicinemgmt:purchase_add')
            purchase.total_amount = total
            purchase.save()
            # create batches and movements
            create_batches_from_purchase(purchase)
        messages.success(request, f"Purchase recorded #{purchase.pk}")
        return redirect('medicinemgmt:purchase_list')


class PurchaseListView(LoginRequiredMixin, ListView):
    model = Purchase
    template_name = "medicinemgmt/purchaselist.html"
    context_object_name = "purchases"
    paginate_by = 25

    def get_queryset(self):
        qs = Purchase.objects.order_by('-purchase_date')
        q = (self.request.GET.get('q') or "").strip()
        if q:
            qs = qs.filter(models.Q(invoice_no__icontains=q) | models.Q(supplier__name__icontains=q))
        return qs


class PurchaseDetailView(LoginRequiredMixin, DetailView):
    model = Purchase
    template_name = "medicinemgmt/purchasedetail.html"
    context_object_name = "purchase"


# Sales / Billing
class SaleCreateView(LoginRequiredMixin, View):
    template_name = "medicinemgmt/saleform.html"

    def get(self, request):
        medicines = Medicine.objects.filter(active=True).order_by('name')
        patients = []
        # import patient model lazily
        from django.apps import apps
        Patient = apps.get_model('patientmgmt', 'Patient')
        patients = Patient.objects.filter(is_active=True).order_by('-created_at')[:200]
        return render(request, self.template_name, {'medicines': medicines, 'patients': patients})

    def post(self, request):
        items_count = int(request.POST.get('items_count') or 0)
        patient_id = request.POST.get('patient')
        payment_status = request.POST.get('payment_status') or "PENDING"
        notes = request.POST.get('notes','').strip()
        patient = None
        from django.apps import apps
        Patient = apps.get_model('patientmgmt', 'Patient')
        if patient_id:
            patient = Patient.objects.filter(pk=patient_id).first()

        if items_count <= 0:
            messages.error(request, "Add at least one sale item.")
            return redirect('medicinemgmt:sale_add')

        with transaction.atomic():
            invoice = SaleInvoice.objects.create(
                patient=patient,
                payment_status=payment_status,
                sale_date=request.POST.get('sale_date') or timezone.localdate(),
                created_by=request.user,
                notes=notes
            )
            total = Decimal('0.00')
            for i in range(items_count):
                med_id = request.POST.get(f'item_med_{i}')
                if not med_id:
                    continue
                med = get_object_or_404(Medicine, pk=int(med_id))
                qty = Decimal(request.POST.get(f'item_qty_{i}','0') or '0')
                unitp = Decimal(request.POST.get(f'item_unit_{i}','0') or '0')
                batch_id = request.POST.get(f'item_batch_{i}') or None
                batch = Batch.objects.filter(pk=batch_id).first() if batch_id else None
                si = SaleItem.objects.create(invoice=invoice, medicine=med, batch=batch, quantity=qty, unit_price=unitp)
                total += si.line_total
            if total <= 0:
                transaction.set_rollback(True)
                messages.error(request, "No valid sale items.")
                return redirect('medicinemgmt:sale_add')
            invoice.total_amount = total
            invoice.save()
            try:
                reduce_stock_for_sale(invoice)
            except ValueError as e:
                transaction.set_rollback(True)
                messages.error(request, f"Stock error: {e}")
                return redirect('medicinemgmt:sale_add')
        messages.success(request, f"Sale created #{invoice.pk} — total ₹{invoice.total_amount}")
        return redirect('medicinemgmt:sale_detail', pk=invoice.pk)


class SaleListView(LoginRequiredMixin, ListView):
    model = SaleInvoice
    template_name = "medicinemgmt/salelist.html"
    context_object_name = "sales"
    paginate_by = 25

    def get_queryset(self):
        qs = SaleInvoice.objects.order_by('-sale_date')
        q = (self.request.GET.get('q') or "").strip()
        status = (self.request.GET.get('status') or "").upper().strip()
        if q:
            qs = qs.filter(models.Q(pk__icontains=q) | models.Q(invoice_no__icontains=q))
        if status in ('PAID','PENDING','PARTIAL'):
            qs = qs.filter(payment_status=status)
        return qs


class SaleDetailView(LoginRequiredMixin, DetailView):
    model = SaleInvoice
    template_name = "medicinemgmt/saledetail.html"
    context_object_name = "sale"


class SaleVoidView(LoginRequiredMixin, View):
    def post(self, request, pk):
        invoice = get_object_or_404(SaleInvoice, pk=pk)
        if invoice.is_void:
            messages.info(request, "Invoice already voided.")
            return redirect('medicinemgmt:sale_detail', pk=pk)
        with transaction.atomic():
            # restore stock
            restore_stock_for_voided_sale(invoice)
            invoice.is_void = True
            invoice.save()
        messages.success(request, f"Sale {pk} voided and stock restored.")
        return redirect('medicinemgmt:sale_detail', pk=pk)


# Exports & live counts
class ExportMedicinesCSV(LoginRequiredMixin, View):
    def get(self, request):
        meds = Medicine.objects.filter(active=True).order_by('name')
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="medicines_{datetime.date.today().isoformat()}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Code','Name','Brand','Unit','MRP','Selling','Purchase','GST'])
        for m in meds:
            writer.writerow([m.code, m.name, m.brand, m.unit, str(m.mrp), str(m.selling_price), str(m.purchase_price), str(m.gst_percent)])
        return response


class LiveCountsView(LoginRequiredMixin, View):
    def get(self, request):
        total = Medicine.objects.filter(active=True).count()
        low = Batch.objects.filter(quantity__lte=5).count()
        value = Batch.objects.aggregate(total=models.Sum(models.F('quantity') * models.F('purchase_price'), output_field=models.DecimalField()))['total'] or Decimal('0.00')
        return JsonResponse({'total_medicines': total, 'low_stock': low, 'stock_value': float(value)})
