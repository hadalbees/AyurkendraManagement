from django.contrib import admin

# Register your models here.
from django.contrib import admin

from fieldmgmt.models import AyurvedicType,SupplierMaster
from .models import Medicine, Stock, StockTransaction

@admin.register(SupplierMaster)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email','address')
    search_fields = ('name', 'phone', 'email','address')

@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ('name', 'ayurvedic_type', 'reorder_level', 'expiry_days_alert')
    search_fields = ('name',)

@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ('medicine','unit', 'batch_number', 'quantity', 'expiry_date', 'supplier','manufacturer', 'last_updated_by', 'updated_at')
    list_filter = ('supplier', 'expiry_date')
    search_fields = ('medicine__name', 'batch_number')

@admin.register(StockTransaction)
class StockTransactionAdmin(admin.ModelAdmin):
    list_display = ('stock_item', 'transaction_type', 'quantity_change', 'recorded_by', 'transaction_date')
    list_filter = ('transaction_type',)
    search_fields = ('stock_item__medicine__name', 'stock_item__batch_number')
    
    
@admin.register(AyurvedicType)
class AyurvedicTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'status']
    search_fields = ['name']
    list_filter = ['status']