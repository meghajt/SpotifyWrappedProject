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
import random
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

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

def home(request):
    return render(request, 'home.html')

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

def get_most_popular(access_token):
    headers = {"Authorization": f"Bearer {access_token}"}

    # Fetch top tracks
    top_tracks_url = "https://api.spotify.com/v1/me/top/tracks?limit=50&time_range=medium_term"
    track_response = requests.get(top_tracks_url, headers=headers)
    most_popular_song = None

    if track_response.status_code == 200:
        track_data = track_response.json().get("items", [])
        if track_data:
            # Find the song with the highest popularity
            most_popular_song = max(
                track_data,
                key=lambda track: track.get("popularity", -1),  # Use -1 as a fallback for missing popularity
                default=None
            )
            if most_popular_song:
                most_popular_song = {
                    'name': most_popular_song['name'],
                    'artist': most_popular_song['artists'][0]['name'] if most_popular_song['artists'] else "Unknown",
                    'popularity': most_popular_song['popularity'],
                    'image_url': most_popular_song['album']['images'][0]['url'] if most_popular_song['album']['images'] else None,
                    'preview_url': most_popular_song['preview_url'],
                }

    # Fetch top artists
    top_artists_url = "https://api.spotify.com/v1/me/top/artists?limit=50&time_range=medium_term"
    artist_response = requests.get(top_artists_url, headers=headers)
    most_popular_artist = None

    if artist_response.status_code == 200:
        artist_data = artist_response.json().get("items", [])
        if artist_data:
            # Find the artist with the highest popularity
            most_popular_artist = max(
                artist_data,
                key=lambda artist: artist.get("popularity", -1),  # Use -1 as a fallback for missing popularity
                default=None
            )
            if most_popular_artist:
                most_popular_artist = {
                    'name': most_popular_artist['name'],
                    'genre': normalize_genre(most_popular_artist['genres'][0]) if most_popular_artist['genres'] else "Unknown Genre",
                    'popularity': most_popular_artist['popularity'],
                    'image_url': most_popular_artist['images'][0]['url'] if most_popular_artist['images'] else None,
                }

    return most_popular_song, most_popular_artist

def scramble_word(phrase):
    def scramble_word(word):
        if len(word) <= 1:
            return word
        word_list = list(word)
        random.shuffle(word_list)
        return ''.join(word_list)

    # Split the phrase into words, scramble each word, and join them back
    scrambled_words = [scramble_word(word) for word in phrase.split()]
    return ' '.join(scrambled_words)

def validate_song_guess(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        user_guess = data.get('user_guess', '').strip().lower()
        correct_name = data.get('correct_name', '').strip().lower()

        if user_guess == correct_name:
            return JsonResponse({'success': True, 'message': 'Correct!'})
        else:
            return JsonResponse({'success': False, 'message': 'Incorrect! Try again.'})

    return JsonResponse({'success': False, 'message': 'Invalid request method.'})

def new_song_question(request):
    access_token = request.session.get('spotify_access_token')
    headers = {"Authorization": f"Bearer {access_token}"}
    tracks_game_other = []
    tracks_game_url = "https://api.spotify.com/v1/me/top/tracks?limit=50&time_range=medium_term"
    tracks_game_response = requests.get(tracks_game_url, headers=headers)
    if tracks_game_response.status_code == 200:
        tracks_game_data = tracks_game_response.json().get("items", [])
        for track_game in tracks_game_data:
            tracks_game_other.append({
                'name': track_game['name'],
                'artist': track_game['artists'][0]['name'] if track_game['artists'] else "Unknown",
                'image_url': track_game['album']['images'][0]['url'] if track_game['album']['images'] else None,
            })
    else:
        messages.error(request, "Failed to fetch top tracks.")

    if not tracks_game_other:
        return JsonResponse({"error": "No tracks available"}, status=400)

    random_track = random.choice(tracks_game_other)
    scrambled_name = scramble_word(random_track['name'])

    return JsonResponse({
        "album_cover_other": random_track['image_url'],
        "scrambled_name_other": scrambled_name,
        "correct_name_other": random_track['name']
    })

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

    tracks_game = []
    tracks_game_url = "https://api.spotify.com/v1/me/top/tracks?limit=50&time_range=medium_term"
    tracks_game_response = requests.get(tracks_game_url, headers=headers)
    if tracks_game_response.status_code == 200:
        tracks_game_data = tracks_game_response.json().get("items", [])
        for track_game in tracks_game_data:
            tracks_game.append({
                'name': track_game['name'],
                'artist': track_game['artists'][0]['name'] if track_game['artists'] else "Unknown",
                'image_url': track_game['album']['images'][0]['url'] if track_game['album']['images'] else None,
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
    most_popular_song, most_popular_artist = get_most_popular(access_token)

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
        most_popular_artist=most_popular_artist,
        most_popular_song=most_popular_song,
        tracks_game=tracks_game,
    )

    # Save wrap data to the database
    wrap_data = {
        'top_tracks': top_tracks,
        'top_artists': top_artists,
        'genres': genres,
        'least_popular_song': least_popular_song,
        'least_popular_artist': least_popular_artist,
        'most_popular_song': most_popular_song,
        'most_popular_artist': most_popular_artist,
        'tracks_game': tracks_game,
    }
    SpotifyWrap.objects.create(
        user=request.user,
        wrap_data=wrap_data  # Save all the wrap data as a dictionary
    )

    # Render the wrapped page with dynamic slides
    return render(request, 'base_slides.html', {'slides': slides})

def generate_wrapped_slides(first_name, top_track=None, top_artist=None, top_tracks=None, top_artists=None, genres=None,
                            least_popular_artist=None, least_popular_song=None, most_popular_artist=None,
                            most_popular_song=None, tracks_game=None,):
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
    # Slide 7: Most Popular Artist and Song
    slides.append({
        'title': "Your Most Popular Picks",
        'template': 'slides/slide7.html',
        'most_popular_artist': most_popular_artist,  # Assuming top_artist is the most popular artist
        'most_popular_song': most_popular_song,  # Assuming top_track is the most popular song
    })
    # Slide 8
    if tracks_game:
        random_track = random.choice(tracks_game)  # Randomly select a track for the game
        scrambled_name = scramble_word(random_track['name'])
        slides.append({
            'title': "Guess the Song!",
            'template': 'slides/slide8.html',
            'album_cover': random_track['image_url'],
            'scrambled_name': scrambled_name,
            'correct_name': random_track['name'],  # Pass correct name to check user's input
        })
    # Slide 9: Outro
    slides.append({
        'title': "Thats's a Wrap!",
        'template': 'slides/slide9.html',
        'message': "We hope you enjoyed this journey through your music tastes. See you next year!",
        'first_name': first_name
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
        # Fetch the selected wrap for the logged-in user
        selected_wrap = SpotifyWrap.objects.get(id=wrap_id, user=request.user)
    except SpotifyWrap.DoesNotExist:
        messages.error(request, "The selected wrap does not exist.")
        return redirect('view_saved_wraps')

    # Extract data from the wrap_data field
    wrap_data = selected_wrap.wrap_data
    top_tracks = wrap_data.get('top_tracks', [])
    top_artists = wrap_data.get('top_artists', [])
    genres = wrap_data.get('genres', [])
    least_popular_song = wrap_data.get('least_popular_song', None)
    least_popular_artist = wrap_data.get('least_popular_artist', None)
    most_popular_song = wrap_data.get('most_popular_song', None)
    most_popular_artist = wrap_data.get('most_popular_artist', None)
    tracks_game = wrap_data.get('tracks_game', [])

    # Generate slides using the stored wrap data
    slides = generate_wrapped_slides(
        first_name=request.user.first_name,
        top_track=top_tracks[0] if top_tracks else None,
        top_artist=top_artists[0] if top_artists else None,
        top_tracks=top_tracks,
        top_artists=top_artists,
        genres=genres,
        least_popular_artist=least_popular_artist,
        least_popular_song=least_popular_song,
        most_popular_artist=most_popular_artist,
        most_popular_song=most_popular_song,
        tracks_game=tracks_game,
    )

    # Render the slides in the Spotify Wrapped template
    context = {
        'slides': slides,
    }
    return render(request, 'base_slides.html', {'slides': slides})


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

    # Fetch the latest wrap for the inviter
    inviter_wrap = SpotifyWrap.objects.filter(user=duo_wrapped.inviter).last()
    invitee_wrap_data = duo_wrapped.invitee_wrap_data  # Get invitee's wrap data from the saved DuoWrapped model

    if inviter_wrap and invitee_wrap_data:
        # Extract data for inviter
        inviter_wrap_data = inviter_wrap.wrap_data
        inviter_top_tracks = inviter_wrap_data.get('top_tracks', [])
        inviter_top_artists = inviter_wrap_data.get('top_artists', [])
        inviter_genres = inviter_wrap_data.get('genres', [])
        inviter_least_popular_song = inviter_wrap_data.get('least_popular_song', None)
        inviter_least_popular_artist = inviter_wrap_data.get('least_popular_artist', None)
        inviter_most_popular_song = inviter_wrap_data.get('most_popular_song', None)
        inviter_most_popular_artist = inviter_wrap_data.get('most_popular_artist', None)
        inviter_tracks_game = inviter_wrap_data.get('tracks_game', [])

        # Generate slides for inviter
        inviter_slides = generate_wrapped_slides(
            first_name=duo_wrapped.inviter.first_name,
            top_track=inviter_top_tracks[0] if inviter_top_tracks else None,
            top_artist=inviter_top_artists[0] if inviter_top_artists else None,
            top_tracks=inviter_top_tracks,
            top_artists=inviter_top_artists,
            genres=inviter_genres,
            least_popular_artist=inviter_least_popular_artist,
            least_popular_song=inviter_least_popular_song,
            most_popular_artist=inviter_most_popular_artist,
            most_popular_song=inviter_most_popular_song,
            tracks_game=inviter_tracks_game,
        )

        # Extract data for invitee
        invitee_top_tracks = invitee_wrap_data.get('top_tracks', [])
        invitee_top_artists = invitee_wrap_data.get('top_artists', [])
        invitee_genres = invitee_wrap_data.get('genres', [])
        invitee_least_popular_song = invitee_wrap_data.get('least_popular_song', None)
        invitee_least_popular_artist = invitee_wrap_data.get('least_popular_artist', None)
        invitee_most_popular_song = invitee_wrap_data.get('most_popular_song', None)
        invitee_most_popular_artist = invitee_wrap_data.get('most_popular_artist', None)
        invitee_tracks_game = invitee_wrap_data.get('tracks_game', [])

        # Generate slides for invitee
        invitee_slides = generate_wrapped_slides(
            first_name=duo_wrapped.invitee.first_name,
            top_track=invitee_top_tracks[0] if invitee_top_tracks else None,
            top_artist=invitee_top_artists[0] if invitee_top_artists else None,
            top_tracks=invitee_top_tracks,
            top_artists=invitee_top_artists,
            genres=invitee_genres,
            least_popular_artist=invitee_least_popular_artist,
            least_popular_song=invitee_least_popular_song,
            most_popular_artist=invitee_most_popular_artist,
            most_popular_song=invitee_most_popular_song,
            tracks_game=invitee_tracks_game,
        )

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
