"""Parcours complet client -> restaurant -> livreur, et regles de coherence."""
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.delivery.models import DriverProfile
from apps.orders.models import Order
from apps.restaurants.models import Dish, DishOption, Restaurant

User = get_user_model()
S = Order.Status


class OrderFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("sync_catalog", "--hours", verbosity=0)
        cls.client_user = User.objects.create_user("c@test.cm", "c@test.cm", "pass12345",
                                                   phone="+237690000009")
        cls.resto = Restaurant.objects.get(name="Chicken & Grill Akwa")  # ouvert 24h/24
        cls.dish = cls.resto.dishes.first()
        cls.driver = User.objects.get(username="livreur1@oneeat.cm")

    def _checkout(self, **extra):
        self.client.force_login(self.client_user)
        self.client.post(reverse("orders:cart_add", args=[self.dish.id]))
        data = {"address": "Akwa, Douala", "payment_method": "cash", "notes": "Sans piment"}
        data.update(extra)
        return self.client.post(reverse("orders:checkout"), data)

    def test_full_cash_flow(self):
        self._checkout()
        order = Order.objects.get(customer=self.client_user)
        self.assertEqual(order.status, S.PENDING)
        self.assertEqual(order.total, order.items_total + self.resto.delivery_fee)
        self.assertEqual(order.notes, "Sans piment")

        # Le livreur ne peut pas prendre une commande pas encore acceptee.
        self.client.force_login(self.driver)
        self.client.post(reverse("delivery:accept", args=[order.id]))
        order.refresh_from_db()
        self.assertIsNone(order.driver_id)

        self.client.force_login(self.resto.owner)
        self.client.post(reverse("restaurants:order_status", args=[order.id]), {"action": "accept"})
        order.refresh_from_db()
        self.assertEqual(order.status, S.CONFIRMED)

        # Livreur accepte : affecte, mais la commande reste en cuisine.
        self.client.force_login(self.driver)
        self.client.post(reverse("delivery:accept", args=[order.id]))
        order.refresh_from_db()
        self.assertEqual(order.driver, self.driver)
        self.assertEqual(order.status, S.CONFIRMED)

        # Recuperation refusee tant que la cuisine n'a pas fini.
        self.client.post(reverse("delivery:update_status", args=[order.id]), {"action": "pickup"})
        order.refresh_from_db()
        self.assertEqual(order.status, S.CONFIRMED)

        self.client.force_login(self.resto.owner)
        self.client.post(reverse("restaurants:order_status", args=[order.id]), {"action": "ready"})
        self.client.force_login(self.driver)
        self.client.post(reverse("delivery:update_status", args=[order.id]), {"action": "pickup"})
        self.client.post(reverse("delivery:update_status", args=[order.id]), {"action": "arrive"})
        order.refresh_from_db()
        self.assertEqual(order.status, S.ARRIVED)
        self.assertIsNone(order.delivered_at)

        # Le client valide avec un mauvais code : refuse.
        self.client.force_login(self.client_user)
        validate_url = reverse("orders:validate", args=[order.number])
        self.client.post(validate_url, {"code": "0000" if order.delivery_code != "0000" else "1111",
                                        "rating": 5})
        order.refresh_from_db()
        self.assertEqual(order.status, S.ARRIVED)

        # Bon code + note : livree, paiement encaisse, avis cree.
        self.client.post(validate_url, {"code": order.delivery_code, "rating": 4, "driver_rating": 5})
        order.refresh_from_db()
        self.assertEqual(order.status, S.DELIVERED)
        self.assertEqual(order.payment_status, Order.PaymentStatus.PAID)
        self.assertTrue(order.picked_up_at and order.delivered_at)
        self.assertEqual(order.review.rating, 4)
        self.assertEqual(DriverProfile.objects.get(user=self.driver)
                         .earnings_since()["amount"], order.delivery_fee)

    def test_customer_can_abandon_until_pickup(self):
        self._checkout()
        order = Order.objects.get(customer=self.client_user)
        self.client.post(reverse("orders:cancel", args=[order.number]))
        order.refresh_from_db()
        self.assertEqual(order.status, S.CANCELLED)
        self.assertEqual(order.cancelled_by, Order.CancelledBy.CUSTOMER)
        self.assertTrue(order.is_abandoned)

    def test_daily_cap_blocks_checkout(self):
        self.resto.max_orders_per_day = 1
        self.resto.save()
        self._checkout()
        self._checkout()
        self.assertEqual(Order.objects.filter(restaurant=self.resto).count(), 1)

    def test_strip_emojis_from_restaurant_text(self):
        self.resto.tagline = "Premium 🔥 Akwa"
        self.resto.save()
        self.resto.refresh_from_db()
        self.assertEqual(self.resto.tagline, "Premium Akwa")

    def test_mobile_money_hidden_until_paid(self):
        self._checkout(payment_method="momo", payment_phone="677000000")
        order = Order.objects.get(customer=self.client_user)
        self.assertTrue(order.is_awaiting_payment)
        self.client.force_login(self.resto.owner)
        r = self.client.get(reverse("restaurants:orders") + "?tab=new")
        self.assertNotContains(r, order.number)
        self.client.force_login(self.client_user)
        self.client.post(reverse("orders:payment", args=[order.number]), {"action": "confirm"})
        order.refresh_from_db()
        self.assertEqual(order.payment_status, Order.PaymentStatus.PAID)

    def test_closed_restaurant_blocks_checkout(self):
        self.resto.is_temporarily_closed = True
        self.resto.save()
        self._checkout()
        self.assertFalse(Order.objects.filter(customer=self.client_user).exists())

    def test_client_cancel_only_before_acceptance(self):
        self._checkout()
        order = Order.objects.get(customer=self.client_user)
        self.client.post(reverse("orders:cancel", args=[order.number]))
        order.refresh_from_db()
        self.assertEqual(order.status, S.CANCELLED)

    def test_pages_render(self):
        self.client.force_login(self.client_user)
        dish = Dish.objects.filter(calories__isnull=False).first()
        for url in ["/", "/explorer/", "/dietetique/", "/dietetique/?objectif=proteine",
                    reverse("restaurants:dish_detail", args=[dish.id]),
                    reverse("restaurants:detail", args=[self.resto.slug]), "/panier/",
                    "/commandes/", "/credits-photos/"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.client.force_login(self.resto.owner)
        for url in ["/resto/", "/resto/commandes/", "/resto/menu/", "/resto/personnaliser/"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.client.force_login(self.driver)
        self.assertEqual(self.client.get("/livreur/").status_code, 200)


class PromoCheckoutTests(TestCase):
    """Code promo au checkout (web + API) : remise persistee, erreurs claires, pas de 500."""

    @classmethod
    def setUpTestData(cls):
        from apps.promotions.models import InfluencerProfile, PromoCode
        call_command("sync_catalog", "--hours", verbosity=0)
        cls.user = User.objects.create_user("promo@test.cm", "promo@test.cm", "pass12345",
                                            phone="+237690000021")
        cls.resto = Restaurant.objects.get(name="Le Ndolé d'Or")
        cls.dish = cls.resto.dishes.first()
        inf_user = User.objects.create_user("inf@test.cm", "inf@test.cm", "pass12345")
        profile = InfluencerProfile.objects.create(user=inf_user, handle="@test")
        cls.code = PromoCode.objects.create(
            influencer=profile, restaurant=cls.resto, code="TEST10", percent=10,
            status=PromoCode.Status.APPROVED)

    def _post(self, **extra):
        self.client.force_login(self.user)
        self.client.post(reverse("orders:cart_add", args=[self.dish.id]))
        data = {"address": "Akwa, Douala", "payment_method": "cash"}
        data.update(extra)
        return self.client.post(reverse("orders:checkout"), data)

    def test_web_promo_discount_is_saved(self):
        self._post(promo_code="test10")
        order = Order.objects.get(customer=self.user)
        order.refresh_from_db()
        self.assertEqual(order.promo_code, "TEST10")
        self.assertEqual(order.discount, round(order.items_total * 10 / 100))
        self.assertEqual(order.total, order.items_total + self.resto.delivery_fee - order.discount)
        self.assertEqual(self.code.redemptions.count(), 1)

    def test_invalid_promo_blocks_order_instead_of_ignoring_it(self):
        response = self._post(promo_code="NOPE")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Order.objects.filter(customer=self.user).exists())

    def test_api_checkout_with_promo_returns_201(self):
        from rest_framework.test import APIClient
        api = APIClient()
        api.force_authenticate(self.user)
        r = api.post("/api/checkout/", {
            "items": [{"dish_id": self.dish.id, "quantity": 2}],
            "delivery_address": "Akwa", "payment_method": "cash",
            "delivery_lat": None, "delivery_lng": None, "promo_code": "TEST10"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Order.objects.get(customer=self.user).promo_code, "TEST10")

    def test_invalid_gps_string_does_not_crash_checkout(self):
        response = self._post(lat="null", lng="undefined")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Order.objects.filter(customer=self.user).exists())


class DishOptionTests(TestCase):
    """Complements et supplements (boissons, extras) choisis au moment de l'ajout au panier."""

    @classmethod
    def setUpTestData(cls):
        call_command("sync_catalog", "--hours", verbosity=0)
        cls.user = User.objects.create_user("opt@test.cm", "opt@test.cm", "pass12345",
                                            phone="+237690000031")
        cls.resto = Restaurant.objects.get(name="Le Ndolé d'Or")
        cls.dish = cls.resto.dishes.first()
        cls.drink = DishOption.objects.create(dish=cls.dish, group="Boissons", name="Coca-Cola 33cl", price=500)
        cls.extra = DishOption.objects.create(dish=cls.dish, group="Suppléments", name="Plantain", price=300)
        cls.free = DishOption.objects.create(dish=cls.dish, group="Sauces", name="Piment", price=0)
        cls.other_dish = cls.resto.dishes.exclude(id=cls.dish.id).first()
        cls.foreign = DishOption.objects.create(dish=cls.other_dish, name="Autre", price=100)

    def setUp(self):
        self.client.force_login(self.user)

    def _cart(self):
        return self.client.session.get("cart", {})

    def test_add_with_options_creates_separate_line_and_price(self):
        r = self.client.post(reverse("orders:cart_add", args=[self.dish.id]),
                             {"options": [self.drink.id, self.extra.id]})
        self.assertEqual(r.status_code, 200)
        key = f"{self.dish.id}:{self.drink.id}-{self.extra.id}"
        self.assertEqual(self._cart()[key]["qty"], 1)
        r = self.client.get(reverse("orders:cart"))
        group = r.context["groups"][0]
        self.assertEqual(group["items"][0]["price"], self.dish.current_price + 800)
        self.assertContains(r, "Coca-Cola 33cl")

    def test_checkout_records_options_on_ticket_and_total(self):
        self.client.post(reverse("orders:cart_add", args=[self.dish.id]), {"options": [self.drink.id]})
        self.client.post(reverse("orders:checkout"), {"address": "Akwa", "payment_method": "cash"})
        order = Order.objects.get(customer=self.user)
        item = order.items.get()
        self.assertIn("Coca-Cola 33cl", item.name)
        self.assertEqual(item.unit_price, self.dish.current_price + 500)
        self.assertEqual(order.items_total, item.unit_price)

    def test_foreign_or_unknown_option_is_refused(self):
        r = self.client.post(reverse("orders:cart_add", args=[self.dish.id]),
                             {"options": [self.foreign.id]})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self._cart(), {})

    def test_unavailable_option_blocks_checkout(self):
        self.client.post(reverse("orders:cart_add", args=[self.dish.id]), {"options": [self.drink.id]})
        self.drink.is_available = False
        self.drink.save(update_fields=["is_available"])
        response = self.client.post(reverse("orders:checkout"), {"address": "Akwa", "payment_method": "cash"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Order.objects.filter(customer=self.user).exists())
        self.drink.is_available = True
        self.drink.save(update_fields=["is_available"])

    def test_legacy_session_cart_still_works(self):
        session = self.client.session
        session["cart"] = {str(self.dish.id): {"qty": 2}}
        session.save()
        self.client.post(reverse("orders:checkout"), {"address": "Akwa", "payment_method": "cash"})
        order = Order.objects.get(customer=self.user)
        self.assertEqual(order.items.get().quantity, 2)

    def test_cart_update_uses_line_key(self):
        self.client.post(reverse("orders:cart_add", args=[self.dish.id]), {"options": [self.drink.id]})
        key = f"{self.dish.id}:{self.drink.id}"
        self.client.post(reverse("orders:cart_update", args=[key]), {"qty": 3})
        self.assertEqual(self._cart()[key]["qty"], 3)

    def test_api_checkout_accepts_option_ids(self):
        from rest_framework.test import APIClient
        api = APIClient()
        api.force_authenticate(self.user)
        r = api.post("/api/checkout/", {
            "items": [{"dish_id": self.dish.id, "quantity": 1, "option_ids": [self.drink.id, self.free.id]}],
            "delivery_address": "Akwa", "payment_method": "cash"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        item = Order.objects.get(customer=self.user).items.get()
        self.assertEqual(item.unit_price, self.dish.current_price + 500)

    def test_owner_manages_options_and_others_cannot(self):
        owner = self.resto.owner
        self.client.force_login(owner)
        r = self.client.post(reverse("restaurants:option_save", args=[self.dish.id]),
                             {"name": "Jus de gingembre", "group": "Boissons", "price": "400"})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(self.dish.options.filter(name="Jus de gingembre", price=400).exists())
        self.client.post(reverse("restaurants:option_save", args=[self.dish.id]),
                         {"name": "Bad", "price": "12,5"})
        self.assertFalse(self.dish.options.filter(name="Bad").exists())
        self.client.force_login(self.user)
        # Un autre client ne peut pas supprimer le complement d'un restaurant : rien n'est modifie.
        self.client.post(reverse("restaurants:option_update", args=[self.drink.id]), {"action": "delete"})
        self.assertTrue(DishOption.objects.filter(id=self.drink.id).exists())
