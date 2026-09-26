"""Parcours complet client -> restaurant -> livreur, et regles de coherence."""
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.delivery.models import DriverProfile
from apps.orders.models import Order
from apps.restaurants.models import Dish, Restaurant

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
        self.client.post(reverse("delivery:update_status", args=[order.id]), {"action": "deliver"})
        order.refresh_from_db()
        self.assertEqual(order.status, S.DELIVERED)
        self.assertEqual(order.payment_status, Order.PaymentStatus.PAID)
        self.assertTrue(order.picked_up_at and order.delivered_at)
        self.assertEqual(DriverProfile.objects.get(user=self.driver)
                         .earnings_since()["amount"], order.delivery_fee)

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
