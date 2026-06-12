from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("explorer/", views.explore, name="explore"),
    path("recherche/", views.search_api, name="search_api"),
    path("notifications/", views.notifications, name="notifications"),
    path("push/subscribe/", views.push_subscribe, name="push_subscribe"),
    path("aide/", views.help_center, name="help"),
    path("legal/<str:page>/", views.legal_page, name="legal"),
    path("tableau-admin/", views.admin_dashboard, name="admin_dashboard"),
    # PWA
    path("manifest.webmanifest", views.manifest, name="manifest"),
    path("sw.js", views.service_worker, name="service_worker"),
    path("offline/", views.offline, name="offline"),
    # SEO
    path("robots.txt", views.robots_txt, name="robots"),
    path("sitemap.xml", views.sitemap_xml, name="sitemap"),
    # Deep links (App Links / Universal Links)
    path(".well-known/assetlinks.json", views.android_assetlinks, name="assetlinks"),
    path(".well-known/apple-app-site-association",
         views.apple_app_site_association, name="aasa"),
]
