from django.urls import path
from . import views

app_name = "accountmgmt"

urlpatterns = [
    path("dashboard/", views.account_dashboard, name="account_dashboard"),
    path('income/', views.income_list, name='income_list'),
    path("expenses/", views.expense_list, name="expense_list"),
    path("expenses/add/", views.expense_add, name="expense_add"),
    path("ledger/", views.ledger_list, name="ledger_list"),
    path("reports/", views.account_reports, name="account_reports"),

]
