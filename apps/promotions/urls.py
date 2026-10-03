from django.urls import path
from . import views

app_name = "promotions"

urlpatterns = [
    path("influenceur/", views.influencer_dashboard, name="influencer_dashboard"),
    path("resto/codes/", views.restaurant_code_create, name="restaurant_code_create"),
    path("tableau-admin/codes/", views.admin_promo_codes, name="admin_promo_codes"),
    path("tableau-admin/codes/<int:pk>/<str:action>/", views.promo_code_review,
         name="promo_code_review"),
]
