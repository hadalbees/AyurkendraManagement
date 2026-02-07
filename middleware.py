from django.shortcuts import redirect
from django.urls import reverse

class GlobalLoginRequiredMiddleware:
    """
    Redirect unauthenticated users to login page
    before any view or error page loads
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        login_url = reverse("login")

        # Allow access to login page & static files
        if (
            request.path == login_url
            or request.path.startswith("/static/")
            or request.path.startswith("/media/")
        ):
            return self.get_response(request)

        # If user is NOT authenticated → redirect to login
        if not request.user.is_authenticated:
            return redirect(login_url)

        return self.get_response(request)
