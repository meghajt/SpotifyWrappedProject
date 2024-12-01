"""
URL configuration for SpotfyWrapped project.

This file contains URL patterns to route incoming HTTP requests to appropriate views.
"""

from django.contrib import admin
from django.shortcuts import redirect
from django.urls import path, include
from spotifywrapped.views import spotify_callback

def redirect_to_spotifywrapped(request):
    """
    Redirect the root URL ('/') to the 'spotifywrapped/' URL.

    Args:
        request: HttpRequest object.

    Returns:
        HttpResponseRedirect: A redirect to the '/spotifywrapped/' URL.
    """
    return redirect('/spotifywrapped/')

urlpatterns = [
    path("spotifywrapped/", include("spotifywrapped.urls")),
    path('', include('django.contrib.auth.urls')),
    path('', redirect_to_spotifywrapped, name='root_redirect'),  # Redirect root URL
    path("admin/", admin.site.urls),
    path('', include('spotifywrapped.urls')),  # Include your app's URLs
    path('callback/', spotify_callback, name='spotify_callback'),
]
