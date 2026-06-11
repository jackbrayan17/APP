from django.urls import path
from . import views

app_name = "promotions"

urlpatterns = [
    path("influenceur/", views.influencer_dashboard, name="influencer_dashboard"),
    path("influenceur/code/", views.code_create, name="code_create"),
]
