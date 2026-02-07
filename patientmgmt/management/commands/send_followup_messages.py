from django.core.management.base import BaseCommand
from datetime import date, timedelta
from patientmgmt.models import Patient
from utils.whatsapp import send_whatsapp_template, format_phone

class Command(BaseCommand):
    help = "Send WhatsApp reminders 1 day before patient visit date"

    def handle(self, *args, **kwargs):
        tomorrow = date.today() + timedelta(days=1)
        patients = Patient.objects.filter(visit_date=tomorrow)

        if not patients.exists():
            print("No patients for tomorrow's visit.")
            return

        for patient in patients:
            phone = format_phone(patient.phone)
            if not phone:
                print(f"Skipping invalid phone: {patient.phone}")
                continue

            template_name = "jaspers_market_plain_text_v1"  # must match approved WhatsApp template
            template_params = []

            send_whatsapp_template(phone, template_name, template_params)

        print("WhatsApp visit reminders sent!")
