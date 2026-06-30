from django.db import models
from django.utils import timezone
from django.conf import settings
from authentication.models import CustomUser
from fieldmgmt.models import TherapyMaster
from patientmgmt.models import Patient
from decimal import Decimal

class MedicalBill(models.Model):
    bill_no = models.CharField(max_length=30, unique=True)
    # reference patientmgmt.Patient (your patient app must be installed)
    patient = models.ForeignKey(
        'patientmgmt.Patient',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    customer_name = models.CharField(max_length=150, blank=True, null=True)
    customer_age = models.PositiveIntegerField(blank=True, null=True)
    customer_gender = models.CharField(max_length=20, blank=True, null=True)

    doctor_name = models.CharField(max_length=150, blank=True)
    bill_date = models.DateField()
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_mode = models.CharField(
        max_length=20,
        choices=(
            ("Cash", "Cash"),
            ("Card", "Card"),
            ("UPI", "UPI"),
            ("NetBanking", "Net Banking"),
            ("Insurance", "Insurance"),
        ),
        default="Cash"
    )
    payment_status = models.CharField(max_length=20, choices=[('Paid','Paid'),('Pending','Pending')], default='Pending')
    remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.bill_no} - {self.patient}"


class MedicineItem(models.Model):
    bill = models.ForeignKey(MedicalBill, related_name='items', on_delete=models.CASCADE)
    medicine_name = models.CharField(max_length=150)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField()
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.medicine_name} x{self.quantity} ({self.bill.bill_no})"
    
    
    


# reference patientmgmt.Patient (must exist)


class InpatientBill(models.Model):

    bill_no = models.CharField(max_length=30, unique=True)

    patient = models.ForeignKey(
        'patientmgmt.Patient',
        on_delete=models.CASCADE
    )

    doctor_name = models.CharField(max_length=150, blank=True)

    admit_date = models.DateField(null=True, blank=True)
    discharge_date = models.DateField(null=True, blank=True)

    # -------- BILL AMOUNTS --------
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )

    # Discount %
    discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00')
    )

    # Discount amount
    discount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )

    tax = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )

    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    advance_payment = models.DecimalField(
    max_digits=12,
    decimal_places=2,
    default=Decimal("0.00")
    )

    balance_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    # -------- PAYMENT --------
    payment_mode = models.CharField(
        max_length=20,
        choices=(
            ("Cash", "Cash"),
            ("Card", "Card"),
            ("UPI", "UPI"),
            ("NetBanking", "Net Banking"),
            ("Insurance", "Insurance"),
        ),
        default="Cash"
    )

    payment_status = models.CharField(
        max_length=20,
        choices=[
            ('Paid', 'Paid'),
            ('Pending', 'Pending')
        ],
        default='Pending'
    )

    # -------- AUDIT --------
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    created_at = models.DateTimeField(auto_now_add=True)

    remarks = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.bill_no} ({self.patient})"

class InpatientItem(models.Model):
    ITEM_TYPES = (
        ('room','Room'),
        ('medicine','Medicine'),
        ('treatment','Treatment'),
        ('lab','Lab'),
        ('other','Other'),
    )
    bill = models.ForeignKey(InpatientBill, related_name='items', on_delete=models.CASCADE)
    item_type = models.CharField(max_length=20, choices=ITEM_TYPES, default='other')
    item_name = models.CharField(max_length=255)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    # when it's a medicine, optionally link stock record so we can reduce quantity
    medical_stock = models.ForeignKey('medicalstockmgmt.MedicalStock', null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"{self.item_name} x{self.quantity} ({self.bill.bill_no})"

class OutpatientBill(models.Model):
    bill_no = models.CharField(max_length=20, unique=True)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    doctor_name = models.CharField(max_length=150)
    visit_date = models.DateField()

    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
        # Discount %
    discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00')
    )

    # Discount amount
    discount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_mode = models.CharField(
        max_length=20,
        choices=(
            ("Cash", "Cash"),
            ("Card", "Card"),
            ("UPI", "UPI"),
            ("NetBanking", "Net Banking"),
            ("Insurance", "Insurance"),
        ),
        default="Cash"
    )
    payment_status = models.CharField(max_length=20, choices=[('Paid','Paid'),('Pending','Pending')], default='Pending')
    created_by = models.ForeignKey(CustomUser, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.bill_no


class OutpatientItem(models.Model):
    bill = models.ForeignKey(OutpatientBill, related_name="items", on_delete=models.CASCADE)
    item_name = models.CharField(max_length=255)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.item_name} x {self.quantity}"
 
 
class TherapyBill(models.Model):
    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    walkin_name = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    customer_type = models.CharField(
        max_length=20,
        default="patient"
    )
    bill_no = models.CharField(max_length=20, unique=True)
    bill_date = models.DateField(default=timezone.localdate)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    advance_payment = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    payment_mode = models.CharField(
        max_length=20,
        choices=(
            ("Cash", "Cash"),
            ("Card", "Card"),
            ("UPI", "UPI"),
            ("NetBanking", "Net Banking"),
            ("Insurance", "Insurance"),
        ),
        default="Cash"
    )

    payment_status = models.CharField(max_length=20, default="Pending")
    remarks = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(default=timezone.now)
    def __str__(self):
        return f"SN-{self.serial_no} | {self.bill_no} | {self.patient.patient_name}"   

class TherapyBillItem(models.Model):
    bill = models.ForeignKey(TherapyBill, on_delete=models.CASCADE, related_name="items")
    therapy = models.ForeignKey(TherapyMaster, on_delete=models.SET_NULL, null=True)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.IntegerField(default=1)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.therapy.name if self.therapy else 'Therapy'} x {self.quantity}"

    
    
class HospitalSetting(models.Model):
    hospital_name = models.CharField(max_length=255)
    hospital_logo = models.ImageField(upload_to='hospital/logo/', blank=True, null=True)

    address = models.TextField()
    phone = models.CharField(max_length=50)
    landline = models.CharField(max_length=50)
    email = models.EmailField(blank=True, null=True)

    registration_number = models.CharField(max_length=100)
    gst_number = models.CharField(max_length=50, blank=True, null=True)

    consultation_gst = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    therapy_gst = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    updated_at = models.DateTimeField(auto_now=True)