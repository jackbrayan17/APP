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


class Address(models.Model):
    """Adresse de livraison sauvegardee (domicile, bureau...)."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="addresses")
    label = models.CharField(max_length=40, default="Domicile")
    address = models.CharField(max_length=255)
    instructions = models.CharField(max_length=160, blank=True,
                                    help_text="Repere pour le livreur (portail bleu, 2e etage...)")
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_default", "-created_at"]

    def __str__(self):
        return f"{self.label} — {self.address}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_default:
            Address.objects.filter(user=self.user).exclude(pk=self.pk).update(is_default=False)
