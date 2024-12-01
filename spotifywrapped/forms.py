from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class CustomUserCreationForm(UserCreationForm):
    """
    Custom user registration form that extends Django's built-in UserCreationForm.

    This form adds additional fields for the user's first name, last name, and email,
    while retaining the username and password fields from the default UserCreationForm.

    Fields:
        first_name (CharField): The user's first name (required).
        last_name (CharField): The user's last name (required).
        email (EmailField): The user's email address (required).

    Meta:
        model (User): The Django User model associated with this form.
        fields (list): Specifies the fields to include in the form, in the order displayed.
    """
    first_name = forms.CharField(max_length=30, required=True, label='First Name')
    last_name = forms.CharField(max_length=30, required=True, label='Last Name')
    email = forms.EmailField(required=True, label='Email')

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']
