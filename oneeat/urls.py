from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("api/", include("apps.api.urls")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.restaurants.urls")),
    path("", include("apps.orders.urls")),
    path("", include("apps.delivery.urls")),
    path("", include("apps.promotions.urls")),
    path("", include("apps.core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / "static")
