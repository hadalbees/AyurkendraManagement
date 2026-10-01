# prescription/models.py
from decimal import Decimal
from django.db import models
from django.utils import timezone
from patientmgmt.models import Patient
from django.conf import settings
from fieldmgmt.models import Adjuvant

User = settings.AUTH_USER_MODEL

class Prescription(models.Model):
    prescription_no = models.CharField(max_length=30, unique=True)
    patient = models.ForeignKey('patientmgmt.Patient', on_delete=models.CASCADE)
    doctor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    # ===== CASE SHEET CLINICAL FIELDS =====
    occupation = models.CharField(max_length=255, blank=True, null=True)
    presenting_complaints = models.TextField(blank=True, null=True)
    associated_complaints = models.TextField(blank=True, null=True)
    history_present_illness = models.TextField(blank=True, null=True)
    history_past_illness = models.TextField(blank=True, null=True)

    # Co-morbidities & Current Meds
    comorbid_diabetes = models.BooleanField(default=False)
    comorbid_hypertension = models.BooleanField(default=False)
    comorbid_thyroid = models.BooleanField(default=False)
    comorbid_cardiac = models.BooleanField(default=False)
    comorbid_kidney = models.BooleanField(default=False)
    comorbid_others = models.CharField(max_length=255, blank=True, null=True)
    current_medications = models.TextField(blank=True, null=True)

    # Vitals / Ashtasthana & Physical Exam Grid (16 fields matching case sheet)
    exam_malam = models.CharField(max_length=100, blank=True, null=True)
    exam_nadi = models.CharField(max_length=100, blank=True, null=True)
    exam_jivha = models.CharField(max_length=100, blank=True, null=True)
    exam_akri = models.CharField(max_length=100, blank=True, null=True)

    exam_diet_habit = models.CharField(max_length=100, blank=True, null=True)
    exam_mutr = models.CharField(max_length=100, blank=True, null=True)
    exam_shabda = models.CharField(max_length=100, blank=True, null=True)
    exam_bp = models.CharField(max_length=100, blank=True, null=True)

    exam_addiction = models.CharField(max_length=100, blank=True, null=True)
    exam_lmp = models.CharField(max_length=100, blank=True, null=True)
    exam_sharira = models.CharField(max_length=100, blank=True, null=True)
    exam_sparsha = models.CharField(max_length=100, blank=True, null=True)

    exam_allergies = models.CharField(max_length=100, blank=True, null=True)
    exam_pulse = models.CharField(max_length=100, blank=True, null=True)
    exam_shir = models.CharField(max_length=100, blank=True, null=True)
    exam_nakha = models.CharField(max_length=100, blank=True, null=True)

    # Additional fields to match exact case sheet image
    exam_muthra = models.CharField(max_length=100, blank=True, null=True)
    exam_nidra = models.CharField(max_length=100, blank=True, null=True)
    exam_agni = models.CharField(max_length=100, blank=True, null=True)
    exam_height = models.CharField(max_length=100, blank=True, null=True)
    exam_weight = models.CharField(max_length=100, blank=True, null=True)
    exam_og_history = models.CharField(max_length=100, blank=True, null=True)
    exam_prakrithi = models.CharField(max_length=100, blank=True, null=True)
    exam_temp = models.CharField(max_length=100, blank=True, null=True)
    exam_rr = models.CharField(max_length=100, blank=True, null=True)

    @property
    def get_muthra(self):
        return self.exam_muthra or self.exam_mutr or ""

    @property
    def get_nidra(self):
        return self.exam_nidra or self.exam_nadi or ""

    @property
    def get_agni(self):
        return self.exam_agni or self.exam_jivha or ""

    @property
    def get_height(self):
        return self.exam_height or self.exam_akri or ""

    @property
    def get_weight(self):
        return self.exam_weight or self.exam_shabda or ""

    @property
    def get_og_history(self):
        return self.exam_og_history or self.exam_sharira or ""

    @property
    def get_prakrithi(self):
        return self.exam_prakrithi or self.exam_sparsha or ""

    @property
    def get_temp(self):
        return self.exam_temp or self.exam_shir or ""

    @property
    def get_rr(self):
        return self.exam_rr or self.exam_nakha or ""

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
    adjuvant = models.ForeignKey(
        Adjuvant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    def __str__(self):
        return f"{self.medicine_name} ({self.prescription.prescription_no})"

class TreatmentPlanItem(models.Model):
    prescription = models.ForeignKey(Prescription, related_name='treatment_items', on_delete=models.CASCADE)
    treatment_name = models.CharField(max_length=255)
    tailam = models.CharField(max_length=255, blank=True, null=True)
    instructions = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.treatment_name} ({self.prescription.prescription_no})"

