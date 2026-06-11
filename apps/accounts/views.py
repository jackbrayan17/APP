from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

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
        u.phone = request.POST.get("phone", u.phone)
        u.address = request.POST.get("address", u.address)
        lat = request.POST.get("lat")
        lng = request.POST.get("lng")
        if lat and lng:
            u.lat, u.lng = float(lat), float(lng)
        u.save()
        messages.success(request, "Profil mis a jour.")
        return redirect("accounts:profile")
    return render(request, "accounts/profile.html")
