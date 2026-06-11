from django.conf import settings


def brand(request):
    """Variables globales de marque disponibles dans tous les templates."""
    unread = 0
    if request.user.is_authenticated:
        unread = request.user.notifications.filter(is_read=False).count()
    return {
        "BRAND_NAME": "ONE EAT",
        "CURRENCY": settings.CURRENCY,
        "DEFAULT_CITY": settings.DEFAULT_CITY,
        "DOUALA_CENTER": settings.DOUALA_CENTER,
        "VAPID_PUBLIC_KEY": settings.VAPID_PUBLIC_KEY,
        "unread_notifications": unread,
    }
