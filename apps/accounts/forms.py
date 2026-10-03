from django import forms
from django.contrib.auth import get_user_model

from apps.core.inputs import clean_phone

User = get_user_model()


class RegisterForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, min_length=6)
    password2 = forms.CharField(widget=forms.PasswordInput, label="Confirmer le mot de passe")

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone", "role")

    def clean_phone(self):
        phone = clean_phone(self.cleaned_data.get("phone"))
        if phone is None:
            raise forms.ValidationError("Téléphone invalide : 8 à 15 chiffres (le + est accepté).")
        return phone

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Cet email est deja utilise.")
        return email

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password") != cleaned.get("password2"):
            self.add_error("password2", "Les mots de passe ne correspondent pas.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"]
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user
