from django.urls import path
from . import views

app_name = "delivery"

urlpatterns = [
    path("livreur/", views.dashboard, name="dashboard"),
    path("livreur/disponibilite/", views.toggle_available, name="toggle_available"),
    path("livreur/position/", views.update_location, name="update_location"),
    path("livreur/commande/<int:order_id>/accepter/", views.accept_order, name="accept"),
    path("livreur/commande/<int:order_id>/statut/", views.update_status, name="update_status"),
    path("suivi/<str:number>/", views.order_map, name="order_map"),
]
