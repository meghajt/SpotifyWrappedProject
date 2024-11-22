from django.shortcuts import redirect
from django.urls import path
from . import views
from .views import spotify_callback, spotify_wrapped, view_saved_wraps, view_duo_wrapped, display_selected_wrap, invite_duo_wrapped, accept_duo_invitation

urlpatterns = [
    path("", views.landing, name="landing"),
    path("register/", views.register, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("home/", views.home, name="home"),
    path("delete-account/", views.delete_account, name="delete_account"),
    path("profile/", views.profile, name="profile"),
    path("contact-us/", views.contact_us, name="contact_us"),
    path("callback/", views.spotify_callback, name="spotify_callback"),
    path("spotify_wrapped/", spotify_wrapped, name="spotify_wrapped"),
    path("get_spotify_auth_url/", views.get_spotify_auth_url, name="get_spotify_auth_url"),
    path('saved-wraps/', view_saved_wraps, name='view_saved_wraps'),
    path('saved-wraps/<int:wrap_id>/', display_selected_wrap, name='display_selected_wrap'),
    path('invite-duo-wrapped/', invite_duo_wrapped, name='invite_duo_wrapped'),
    path('accept-duo-invitation/<int:duo_id>/', accept_duo_invitation, name='accept_duo_invitation'),
    path('duo-wrapped/<int:duo_id>/', view_duo_wrapped, name='view_duo_wrapped'),
    path('wrap/download/<int:wrap_id>/', views.generate_wrap_image, name='generate_wrap_image'),

]
