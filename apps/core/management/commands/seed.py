"""Donnees de demonstration ONE EAT (Douala)."""
import random
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.text import slugify
from PIL import Image, ImageDraw

from apps.restaurants.models import Category, Restaurant, MenuSection, Dish
from apps.delivery.models import DriverProfile
from apps.orders.models import Order, OrderItem, Review
from apps.promotions.models import Promotion, InfluencerProfile, PromoCode

User = get_user_model()

# Centre Douala + quartiers
HOODS = {
    "Bonanjo": (4.0469, 9.6890),
    "Akwa": (4.0500, 9.7000),
    "Bonapriso": (4.0300, 9.7050),
    "Bali": (4.0420, 9.6960),
    "Deido": (4.0650, 9.7100),
}

CATEGORIES = [
    ("Tous", "🍽️", True, False, 0),
    ("Local", "🍲", False, True, 1),
    ("Fast Food", "🍔", False, True, 2),
    ("Grillades", "🔥", False, False, 3),
    ("Snacks", "🥪", False, False, 4),
    ("Boissons", "🥤", False, False, 5),
    ("Healthy", "🥗", False, True, 6),
    ("Café", "☕", False, True, 7),
]

RESTOS = [
    {
        "name": "Le Ndolé d'Or", "tagline": "Cuisine Locale", "hood": "Bonanjo",
        "bio": "Spécialiste du Ndolé depuis 1998. Recette traditionnelle camerounaise.",
        "rating": 4.9, "fee": 800, "tmin": 25, "tmax": 40, "featured": True, "pro": True,
        "cats": ["Local", "Healthy"],
        "sections": {
            "Cuisine Camerounaise": [
                ("Ndolé Spécial + Riz", "Notre recette signature depuis 1998. Ndolé aux crevettes géantes et bœuf, servi avec riz blanc parfumé.", 4000, 35, True),
                ("Okok + Bâton de Manioc", "Feuilles d'okok pilées aux graines de courge. Cuisson lente, saveur profonde du terroir.", 2800, 40, False),
                ("Sanga (Maïs + Haricots)", "Maïs doux et haricots blancs cuits ensemble avec huile de palme et épices.", 2500, 30, False),
            ],
            "Riz & Accompagnements": [
                ("Riz sauté au poulet", "Riz sauté maison, légumes croquants et poulet émincé.", 3000, 25, False),
                ("Poisson braisé + Miondo", "Bar braisé au feu de bois, accompagné de miondo et piment.", 4500, 30, True),
            ],
            "Snacks": [
                ("Beignets Haricots", "Beignets moelleux servis avec une purée de haricots épicée.", 1000, 15, False),
            ],
        },
    },
    {
        "name": "Chicken & Grill Akwa", "tagline": "Premium", "hood": "Akwa",
        "bio": "Les meilleures grillades de Douala. Poulet braisé, poisson et brochettes.",
        "rating": 4.8, "fee": 500, "tmin": 15, "tmax": 25, "featured": True, "pro": True, "premium": True,
        "cats": ["Grillades", "Fast Food"],
        "sections": {
            "Grillades": [
                ("Poulet braisé entier", "Poulet mariné 24h, braisé au charbon. Servi avec frites et piment.", 6000, 25, True),
                ("Demi-poulet grillé", "Demi-poulet grillé, sauce maison et plantains mûrs.", 3500, 20, True),
                ("Brochettes de bœuf (x5)", "Brochettes de bœuf tendres marinées aux épices locales.", 2500, 15, False),
            ],
            "Accompagnements": [
                ("Frites de plantain", "Plantains mûrs frits, croustillants à souhait.", 1000, 10, False),
                ("Alloco", "Bananes plantain frites, sauce tomate pimentée.", 1200, 12, False),
            ],
        },
    },
    {
        "name": "Mama Africa Kitchen", "tagline": "Cuisine Locale", "hood": "Bonapriso",
        "bio": "Cuisine camerounaise authentique. Ndolé, Eru, Koki et plus.",
        "rating": 4.7, "fee": 700, "tmin": 20, "tmax": 35, "featured": False, "pro": False,
        "cats": ["Local"],
        "sections": {
            "Plats du jour": [
                ("Eru + Water Fufu", "Eru aux feuilles fraîches, viande et poisson fumé. Servi avec water fufu.", 3000, 30, True),
                ("Koki + Plantain", "Gâteau de haricots à la vapeur dans des feuilles de bananier.", 2000, 35, False),
                ("Poulet DG", "Poulet Directeur Général : poulet, plantains et légumes sautés.", 5000, 30, True),
            ],
        },
    },
    {
        "name": "Grill Master Bonapriso", "tagline": "Premium", "hood": "Bonapriso",
        "bio": "Viandes premium grillées au charbon. Côtes de bœuf, agneau et plus.",
        "rating": 4.7, "fee": 700, "tmin": 20, "tmax": 30, "featured": False, "pro": True, "premium": True,
        "cats": ["Grillades"],
        "sections": {
            "Viandes Premium": [
                ("Côtes de bœuf (500g)", "Côtes de bœuf maturées, grillées au charbon de bois.", 9000, 30, True),
                ("Gigot d'agneau", "Gigot d'agneau rôti lentement, herbes de Provence.", 8500, 30, False),
                ("Mixed Grill", "Assortiment de bœuf, poulet et merguez. Idéal à partager.", 12000, 25, True),
            ],
        },
    },
    {
        "name": "Pizza Roma Akwa", "tagline": "Fast Food", "hood": "Akwa",
        "bio": "Pizzas au feu de bois, pâtes fraîches et tiramisu maison.",
        "rating": 4.6, "fee": 600, "tmin": 20, "tmax": 30, "featured": False, "pro": False,
        "cats": ["Fast Food"],
        "sections": {
            "Pizzas": [
                ("Pizza Margherita", "Tomate, mozzarella, basilic frais.", 5000, 20, True),
                ("Pizza Reine", "Tomate, mozzarella, jambon, champignons.", 6000, 22, False),
                ("Pizza 4 Fromages", "Mozzarella, gorgonzola, parmesan, chèvre.", 6500, 22, True),
            ],
        },
    },
    {
        "name": "Burger House Bali", "tagline": "Fast Food", "hood": "Bali",
        "bio": "Burgers gourmets, frites maison et milkshakes.",
        "rating": 4.5, "fee": 500, "tmin": 15, "tmax": 25, "featured": False, "pro": False,
        "cats": ["Fast Food", "Snacks"],
        "sections": {
            "Burgers": [
                ("Classic Beef Burger", "Steak haché, cheddar, salade, tomate, sauce maison.", 4000, 18, True),
                ("Chicken Crispy", "Poulet pané croustillant, coleslaw et sauce barbecue.", 3500, 18, True),
                ("Double Cheese", "Double steak, double cheddar, oignons caramélisés.", 5500, 20, False),
            ],
            "Sides": [
                ("Frites maison", "Frites fraîches coupées à la main.", 1500, 10, False),
                ("Milkshake vanille", "Milkshake crémeux à la vanille de Madagascar.", 2000, 8, False),
            ],
        },
    },
]

DIETARY_INFO = {
    "Ndolé Spécial + Riz": (True, 620, 34, "riche en protéines, fibres, cuisine locale", "Un bon choix complet; demandez moins d'huile si vous voulez un repas plus léger."),
    "Okok + Bâton de Manioc": (True, 540, 22, "fibres, végétal, traditionnel", "Riche en fibres; idéal pour un déjeuner rassasiant sans friture."),
    "Sanga (Maïs + Haricots)": (True, 480, 18, "végétarien, fibres, énergie lente", "Bon équilibre glucides-fibres pour tenir l'après-midi."),
    "Riz sauté au poulet": (False, 690, 31, "protéiné, copieux", "Préférez une portion de légumes en plus pour équilibrer l'assiette."),
    "Poisson braisé + Miondo": (True, 610, 38, "protéiné, grillé, oméga-3", "Une option intéressante si la sauce pimentée reste servie à part."),
    "Beignets Haricots": (False, 520, 14, "snack, végétarien", "A réserver aux petites faims; accompagnez d'eau plutôt que boisson sucrée."),
    "Poulet braisé entier": (False, 980, 72, "très protéiné, grillé, à partager", "Plat copieux, meilleur à partager ou à compléter avec crudités."),
    "Demi-poulet grillé": (True, 580, 42, "protéiné, grillé, faible sucre", "Choisissez plantain ou frites, pas forcément les deux."),
    "Brochettes de bœuf (x5)": (True, 520, 36, "protéiné, grillé", "Bonne option protéinée; ajoutez un accompagnement léger."),
    "Frites de plantain": (False, 430, 3, "accompagnement, frit", "Accompagnement plaisir; portion modérée recommandée."),
    "Alloco": (False, 470, 3, "accompagnement, frit", "Très énergétique; équilibrer avec une protéine grillée."),
    "Eru + Water Fufu": (True, 650, 32, "fibres, protéines, traditionnel", "Repas complet, riche en feuilles; demandez moins d'huile si besoin."),
    "Koki + Plantain": (True, 520, 19, "végétarien, vapeur, fibres", "Cuisson vapeur intéressante pour un repas local plus doux."),
    "Poulet DG": (False, 820, 38, "copieux, protéiné", "Très généreux; bon en repas principal unique."),
    "Côtes de bœuf (500g)": (False, 1050, 70, "très protéiné, premium", "Riche et très copieux; à accompagner de légumes plutôt que frites."),
    "Gigot d'agneau": (False, 920, 62, "protéiné, premium", "Option gourmande; privilégiez une portion modérée."),
    "Mixed Grill": (False, 1180, 78, "à partager, très protéiné", "Pensé pour partager; évitez d'en faire une portion individuelle complète."),
    "Pizza Margherita": (False, 760, 28, "végétarien, fromage", "Plus légère que les pizzas garnies, mais reste riche en fromage."),
    "Pizza Reine": (False, 840, 34, "copieux, fromage", "Choisissez une demi-portion avec salade si disponible."),
    "Pizza 4 Fromages": (False, 910, 36, "fromage, riche", "Option plaisir; à équilibrer sur le reste de la journée."),
    "Classic Beef Burger": (False, 820, 39, "protéiné, fast food", "Demandez sauce à part pour mieux contrôler l'apport."),
    "Chicken Crispy": (False, 790, 35, "poulet, croustillant", "Poulet pané plus riche; préférez eau ou boisson non sucrée."),
    "Double Cheese": (False, 1040, 55, "très copieux, fromage", "Très rassasiant; évitez de multiplier les sides."),
    "Frites maison": (False, 430, 5, "accompagnement, frit", "Portion plaisir, à partager si possible."),
    "Milkshake vanille": (False, 520, 11, "dessert, sucré", "A considérer comme dessert plutôt que simple boisson."),
}


DEMO_IMAGE_PALETTES = [
    ("#FFF4E8", "#FF6B1A", "#2F855A", "#9C4221"),
    ("#F7FAFC", "#E53E3E", "#F6AD55", "#2D3748"),
    ("#F0FFF4", "#38A169", "#ECC94B", "#744210"),
    ("#FFFAF0", "#DD6B20", "#805AD5", "#2F855A"),
    ("#F8F5FF", "#6B46C1", "#ED8936", "#276749"),
]


def ensure_demo_dish_image(dish):
    """Cree une image locale deterministic pour les plats de demo."""
    slug = slugify(dish.name) or f"dish-{dish.id}"
    real_rel_path = Path("dishes") / "demo" / f"{slug}.jpg"
    real_abs_path = settings.MEDIA_ROOT / real_rel_path
    if real_abs_path.exists():
        dish.image = str(real_rel_path).replace("\\", "/")
        return

    rel_path = Path("dishes") / "demo" / f"{slug}.png"
    abs_path = settings.MEDIA_ROOT / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)

    if not abs_path.exists():
        palette = DEMO_IMAGE_PALETTES[dish.id % len(DEMO_IMAGE_PALETTES)]
        bg, main, accent, dark = palette
        rng = random.Random(slug)

        img = Image.new("RGB", (900, 700), bg)
        draw = ImageDraw.Draw(img)

        # Fond doux, sans texte, pour rester lisible en miniature.
        for _ in range(18):
            x = rng.randint(-80, 900)
            y = rng.randint(-80, 700)
            r = rng.randint(30, 120)
            color = rng.choice([main, accent])
            draw.ellipse((x, y, x + r, y + r), fill=color)

        # Assiette.
        draw.ellipse((185, 105, 715, 635), fill="#FFFFFF", outline="#E5E7EB", width=10)
        draw.ellipse((245, 165, 655, 575), fill="#F9FAFB", outline="#F3F4F6", width=5)

        # Composition du plat.
        for i in range(9):
            cx = rng.randint(315, 585)
            cy = rng.randint(235, 465)
            rx = rng.randint(34, 82)
            ry = rng.randint(24, 66)
            color = [main, accent, dark, "#FBBF24", "#16A34A"][i % 5]
            draw.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=color)

        for _ in range(14):
            x = rng.randint(300, 600)
            y = rng.randint(210, 490)
            draw.line((x, y, x + rng.randint(-50, 50), y + rng.randint(-35, 35)),
                      fill="#14532D", width=rng.randint(4, 8))

        img.save(abs_path, "PNG", optimize=True)

    dish.image = str(rel_path).replace("\\", "/")


class Command(BaseCommand):
    help = "Charge des donnees de demonstration ONE EAT"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Supprime les donnees existantes")

    def handle(self, *args, **opts):
        if opts.get("reset"):
            self.stdout.write("Suppression des donnees...")
            Order.objects.all().delete()
            Restaurant.objects.all().delete()
            User.objects.filter(is_superuser=False).delete()

        # --- Admin ---
        admin, created = User.objects.get_or_create(
            username="admin@oneeat.cm",
            defaults={"email": "admin@oneeat.cm", "role": User.Role.ADMIN,
                      "is_staff": True, "is_superuser": True, "first_name": "Admin",
                      "last_name": "ONE EAT"})
        if created:
            admin.set_password("admin123")
            admin.save()
        self.stdout.write(self.style.SUCCESS("Admin: admin@oneeat.cm / admin123"))

        # --- Categories ---
        cat_map = {}
        for name, emoji, is_tous, is_nav, order in CATEGORIES:
            c, _ = Category.objects.get_or_create(
                name=name, defaults={"emoji": emoji, "is_nav": is_nav, "order": order})
            c.emoji, c.is_nav, c.order = emoji, is_nav, order
            c.save()
            cat_map[name] = c

        # --- Client de demo ---
        client, c_created = User.objects.get_or_create(
            username="client@oneeat.cm",
            defaults={"email": "client@oneeat.cm", "role": User.Role.CLIENT,
                      "first_name": "Jean", "last_name": "Mbarga", "phone": "+237690000001",
                      "address": "Akwa, Douala", "lat": 4.0500, "lng": 9.7000})
        if c_created:
            client.set_password("client123")
            client.save()
        self.stdout.write(self.style.SUCCESS("Client: client@oneeat.cm / client123"))

        # --- Restaurants ---
        all_dishes = []
        for i, data in enumerate(RESTOS):
            owner, _ = User.objects.get_or_create(
                username=f"resto{i+1}@oneeat.cm",
                defaults={"email": f"resto{i+1}@oneeat.cm", "role": User.Role.RESTAURANT,
                          "first_name": data["name"]})
            owner.set_password("resto123"); owner.role = User.Role.RESTAURANT; owner.save()

            lat, lng = HOODS[data["hood"]]
            lat += random.uniform(-0.004, 0.004); lng += random.uniform(-0.004, 0.004)
            resto, _ = Restaurant.objects.get_or_create(
                name=data["name"], owner=owner,
                defaults={
                    "tagline": data["tagline"], "bio": data["bio"], "neighborhood": data["hood"],
                    "rating": data["rating"], "delivery_fee": data["fee"],
                    "delivery_time_min": data["tmin"], "delivery_time_max": data["tmax"],
                    "is_featured": data["featured"], "is_pro": data.get("pro", False),
                    "is_premium": data.get("premium", False), "lat": lat, "lng": lng,
                    "address": f"{data['hood']}, Douala",
                    "phone": f"+23769{random.randint(1000000,9999999)}",
                })
            resto.tagline = data["tagline"]; resto.bio = data["bio"]
            resto.rating = data["rating"]; resto.is_featured = data["featured"]
            resto.lat, resto.lng = lat, lng
            resto.save()
            resto.categories.set([cat_map[c] for c in data["cats"]])

            for s_order, (sec_name, dishes) in enumerate(data["sections"].items()):
                section, _ = MenuSection.objects.get_or_create(
                    restaurant=resto, name=sec_name, defaults={"order": s_order})
                for d_name, d_desc, price, prep, popular in dishes:
                    dish, _ = Dish.objects.get_or_create(
                        restaurant=resto, name=d_name,
                        defaults={"description": d_desc, "price": price, "prep_time": prep,
                                  "is_popular": popular, "section": section,
                                  "category": resto.categories.first(),
                                  "orders_count": random.randint(5, 120)})
                    dish.section = section; dish.description = d_desc
                    dish.price = price; dish.prep_time = prep; dish.is_popular = popular
                    dish.category = resto.categories.first()
                    diet = DIETARY_INFO.get(d_name)
                    if diet:
                        (dish.is_diet, dish.calories, dish.protein_grams,
                         dish.dietary_tags, dish.dietary_note) = diet
                    ensure_demo_dish_image(dish)
                    dish.save()
                    all_dishes.append(dish)

            hero_dish = resto.dishes.filter(is_popular=True, image__isnull=False).first() or resto.dishes.filter(image__isnull=False).first()
            if hero_dish:
                resto.cover_image = hero_dish.image.name
                resto.logo = hero_dish.image.name
                resto.save(update_fields=["cover_image", "logo"])

        # --- Livreurs ---
        for i in range(3):
            d_user, _ = User.objects.get_or_create(
                username=f"livreur{i+1}@oneeat.cm",
                defaults={"email": f"livreur{i+1}@oneeat.cm", "role": User.Role.DRIVER,
                          "first_name": f"Livreur", "last_name": f"{i+1}",
                          "phone": f"+23767{random.randint(1000000,9999999)}"})
            d_user.set_password("livreur123"); d_user.role = User.Role.DRIVER; d_user.save()
            lat, lng = list(HOODS.values())[i]
            DriverProfile.objects.update_or_create(
                user=d_user, defaults={"current_lat": lat, "current_lng": lng,
                                       "is_available": True, "service_radius_km": 10,
                                       "deliveries_count": random.randint(10, 80),
                                       "rating": round(random.uniform(4.3, 5.0), 1)})
        self.stdout.write(self.style.SUCCESS("Livreurs: livreur1@oneeat.cm / livreur123"))

        # --- Influenceur ---
        inf_user, _ = User.objects.get_or_create(
            username="influenceur@oneeat.cm",
            defaults={"email": "influenceur@oneeat.cm", "role": User.Role.INFLUENCER,
                      "first_name": "Stéphanie", "last_name": "Foodie"})
        inf_user.set_password("influ123"); inf_user.role = User.Role.INFLUENCER; inf_user.save()
        inf_profile, _ = InfluencerProfile.objects.get_or_create(
            user=inf_user, defaults={"handle": "@steph_eats_dla", "followers": 25400,
                                     "bio": "Food blogueuse à Douala 🍴"})
        resto0 = Restaurant.objects.first()
        PromoCode.objects.get_or_create(
            influencer=inf_profile, restaurant=resto0,
            defaults={"code": "STEPH10", "percent": 10, "max_uses": 100})
        self.stdout.write(self.style.SUCCESS("Influenceur: influenceur@oneeat.cm / influ123"))

        # --- Promotions ---
        if all_dishes:
            promo_resto = Restaurant.objects.get(name="Burger House Bali")
            promo = Promotion.objects.create(
                restaurant=promo_resto, title="Happy Hour Burgers",
                description="-25% sur tous les burgers de 15h à 18h !",
                discount_type=Promotion.DiscountType.PERCENT, discount_value=25,
                ends_at=timezone.now() + timedelta(days=14))
            promo.dishes.set(promo_resto.dishes.all()[:3])

        # --- Commandes de demo ---
        statuses = [Order.Status.PREPARING, Order.Status.ON_THE_WAY,
                    Order.Status.DELIVERED, Order.Status.DELIVERED]
        restos = list(Restaurant.objects.all())
        for n in range(8):
            resto = random.choice(restos)
            dishes = list(resto.dishes.all())
            if not dishes:
                continue
            order = Order.objects.create(
                customer=client, restaurant=resto,
                status=random.choice(statuses), delivery_fee=resto.delivery_fee,
                delivery_address="Akwa, Douala", delivery_lat=4.05, delivery_lng=9.70,
                payment_method=Order.Payment.CASH)
            for dish in random.sample(dishes, min(2, len(dishes))):
                OrderItem.objects.create(order=order, dish=dish, name=dish.name,
                                         unit_price=dish.price, quantity=random.randint(1, 2))
            order.recompute_totals()
            order.created_at = timezone.now() - timedelta(days=random.randint(0, 5),
                                                          hours=random.randint(0, 20))
            order.save()
            if order.status == Order.Status.DELIVERED and not hasattr(order, "review"):
                Review.objects.create(
                    order=order, customer=client, restaurant=resto,
                    rating=random.randint(4, 5),
                    comment=random.choice([
                        "Excellent, livraison rapide !", "Très bon, je recommande.",
                        "Plats savoureux et copieux.", "Parfait comme toujours."]))

        # Recalcul des notes
        for r in Restaurant.objects.all():
            r.recompute_rating()
            demo_rating = next((data["rating"] for data in RESTOS if data["name"] == r.name), None)
            if r.rating_count == 0 and demo_rating is not None:
                r.rating = demo_rating
            r.orders_count = r.orders.count()
            r.save(update_fields=["rating", "orders_count"])

        self.stdout.write(self.style.SUCCESS(
            f"\n[OK] Seed termine : {Restaurant.objects.count()} restaurants, "
            f"{Dish.objects.count()} plats, {Order.objects.count()} commandes."))
