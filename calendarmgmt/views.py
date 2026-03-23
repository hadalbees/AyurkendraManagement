from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from .models import CalendarEvent
from authentication.models import CustomUser
import json


@login_required
def calendar_view(request):

    users = CustomUser.objects.select_related("role").filter(is_active=True)

    return render(
        request,
        "calendarmgmt/calendar.html",
        {"users": users}
    )


@login_required
def calendar_events(request):

    events = CalendarEvent.objects.select_related("assigned_to")

    data = []

    for e in events:

        data.append({
            "id": e.id,
            "title": e.title,
            "start": e.start_date.isoformat(),
            "end": e.end_date.isoformat(),
            "color": e.color,

            # extra fields
            "assigned_to": e.assigned_to.id,
            "assigned_name": e.assigned_to.get_full_name() or e.assigned_to.username,
            "event_type": e.event_type
        })

    return JsonResponse(data, safe=False)


@csrf_exempt
@login_required
def create_event(request):

    if request.method == "POST":

        data = json.loads(request.body)

        user = CustomUser.objects.get(id=data["assigned_to"])

        event = CalendarEvent.objects.create(
            title=data["title"],
            start_date=data["start"],
            end_date=data["end"],
            assigned_to=user,
            created_by=request.user,
            color=data["color"]
        )

        return JsonResponse({"success": True, "id": event.id})


@csrf_exempt
@login_required
def update_event(request):

    if request.method == "POST":

        data = json.loads(request.body)

        event = CalendarEvent.objects.get(id=data["id"])

        event.title = data["title"]

        event.color = data["color"]

        event.assigned_to_id = data["assigned_to"]

        event.save()

        return JsonResponse({"success": True})
    
def delete_event(request):

    if request.method == "POST":

        data = json.loads(request.body)

        CalendarEvent.objects.filter(id=data["id"]).delete()

        return JsonResponse({"success": True})