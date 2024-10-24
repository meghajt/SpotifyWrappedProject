from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout
from spotifywrapped.forms import CustomUserCreationForm
from django.views.decorators.cache import cache_control
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import requests


def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            return redirect('home')
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            return redirect('home')
    else:
        form = AuthenticationForm()
    return render(request, 'registration/login.html', {'form': form})

def logout_view(request):
    logout(request)
    request.session.flush()
    return redirect('')

def landing(request):
    return render(request, 'landing.html')

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@login_required
def home(request):
    return render(request, 'home.html')

@login_required()
def delete_account(request):
    if request.method == 'POST':
        user = request.user
        user.delete()
        messages.success(request, "Your account has been deleted successfully.")
        return redirect('landing')

    return render(request, 'delete_account.html')

@login_required()
def profile(request):
    user = request.user
    context = {
        'first_name': user.first_name,
        'last_name': user.last_name,
        'email': user.email,
    }
    return render(request, 'profile.html', context)

@login_required()
def contact_us(request):
    return render(request, 'contact_us.html')

@login_required
def spotify_wrapped(request):
    spotify_data = get_spotify_data(request.user)
    wrapped_summary = create_wrapped_summary(spotify_data)
    context = {
        'wrapped_summary': wrapped_summary,
    }
    return render(request, 'spotify_wrapped.html', context)

def get_spotify_auth_url():
    auth_url = "https://accounts.spotify.com/authorize"
    params = {
        "client_id":'d73cbd01c3ef47739c91ed2422810311',
        "response_type": "code",
        "redirect_uri": 'http://localhost:8000/',
        "scope": "user-top-read user-read-recently-played",
        "show_dialog": True
    }
    response = requests.get(auth_url, params=params)
    return response.url

def get_access_token(code):
    token_url = "https://accounts.spotify.com/api/token"
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": 'http://localhost:8000/',
        "client_id": 'd73cbd01c3ef47739c91ed2422810311',
        "client_secret": '880b50bfa85548d99529c604d05f8bd3',
    }
    
    response = requests.post(token_url, data=payload)
    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        return None

def get_spotify_data(access_token):
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    # Fetch top tracks
    url_tracks = "https://api.spotify.com/v1/me/top/tracks"
    params = {
        "limit": 10,  # Fetch top 10 tracks
        "time_range": "medium_term"  # Options: short_term, medium_term, long_term
    }
    response_tracks = requests.get(url_tracks, headers=headers, params=params)
    
    # Fetch top artists
    url_artists = "https://api.spotify.com/v1/me/top/artists"
    response_artists = requests.get(url_artists, headers=headers, params=params)
    
    if response_tracks.status_code == 200 and response_artists.status_code == 200:
        return {
            'tracks': response_tracks.json(),
            'artists': response_artists.json()
        }
    else:
        return None

def spotify_callback(request):
    code = request.GET.get('code')
    if code:
        access_token = get_access_token(code)
        if access_token:
            spotify_data = get_spotify_data(access_token)
            if spotify_data:
                # Save the data
                SpotifyWrap.objects.create(user=request.user, wrap_data=spotify_data['tracks'])
                return render(request, 'spotify_wrapped.html', {'spotify_data': spotify_data['tracks']})
    messages.error(request, "Failed to retrieve data from Spotify. Please try again.")
    return redirect('home')

def spotify_wrapped(request):
    # Assuming the access token is stored in the user's session
    access_token = request.session.get('spotify_access_token')

    if not access_token:
        # Redirect user to home or error page if access token is missing
        messages.error(request, "Spotify access token missing. Please reconnect.")
        return redirect('home')

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    # Example: Fetching top tracks from Spotify API
    top_tracks_url = "https://api.spotify.com/v1/me/top/tracks"
    params = {
        "limit": 10,  # Fetch top 10 tracks
        "time_range": "medium_term"  # Fetch over a medium-term period
    }

    response = requests.get(top_tracks_url, headers=headers, params=params)

    if response.status_code == 200:
        # Successful API call, get the data
        top_tracks = response.json().get('items', [])
    else:
        # Handle errors (e.g., token expired)
        messages.error(request, "Failed to retrieve Spotify data. Please try again.")
        return redirect('home')

    # Example: Fetching top artists from Spotify API
    top_artists_url = "https://api.spotify.com/v1/me/top/artists"
    response_artists = requests.get(top_artists_url, headers=headers, params=params)

    if response_artists.status_code == 200:
        # Successful API call, get the data
        top_artists = response_artists.json().get('items', [])
    else:
        top_artists = []

    # Pass the data to the template for rendering
    context = {
        'top_tracks': top_tracks,
        'top_artists': top_artists
    }

    return render(request, 'spotify_wrapped.html', context)