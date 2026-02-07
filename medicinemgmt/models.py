# medicinemgmt/models.py
from django.db import models
from decimal import Decimal
from django.db import models, transaction
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator

# Create your models here.


User = settings.AUTH_USER_MODEL

class Supplier(models.Model):
    name = models.CharField(max_length=255)
    contact = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    gstin = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Medicine(models.Model):
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    brand = models.CharField(max_length=255, blank=True, null=True)
    unit = models.CharField(max_length=50, default="strip")  # strip, bottle
    hsn_code = models.CharField(max_length=50, blank=True, null=True)
    mrp = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    gst_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def total_stock(self):
        # sum of all non-expired batches quantity
        return self.batches.filter(quantity__gt=0).aggregate(total=models.Sum('quantity'))['total'] or Decimal('0.00')


class Batch(models.Model):
    """
    Per-batch stock record. Created during purchase.
    """
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE, related_name="batches")
    batch_no = models.CharField(max_length=128, blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(0)])
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    mrp = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["expiry_date", "created_at"]

    def __str__(self):
        return f"{self.medicine.name} - {self.batch_no or 'batch'} ({self.quantity})"

    def is_expired(self):
        if not self.expiry_date:
            return False
        return self.expiry_date < timezone.localdate()


class StockMovement(models.Model):
    """
    Ledger for stock changes - purchase(+), sale(-), return(+)
    """
    MOVEMENT_CHOICES = (("PURCHASE", "Purchase"), ("SALE", "Sale"), ("RETURN", "Return"), ("ADJUST", "Adjust"))
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name="movements")
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_CHOICES)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reference = models.CharField(max_length=255, blank=True, null=True)  # e.g invoice id or purchase id

    class Meta:
        ordering = ["-created_at"]


class Purchase(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    invoice_no = models.CharField(max_length=255, blank=True, null=True)
    purchase_date = models.DateField(default=timezone.localdate)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Purchase[{self.pk}] {self.supplier} - {self.total_amount}"


class PurchaseItem(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name="items")
    medicine = models.ForeignKey(Medicine, on_delete=models.PROTECT)
    batch_no = models.CharField(max_length=128, blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    line_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    def save(self, *args, **kwargs):
        self.line_total = (self.quantity or Decimal("0.00")) * (self.unit_price or Decimal("0.00"))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.medicine} x {self.quantity}"


class SaleInvoice(models.Model):
    PAYMENT_STATUS = (("PENDING", "Pending"), ("PAID", "Paid"), ("PARTIAL", "Partial"))
    patient = models.ForeignKey("patientmgmt.Patient", on_delete=models.SET_NULL, null=True, blank=True, related_name="medicine_bills")
    invoice_no = models.CharField(max_length=255, blank=True, null=True)
    sale_date = models.DateField(default=timezone.localdate)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default="PENDING")
    is_void = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Sale[{self.pk}] {self.total_amount}"


class SaleItem(models.Model):
    invoice = models.ForeignKey(SaleInvoice, on_delete=models.CASCADE, related_name="items")
    medicine = models.ForeignKey(Medicine, on_delete=models.PROTECT)
    batch = models.ForeignKey(Batch, on_delete=models.PROTECT, null=True, blank=True, help_text="Batch used (if chosen). If blank, FIFO will be used.")
    quantity = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    line_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    def save(self, *args, **kwargs):
        self.line_total = (self.quantity or Decimal("0.00")) * (self.unit_price or Decimal("0.00"))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.medicine} x {self.quantity}"


# ----------------------------
# Utility functions for stock
# ----------------------------
def create_batches_from_purchase(purchase: Purchase):
    """
    For each PurchaseItem create/update Batch and StockMovement
    """
    for it in purchase.items.all():
        batch, created = Batch.objects.get_or_create(
            medicine=it.medicine,
            batch_no=it.batch_no or "",
            expiry_date=it.expiry_date
        )
        # increase batch quantity
        batch.quantity = (batch.quantity or Decimal("0.00")) + (it.quantity or Decimal("0.00"))
        batch.purchase_price = it.unit_price
        batch.mrp = it.medicine.mrp or it.medicine.mrp
        batch.save()
        StockMovement.objects.create(
            batch=batch,
            movement_type="PURCHASE",
            quantity=it.quantity,
            note=f"Purchase {purchase.pk}",
            reference=str(purchase.pk)
        )


def reduce_stock_for_sale(invoice: SaleInvoice):
    """
    Deduct quantities from batches using FIFO (earliest expiry first),
    and create StockMovement records. Raises ValueError if insufficient stock.
    """
    for it in invoice.items.all():
        qty_to_deduct = it.quantity or Decimal("0.00")
        # If batch specified, use it first
        if it.batch:
            batch = it.batch
            if batch.quantity < qty_to_deduct:
                raise ValueError(f"Insufficient stock in batch {batch.batch_no} for {it.medicine.name}")
            batch.quantity = batch.quantity - qty_to_deduct
            batch.save()
            StockMovement.objects.create(batch=batch, movement_type="SALE", quantity=-qty_to_deduct, note=f"Sale {invoice.pk}", reference=str(invoice.pk))
            continue

        # FIFO: prefer non-expired batches with earliest expiry
        available_batches = Batch.objects.filter(medicine=it.medicine, quantity__gt=0).order_by('expiry_date', 'created_at')
        remaining = qty_to_deduct
        for b in available_batches:
            if remaining <= 0:
                break
            take = min(b.quantity, remaining)
            b.quantity = b.quantity - take
            b.save()
            StockMovement.objects.create(batch=b, movement_type="SALE", quantity=-take, note=f"Sale {invoice.pk}", reference=str(invoice.pk))
            remaining -= take

        if remaining > 0:
            raise ValueError(f"Insufficient stock for {it.medicine.name}. Short by {remaining}")


def restore_stock_for_voided_sale(invoice: SaleInvoice):
    """
    When a sale is voided, rolls back the stock movements for that invoice
    by adding quantities back to batches and recording RETURN movement.
    (Assumes sale movements reference invoice pk in StockMovement.reference)
    """
    movements = StockMovement.objects.filter(reference=str(invoice.pk), movement_type="SALE")
    for mv in movements:
        batch = mv.batch
        # mv.quantity is negative for sale, so restore -mv.quantity
        restore_qty = -mv.quantity
        batch.quantity = (batch.quantity or Decimal("0.00")) + restore_qty
        batch.save()
        StockMovement.objects.create(batch=batch, movement_type="RETURN", quantity=restore_qty, note=f"Restore for voided sale {invoice.pk}", reference=str(invoice.pk))

