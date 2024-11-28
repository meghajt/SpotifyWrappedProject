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
from collections import Counter


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

def normalize_genre(genre):
    if not genre:
        return "Unknown Genre"
    genre_lower = genre.lower()
    if "hip hop" in genre_lower:
        return "Hip Hop"
    elif "r&b" in genre_lower or "rnb" in genre_lower:
        return "R&B"
    else:
        return " ".join(word.capitalize() for word in genre.split())


def top_genres(access_token):
    top_artists_url = "https://api.spotify.com/v1/me/top/artists?limit=50&time_range=medium_term"
    headers = {"Authorization": f"Bearer {access_token}"}

    response = requests.get(top_artists_url, headers=headers)
    if response.status_code != 200:
        return []  # Return an empty list if the request fails

    # Extract the first genre from each artist and normalize it
    genres = []
    artist_data = response.json().get("items", [])
    for artist in artist_data:
        if artist.get('genres'):  # Check if the artist has genres listed
            first_genre = artist['genres'][0]  # Get the first listed genre
            normalized_genre = normalize_genre(first_genre)  # Normalize the genre
            genres.append(normalized_genre)  # Add the normalized genre to the list

    # Count genres and calculate percentages
    genre_counts = Counter(genres)

    # Format the top genres into a list of dictionaries with percentages
    top_genres = []
    for genre, count in genre_counts.most_common(5):
        percentage = int(round((count / 50) * 100, 1))
        top_genres.append({'genre': genre, 'count': count, 'percentage': percentage})

    return top_genres

def get_least_popular(access_token):
    headers = {"Authorization": f"Bearer {access_token}"}

    # Fetch top tracks
    top_tracks_url = "https://api.spotify.com/v1/me/top/tracks?limit=50&time_range=medium_term"
    track_response = requests.get(top_tracks_url, headers=headers)
    least_popular_song = None

    if track_response.status_code == 200:
        track_data = track_response.json().get("items", [])
        if track_data:
            # Find the song with the lowest popularity
            least_popular_song = min(
                track_data,
                key=lambda track: track.get("popularity", 101),  # Use 101 as a fallback for missing popularity
                default=None
            )
            if least_popular_song:
                least_popular_song = {
                    'name': least_popular_song['name'],
                    'artist': least_popular_song['artists'][0]['name'] if least_popular_song['artists'] else "Unknown",
                    'popularity': least_popular_song['popularity'],
                    'image_url': least_popular_song['album']['images'][0]['url'] if least_popular_song['album']['images'] else None,
                    'preview_url': least_popular_song['preview_url'],
                }

    # Fetch top artists
    top_artists_url = "https://api.spotify.com/v1/me/top/artists?limit=50&time_range=medium_term"
    artist_response = requests.get(top_artists_url, headers=headers)
    least_popular_artist = None

    if artist_response.status_code == 200:
        artist_data = artist_response.json().get("items", [])
        if artist_data:
            # Find the artist with the lowest popularity
            least_popular_artist = min(
                artist_data,
                key=lambda artist: artist.get("popularity", 101),  # Use 101 as a fallback for missing popularity
                default=None
            )
            if least_popular_artist:
                least_popular_artist = {
                    'name': least_popular_artist['name'],
                    'genre': normalize_genre(least_popular_artist['genres'][0]) if least_popular_artist['genres'] else None,
                    'popularity': least_popular_artist['popularity'],
                    'image_url': least_popular_artist['images'][0]['url'] if least_popular_artist['images'] else None,
                }

    return least_popular_song, least_popular_artist

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
    top_tracks = []
    top_tracks_url = "https://api.spotify.com/v1/me/top/tracks?limit=10&time_range=medium_term"
    track_response = requests.get(top_tracks_url, headers=headers)
    if track_response.status_code == 200:
        track_data = track_response.json().get("items", [])
        for track in track_data:
            top_tracks.append({
                'name': track['name'],
                'artist': track['artists'][0]['name'] if track['artists'] else "Unknown",
                'image_url': track['album']['images'][0]['url'] if track['album']['images'] else None,
                'preview_url': track['preview_url'],
            })
    else:
        messages.error(request, "Failed to fetch top tracks.")

    top_artists = []
    top_artists_url = "https://api.spotify.com/v1/me/top/artists?limit=10&time_range=medium_term"
    artist_response = requests.get(top_artists_url, headers=headers)
    if artist_response.status_code == 200:
        artist_data = artist_response.json().get("items", [])
        for artist in artist_data:
            top_artists.append({
                'name': artist['name'],
                'genre': normalize_genre(artist['genres'][0]) if artist['genres'] else None,
                'image_url': artist['images'][0]['url'] if artist['images'] else None,
            })
    else:
        messages.error(request, "Failed to fetch top tracks.")

    genres = top_genres(access_token)

    least_popular_song, least_popular_artist = get_least_popular(access_token)

    # Generate slides
    slides = generate_wrapped_slides(
        request.user.first_name,
        top_track=top_tracks[0] if top_tracks else None,
        top_artist=top_artists[0] if top_artists else None,
        top_tracks=top_tracks,
        top_artists=top_artists,
        genres=genres,
        least_popular_artist=least_popular_artist,
        least_popular_song=least_popular_song,
    )

    # Save wrap data to the database
#    SpotifyWrap.objects.create(
#        user=request.user,
#        wrap_data={'top_tracks': top_tracks, 'top_artists': top_artists}
#    )

    # Render the wrapped page with dynamic slides
    return render(request, 'base_slides.html', {'slides': slides})



def generate_wrapped_slides(first_name, top_track=None, top_artist=None, top_tracks=None, top_artists=None, genres=None, least_popular_artist=None, least_popular_song=None):
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
    # slide 3
    slides.append({
        'title': "Your Top 10 Tracks",
        'template': 'slides/slide3.html',
        'top_tracks': top_tracks,
    })
    # slide 4
    slides.append({
        'title': "Your Top 10 Artists",
        'template': 'slides/slide4.html',
        'top_artists': top_artists,
    })
    # Slide 5: Your Top Genres
    slides.append({
        'title': "Your Top 5 Genres",
        'template': 'slides/slide5.html',
        'top_genres': genres,
    })
    # Slide 6: Least Popular Picks
    slides.append({
        'title': "Your Hidden Gems",
        'template': 'slides/slide6.html',
        'least_popular_artist': least_popular_artist,
        'least_popular_song': least_popular_song,
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
