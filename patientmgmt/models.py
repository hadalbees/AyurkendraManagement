# patientmgmt/models.py
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone

from fieldmgmt.models import TherapyMaster

User = settings.AUTH_USER_MODEL


class Patient(models.Model):

    PATIENT_TYPES = (
        ('OP', 'Outpatient'),
        ('IP', 'Inpatient'),
    )

    GENDERS = (
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    )

    # ===== CLINICAL INFO =====
    consultant_doctor = models.CharField(max_length=255, blank=True, null=True)
    department = models.CharField(max_length=255, blank=True, null=True)
    assigned_doctor = models.CharField(max_length=255, blank=True, null=True)

    # ===== PATIENT IDENTIFIERS =====
    patient_unique_id = models.CharField(max_length=20, unique=True)
    prefix = models.CharField(max_length=20, blank=True, null=True)
    patient_name = models.CharField(max_length=255)
    age = models.PositiveIntegerField(default=0)
    gender = models.CharField(max_length=1, choices=GENDERS)

    dob = models.DateField(blank=True, null=True)

    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

    address = models.TextField(blank=True, null=True)

    # ===== EXTRA DETAILS =====
    id_card = models.CharField(max_length=100, blank=True, null=True)
    id_card_image = models.ImageField(
        upload_to="patient/id_cards/",
        blank=True,
        null=True
    )

    emergency_contact = models.CharField(max_length=20, blank=True, null=True)

    patient_type = models.CharField(max_length=2, choices=PATIENT_TYPES)
    visit_date = models.DateField()

    notes = models.TextField(blank=True, null=True)

    # ===== REFERRAL =====
    refered_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referrals"
    )

    # ===== SYSTEM =====
    registered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["patient_name"]),
            models.Index(fields=["phone"]),
        ]

    def __str__(self):
        return f"{self.patient_name} ({self.patient_unique_id})"


class PatientVisit(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="visits")
    diagnosis = models.TextField(blank=True, null=True)
    prescription_notes = models.TextField(blank=True, null=True)
    visit_date = models.DateTimeField(default=timezone.now)

    is_valid = models.BooleanField(default=True)  # keep history; mark invalid rather than delete

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Visit[{self.pk}] {self.patient.patient_name}"


class InpatientAdmission(models.Model):
    STATUS_CHOICES = (
        ('ACTIVE', 'Active'),
        ('DISCHARGED', 'Discharged'),
    )

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="admissions")
    admission_date = models.DateTimeField(default=timezone.now)
    discharge_date = models.DateTimeField(blank=True, null=True)

    room_number = models.CharField(max_length=20, blank=True, null=True)
    bed_id = models.CharField(max_length=20, blank=True, null=True)

    current_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def discharge(self):
        self.current_status = 'DISCHARGED'
        self.discharge_date = timezone.now()
        self.save()

    def __str__(self):
        return f"Admission[{self.pk}] {self.patient.patient_name}"


class BillingInvoice(models.Model):
    PAYMENT_STATUS = (
        ('PENDING', 'Pending'),
        ('PAID', 'Paid'),
        ('PARTIAL', 'Partial'),
    )

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="invoices")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='PENDING')

    invoice_date = models.DateField(default=timezone.localdate)
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    is_void = models.BooleanField(default=False)  # void instead of delete

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def mark_void(self):
        self.is_void = True
        self.save()

    def __str__(self):
        return f"Invoice {self.pk} - {self.patient.patient_name}"


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(BillingInvoice, on_delete=models.CASCADE, related_name="items")
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.line_total = (self.quantity or Decimal('0.00')) * (self.unit_price or Decimal('0.00'))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.description} = {self.line_total}"


class Appointment(models.Model):

    APPOINTMENT_TYPES = (
        ('CONSULT', 'Consultation'),
        ('THERAPY', 'Therapy'),
        ('BOTH', 'Both'),
    )

    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    )

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="appointments")
    appointment_type = models.CharField(max_length=10, choices=APPOINTMENT_TYPES)
    therapy = models.ForeignKey(TherapyMaster, on_delete=models.SET_NULL, null=True, blank=True)

    appointment_date = models.DateField()
    appointment_time = models.TimeField()

    notes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.patient.patient_name} - {self.appointment_date}"
    
    
    
class WhatsAppLog(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("sent", "Sent"),
        ("failed", "Failed"),
    )

    patient = models.ForeignKey(
        "patientmgmt.Patient",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    phone = models.CharField(max_length=15)
    message = models.TextField()
    image = models.FileField(upload_to="whatsapp/images/", null=True, blank=True)
    document = models.FileField(upload_to="whatsapp/docs/", null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.phone} - {self.status}"