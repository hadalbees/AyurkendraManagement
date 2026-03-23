from django.urls import path
from . import views

app_name = "calendarmgmt"

urlpatterns = [

    path("", views.calendar_view, name="calendar"),

    path("events/", views.calendar_events, name="calendar_events"),

    path("create/", views.create_event, name="create_event"),

    path("update/", views.update_event, name="update_event"),
    path("delete/", views.delete_event, name="delete_event"),

]