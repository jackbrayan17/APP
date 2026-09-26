from datetime import time as dtime

from django.conf import settings
from django.db import models
from django.utils import timezone
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


WEEKDAYS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


def default_opening_hours():
    """Horaires par jour (0 = lundi) : [ouverture, fermeture], ou None si ferme."""
    return {str(d): ["10:00", "22:30"] for d in range(7)}


def _parse_hm(value):
    try:
        h, m = value.split(":")
        return dtime(int(h), int(m))
    except (AttributeError, TypeError, ValueError):
        return None


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

    # Horaires & fermeture exceptionnelle
    opening_hours = models.JSONField(default=default_opening_hours, blank=True)
    is_temporarily_closed = models.BooleanField(
        default=False, help_text="Fermeture exceptionnelle : plus aucune commande acceptee")
    closure_note = models.CharField(max_length=120, blank=True,
                                    help_text="Message affiche aux clients pendant la fermeture")

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

    # ---- Horaires ----
    def hours_for(self, weekday):
        slot = (self.opening_hours or {}).get(str(weekday))
        if not slot or len(slot) != 2:
            return None
        start, end = _parse_hm(slot[0]), _parse_hm(slot[1])
        return (start, end) if start and end else None

    @property
    def is_open_now(self):
        if self.is_temporarily_closed or not self.is_active:
            return False
        now = timezone.localtime()
        t = now.time()
        today = self.hours_for(now.weekday())
        if today:
            start, end = today
            if start <= end and start <= t <= end:
                return True
            if start > end and (t >= start or t <= end):  # service apres minuit
                return True
        yesterday = self.hours_for((now.weekday() - 1) % 7)
        return bool(yesterday and yesterday[0] > yesterday[1] and t <= yesterday[1])

    @property
    def opening_status_label(self):
        """Texte court : 'Ouvert · ferme à 22:30' ou 'Fermé · ouvre demain à 10:00'."""
        if self.is_temporarily_closed:
            return self.closure_note or "Fermé temporairement"
        now = timezone.localtime()
        today = self.hours_for(now.weekday())
        if self.is_open_now:
            return f"Ouvert · ferme à {today[1].strftime('%H:%M')}" if today else "Ouvert"
        if today and now.time() < today[0]:
            return f"Fermé · ouvre à {today[0].strftime('%H:%M')}"
        for offset in range(1, 8):
            day = (now.weekday() + offset) % 7
            slot = self.hours_for(day)
            if slot:
                when = "demain" if offset == 1 else WEEKDAYS[day].lower()
                return f"Fermé · ouvre {when} à {slot[0].strftime('%H:%M')}"
        return "Fermé"

    @property
    def weekly_hours(self):
        rows = []
        for d, label in enumerate(WEEKDAYS):
            slot = self.hours_for(d)
            rows.append({"day": d, "label": label, "open": bool(slot),
                         "start": slot[0].strftime("%H:%M") if slot else "10:00",
                         "end": slot[1].strftime("%H:%M") if slot else "22:00"})
        return rows

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


class Favorite(TimeStampedModel):
    """Restaurant ajouté en favori par un utilisateur."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="favorites")
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE,
                                   related_name="favorited_by")

    class Meta:
        unique_together = ("user", "restaurant")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} ♥ {self.restaurant}"


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

    is_diet = models.BooleanField(default=False, help_text="Plat recommande pour une alimentation equilibree")
    calories = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Calories estimees par portion")
    protein_grams = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Proteines estimees par portion")
    carbs_grams = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Glucides estimes par portion")
    fat_grams = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Lipides estimes par portion")
    fiber_grams = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Fibres estimees par portion")
    dietary_tags = models.CharField(
        max_length=160, blank=True,
        help_text="Tags separes par des virgules, ex: leger, riche en proteines")
    dietary_note = models.CharField(
        max_length=220, blank=True,
        help_text="Conseil court pour aider le client a choisir")

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

    @property
    def dietary_tag_list(self):
        return [tag.strip() for tag in self.dietary_tags.split(",") if tag.strip()]

    # ---- Nutrition ----
    @property
    def daily_value_percent(self):
        """Part des apports de reference d'un adulte (2000 kcal/jour)."""
        return round(self.calories * 100 / 2000) if self.calories else None

    @property
    def macros(self):
        """Repartition energetique proteines/glucides/lipides en % (4/4/9 kcal par g)."""
        p, c, f = self.protein_grams, self.carbs_grams, self.fat_grams
        if None in (p, c, f):
            return None
        kp, kc, kf = p * 4, c * 4, f * 9
        total = (kp + kc + kf) or 1
        return {"protein": round(kp * 100 / total), "carbs": round(kc * 100 / total),
                "fat": round(kf * 100 / total)}

    @property
    def diet_goals(self):
        """Objectifs nutritionnels couverts par le plat (slugs de DIET_GOALS)."""
        tags = self.dietary_tags.lower()
        goals = []
        if self.calories and self.calories <= 550:
            goals.append("leger")
        if self.protein_grams and self.protein_grams >= 30:
            goals.append("proteine")
        if "végétarien" in tags or "vegan" in tags:
            goals.append("vegetarien")
        if self.carbs_grams is not None and self.carbs_grams <= 30:
            goals.append("low-carb")
        if self.fiber_grams and self.fiber_grams >= 8:
            goals.append("fibres")
        return goals

    @property
    def nutri_grade(self):
        """Indice ONE EAT A-D (indicatif) : energie, proteines, fibres, friture/sucre."""
        if not self.calories:
            return None
        tags = self.dietary_tags.lower()
        pts = 2 if self.calories <= 450 else 1 if self.calories <= 650 else 0 if self.calories <= 850 else -1
        pts += 1 if (self.protein_grams or 0) >= 25 else 0
        pts += 1 if (self.fiber_grams or 0) >= 6 else 0
        pts -= 1 if ("frit" in tags or "sucré" in tags) else 0
        return "A" if pts >= 3 else "B" if pts == 2 else "C" if pts == 1 else "D"


DIET_GOALS = [
    ("leger", "Léger", "550 kcal max"),
    ("proteine", "Protéiné", "30 g de protéines et plus"),
    ("vegetarien", "Végétarien", "Sans viande ni poisson"),
    ("low-carb", "Pauvre en glucides", "30 g de glucides max"),
    ("fibres", "Riche en fibres", "8 g de fibres et plus"),
]
