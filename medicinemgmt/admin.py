from django.contrib import admin
from .models import Supplier, Medicine, Batch, StockMovement, Purchase, PurchaseItem, SaleInvoice, SaleItem

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name','contact','email','created_at')
    search_fields = ('name','contact','email')

@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ('code','name','brand','unit','mrp','selling_price','active')
    search_fields = ('name','code','brand')
    list_filter = ('active','brand')

@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ('medicine','batch_no','expiry_date','quantity','purchase_price')
    search_fields = ('medicine__name','batch_no')

@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('pk','supplier','invoice_no','purchase_date','total_amount','created_at')
    search_fields = ('invoice_no','supplier__name')

@admin.register(SaleInvoice)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('pk','patient','sale_date','total_amount','payment_status','is_void')
    search_fields = ('invoice_no','patient__name')
