from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string

from apps.core.models import TimeStampedModel
from apps.restaurants.models import Restaurant, Dish


class Promotion(TimeStampedModel):
    """Promo lancee par un restaurant sur des plats, avec theme et duree."""

    class DiscountType(models.TextChoices):
        PERCENT = "percent", "Pourcentage (-X%)"
        AMOUNT = "amount", "Reduction fixe (-X FCFA)"
        FIXED_PRICE = "fixed_price", "Prix promo (X FCFA)"

    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="promotions")
    title = models.CharField(max_length=120, help_text="Theme de la promo ex: Black Friday")
    description = models.TextField(blank=True)

    discount_type = models.CharField(max_length=12, choices=DiscountType.choices,
                                     default=DiscountType.PERCENT)
    discount_value = models.PositiveIntegerField(
        help_text="% (ex 50, 75), montant FCFA, ou prix promo selon le type")

    dishes = models.ManyToManyField(Dish, related_name="promotions", blank=True)

    banner_color = models.CharField(max_length=9, default="#E53935")
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-starts_at"]

    def __str__(self):
        return f"{self.title} ({self.restaurant.name})"

    @property
    def is_live(self):
        now = timezone.now()
        return self.is_active and self.starts_at <= now <= self.ends_at

    @property
    def label(self):
        if self.discount_type == self.DiscountType.PERCENT:
            return f"-{self.discount_value}%"
        if self.discount_type == self.DiscountType.AMOUNT:
            return f"-{self.discount_value} FCFA"
        return f"{self.discount_value} FCFA"

    def apply_to(self, price):
        if self.discount_type == self.DiscountType.PERCENT:
            return max(0, round(price * (100 - self.discount_value) / 100))
        if self.discount_type == self.DiscountType.AMOUNT:
            return max(0, price - self.discount_value)
        return self.discount_value


class InfluencerProfile(TimeStampedModel):
    """Profil influenceur — note selon sa portee (usage des codes)."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="influencer_profile")
    handle = models.CharField(max_length=80, blank=True)
    bio = models.TextField(blank=True)
    followers = models.PositiveIntegerField(default=0)
    # Note de portee (recalculee selon redemptions / CA genere)
    reach_score = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    total_redemptions = models.PositiveIntegerField(default=0)
    total_revenue = models.PositiveBigIntegerField(default=0, help_text="CA genere (FCFA)")

    def __str__(self):
        return self.handle or self.user.display_name

    def recompute_score(self):
        """Note /10 basee sur le nombre d'utilisations et le CA genere."""
        red = self.codes.aggregate(
            n=models.Sum("uses"))["n"] or 0
        rev = PromoCodeRedemption.objects.filter(
            promo_code__influencer=self).aggregate(s=models.Sum("discount_amount"))["s"] or 0
        self.total_redemptions = red
        self.total_revenue = rev
        # Score simple : sature a 10
        score = min(10, red * 0.2 + (rev / 100000))
        self.reach_score = round(score, 1)
        self.save(update_fields=["total_redemptions", "total_revenue", "reach_score"])


class PromoCode(TimeStampedModel):
    """Code promo influenceur valable chez un restaurant partenaire."""
    influencer = models.ForeignKey(InfluencerProfile, on_delete=models.CASCADE,
                                   related_name="codes")
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE,
                                   related_name="promo_codes")
    code = models.CharField(max_length=24, unique=True)
    percent = models.PositiveSmallIntegerField(default=10, help_text="Rabais en %")
    is_active = models.BooleanField(default=True)
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True)
    max_uses = models.PositiveIntegerField(default=0, help_text="0 = illimite")
    uses = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = get_random_string(8).upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} (-{self.percent}%)"

    @property
    def is_valid(self):
        now = timezone.now()
        if not self.is_active:
            return False
        if self.ends_at and now > self.ends_at:
            return False
        if self.starts_at > now:
            return False
        if self.max_uses and self.uses >= self.max_uses:
            return False
        return True

    def discount_for(self, amount):
        return round(amount * self.percent / 100)


class PromoCodeRedemption(TimeStampedModel):
    promo_code = models.ForeignKey(PromoCode, on_delete=models.CASCADE, related_name="redemptions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, null=True,
                              related_name="promo_redemptions")
    discount_amount = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.promo_code.code} -> {self.discount_amount} FCFA"
