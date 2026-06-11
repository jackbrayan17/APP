# 🍽️ ONE EAT — Livraison de repas à Douala

Plateforme complète de commande et livraison de repas (type Uber Eats) pour **Douala, Cameroun**.
Django + DRF, **PWA** installable (Android / iOS / desktop) avec notifications push et cartes temps réel.

![brand](https://img.shields.io/badge/ONE_EAT-FF6B1A?style=flat) ![django](https://img.shields.io/badge/Django-5.2-092E20) ![pwa](https://img.shields.io/badge/PWA-ready-5A0FC8)

## ✨ Fonctionnalités

- 📱 **App client** : accueil, catégories, À la une, recherche, page restaurant, panier, commandes, suivi, notation + commentaire.
- 🍴 **Espace restaurant** : gestion du menu (plats photo/vidéo, prix, temps de prépa), commandes, livreurs rattachés, **personnalisation** (couleurs, bio, logo, photos, position carte, badge Pro), **promotions** (thème, durée, -% / -FCFA).
- 🛵 **Espace livreur** : carte des commandes dans un **périmètre de 10 km**, géolocalisation temps réel, acceptation et suivi de course.
- ⭐ **Espace influenceur** : codes promo `-%` chez les partenaires, **note de portée** selon l'usage.
- 🛠️ **Dashboard admin** : trafic, top plats, restaurants les mieux notés, gestion utilisateurs/restaurants, logs.
- 🔗 **Liens de partage** publics : restaurant (logo, nom, note, plats) et suivi de commande.
- 🔔 **PWA + Web Push** (iOS 16.4+, Android), mode hors-ligne.
- 📜 **Pages légales** : CGU, Politique de confidentialité, CGV, Mentions légales.
- 🌐 **API REST** (DRF, token auth).

## 🚀 Démarrage

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py seed --reset
python manage.py runserver
```

Ouvrir http://127.0.0.1:8000 — comptes de démo dans la page de connexion.

## 📚 Documentation

Voir [`ARCHITECTURE.md`](ARCHITECTURE.md) : modèles de données, workflows, API, PWA, sécurité.

## 🔑 Comptes de démo

| Rôle | Email | Mot de passe |
|---|---|---|
| Admin | admin@oneeat.cm | admin123 |
| Client | client@oneeat.cm | client123 |
| Restaurant | resto1@oneeat.cm | resto123 |
| Livreur | livreur1@oneeat.cm | livreur123 |
| Influenceur | influenceur@oneeat.cm | influ123 |
