from django.urls import path
from . import views

app_name = 'attendancemgmt'

urlpatterns = [
    path('', views.attendance_list, name='attendancehome'),               # admin & manager list + marking UI
    path('mark/', views.employee_mark, name='employee_mark'),              # employee quick mark (POST)
    path("admin-mark/<int:user_id>/", views.admin_mark_user, name="admin_mark_user"),
    path('reports/', views.attendance_reports, name='attendance_reports'), # reports + export
    path('export/csv/', views.export_attendance_csv, name='attendance_export_csv'),
]
