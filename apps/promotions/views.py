from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST

from apps.core.inputs import clean_int
from apps.core.views import _is_admin
from apps.restaurants.models import Restaurant
from .models import InfluencerProfile, PromoCode


def counts_out(key, counts):
    return counts.get(key, 0)


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
    }
    return render(request, "influencer/dashboard.html", context)


def _owner_resto(user):
    return Restaurant.objects.filter(owner=user).first()


@login_required
@require_POST
def restaurant_code_create(request):
    """Le restaurant cree un code influenceur : il reste en attente tant qu'ONE EAT ne l'a pas valide."""
    resto = _owner_resto(request.user)
    if not resto:
        return redirect("restaurants:onboarding")
    prof = InfluencerProfile.objects.filter(id=request.POST.get("influencer")).first()
    if not prof:
        messages.error(request, "Choisissez un influenceur ONE EAT.")
        return redirect("restaurants:promos")
    raw_code = (request.POST.get("code") or "").strip().upper().replace(" ", "")
    if raw_code and PromoCode.objects.filter(code=raw_code).exists():
        messages.error(request, "Ce code existe déjà. Choisissez-en un autre.")
        return redirect("restaurants:promos")
    percent = clean_int(request.POST.get("percent"), default=None, lo=1, hi=100)
    max_uses = clean_int(request.POST.get("max_uses"), default=0, lo=0, hi=1_000_000)
    if percent is None or max_uses is None:
        messages.error(request, "Pourcentage (1 à 100) ou nombre d'utilisations invalide.")
        return redirect("restaurants:promos")
    ends_at = None
    if request.POST.get("ends_at"):
        ends_at = parse_datetime(request.POST["ends_at"])
        if ends_at is None:
            messages.error(request, "Date de fin invalide.")
            return redirect("restaurants:promos")
        if timezone.is_naive(ends_at):
            ends_at = timezone.make_aware(ends_at)
    PromoCode.objects.create(
        influencer=prof, restaurant=resto, created_by=request.user,
        code=raw_code or None, percent=percent, max_uses=max_uses, ends_at=ends_at,
    )
    messages.success(request, "Code envoyé à ONE EAT pour validation.")
    return redirect("restaurants:promos")


@user_passes_test(_is_admin, login_url="/connexion/")
def admin_promo_codes(request):
    """Validation et suivi des codes influenceurs (tableau admin)."""
    status = request.GET.get("status", PromoCode.Status.PENDING)
    if status not in PromoCode.Status.values and status != "all":
        status = PromoCode.Status.PENDING
    codes = PromoCode.objects.select_related("restaurant", "influencer__user", "created_by")
    counts = {row["status"]: row["n"] for row in codes.values("status").annotate(n=Count("id"))}
    if status != "all":
        codes = codes.filter(status=status)
    context = {
        "codes": codes[:200],
        "status": status,
        "counts": {
            "pending": counts.get(PromoCode.Status.PENDING, 0),
            "approved": counts.get(PromoCode.Status.APPROVED, 0),
            "rejected": counts.get(PromoCode.Status.REJECTED, 0),
            "all": sum(counts.values()),
        },
        "tabs": [("pending", "En attente", counts_out("pending", counts)),
                 ("approved", "Validés", counts_out("approved", counts)),
                 ("rejected", "Refusés", counts_out("rejected", counts)),
                 ("all", "Tous", sum(counts.values()))],
    }
    return render(request, "admin_dashboard/promo_codes.html", context)


@user_passes_test(_is_admin, login_url="/connexion/")
@require_POST
def promo_code_review(request, pk, action):
    code = get_object_or_404(PromoCode, pk=pk)
    if action == "approve":
        code.status = PromoCode.Status.APPROVED
        code.validated_by, code.validated_at = request.user, timezone.now()
        code.rejection_reason = ""
        code.is_active = True
        code.save(update_fields=["status", "validated_by", "validated_at", "rejection_reason", "is_active", "updated_at"])
        messages.success(request, f"Code {code.code} validé et mis en ligne.")
    elif action == "reject":
        code.status = PromoCode.Status.REJECTED
        code.validated_by, code.validated_at = request.user, timezone.now()
        code.rejection_reason = (request.POST.get("reason") or "Non conforme.")[:160]
        code.save(update_fields=["status", "validated_by", "validated_at", "rejection_reason", "updated_at"])
        messages.info(request, f"Code {code.code} refusé.")
    elif action == "toggle":
        code.is_active = not code.is_active
        code.save(update_fields=["is_active", "updated_at"])
        messages.info(request, f"Code {code.code} {'activé' if code.is_active else 'désactivé'}.")
    elif action == "delete":
        label = code.code
        code.delete()
        messages.info(request, f"Code {label} supprimé.")
    status = request.POST.get("status", "pending")
    if status not in PromoCode.Status.values:
        status = "all"
    return redirect(f"{reverse('promotions:admin_promo_codes')}?status={status}")
