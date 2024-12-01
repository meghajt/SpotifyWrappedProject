from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import User

class SpotifyWrap(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    wrap_data = models.JSONField()  # Store wrap details in JSON format
    time_range = models.CharField(max_length=20, default='medium_term')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Spotify Wrap for {self.user.username} ({self.time_range}) on {self.created_at.strftime('%Y-%m-%d')}"
    
class DuoWrapped(models.Model):
    inviter = models.ForeignKey(User, related_name='duo_invitations_sent', on_delete=models.CASCADE)
    invitee = models.ForeignKey(User, related_name='duo_invitations_received', on_delete=models.CASCADE)
    invitee_wrap_data = models.JSONField(blank=True, null=True)  # Wrap data for the invitee
    created_at = models.DateTimeField(auto_now_add=True)
    is_accepted = models.BooleanField(default=False)

    def __str__(self):
        return f"Duo-Wrapped between {self.inviter.username} and {self.invitee.username}"


