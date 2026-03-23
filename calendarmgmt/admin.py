from django.contrib import admin
from .models import CalendarEvent


@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "assigned_to",
        "start_date",
        "end_date",
    )