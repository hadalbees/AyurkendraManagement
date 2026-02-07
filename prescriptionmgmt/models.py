# prescription/models.py
from decimal import Decimal
from django.db import models
from django.utils import timezone
from patientmgmt.models import Patient
from django.conf import settings

User = settings.AUTH_USER_MODEL

class Prescription(models.Model):
    prescription_no = models.CharField(max_length=30, unique=True)
    patient = models.ForeignKey('patientmgmt.Patient', on_delete=models.CASCADE)
    doctor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)
    next_visit = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.prescription_no} — {self.patient}"

class PrescriptionItem(models.Model):
    prescription = models.ForeignKey(Prescription, related_name='items', on_delete=models.CASCADE)
    # link to stock row so we can reduce it
    stock = models.ForeignKey('stockmgmt.Stock', null=True, blank=True, on_delete=models.SET_NULL)
    medicine_name = models.CharField(max_length=255)
    dosage = models.CharField(max_length=100, blank=True)   # e.g. 1-0-1
    duration_days = models.PositiveIntegerField(default=0)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # units to dispense
    instructions = models.CharField(max_length=255, blank=True, null=True)
    food_timing = models.CharField(max_length=50, blank=True, null=True)
    def __str__(self):
        return f"{self.medicine_name} ({self.prescription.prescription_no})"
