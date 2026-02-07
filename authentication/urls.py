from django.urls import path
from . import views

urlpatterns = [
    path('', views.loginview, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
]