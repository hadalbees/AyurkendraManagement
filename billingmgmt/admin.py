from django.contrib import admin
from .models import MedicalBill, MedicineItem

class MedicineItemInline(admin.TabularInline):
    model = MedicineItem
    extra = 0

@admin.register(MedicalBill)
class MedicalBillAdmin(admin.ModelAdmin):
    list_display = ('bill_no', 'patient', 'bill_date', 'total', 'payment_status')
    inlines = [MedicineItemInline]
