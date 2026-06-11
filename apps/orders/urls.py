from django.urls import path
from . import views

app_name = "orders"

urlpatterns = [
    path("panier/", views.cart_view, name="cart"),
    path("panier/ajouter/<int:dish_id>/", views.cart_add, name="cart_add"),
    path("panier/modifier/<int:dish_id>/", views.cart_update, name="cart_update"),
    path("commander/", views.checkout, name="checkout"),
    path("commandes/", views.order_list, name="list"),
    path("commande/<str:number>/", views.order_detail, name="detail"),
    path("commande/<str:number>/noter/", views.review_order, name="review"),
    path("c/<str:token>/", views.order_share, name="share"),
]
