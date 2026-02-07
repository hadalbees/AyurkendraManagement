from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator

from fieldmgmt.models import AyurvedicType, ManufacturerMaster, SupplierMaster

User = settings.AUTH_USER_MODEL

# class Supplier(models.Model):
#     name = models.CharField(max_length=255)
#     contact_person = models.CharField(max_length=255, blank=True, null=True)
#     phone = models.CharField(max_length=50, blank=True, null=True)
#     email = models.EmailField(blank=True, null=True)
#     address = models.TextField(blank=True, null=True)

#     class Meta:
#         verbose_name = "Supplier"
#         verbose_name_plural = "Suppliers" 

#     def __str__(self):
#         return self.name


class Medicine(models.Model):

    name = models.CharField(max_length=255)
    hsn_code = models.CharField(max_length=255)
    ayurvedic_type = models.ForeignKey(
        AyurvedicType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="medicines"
    )
    description = models.TextField(blank=True, null=True)

    reorder_level = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)]
    )
    expiry_days_alert = models.IntegerField(
        default=30,
        validators=[MinValueValidator(0)]
    )
    class Meta:
        verbose_name = "Medicine / Item"
        verbose_name_plural = "Medicines / Items"

    def __str__(self):
        return self.name

class Stock(models.Model):
    UNIT_CHOICES = [
        ('kg', 'Kilogram'),
        ('g', 'Gram'),
        ('mg', 'Milligram'),
        ('l', 'Litre'),
        ('ml', 'Millilitre'),
        ('unit', 'Unit'),  # for pieces
    ]
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE, related_name='stocks')
    batch_number = models.CharField(max_length=100)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])  # supports fractional units
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    price_per_single = models.DecimalField(max_digits=12, decimal_places=6, blank=True, null=True)
    manufacture_date = models.DateField(blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True)
    supplier = models.ForeignKey(SupplierMaster, on_delete=models.SET_NULL, null=True, blank=True)
    manufacturer = models.ForeignKey(ManufacturerMaster, on_delete=models.SET_NULL, null=True, blank=True)
    last_updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='stock_updates')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Stock / Batch"
        verbose_name_plural = "Stock / Batches"
        ordering = ['-expiry_date', 'medicine__name']

    def __str__(self):
        return f"{self.medicine.name} — Batch {self.batch_number}"

    @property
    def is_low_stock(self):
        try:
            return float(self.quantity) <= float(self.medicine.reorder_level)
        except Exception:
            return False

    @property
    def days_to_expiry(self):
        if not self.expiry_date:
            return None
        delta = (self.expiry_date - timezone.localdate()).days
        return delta

    @property
    def is_near_expiry(self):
        if not self.expiry_date:
            return False
        alert_days = self.medicine.expiry_days_alert or 30
        return (self.expiry_date - timezone.localdate()).days <= alert_days


TRANSACTION_TYPES = (
    ('PURCHASE', 'Purchase'),
    ('DISPENSE', 'Dispense'),
    ('ADJUSTMENT', 'Adjustment'),
)


class StockTransaction(models.Model):
    stock_item = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    quantity_change = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_date = models.DateTimeField(default=timezone.now)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='stock_transactions')
    notes = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Stock Transaction"
        verbose_name_plural = "Stock Transactions"
        ordering = ['-transaction_date']

    def __str__(self):
        sign = '+' if self.quantity_change >= 0 else ''
        return f"{self.transaction_type} {sign}{self.quantity_change} for {self.stock_item}"
