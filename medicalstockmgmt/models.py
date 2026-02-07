from django.db import models
from django.utils import timezone
from stockmgmt.models import Medicine, Stock  # <-- IMPORTANT

class MedicalStock(models.Model):
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE)
    batch_number = models.CharField(max_length=100)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    manufacture_date = models.DateField(blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Medical Stock"
        verbose_name_plural = "Medical Stocks"

    def __str__(self):
        return f"{self.medicine.name} - Batch {self.batch_number}"
