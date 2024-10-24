from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import User

class SpotifyWrap(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    wrap_data = models.JSONField() 
    created_at = models.DateTimeField(auto_now_add=True)

