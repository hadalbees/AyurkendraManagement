from django.shortcuts import redirect, render, get_object_or_404
from django.contrib import messages
from .models import Role
from django.core.paginator import Paginator
from django.views import View
from django.http import JsonResponse
from fieldmgmt.models import ActivityHistory

def roledashboardview(request):
    role_qs = Role.objects.all().order_by('-created_at')

    paginator = Paginator(role_qs, 10)   # 🔹 10 roles per page
    page_number = request.GET.get('page')
    roles = paginator.get_page(page_number)

    return render(
        request,
        "rolemgmt/rolehome.html",
        {"roles": roles}
    )
class RoleFormView(View):
    template_name = "rolemgmt/roleform.html"

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)

    def post(self, request, *args, **kwargs):
        role_name = request.POST.get("role_name")
        if role_name:
            role = Role.objects.create(role_name=role_name)
            ActivityHistory.objects.create(
                user=request.user,
                action="CREATE",
                module="ROLE",
                record_id=role.id,
                description=f"Role #{role.id} created by {request.user}"
            )
            messages.success(request, f"Role '{role_name}' added successfully!")
            return redirect("roledashboard")
        else:
            messages.error(request, "Please enter a role name.")
            return render(request, self.template_name)
def roleeditform(request, pk):
    role = get_object_or_404(Role, pk=pk)

    if request.method == "POST":
        role_name = request.POST.get("role_name")
        if role_name:
            role.role_name = role_name
            role.save()
            ActivityHistory.objects.create(
                user=request.user,
                action="UPDATE",
                module="ROLE",
                record_id=role.id,
                description=f"Role #{role.id} updated by {request.user}"
            )
            messages.success(request, f"Role '{role_name}' updated successfully!")
            return redirect("roledashboard")
        else:
            messages.error(request, "Please enter a role name.")

    return render(request, "rolemgmt/roleedit.html", {"role": role})
def roledelete(request, pk):
    role = get_object_or_404(Role, pk=pk)
    role.delete()
    ActivityHistory.objects.create(
        user=request.user,
        action="DELETE",
        module="ROLE",
        record_id=role.id,
        description=f"Role #{role.id} deleted by {request.user}"
    )
    messages.success(request, f"Role '{role.role_name}' deleted successfully!")
    return redirect("roledashboard")
def toggle_role_status(request, pk):
    if request.method == "POST":
        role = get_object_or_404(Role, pk=pk)
        # Toggle the status
        role.status = not role.status
        role.save()
        return JsonResponse({"success": True, "status": role.status})
    return JsonResponse({"success": False}, status=400)