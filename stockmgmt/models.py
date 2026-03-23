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


# models.py

class Medicine(models.Model):

    FORM_CHOICES = [
        ('LIQUID', 'Liquid'),
        ('POWDER', 'Powder'),
        ('PIECE', 'Piece / Tablet'),
    ]

    name = models.CharField(max_length=255)

    hsn_code = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="HSN code for GST billing"
    )

    form_type = models.CharField(
        max_length=20,
        choices=FORM_CHOICES
    )

    ayurvedic_type = models.ForeignKey(
        "fieldmgmt.AyurvedicType",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    description = models.TextField(blank=True, null=True)

    # ✅ GST Percentage
    gst_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text="Enter GST % (Example: 5, 12, 18)"
    )

    # ✅ Stock Control
    reorder_level = models.PositiveIntegerField(
        default=0,
        help_text="Minimum stock level alert"
    )

    # ✅ Expiry Alert
    expiry_days_alert = models.PositiveIntegerField(
        default=30,
        help_text="Alert before expiry (in days)"
    )

    # ✅ Created Date (SAFE)
    created_at = models.DateTimeField(default=timezone.now)

    # ✅ Updated Date (Recommended)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['name']
        verbose_name = "Medicine"
        verbose_name_plural = "Medicines"

    def __str__(self):
        return f"{self.name} ({self.form_type})"

class Stock(models.Model):

    BASE_UNIT_CHOICES = [
        ('g', 'Gram (g)'),
        ('ml', 'Millilitre (ml)'),
        ('piece', 'Piece / Tablet'),
    ]

    medicine = models.ForeignKey(
        "stockmgmt.Medicine",
        on_delete=models.CASCADE,
        related_name="stocks"
    )

    batch_number = models.CharField(max_length=100)

    base_unit = models.CharField(
        max_length=10,
        choices=BASE_UNIT_CHOICES
    )

    # GST INCLUDED purchase price
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Purchase price including GST"
    )

    # Selling price (editable)
    selling_price = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    # Extracted GST amount (calculated)
    gst_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    pack_size = models.DecimalField(max_digits=10, decimal_places=2)
    number_of_packs = models.DecimalField(max_digits=10, decimal_places=2)

    total_base_quantity = models.DecimalField(max_digits=12, decimal_places=2)

    price_per_base_unit = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        blank=True,
        null=True
    )

    manufacture_date = models.DateField(blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True)

    supplier = models.ForeignKey(
        "fieldmgmt.SupplierMaster",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    manufacturer = models.ForeignKey(
        "fieldmgmt.ManufacturerMaster",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    last_updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.medicine.name} - Batch {self.batch_number}"


    @property
    def is_low_stock(self):
        try:
            return float(self.total_base_quantity) <= float(self.medicine.reorder_level)
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
