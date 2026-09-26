"""Donnees de demonstration ONE EAT (Douala) : comptes, catalogue, commandes coherentes."""
import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import Address
from apps.orders.models import Order, OrderItem, Review
from apps.promotions.models import InfluencerProfile, PromoCode, Promotion
from apps.restaurants.models import Restaurant

User = get_user_model()
S = Order.Status


class Command(BaseCommand):
    help = "Charge des donnees de demonstration ONE EAT"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Supprime les donnees existantes")

    def handle(self, *args, **opts):
        rng = random.Random(237)
        if opts.get("reset"):
            self.stdout.write("Suppression des donnees...")
            Order.objects.all().delete()
            Restaurant.objects.all().delete()
            User.objects.filter(is_superuser=False).delete()

        admin, created = User.objects.get_or_create(
            username="admin@oneeat.cm",
            defaults={"email": "admin@oneeat.cm", "role": User.Role.ADMIN, "is_staff": True,
                      "is_superuser": True, "first_name": "Admin", "last_name": "ONE EAT"})
        if created:
            admin.set_password("admin123")
            admin.save()

        client, created = User.objects.get_or_create(
            username="client@oneeat.cm",
            defaults={"email": "client@oneeat.cm", "role": User.Role.CLIENT, "first_name": "Jean",
                      "last_name": "Mbarga", "phone": "+237690000001", "address": "Akwa, Douala",
                      "lat": 4.0500, "lng": 9.7000})
        if created:
            client.set_password("client123")
            client.save()
        if not client.addresses.exists():
            Address.objects.create(user=client, label="Domicile", address="Rue Joss, Akwa, Douala",
                                   instructions="Immeuble jaune, 2e étage", lat=4.0500, lng=9.7000,
                                   is_default=True)
            Address.objects.create(user=client, label="Bureau", address="Boulevard de la Liberté, Bonanjo",
                                   instructions="Accueil au rez-de-chaussée", lat=4.0469, lng=9.6890)

        call_command("sync_catalog", "--hours", stdout=self.stdout)

        inf_user, _ = User.objects.get_or_create(
            username="influenceur@oneeat.cm",
            defaults={"email": "influenceur@oneeat.cm", "role": User.Role.INFLUENCER,
                      "first_name": "Stéphanie", "last_name": "Foodie"})
        inf_user.set_password("influ123")
        inf_user.save()
        inf_profile, _ = InfluencerProfile.objects.get_or_create(
            user=inf_user, defaults={"handle": "@steph_eats_dla", "followers": 25400,
                                     "bio": "Food blogueuse à Douala 🍴"})
        PromoCode.objects.get_or_create(
            code="STEPH10", defaults={"influencer": inf_profile, "percent": 10, "max_uses": 100,
                                      "restaurant": Restaurant.objects.get(name="Le Ndolé d'Or")})

        burger = Restaurant.objects.get(name="Burger House Bali")
        if not burger.promotions.exists():
            promo = Promotion.objects.create(
                restaurant=burger, title="Happy Hour Burgers",
                description="-25% sur les burgers de 15h à 18h !",
                discount_type=Promotion.DiscountType.PERCENT, discount_value=25,
                ends_at=timezone.now() + timedelta(days=30))
            promo.dishes.set(burger.dishes.filter(section__name="Burgers"))

        if not Order.objects.filter(customer=client).exists():
            self._demo_orders(client, rng)

        for r in Restaurant.objects.all():
            demo_rating = r.rating
            r.recompute_rating()
            if r.rating_count == 0:
                r.rating = demo_rating
            r.orders_count = r.orders.count()
            r.save(update_fields=["rating", "orders_count"])

        self.stdout.write(self.style.SUCCESS(
            "\nComptes : admin@oneeat.cm/admin123 · client@oneeat.cm/client123 · "
            "resto1@oneeat.cm/resto123 · resto7@oneeat.cm/resto123 (Green Bowl) · "
            "livreur1@oneeat.cm/livreur123 · influenceur@oneeat.cm/influ123"))

    def _demo_orders(self, client, rng):
        """Historique coherent : chaque statut a les bons horodatages et acteurs."""
        drivers = list(User.objects.filter(role=User.Role.DRIVER).order_by("username"))
        now = timezone.now()
        plan = [  # (restaurant, statut, anciennete en heures)
            ("Green Bowl Bonapriso", S.PREPARING, 0.3),
            ("Le Ndolé d'Or", S.DELIVERED, 26),
            ("Burger House Bali", S.DELIVERED, 50),
            ("Grill Master Bonapriso", S.DELIVERED, 75),
            ("Mama Africa Kitchen", S.CANCELLED, 98),
            ("Chicken & Grill Akwa", S.DELIVERED, 120),
        ]
        for n, (resto_name, status, age_h) in enumerate(plan):
            resto = Restaurant.objects.get(name=resto_name)
            created_at = now - timedelta(hours=age_h)
            order = Order.objects.create(
                customer=client, restaurant=resto, status=status, delivery_fee=resto.delivery_fee,
                delivery_address="Rue Joss, Akwa, Douala — Immeuble jaune, 2e étage",
                delivery_lat=4.05, delivery_lng=9.70,
                payment_method=Order.Payment.MOMO if n % 2 else Order.Payment.CASH,
                payment_status=Order.PaymentStatus.PAID if n % 2 else Order.PaymentStatus.ON_DELIVERY)
            for dish in rng.sample(list(resto.dishes.all()), 2):
                OrderItem.objects.create(order=order, dish=dish, name=dish.name,
                                         unit_price=dish.price, quantity=rng.randint(1, 2))
            order.recompute_totals()
            order.created_at = created_at
            order.confirmed_at = created_at + timedelta(minutes=3)
            if status == S.CANCELLED:
                order.confirmed_at = None
                order.cancelled_at = created_at + timedelta(minutes=6)
                order.cancel_reason = "Rupture de stock sur un plat."
                order.payment_status = Order.PaymentStatus.REFUNDED if n % 2 else order.payment_status
            if status == S.DELIVERED:
                driver = drivers[n % len(drivers)]
                order.driver = driver
                order.driver_assigned_at = created_at + timedelta(minutes=5)
                order.ready_at = created_at + timedelta(minutes=resto.delivery_time_min)
                order.picked_up_at = order.ready_at + timedelta(minutes=4)
                order.delivered_at = order.picked_up_at + timedelta(minutes=14)
                order.payment_status = Order.PaymentStatus.PAID
            order.save()
            if status == S.DELIVERED and n != 1:
                Review.objects.create(
                    order=order, customer=client, restaurant=resto, driver=order.driver,
                    rating=rng.randint(4, 5), driver_rating=5,
                    comment=rng.choice(["Excellent, livraison rapide !", "Très bon, je recommande.",
                                        "Plats savoureux et copieux.", "Livreur très poli."]))
