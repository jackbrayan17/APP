from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from apps.restaurants.models import Restaurant
from .models import InfluencerProfile, PromoCode


@login_required
def influencer_dashboard(request):
    if not request.user.is_influencer and not request.user.is_staff:
        messages.error(request, "Acces reserve aux influenceurs.")
        return redirect("core:home")
    prof, _ = InfluencerProfile.objects.get_or_create(user=request.user)
    prof.recompute_score()
    context = {
        "profile": prof,
        "codes": prof.codes.select_related("restaurant").all(),
        "restaurants": Restaurant.objects.filter(is_active=True),
    }
    return render(request, "influencer/dashboard.html", context)


@login_required
def code_create(request):
    prof, _ = InfluencerProfile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        resto = Restaurant.objects.filter(id=request.POST.get("restaurant")).first()
        if resto:
            PromoCode.objects.create(
                influencer=prof, restaurant=resto,
                code=request.POST.get("code", "").upper() or None,
                percent=int(request.POST.get("percent") or 10),
                max_uses=int(request.POST.get("max_uses") or 0),
            )
            messages.success(request, "Code promo cree.")
    return redirect("promotions:influencer_dashboard")
