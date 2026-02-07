from django.db import models
from django.conf import settings
from patientmgmt.models import Patient

REPORT_TYPE_CHOICES = [
    ("LAB", "Lab Report"),
    ("SCAN", "Scan / X-Ray"),
    ("PRESCRIPTION", "Prescription"),
    ("DISCHARGE", "Discharge Summary"),
    ("OTHER", "Other"),
]

def patient_report_path(instance, filename):
    folder = instance.patient.patient_unique_id or f"patient_{instance.patient.id}"
    return f"patient_reports/{folder}/{filename}"

class PatientReport(models.Model):
    patient = models.ForeignKey(Patient, related_name="reports", on_delete=models.CASCADE)
    report_title = models.CharField(max_length=255)
    report_type = models.CharField(max_length=30, choices=REPORT_TYPE_CHOICES)
    report_date = models.DateField()
    uploaded_file = models.FileField(upload_to=patient_report_path)
    notes = models.TextField(blank=True, null=True)

    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.patient.patient_name} - {self.report_title}"
