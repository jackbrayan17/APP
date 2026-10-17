from django.urls import path, re_path
from . import views

app_name = "payments"

urlpatterns = [
    re_path(r"^webhooks/notchpay/?$", views.notchpay_webhook, name="notchpay_webhook"),
    path("retrait/", views.request_payout, name="request_payout"),
    path("diagnostic/", views.diagnostic_transfer, name="diagnostic_transfer"),
]
