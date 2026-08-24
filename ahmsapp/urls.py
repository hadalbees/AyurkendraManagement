from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboardview, name='dashboard'),
    path('global-search/', views.global_search, name='global_search'),
]

