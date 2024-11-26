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
    # Get the access token from the session
    access_token = request.session.get('spotify_access_token')

    if not access_token:
        messages.error(request, "Spotify access token is missing. Please reconnect.")
        return redirect('get_spotify_auth_url')

    user_first_name = request.user.first_name
    headers = {"Authorization": f"Bearer {access_token}"}

    # Listening Habits: Fetch recently played tracks
    listening_habits = {"total_minutes": 0, "peak_time": "unknown"}
    recent_tracks_url = "https://api.spotify.com/v1/me/player/recently-played"
    recent_tracks_response = requests.get(recent_tracks_url, headers=headers, params={"limit": 50})

    if recent_tracks_response.status_code == 200:
        recent_tracks_data = recent_tracks_response.json()
        if "items" in recent_tracks_data:
            from collections import Counter
            from datetime import datetime

            # Calculate total minutes listened
            listening_habits["total_minutes"] = sum(
                item['track']['duration_ms'] for item in recent_tracks_data['items']
            ) // (1000 * 60)

            # Calculate peak times
            played_times = [
                datetime.fromisoformat(item['played_at'].replace("Z", "+00:00")).hour
                for item in recent_tracks_data['items']
            ]
            peak_time_hour = Counter(played_times).most_common(1)[0][0]
            if 6 <= peak_time_hour < 12:
                listening_habits["peak_time"] = "morning"
            elif 12 <= peak_time_hour < 18:
                listening_habits["peak_time"] = "afternoon"
            else:
                listening_habits["peak_time"] = "evening"

    # Top Tracks: Fetch user's top 10 tracks
    top_tracks = []
    top_tracks_url = "https://api.spotify.com/v1/me/top/tracks"
    top_tracks_response = requests.get(top_tracks_url, headers=headers, params={"limit": 10, "time_range": "medium_term"})

    if top_tracks_response.status_code == 200:
        top_tracks_data = top_tracks_response.json()
        top_tracks = top_tracks_data.get('items', [])

    # Top Artists: Fetch user's top 10 artists
    top_artists = []
    top_artists_url = "https://api.spotify.com/v1/me/top/artists"
    top_artists_response = requests.get(top_artists_url, headers=headers, params={"limit": 10, "time_range": "medium_term"})

    if top_artists_response.status_code == 200:
        top_artists_data = top_artists_response.json()
        top_artists = top_artists_data.get('items', [])

    # Top Genres: Extract from top artists
    top_genres = []
    if top_artists:
        genres = [genre for artist in top_artists for genre in artist.get('genres', [])]
        from collections import Counter

        genre_counts = Counter(genres)
        top_genres = [genre for genre, _ in genre_counts.most_common(5)]

    # Playlist Highlights: Fetch user's playlists
    top_playlist = {"name": "unknown", "cover_art": None, "top_songs": []}
    playlists_url = "https://api.spotify.com/v1/me/playlists"
    playlists_response = requests.get(playlists_url, headers=headers, params={"limit": 10})

    if playlists_response.status_code == 200:
        playlists_data = playlists_response.json()
        if playlists_data.get('items'):
            # Pick the first playlist as the favorite (you can refine this logic)
            playlist = playlists_data['items'][0]
            top_playlist = {
                "name": playlist['name'],
                "cover_art": playlist['images'][0]['url'] if playlist['images'] else None,
                "top_songs": []  # Placeholder: Add logic to fetch songs if needed
            }

    # Discovery Stats: Compare recent tracks and top tracks
    discovery_stats = {"new_artists": 0, "new_songs": 0, "most_listened_song": "unknown"}
    if recent_tracks_response.status_code == 200 and top_tracks_response.status_code == 200:
        recent_artists = {item['track']['artists'][0]['id'] for item in recent_tracks_data['items']}
        top_track_artists = {track['artists'][0]['id'] for track in top_tracks}

        new_artists = recent_artists - top_track_artists
        discovery_stats = {
            "new_artists": len(new_artists),
            "new_songs": len(top_tracks),
            "most_listened_song": top_tracks[0]['name'] if top_tracks else "unknown"
        }

    # Generate slides
    slides = generate_wrapped_slides(
        top_tracks,
        top_artists,
        user_first_name,
        listening_stats=listening_habits,
        top_playlist=top_playlist,
        discovery_stats=discovery_stats
    )

    # Save wrap data to the database
    SpotifyWrap.objects.create(
        user=request.user,
        wrap_data={'top_tracks': top_tracks, 'top_artists': top_artists}
    )

    # Render the wrapped page with dynamic slides
    return render(request, 'base_slides.html', {'slides': slides})



def generate_wrapped_slides(top_tracks, top_artists, first_name, listening_stats=None, top_playlist=None, discovery_stats=None):
    slides = []

    # Slide 1: Intro
    slides.append({
        'title': f"Welcome to your Spotify Wrapped, {first_name}!",
        'template': 'slides/slide1.html'
    })

    # Slide 2: Listening Habits
    if listening_stats:
        slides.append({
            'title': "Your Listening Habits",
            'description': (
                f"You've listened for a total of {listening_stats['total_minutes']} minutes this year. "
                f"Your peak listening times are in the {listening_stats['peak_time']}."
            ),
            'template': 'slides/slide2.html'
        })

    # Slide 3: Top 10 Tracks
    top_track_names = [track['name'] for track in top_tracks]
    top_track_images = [track['album']['images'][0]['url'] for track in top_tracks] if top_tracks else []
    slides.append({
        'title': "Your Top 10 Tracks",
        'items': top_track_names,
        'image': top_track_images[0] if top_track_images else '',  # Use the album cover of the top track
        'template': 'slides/slide3.html'
    })

    # Slide 4: Top 10 Artists
    top_artist_names = [artist['name'] for artist in top_artists]
    top_artist_images = [artist['images'][0]['url'] for artist in top_artists if artist['images']] if top_artists else []
    slides.append({
        'title': "Your Top 10 Artists",
        'items': top_artist_names,
        'image': top_artist_images[0] if top_artist_images else '',  # Use the image of the top artist
        'template': 'slides/slide4.html'
    })

    # Slide 5: Top 5 Genres
    genres = [genre for artist in top_artists for genre in artist['genres']]
    genre_counts = {genre: genres.count(genre) for genre in set(genres)}
    sorted_genres = sorted(genre_counts, key=genre_counts.get, reverse=True)[:5]
    slides.append({
        'title': "Your Top 5 Genres",
        'items': sorted_genres,
        'template': 'slides/slide5.html'
    })

    # Slide 6: Playlist Highlights
    if top_playlist:
        slides.append({
            'title': f"Your Favorite Playlist: {top_playlist['name']}",
            'description': f"Here are the top songs from '{top_playlist['name']}':",
            'items': [song['name'] for song in top_playlist['top_songs']],
            'image': top_playlist['cover_art'],
            'template': 'slides/slide6.html'
        })

    # Slide 7: Discovery Stats
    if discovery_stats:
        slides.append({
            'title': "Your Discovery Stats",
            'description': (
                f"This year, you discovered {discovery_stats['new_artists']} new artists and {discovery_stats['new_songs']} new songs. "
                f"Your favorite discovery was '{discovery_stats['most_listened_song']}'."
            ),
            'template': 'slides/slide7.html'
        })

    # Slide 8: Game (placeholder for interactivity)
    slides.append({
        'title': "Spotify Game Time!",
        'description': "Test your knowledge of your listening habits this year.",
        'template': 'slides/slide8.html'
    })

    # Slide 9: Outro
    slides.append({
        'title': "That's a Wrap!",
        'description': "Thanks for listening to Spotify this year! See you next time.",
        'template': 'slides/slide9.html'
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
