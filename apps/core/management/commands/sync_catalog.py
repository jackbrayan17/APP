"""Synchronise le catalogue de demonstration sans rien supprimer.

Idempotent : peut tourner a chaque deploiement sur la base de production.
Cree ce qui manque (categories, restaurants, plats, livreurs de test) et met a
jour photos, descriptions et valeurs nutritionnelles. Ne touche jamais aux
commandes, avis, comptes clients ni aux plats ajoutes par les restaurateurs.
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.delivery.models import DriverProfile
from apps.restaurants.catalog import CATEGORIES, DRIVERS, HOODS, RESTAURANTS
from apps.restaurants.models import Category, Dish, MenuSection, Restaurant, default_opening_hours

User = get_user_model()
DEMO_IMAGE_DIR = "dishes/demo"


def _image_path(name):
    rel = f"{DEMO_IMAGE_DIR}/{name}.jpg"
    return rel if (settings.MEDIA_ROOT / rel).exists() else None


class Command(BaseCommand):
    help = "Cree/met a jour le catalogue de demo (photos, nutrition, restaurants) sans suppression"

    def add_arguments(self, parser):
        parser.add_argument("--hours", action="store_true",
                            help="Reapplique aussi les horaires d'ouverture du catalogue")

    @transaction.atomic
    def handle(self, *args, **opts):
        cats = {}
        for name, emoji, order in CATEGORIES:
            c, _ = Category.objects.get_or_create(name=name, defaults={"emoji": emoji, "order": order})
            c.emoji, c.order = emoji, order
            c.is_nav = name in ("Local", "Healthy", "Fast Food", "Grillades")
            c.save()
            cats[name] = c
        Category.objects.filter(name="Café").update(order=9, is_nav=False)

        created_restos = created_dishes = updated_dishes = 0
        for i, data in enumerate(RESTAURANTS):
            idx = data.get("owner_index", i + 1)
            email = f"resto{idx}@oneeat.cm"
            owner, new_owner = User.objects.get_or_create(
                username=email, defaults={"email": email, "role": User.Role.RESTAURANT,
                                          "first_name": data["name"][:30]})
            if new_owner:
                owner.set_password("resto123")
                owner.save()

            resto = Restaurant.objects.filter(name=data["name"]).first()
            lat, lng = HOODS[data["hood"]]
            if not resto:
                resto = Restaurant(name=data["name"], owner=owner, lat=lat + 0.002 * (i % 3 - 1),
                                   lng=lng + 0.002 * (i % 2), rating=data["rating"],
                                   phone=f"+2376990000{i:02d}")
                created_restos += 1
            resto.tagline, resto.bio = data["tagline"], data["bio"]
            resto.neighborhood, resto.address = data["hood"], f"{data['hood']}, Douala"
            resto.delivery_fee = data["fee"]
            resto.delivery_time_min, resto.delivery_time_max = data["tmin"], data["tmax"]
            resto.is_featured = data["featured"]
            resto.is_pro, resto.is_premium = data.get("pro", False), data.get("premium", False)
            resto.brand_color = data.get("brand", resto.brand_color)
            if resto.lat is None:
                resto.lat, resto.lng = lat, lng
            if (opts["hours"] or not resto.pk or not resto.opening_hours
                    or resto.opening_hours == default_opening_hours()):
                resto.opening_hours = data["hours"]
            resto.save()
            resto.categories.add(*[cats[c] for c in data["cats"]])

            hero = None
            for s_order, (sec_name, dishes) in enumerate(data["sections"].items()):
                section, _ = MenuSection.objects.get_or_create(
                    restaurant=resto, name=sec_name, defaults={"order": s_order})
                for name, desc, price, prep, popular, image, nutri in dishes:
                    dish = Dish.objects.filter(restaurant=resto, name=name).first()
                    if dish:
                        updated_dishes += 1
                    else:
                        dish = Dish(restaurant=resto, name=name, orders_count=10 + len(name))
                        created_dishes += 1
                    dish.section, dish.description = section, desc
                    dish.price, dish.prep_time, dish.is_popular = price, prep, popular
                    dish.category = cats[data["cats"][0]]
                    (dish.is_diet, dish.calories, dish.protein_grams, dish.carbs_grams,
                     dish.fat_grams, dish.fiber_grams, dish.dietary_tags, dish.dietary_note) = nutri
                    img = _image_path(image)
                    if img:
                        dish.image = img
                    dish.save()
                    if popular and img and not hero:
                        hero = img
            if hero:
                resto.cover_image = hero
                resto.logo = hero
                resto.save(update_fields=["cover_image", "logo"])

        for i, (first, last, hood, vehicle) in enumerate(DRIVERS):
            email = f"livreur{i + 1}@oneeat.cm"
            user, new_user = User.objects.get_or_create(
                username=email, defaults={"email": email, "role": User.Role.DRIVER,
                                          "phone": f"+2376770000{i:02d}"})
            if new_user:
                user.set_password("livreur123")
            user.first_name, user.last_name, user.role = first, last, User.Role.DRIVER
            user.save()
            lat, lng = HOODS[hood]
            prof, new_prof = DriverProfile.objects.get_or_create(
                user=user, defaults={"current_lat": lat, "current_lng": lng, "is_available": True,
                                     "rating": 4.8 - i * 0.1, "deliveries_count": 40 - i * 9})
            prof.vehicle = vehicle
            prof.phone = prof.phone or user.phone
            prof.save(update_fields=["vehicle", "phone"])

        self.stdout.write(self.style.SUCCESS(
            f"Catalogue synchronise : {created_restos} restaurant(s) et {created_dishes} plat(s) crees, "
            f"{updated_dishes} plat(s) mis a jour."))
