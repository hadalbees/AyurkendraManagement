from django.db import models
from authentication.models import CustomUser


class CalendarEvent(models.Model):

    EVENT_TYPES = (
        ("OPD", "OPD Duty"),
        ("SURGERY", "Surgery"),
        ("MEETING", "Meeting"),
        ("STAFF", "Staff Task"),
    )

    title = models.CharField(max_length=255)

    event_type = models.CharField(
        max_length=20,
        choices=EVENT_TYPES,
        default="STAFF"
    )

    start_date = models.DateTimeField()

    end_date = models.DateTimeField()

    assigned_to = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE
    )

    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_calendar_events"
    )

    color = models.CharField(
        max_length=20,
        default="#4f46e5"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title