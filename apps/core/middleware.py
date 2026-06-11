"""Middleware de journalisation du traffic."""
import logging

logger = logging.getLogger("oneeat")

# Chemins ignores pour ne pas polluer les logs
_SKIP_PREFIXES = ("/static/", "/media/", "/sw.js", "/favicon", "/manifest")


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class ActivityLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            path = request.path
            if path.startswith(_SKIP_PREFIXES):
                return response
            # On ne logge en base que les actions "metier" (POST/PUT/DELETE)
            # et les erreurs, pour rester leger. Tout passe par le logger fichier.
            from apps.core.models import ActivityLog

            level = "info"
            if response.status_code >= 500:
                level = "error"
            elif response.status_code >= 400:
                level = "warning"

            should_persist = request.method in ("POST", "PUT", "PATCH", "DELETE") \
                or response.status_code >= 400

            logger.info("%s %s -> %s", request.method, path, response.status_code)

            if should_persist:
                ActivityLog.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    level=level,
                    action=f"{request.method} {path}",
                    path=path,
                    method=request.method,
                    status_code=response.status_code,
                    ip=_client_ip(request),
                    user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
                )
        except Exception:  # ne jamais casser la requete a cause du log
            logger.exception("ActivityLogMiddleware error")
        return response
