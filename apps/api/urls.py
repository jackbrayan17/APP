from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token

from . import views

app_name = "api"

router = DefaultRouter()
router.register("restaurants", views.RestaurantViewSet, basename="restaurant")
router.register("categories", views.CategoryViewSet, basename="category")
router.register("orders", views.OrderViewSet, basename="order")

urlpatterns = [
    path("", include(router.urls)),
    path("auth/login/", views.api_login, name="login"),
    path("auth/token/", obtain_auth_token, name="token"),
    path("delivery/nearby/", views.nearby_orders, name="nearby_orders"),
]
