from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import get_user_model
from django.contrib import messages

from rolemgmt.models import Role

def loginview(request):
    User = get_user_model()
    
    if request.method == 'POST':
        email = request.POST.get('username')  # form field can still be 'username'
        password = request.POST.get('password')

        try:
            # Get the user by email
            user_obj = User.objects.get(email=email)

            # Superuser bypasses all checks
            if not user_obj.is_superuser:

                # Check if user is active
                if not user_obj.is_active:
                    messages.error(request, 'Your account is inactive. Contact admin.')
                    return render(request, 'authentication/login.html')

                # Check if user has a role
                if not user_obj.role_id:
                    messages.error(request, 'No role assigned. Contact admin.')
                    return render(request, 'authentication/login.html')

                # Fetch Role object if role_id is integer
                try:
                    role = Role.objects.get(id=user_obj.role_id)
                except Role.DoesNotExist:
                    messages.error(request, 'Assigned role does not exist. Contact admin.')
                    return render(request, 'authentication/login.html')

                # Check if role is active
                if role.status == 0:
                    messages.error(request, f"Login denied. Your role ({role.name}) is inactive.")
                    return render(request, 'authentication/login.html')

            # Authenticate user
            user = authenticate(request, username=user_obj.username, password=password)

        except User.DoesNotExist:
            user = None

        if user is not None:
            login(request, user)
            return redirect('/dashboard/')
        else:
            messages.error(request, 'Invalid email or password.')

    return render(request, 'authentication/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')

# def logout_view(request):
#     logout(request)
#     return redirect('/login/')
def profile_view(request):
    user = request.user

    if request.method == "POST":
        old_pass = request.POST.get("old_password")
        new_pass = request.POST.get("new_password")
        confirm_pass = request.POST.get("confirm_password")

        # Validate old password
        if not user.check_password(old_pass):
            messages.error(request, "Old password is incorrect!")
            return redirect("profile")

        # New password check
        if new_pass == old_pass:
            messages.error(request, "New password cannot be same as old password!")
            return redirect("profile")

        if new_pass != confirm_pass:
            messages.error(request, "Passwords do not match!")
            return redirect("profile")

        # Save new password
        user.set_password(new_pass)
        user.save()

        messages.success(request, "Password updated successfully!")
        return redirect("profile")

    return render(request, "authentication/profile.html", {"user": user})