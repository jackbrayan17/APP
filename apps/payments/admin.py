from django.contrib import admin

from .models import Payout, Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("reference", "amount", "currency", "status", "channel", "created_at")
    list_filter = ("status", "channel")
    search_fields = ("reference", "notchpay_reference", "phone")
    readonly_fields = ("raw_payload",)


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ("recipient_type", "restaurant", "driver", "amount", "phone", "status",
                    "created_at")
    list_filter = ("status", "recipient_type", "channel")
    search_fields = ("phone", "notchpay_transfer_ref", "beneficiary_id")
