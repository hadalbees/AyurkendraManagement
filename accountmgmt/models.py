from django.db import models
from django.utils import timezone
from authentication.models import CustomUser

class Expense(models.Model):

    CATEGORY_CHOICES = (
        ("Salary", "Salary"),
        ("Rent", "Rent"),
        ("Electricity", "Electricity"),
        ("Purchase", "Purchase"),
        ("Maintenance", "Maintenance"),
        ("Other", "Other"),
    )

    PAYMENT_MODES = (
        ("Cash", "Cash"),
        ("Card", "Card"),
        ("UPI", "UPI"),
        ("NetBanking", "Net Banking"),
        ("Cheque", "Cheque"),
    )

    expense_date = models.DateField(default=timezone.localdate)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    # ✅ NEW FIELD
    payment_mode = models.CharField(
        max_length=20,
        choices=PAYMENT_MODES,
        default="Cash"
    )

    attachment = models.FileField(
        upload_to="expenses/",
        blank=True,
        null=True
    )

    paid_by = models.ForeignKey(
        CustomUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.category} - ₹{self.amount}"
