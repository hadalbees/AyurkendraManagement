from django.urls import path
from . import views

app_name = "stockmgmt"

urlpatterns = [
    path('stock/', views.StockListView.as_view(), name='stock_list'),
    path('stock/add/', views.StockCreateView.as_view(), name='stock_add'),
    path('stock/<int:pk>/update/', views.StockUpdateView.as_view(), name='stock_update'),
    path('stock/<int:pk>/delete/',views.stock_delete,name='stock_delete'),
    path('stock/dispense/', views.StockDispenseView.as_view(), name='dispense'),
    path("add-medicine-ajax/", views.add_medicine_ajax, name="add_medicine_ajax"),
    path("medicine/update/", views.update_medicine, name="update_medicine"),
    path("bulk-import/", views.bulk_import_stock, name="bulk_import_stock"),
    path("medicine-check/",views.medicine_check,name="medicine_check"),
    path(
        "stock/details/<int:medicine_id>/",
        views.stock_details,
        name="stock_details",
    ),
]
