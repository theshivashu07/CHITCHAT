from django.db import models
from django.contrib.auth.models import User

from django.conf import settings

# Create your models here.







class Profile(models.Model):

    # User.id hi Profile ka primary key hoga
    user = models.OneToOneField(
        # settings.AUTH_USER_MODEL,  # Agar settings me current User default Django User hi hai, to ye bhi kaam karega! 
        User, # User directly likhne ka matlab: Mujhe specifically Django ka ye User model chahiye.
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="profile"
    )

    profile_picture = models.ImageField(
        upload_to="profile-pictures/",
        blank=True,
        null=True
    )

    # full_name = models.CharField(
    #    max_length=150,
    #    blank=True
    # )

    mobile = models.CharField( 
        max_length=20, 
        blank=True 
    )

    recovery_mobile = models.CharField(
        max_length=20,
        blank=True
    )

    recovery_email = models.EmailField(
        blank=True
    )

    profession = models.CharField(
        max_length=150,
        blank=True
    )

    date_of_birth = models.DateField(
        blank=True,
        null=True
    )

    bio = models.TextField(
        blank=True
    )

    about = models.TextField(
        blank=True
    )

    work_address = models.TextField(
        blank=True
    )

    home_address = models.TextField(
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    

    def __str__(self):
        return self.user.username

    @property
    def full_name(self):
        return f"{self.user.first_name} {self.user.last_name}".strip()

    @property
    def username(self):
        return self.user.username

    @property
    def email(self):
        return self.user.email

    @property
    def date_joined(self):
        return self.created_at 

    @property
    def last_updated(self):
        return self.updated_at 




