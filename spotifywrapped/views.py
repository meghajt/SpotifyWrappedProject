from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout
from django.contrib.auth.models import User
from spotifywrapped.forms import CustomUserCreationForm
from django.views.decorators.cache import cache_control
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import requests
from django.http import HttpResponse
from app_secrets import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
from .models import SpotifyWrap, DuoWrapped
from django.shortcuts import get_object_or_404


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
    return redirect('landing')


def landing(request):
    return render(request, 'landing.html')


@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@login_required
def home(request):
    return render(request, 'home.html')


@login_required
def delete_account(request):
    if request.method == 'POST':
        user = request.user
        user.delete()
        messages.success(request, "Your account has been deleted successfully.")
        return redirect('landing')

    return render(request, 'delete_account.html')


@login_required
def profile(request):
    user = request.user
    # Fetch outstanding Duo Wrapped invitations
    duo_invitations = DuoWrapped.objects.filter(invitee=user, is_accepted=False)
    
    context = {
        'first_name': user.first_name,
        'last_name': user.last_name,
        'email': user.email,
        'duo_invitations': duo_invitations
    }
    return render(request, 'profile.html', context)


@login_required
def contact_us(request):
    return render(request, 'contact_us.html')



@login_required
def spotify_wrapped(request):
    # Fetch top track
    access_token = request.session.get('spotify_access_token')
    if not access_token:
        messages.error(request, "Spotify access token is missing. Please reconnect.")
        return redirect('get_spotify_auth_url')
    user_first_name = request.user.first_name
    headers = {"Authorization": f"Bearer {access_token}"}

    # Fetch top track
    top_track = None
    top_tracks_url = "https://api.spotify.com/v1/me/top/tracks?limit=1&time_range=medium_term"
    track_response = requests.get(top_tracks_url, headers=headers)
    if track_response.status_code == 200:
        track_data = track_response.json().get("items", [])
        if track_data:
            track = track_data[0]
            top_track = {
                'name': track['name'],
                'image_url': track['album']['images'][0]['url'] if track['album']['images'] else None,
                'artist': track['artists'][0]['name'] if track['artists'] else None,
                'link': track['external_urls']['spotify'] if 'external_urls' in track else None,
            }
    else:
        messages.error(request, "Failed to fetch top track data.")

    # Fetch top artist
    top_artist = None
    top_artists_url = "https://api.spotify.com/v1/me/top/artists?limit=1&time_range=medium_term"
    artist_response = requests.get(top_artists_url, headers=headers)
    if artist_response.status_code == 200:
        artist_data = artist_response.json().get("items", [])
        if artist_data:
            artist = artist_data[0]
            top_artist = {
                'name': artist['name'],
                'image_url': artist['images'][0]['url'] if artist['images'] else None,
                'genre': artist['genres'][0] if artist['genres'] else None,
                'link': artist['external_urls']['spotify'] if 'external_urls' in artist else None,
            }
    else:
        messages.error(request, "Failed to fetch top artist data.")

    # Generate slides
    slides = generate_wrapped_slides(
        user_first_name,
        top_track=top_track,
        top_artist=top_artist
    )

    # Save wrap data to the database
#    SpotifyWrap.objects.create(
#        user=request.user,
#        wrap_data={'top_tracks': top_tracks, 'top_artists': top_artists}
#    )

    # Render the wrapped page with dynamic slides
    return render(request, 'base_slides.html', {'slides': slides})



def generate_wrapped_slides(first_name, top_track=None, top_artist=None):
    slides = []

    # Slide 1: Intro
    slides.append({
        'title': f"Welcome to your Spotify Wrapped, {first_name}!",
        'template': 'slides/slide1.html'
    })
    #slide 2
    slides.append({
        'title': "Your Top Spotify Picks",
        'template': 'slides/slide2.html',
        'top_track': top_track,
        'top_artist': top_artist,
    })

    return slides

@login_required
def view_saved_wraps(request):
    saved_wraps = SpotifyWrap.objects.filter(user=request.user).order_by('-created_at')
    
    if not saved_wraps:
        messages.info(request, "You don't have any saved wraps yet.")
        return redirect('home')
    
    return render(request, 'select_wrap.html', {'saved_wraps': saved_wraps})

@login_required
def display_selected_wrap(request, wrap_id):
    try:
        selected_wrap = SpotifyWrap.objects.get(id=wrap_id, user=request.user)
    except SpotifyWrap.DoesNotExist:
        messages.error(request, "The selected wrap does not exist.")
        return redirect('view_saved_wraps')
    
    top_tracks = selected_wrap.wrap_data.get('top_tracks', [])
    top_artists = selected_wrap.wrap_data.get('top_artists', [])
    slides = generate_wrapped_slides(top_tracks, top_artists)

    context = {
        'slides': slides,
    }
    return render(request, 'spotify_wrapped.html', context)

@login_required
def invite_duo_wrapped(request):
    """Invite a friend to join a Duo Wrapped."""
    if request.method == 'POST':
        invitee_username = request.POST.get('invitee')
        try:
            invitee = User.objects.get(username=invitee_username)
            
            # Ensure inviter is not inviting themselves
            if invitee == request.user:
                messages.error(request, "You cannot invite yourself.")
                return redirect('profile')

            # Check for an existing pending invitation
            existing_invitation = DuoWrapped.objects.filter(
                inviter=request.user,
                invitee=invitee,
                is_accepted=False
            ).first()

            if existing_invitation:
                messages.error(request, f"You already have a pending invitation to {invitee_username}.")
            else:
                # Create a new invitation if no pending one exists
                DuoWrapped.objects.create(inviter=request.user, invitee=invitee)
                messages.success(request, f"Invitation sent to {invitee_username}.")
                
        except User.DoesNotExist:
            messages.error(request, "User not found.")
    
    return redirect('profile')


@login_required
def accept_duo_invitation(request, duo_id):
    """Accept a Duo Wrapped invitation and save the invitee's wrap data."""
    duo_invitation = get_object_or_404(DuoWrapped, id=duo_id, invitee=request.user, is_accepted=False)

    # Fetch the invitee's latest wrap data and save it to the invitation
    latest_wrap = SpotifyWrap.objects.filter(user=request.user).order_by('-created_at').first()
    if latest_wrap:
        duo_invitation.invitee_wrap_data = latest_wrap.wrap_data
        duo_invitation.is_accepted = True
        duo_invitation.save()
        messages.success(request, "You have accepted the Duo Wrapped invitation.")

        # Redirect to the Duo Wrapped view page to generate the slides
        return redirect('view_duo_wrapped', duo_id=duo_invitation.id)
    else:
        messages.error(request, "No wrap data found to share in Duo Wrapped.")
    
    return redirect('home')


@login_required
def view_duo_wrapped(request, duo_id):
    """Display the combined Duo Wrapped slides for both inviter and invitee."""
    duo_wrapped = get_object_or_404(DuoWrapped, id=duo_id, is_accepted=True)

    inviter_wrap = SpotifyWrap.objects.filter(user=duo_wrapped.inviter).last()
    invitee_wrap_data = duo_wrapped.invitee_wrap_data

    if inviter_wrap and invitee_wrap_data:
        # Generate slides for both inviter and invitee's data
        inviter_slides = generate_wrapped_slides(inviter_wrap.wrap_data.get('top_tracks', []), inviter_wrap.wrap_data.get('top_artists', []))
        invitee_slides = generate_wrapped_slides(invitee_wrap_data.get('top_tracks', []), invitee_wrap_data.get('top_artists', []))

        context = {
            'inviter_slides': inviter_slides,
            'invitee_slides': invitee_slides,
        }
        return render(request, 'duo_wrapped.html', context)
    else:
        messages.error(request, "Wrap data is missing for one or both users.")
        return redirect('home')

def get_spotify_auth_url(request):
    auth_url = "https://accounts.spotify.com/authorize"
    params = {
        "client_id": SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": 'http://localhost:8000/callback/',  # Ensure this matches
        "scope": "user-top-read user-read-recently-played",
        "show_dialog": True
    }
    response = requests.get(auth_url, params=params)
    return redirect(response.url)

def spotify_callback(request):
    code = request.GET.get('code')
    if code:
        # Attempt to get the access token
        access_token = get_access_token(code)
        if access_token:
            # Store the access token in the session
            request.session['spotify_access_token'] = access_token
            # Redirect to the Spotify Wrapped page
            return redirect('spotify_wrapped')
        else:
            return HttpResponse("Failed to retrieve access token.")
    else:
        return HttpResponse("No authorization code received.")


def get_access_token(code):
    token_url = "https://accounts.spotify.com/api/token"
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": 'http://localhost:8000/callback/',  # Updated URI
        "client_id": SPOTIFY_CLIENT_ID,
        "client_secret": SPOTIFY_CLIENT_SECRET,
    }

    response = requests.post(token_url, data=payload)
    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        return None
