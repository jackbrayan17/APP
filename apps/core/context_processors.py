from django.conf import settings


def brand(request):
    """Variables globales de marque disponibles dans tous les templates."""
    unread = active_orders = 0
    if request.user.is_authenticated:
        unread = request.user.notifications.filter(is_read=False).count()
        active_orders = request.user.orders.exclude(status__in=["delivered", "cancelled"]).count()
    cart = request.session.get("cart", {}) if hasattr(request, "session") else {}
    return {
        "BRAND_NAME": "ONE EAT",
        "CURRENCY": settings.CURRENCY,
        "DEFAULT_CITY": settings.DEFAULT_CITY,
        "DOUALA_CENTER": settings.DOUALA_CENTER,
        "VAPID_PUBLIC_KEY": settings.VAPID_PUBLIC_KEY,
        "unread_notifications": unread,
        "active_order_count": active_orders,
        "cart_count": sum(i.get("qty", 0) for i in cart.values()),
    }
