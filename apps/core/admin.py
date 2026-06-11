from django.contrib import admin
from .models import ActivityLog, Notification, PushSubscription


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "level", "action", "user", "status_code", "ip")
    list_filter = ("level", "method", "status_code")
    search_fields = ("action", "path", "user__username")
    readonly_fields = [f.name for f in ActivityLog._meta.fields]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "is_read", "created_at")
    list_filter = ("is_read",)


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "user_agent", "created_at")
