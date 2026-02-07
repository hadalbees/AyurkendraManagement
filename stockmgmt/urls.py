from django.urls import path
from . import views

app_name = "stockmgmt"

urlpatterns = [
    path('stock/', views.StockListView.as_view(), name='stock_list'),
    path('stock/add/', views.StockCreateView.as_view(), name='stock_add'),
    path('stock/<int:pk>/update/', views.StockUpdateView.as_view(), name='stock_update'),
    path('stock/dispense/', views.StockDispenseView.as_view(), name='dispense'),
    path('add-medicine-ajax/', views.add_medicine_ajax, name='add_medicine_ajax'),

]
