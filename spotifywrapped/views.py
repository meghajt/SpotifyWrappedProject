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
from .app_secrets import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
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

    # If no access token, redirect to the Spotify authorization flow
    if not access_token:
        messages.error(request, "Spotify access token is missing. Please reconnect.")
        return redirect('get_spotify_auth_url')

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    # Fetch user’s top tracks and artists
    top_tracks_url = "https://api.spotify.com/v1/me/top/tracks"
    top_artists_url = "https://api.spotify.com/v1/me/top/artists"
    params = {"limit": 10, "time_range": "medium_term"}
    response_tracks = requests.get(top_tracks_url, headers=headers, params=params)
    response_artists = requests.get(top_artists_url, headers=headers, params=params)

    if response_tracks.status_code == 200 and response_artists.status_code == 200:
        top_tracks = response_tracks.json().get('items', [])
        top_artists = response_artists.json().get('items', [])
    else:
        messages.error(request, "Failed to retrieve Spotify data. Please try again.")
        return redirect('home')

    # Generate slide data for presentation
    slides = generate_wrapped_slides(top_tracks, top_artists)

    context = {
        'slides': slides,
    }
    SpotifyWrap.objects.create(
        user=request.user,
        wrap_data={'top_tracks': top_tracks, 'top_artists': top_artists}
    )

    context = {
        'slides': generate_wrapped_slides(top_tracks, top_artists),
    }
    return render(request, 'spotify_wrapped.html', context)

def generate_wrapped_slides(top_tracks, top_artists):
    slides = []

    # Slide 1: Welcome
    slides.append({
        'title': "Your Spotify Wrapped!",
        'background': 'linear-gradient(135deg, #1DB954, #1ED760)',
        'type': 'intro',
        'shape': 'starburst',
        'animation': 'zoom-in',
        'font_size': '4em',
        'bold_text': True,
        'center_text': True,
        'color': '#000',  # Black text for high contrast
        'image': 'https://www.freepnglogos.com/uploads/spotify-logo-png/spotify-icon-black-17.png'  # Spotify logo
    })


    # Slide 2: Top 10 Tracks
    top_track_names = [track['name'] for track in top_tracks]
    top_track_images = [track['album']['images'][0]['url'] for track in top_tracks] if top_tracks else []
    slides.append({
        'title': "Your Top 10 Tracks",
        'items': top_track_names,
        'background': 'linear-gradient(135deg, #ff9a9e, #fecfef)',
        'type': 'list',
        'shape': 'explosion',
        'animation': 'slide-left',
        'image': top_track_images[0] if top_track_images else ''  # Use album cover of the top track
    })

    # Slide 3: Top 10 Artists
    top_artist_names = [artist['name'] for artist in top_artists]
    top_artist_images = [artist['images'][0]['url'] for artist in top_artists if artist['images']] if top_artists else []
    slides.append({
        'title': "Your Top 10 Artists",
        'items': top_artist_names,
        'background': 'linear-gradient(135deg, #36d1dc, #5b86e5)',
        'type': 'list',
        'shape': 'burst',
        'animation': 'slide-right',
        'image': top_artist_images[0] if top_artist_images else ''  # Use image of the top artist
    })

    # Slide 4: Top Genres
    genres = [genre for artist in top_artists for genre in artist['genres']]
    genre_counts = {genre: genres.count(genre) for genre in set(genres)}
    sorted_genres = sorted(genre_counts, key=genre_counts.get, reverse=True)[:5]
    slides.append({
        'title': "Your Favorite Genres",
        'items': sorted_genres,
        'background': 'linear-gradient(135deg, #c471ed, #f64f59)',
        'type': 'list',
        'shape': 'circle',
        'animation': 'fade-in',
        'image': 'https://cdn-icons-png.flaticon.com/512/2462/2462719.png'  # Genre icon from Flaticon
    })

    # Slide 5: Most Played Track
    if top_tracks:
        slides.append({
            'title': "Your Most Played Track",
            'description': f"{top_tracks[0]['name']} by {', '.join([artist['name'] for artist in top_tracks[0]['artists']])}",
            'background': 'linear-gradient(135deg, #fc466b, #3f5efb)',
            'type': 'fact',
            'shape': 'spiky',
            'animation': 'zoom-in',
            'image': top_tracks[0]['album']['images'][0]['url'] if top_tracks[0]['album']['images'] else ''  # Album cover of the most played track
        })

    # Slide 6: Most Played Artist
    if top_artists:
        slides.append({
            'title': "Your Most Played Artist",
            'description': f"{top_artists[0]['name']}",
            'background': 'linear-gradient(135deg, #ffafbd, #ffc3a0)',
            'type': 'fact',
            'shape': 'starburst',
            'animation': 'rotate',
            'image': top_artist_images[0] if top_artist_images else ''  # Image of the most played artist
        })

    # Slide 7: Fun Fact
    fun_fact = "You explored over 20 different genres this year!"
    slides.append({
        'title': "Fun Fact!",
        'description': fun_fact,
        'background': 'linear-gradient(135deg, #f6d365, #fda085)',
        'type': 'fact',
        'shape': 'explosion',
        'animation': 'bounce',
        'image': 'https://cdn-icons-png.flaticon.com/512/1077/1077035.png'  # Fun fact icon from Flaticon
    })

    # Slide 8: Wrap-Up
    slides.append({
        'title': "That's a Wrap!",
        'description': "We hope you enjoyed your personalized Spotify Wrapped!",
        'background': 'linear-gradient(135deg, #d4fc79, #96e6a1)',
        'type': 'end',
        'shape': 'burst',
        'animation': 'slide-up',
        'image': 'https://upload.wikimedia.org/wikipedia/commons/1/19/Spotify_logo_without_text.svg'  # Spotify logo from Wikipedia
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
