"""Saisies utilisateur : aucun « faux chiffre » enregistre, aucune erreur 500 sur une valeur absurde."""
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.core.inputs import clean_float, clean_int, clean_phone
from apps.restaurants.models import Dish, MenuSection, Restaurant

User = get_user_model()


class InputHelpersTests(TestCase):
    def test_clean_int_rejects_fake_numbers(self):
        self.assertEqual(clean_int("1 500", lo=0), 1500)
        self.assertIsNone(clean_int("12,5"))
        self.assertIsNone(clean_int("abc"))
        self.assertIsNone(clean_int("1e9"))
        self.assertIsNone(clean_int("-3", lo=0))
        self.assertIsNone(clean_int("101", lo=1, hi=100))
        self.assertEqual(clean_int("", default=20), 20)

    def test_clean_float_rejects_nan_and_out_of_range(self):
        self.assertEqual(clean_float("4,05", lo=-90, hi=90), 4.05)
        self.assertIsNone(clean_float("nan", lo=-90, hi=90))
        self.assertIsNone(clean_float("inf"))
        self.assertIsNone(clean_float("95", lo=-90, hi=90))
        self.assertIsNone(clean_float("null"))

    def test_clean_phone(self):
        self.assertEqual(clean_phone("+237 690 00 00 01"), "+237690000001")
        self.assertEqual(clean_phone(""), "")
        self.assertIsNone(clean_phone("abc"))
        self.assertIsNone(clean_phone("12"))


class InvalidInputViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("sync_catalog", "--hours", verbosity=0)
        cls.resto = Restaurant.objects.get(name="Le Ndolé d'Or")
        cls.owner = cls.resto.owner
        cls.dish = cls.resto.dishes.first()

    def setUp(self):
        self.client.force_login(self.owner)

    def test_dish_price_refused_not_saved_as_zero(self):
        old_price = self.dish.price
        r = self.client.post(reverse("restaurants:dish_save"), {
            "dish_id": self.dish.id, "name": self.dish.name, "price": "12,5"})
        self.assertEqual(r.status_code, 302)
        self.dish.refresh_from_db()
        self.assertEqual(self.dish.price, old_price)

    def test_customize_keeps_previous_values_on_garbage(self):
        old_fee, old_lat = self.resto.delivery_fee, self.resto.lat
        r = self.client.post(reverse("restaurants:customize"), {
            "delivery_fee": "abc", "delivery_time_min": "-5", "phone": "call me",
            "max_orders_per_day": "1e9", "lat": "nan", "lng": "4"})
        self.assertEqual(r.status_code, 302)
        self.resto.refresh_from_db()
        self.assertEqual(self.resto.delivery_fee, old_fee)
        self.assertEqual(self.resto.lat, old_lat)

    def test_promo_creation_refuses_percent_over_100(self):
        r = self.client.post(reverse("restaurants:promos"), {
            "title": "Test", "discount_type": "percent", "discount_value": "150"})
        self.assertEqual(r.status_code, 302)
        self.assertFalse(self.resto.promotions.filter(title="Test").exists())

    def test_promo_creation_bad_date_does_not_crash(self):
        r = self.client.post(reverse("restaurants:promos"), {
            "title": "Date", "discount_type": "percent", "discount_value": "10", "ends_at": "demain"})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(self.resto.promotions.filter(title="Date").exists())

    def test_section_order_garbage_does_not_crash(self):
        r = self.client.post(reverse("restaurants:section_save"), {"name": "Desserts", "order": "x"})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(MenuSection.objects.filter(restaurant=self.resto, name="Desserts").exists())

    def test_profile_rejects_bad_phone(self):
        customer = User.objects.create_user("saisie@test.cm", "saisie@test.cm", "pass12345",
                                            phone="+237690000041")
        self.client.force_login(customer)
        self.client.post(reverse("accounts:profile"), {"phone": "xx", "lat": "95", "lng": "0"})
        customer.refresh_from_db()
        self.assertEqual(customer.phone, "+237690000041")

    def test_driver_position_rejects_nan(self):
        from apps.delivery.models import DriverProfile
        driver = User.objects.get(username="livreur1@oneeat.cm")
        self.client.force_login(driver)
        r = self.client.post(reverse("delivery:update_location"),
                             data='{"lat": "NaN", "lng": 4.05}', content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertIsInstance(DriverProfile.objects.get(user=driver), DriverProfile)
