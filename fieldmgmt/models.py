from django.db import models

class TherapyMaster(models.Model):
    serial_no = models.CharField(
        max_length=20,
        unique=True,
        blank=True
    )

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    charges = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.serial_no:
            last = TherapyMaster.objects.order_by("-id").first()
            if last and last.serial_no:
                last_num = int(last.serial_no.split("-")[-1])
                self.serial_no = f"THR-{last_num + 1:03d}"
            else:
                self.serial_no = "THR-001"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.serial_no} - {self.name}"

    
    
    
class AyurvedicType(models.Model):
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True, null=True)
    status = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
    
class SupplierMaster(models.Model):
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    status = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class ManufacturerMaster(models.Model):
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    status = models.BooleanField(default=True)

    def __str__(self):
        return self.name
