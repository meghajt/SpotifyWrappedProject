from django.db import models
from django.contrib.auth.models import User

class SpotifyWrap(models.Model):
    """
    Model to store Spotify wrap details for a user.

    Attributes:
        user (ForeignKey): A reference to the User model, representing the owner of the wrap data.
        wrap_data (JSONField): JSON-encoded data containing details of the Spotify wrap (e.g., top songs, artists).
        time_range (CharField): Time range for the wrap (e.g., 'short_term', 'medium_term', 'long_term').
        created_at (DateTimeField): Timestamp when the SpotifyWrap instance was created.

    Methods:
        __str__: Returns a string representation of the wrap, including the user, time range, and creation date.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    wrap_data = models.JSONField()  # Store wrap details in JSON format
    time_range = models.CharField(max_length=20, default='medium_term')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        """
        Returns a readable string representation of the SpotifyWrap instance.
        """
        return f"Spotify Wrap for {self.user.username} ({self.time_range}) on {self.created_at.strftime('%Y-%m-%d')}"


class DuoWrapped(models.Model):
    """
    Model to store information about a duo-wrapped session between two users.

    Attributes:
        inviter (ForeignKey): The user who initiated the duo-wrapped invitation.
        invitee (ForeignKey): The user who received the duo-wrapped invitation.
        invitee_wrap_data (JSONField): JSON-encoded data containing wrap details for the invitee.
        created_at (DateTimeField): Timestamp when the duo-wrapped invitation was created.
        is_accepted (BooleanField): Status of the invitation; True if accepted, False otherwise.

    Methods:
        __str__: Returns a string representation of the duo-wrapped instance, including the inviter and invitee usernames.
    """
    inviter = models.ForeignKey(User, related_name='duo_invitations_sent', on_delete=models.CASCADE)
    invitee = models.ForeignKey(User, related_name='duo_invitations_received', on_delete=models.CASCADE)
    invitee_wrap_data = models.JSONField(blank=True, null=True)  # Wrap data for the invitee
    created_at = models.DateTimeField(auto_now_add=True)
    is_accepted = models.BooleanField(default=False)

    def __str__(self):
        """
        Returns a readable string representation of the DuoWrapped instance.
        """
        return f"Duo-Wrapped between {self.inviter.username} and {self.invitee.username}"
