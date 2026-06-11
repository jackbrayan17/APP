from django.conf import settings
from django.db import models
from django.utils.text import slugify
from django.utils.crypto import get_random_string

from apps.core.models import TimeStampedModel


class Category(models.Model):
    """Categorie globale (filtres accueil : Tous, Local, Fast Food, Grillades...)."""
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=70, unique=True, blank=True)
    emoji = models.CharField(max_length=8, blank=True, help_text="Icone emoji (ex 🍔)")
    order = models.PositiveSmallIntegerField(default=0)
    is_nav = models.BooleanField(default=False, help_text="Afficher dans la barre du bas")

    class Meta:
        ordering = ["order", "name"]
        verbose_name_plural = "Categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.emoji} {self.name}".strip()


class Restaurant(TimeStampedModel):
    """Restaurant partenaire — page 100% personnalisable."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="restaurants")
    name = models.CharField(max_length=140)
    slug = models.SlugField(max_length=160, unique=True, blank=True)
    share_token = models.CharField(max_length=22, unique=True, blank=True, db_index=True)

    tagline = models.CharField(max_length=60, blank=True,
                               help_text="Badge ex: Cuisine Locale / Premium")
    bio = models.TextField(blank=True, help_text="Description / bio du restaurant")

    logo = models.ImageField(upload_to="restaurants/logos/", blank=True, null=True)
    cover_image = models.ImageField(upload_to="restaurants/covers/", blank=True, null=True)

    categories = models.ManyToManyField(Category, blank=True, related_name="restaurants")

    # Localisation / zone
    neighborhood = models.CharField(max_length=80, blank=True,
                                    help_text="Quartier ex: Bonanjo, Akwa, Bonapriso, Bali")
    city = models.CharField(max_length=80, default="Douala")
    address = models.CharField(max_length=255, blank=True)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)

    # Logistique
    delivery_fee = models.PositiveIntegerField(default=500, help_text="Frais livraison en FCFA")
    delivery_time_min = models.PositiveSmallIntegerField(default=20)
    delivery_time_max = models.PositiveSmallIntegerField(default=40)
    min_order = models.PositiveIntegerField(default=0)

    # Personnalisation de la page
    brand_color = models.CharField(max_length=9, default="#FF6B1A")
    accent_color = models.CharField(max_length=9, default="#FFF1E8")

    # Statut / badges
    is_pro = models.BooleanField(default=False, help_text="Badge Pro")
    is_premium = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False, help_text="A la une")
    is_active = models.BooleanField(default=True)

    # Notes (cache, recalcule a chaque avis)
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=0)
    rating_count = models.PositiveIntegerField(default=0)
    orders_count = models.PositiveIntegerField(default=0)

    phone = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ["-is_featured", "-rating"]
        indexes = [models.Index(fields=["slug"]), models.Index(fields=["share_token"])]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or "resto"
            slug = base
            i = 1
            while Restaurant.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                i += 1
                slug = f"{base}-{i}"
            self.slug = slug
        if not self.share_token:
            self.share_token = get_random_string(16)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    @property
    def delivery_time_label(self):
        return f"{self.delivery_time_min}-{self.delivery_time_max} min"

    @property
    def rating_label(self):
        return f"{self.rating:.1f}"

    @property
    def is_elite(self):
        return self.rating >= 4.8

    def recompute_rating(self):
        from apps.orders.models import Review
        agg = Review.objects.filter(restaurant=self).aggregate(
            avg=models.Avg("rating"), n=models.Count("id"))
        self.rating = round(agg["avg"] or 0, 1)
        self.rating_count = agg["n"] or 0
        self.save(update_fields=["rating", "rating_count"])


class RestaurantPhoto(TimeStampedModel):
    """Galerie photos du restaurant."""
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="restaurants/gallery/")
    caption = models.CharField(max_length=140, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order"]


class MenuSection(models.Model):
    """Onglet de menu (ex: Cuisine Camerounaise, Riz & Accompagnements, Snacks)."""
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="sections")
    name = models.CharField(max_length=100)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.restaurant.name} — {self.name}"


class Dish(TimeStampedModel):
    """Plat du menu d'un restaurant."""
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="dishes")
    section = models.ForeignKey(MenuSection, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="dishes")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="dishes")

    name = models.CharField(max_length=140)
    description = models.TextField(blank=True)
    price = models.PositiveIntegerField(help_text="Prix en FCFA")
    prep_time = models.PositiveSmallIntegerField(default=20, help_text="Temps de preparation (min)")

    image = models.ImageField(upload_to="dishes/", blank=True, null=True)
    video = models.FileField(upload_to="dishes/videos/", blank=True, null=True)

    is_available = models.BooleanField(default=True)
    is_popular = models.BooleanField(default=False)
    orders_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["section__order", "-is_popular", "name"]
        indexes = [models.Index(fields=["restaurant", "is_available"])]

    def __str__(self):
        return self.name

    @property
    def active_promo(self):
        """Retourne la promo active pour ce plat, sinon None."""
        from apps.promotions.models import Promotion
        from django.utils import timezone
        now = timezone.now()
        return (self.promotions.filter(
            is_active=True, starts_at__lte=now, ends_at__gte=now).first())

    @property
    def current_price(self):
        promo = self.active_promo
        if promo:
            return promo.apply_to(self.price)
        return self.price

    @property
    def has_promo(self):
        return self.active_promo is not None
