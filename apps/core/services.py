"""Services transverses : notifications in-app + Web Push (PWA)."""
import json
import logging

from django.conf import settings

from .models import Notification, PushSubscription

logger = logging.getLogger("oneeat")


def notify(user, title, body="", url="", icon="/static/icons/icon-192.png"):
    """Cree une notification in-app et tente un Web Push (Android/iOS/desktop)."""
    notif = Notification.objects.create(
        user=user, title=title, body=body, url=url, icon=icon)
    send_web_push(user, title, body, url, icon)
    return notif


def send_web_push(user, title, body="", url="/", icon="/static/icons/icon-192.png"):
    """Envoie une notification Web Push a tous les abonnements de l'utilisateur."""
    if not settings.VAPID_PRIVATE_KEY:
        logger.info("VAPID non configure — push ignore pour %s", user)
        return
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logger.warning("pywebpush non installe")
        return

    payload = json.dumps({"title": title, "body": body, "url": url, "icon": icon})
    for sub in PushSubscription.objects.filter(user=user):
        try:
            webpush(
                subscription_info=sub.as_webpush(),
                data=payload,
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={"sub": f"mailto:{settings.VAPID_ADMIN_EMAIL}"},
            )
        except WebPushException as exc:
            logger.warning("Push echoue (%s) — suppression abonnement", exc)
            # 404/410 => abonnement expire
            if exc.response is not None and exc.response.status_code in (404, 410):
                sub.delete()
        except Exception:
            logger.exception("Erreur Web Push")
