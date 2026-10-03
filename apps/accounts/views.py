from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from apps.core.inputs import clean_float, clean_phone
from apps.delivery.models import DriverProfile
from apps.promotions.models import InfluencerProfile
from .forms import RegisterForm
from .models import User


def _post_login_redirect(user):
    """Redirige chaque entite vers son espace."""
    if user.role == User.Role.RESTAURANT:
        return redirect("restaurants:dashboard")
    if user.role == User.Role.DRIVER:
        return redirect("delivery:dashboard")
    if user.role == User.Role.INFLUENCER:
        return redirect("promotions:influencer_dashboard")
    if user.role == User.Role.ADMIN or user.is_staff:
        return redirect("core:admin_dashboard")
    return redirect("core:home")


def register_view(request):
    if request.user.is_authenticated:
        return redirect("core:home")
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Profils dependants du role
            if user.role == User.Role.DRIVER:
                DriverProfile.objects.get_or_create(user=user)
            elif user.role == User.Role.INFLUENCER:
                InfluencerProfile.objects.get_or_create(user=user)
            login(request, user)
            messages.success(request, f"Bienvenue sur ONE EAT, {user.display_name} !")
            return _post_login_redirect(user)
    else:
        form = RegisterForm()
    return render(request, "accounts/register.html", {"form": form,
                                                       "roles": User.Role.choices})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("core:home")
    error = None
    if request.method == "POST":
        identifier = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        # username == email a l'inscription
        user = authenticate(request, username=identifier, password=password)
        if user is None:
            # tentative par email
            try:
                u = User.objects.get(email__iexact=identifier)
                user = authenticate(request, username=u.username, password=password)
            except User.DoesNotExist:
                user = None
        if user is not None:
            login(request, user)
            next_url = request.GET.get("next")
            if next_url:
                return redirect(next_url)
            return _post_login_redirect(user)
        error = "Email ou mot de passe incorrect."
    return render(request, "accounts/login.html", {"error": error})


def logout_view(request):
    logout(request)
    return redirect("core:home")


@login_required
def profile_view(request):
    if request.method == "POST":
        u = request.user
        u.first_name = request.POST.get("first_name", u.first_name)
        u.last_name = request.POST.get("last_name", u.last_name)
        phone = clean_phone(request.POST.get("phone", u.phone))
        if phone is None:
            messages.error(request, "Téléphone invalide : 8 à 15 chiffres (le + est accepté).")
            return redirect("accounts:profile")
        u.phone = phone
        u.address = request.POST.get("address", u.address)[:255]
        lat = clean_float(request.POST.get("lat"), lo=-90, hi=90)
        lng = clean_float(request.POST.get("lng"), lo=-180, hi=180)
        if lat is not None and lng is not None:
            u.lat, u.lng = lat, lng
        u.save()
        messages.success(request, "Profil mis a jour.")
        return redirect("accounts:profile")
    return render(request, "accounts/profile.html")
