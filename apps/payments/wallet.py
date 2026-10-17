"""Solde disponible (gains livres - retraits) pour restaurants et livreurs."""
from django.conf import settings
from django.db.models import Sum

from .models import Payout

ACTIVE_PAYOUT_STATUSES = [Payout.Status.PENDING, Payout.Status.PROCESSING, Payout.Status.PAID]


def restaurant_available_balance(restaurant):
    """Net apres commission plateforme, moins les retraits deja demandes."""
    from apps.orders.models import Order
    agg = (Order.objects.filter(restaurant=restaurant, status=Order.Status.DELIVERED)
           .aggregate(items=Sum("items_total"), disc=Sum("discount")))
    gross = (agg["items"] or 0) - (agg["disc"] or 0)
    commission = settings.PLATFORM_COMMISSION_PERCENT
    net_earned = round(gross * (100 - commission) / 100)
    withdrawn = (restaurant.payouts.filter(status__in=ACTIVE_PAYOUT_STATUSES)
                .aggregate(t=Sum("amount"))["t"] or 0)
    return max(0, net_earned - withdrawn)


def driver_available_balance(user):
    from apps.orders.models import Order
    earned = (Order.objects.filter(driver=user, status=Order.Status.DELIVERED)
              .aggregate(t=Sum("delivery_fee"))["t"] or 0)
    withdrawn = (user.payouts.filter(status__in=ACTIVE_PAYOUT_STATUSES)
                .aggregate(t=Sum("amount"))["t"] or 0)
    return max(0, earned - withdrawn)
