from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Utilisateur unique multi-role pour ONE EAT."""

    class Role(models.TextChoices):
        CLIENT = "client", "Client"
        RESTAURANT = "restaurant", "Restaurant"
        DRIVER = "driver", "Livreur"
        INFLUENCER = "influencer", "Influenceur"
        ADMIN = "admin", "Administrateur"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CLIENT)
    phone = models.CharField(max_length=20, blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    city = models.CharField(max_length=80, default="Douala")
    # Adresse de livraison par defaut (geolocalisation client)
    address = models.CharField(max_length=255, blank=True)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def initials(self):
        full = (self.get_full_name() or self.username).strip()
        parts = full.split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[1][0]).upper()
        return full[:2].upper() if full else "OE"

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    # Helpers de role
    @property
    def is_restaurant(self):
        return self.role == self.Role.RESTAURANT

    @property
    def is_driver(self):
        return self.role == self.Role.DRIVER

    @property
    def is_influencer(self):
        return self.role == self.Role.INFLUENCER

    @property
    def is_client(self):
        return self.role == self.Role.CLIENT
