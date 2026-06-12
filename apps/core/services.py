"""Services transverses : notifications in-app + Web Push (PWA) + Push natif (FCM)."""
import json
import logging
import os

from django.conf import settings

from .models import Notification, PushSubscription

logger = logging.getLogger("oneeat")


def notify(user, title, body="", url="", icon="/static/icons/icon-192.png"):
    """Cree une notification in-app + Web Push (PWA) + Push natif FCM (app Flutter)."""
    notif = Notification.objects.create(
        user=user, title=title, body=body, url=url, icon=icon)
    send_web_push(user, title, body, url, icon)
    send_native_push(user, title, body, url)
    return notif


def send_native_push(user, title, body="", url="/"):
    """Envoie une notification Firebase Cloud Messaging (FCM HTTP v1) aux appareils
    mobiles de l'utilisateur (app Flutter Android/iOS). No-op si non configure.

    Configuration : definir GOOGLE_APPLICATION_CREDENTIALS (chemin du JSON de
    compte de service Firebase) et FCM_PROJECT_ID dans l'environnement, puis
    `pip install firebase-admin`.
    """
    from .models import DevicePushToken

    project_id = getattr(settings, "FCM_PROJECT_ID", "") or os.environ.get("FCM_PROJECT_ID", "")
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if not (project_id and creds_path):
        logger.info("FCM non configure — push natif ignore pour %s", user)
        return

    tokens = list(DevicePushToken.objects.filter(user=user, is_active=True)
                  .values_list("token", flat=True))
    if not tokens:
        return
    try:
        import firebase_admin
        from firebase_admin import credentials, messaging
    except ImportError:
        logger.warning("firebase-admin non installe — push natif ignore")
        return

    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(creds_path))

    message = messaging.MulticastMessage(
        tokens=tokens,
        notification=messaging.Notification(title=title, body=body),
        data={"url": url or "/"},
        android=messaging.AndroidConfig(priority="high"),
        apns=messaging.APNSConfig(payload=messaging.APNSPayload(
            aps=messaging.Aps(sound="default", content_available=True))),
    )
    try:
        resp = messaging.send_each_for_multicast(message)
        # Nettoie les tokens invalides
        for idx, r in enumerate(resp.responses):
            if not r.success:
                DevicePushToken.objects.filter(token=tokens[idx]).update(is_active=False)
    except Exception:
        logger.exception("Erreur FCM push natif")


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
