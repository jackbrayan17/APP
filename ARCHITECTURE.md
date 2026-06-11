# ONE EAT — Architecture du système

> Plateforme de livraison de repas à **Douala, Cameroun** (type Uber Eats), construite en **Django 5 + DRF**, livrée en **PWA** (Android / iOS / desktop) avec notifications push, cartes de géolocalisation et 6 espaces (client, restaurant, livreur, influenceur, admin, public/partage).

---

## 1. Vue d'ensemble

| Couche | Technologie |
|---|---|
| Backend | Django 5.2, Python 3.13 |
| API | Django REST Framework (Token + Session auth) |
| Base de données | SQLite (dev) — migrable PostgreSQL (prod) |
| Frontend | Templates Django + Tailwind CSS (CDN) + Alpine.js |
| Cartes | Leaflet + OpenStreetMap (sans clé API) |
| PWA | Web App Manifest + Service Worker + Web Push (VAPID) |
| Géoloc | Formule de Haversine (`apps/core/geo.py`), pas de PostGIS requis |
| Notifications | `pywebpush` (Web Push), notifications in-app |

### Structure des apps

```
oneeat/                 # config projet (settings, urls, wsgi/asgi)
apps/
  core/        # logs, notifications, push, géo, PWA, dashboard admin, seed
  accounts/    # User multi-rôle, auth (login/register/profil)
  restaurants/ # Restaurant, Category, MenuSection, Dish, photos, dashboard resto
  orders/      # Order, OrderItem, Review, panier, checkout, partage
  delivery/    # DriverProfile, dashboard livreur, carte, géoloc temps réel
  promotions/  # Promotion, InfluencerProfile, PromoCode, redemptions
  api/         # DRF — serializers, viewsets, endpoints
templates/     # tous les écrans (client, dashboards, share, legal, pwa)
static/        # js/app.js, icônes PWA
```

---

## 2. Modèle de données

### accounts.User (AbstractUser)
Utilisateur unique multi-rôle.

| Champ | Type | Notes |
|---|---|---|
| role | choices | `client`, `restaurant`, `driver`, `influencer`, `admin` |
| phone, city, address | char | |
| lat, lng | float | adresse de livraison géolocalisée |
| avatar | image | |
| is_verified | bool | |

### restaurants
- **Category** — catégories globales (Tous, Local, Fast Food, Grillades, Snacks, Boissons, Healthy, Café). `is_nav` = visible dans la barre du bas.
- **Restaurant** — `owner` (FK User), `slug`, `share_token`, `tagline` (badge), `bio`, `logo`, `cover_image`, `neighborhood`, `lat/lng` (position carte), `delivery_fee`, `delivery_time_min/max`, `brand_color` / `accent_color` (personnalisation page), `is_pro` (badge Pro), `is_premium`, `is_featured` (À la une), `rating` (cache), `rating_count`, `orders_count`.
- **RestaurantPhoto** — galerie.
- **MenuSection** — onglets du menu (ex : « Cuisine Camerounaise »).
- **Dish** — `name`, `description`, `price`, `prep_time`, `image`, `video`, `is_available`, `is_popular`, `orders_count`. Propriétés : `active_promo`, `current_price`, `has_promo`.

### orders
- **Order** — `number`, `share_token`, `customer`, `restaurant`, `driver`, `status` (pending → confirmed → preparing → ready → picked_up → on_the_way → delivered / cancelled), `payment_method` (cash/momo/om/card), montants (`items_total`, `delivery_fee`, `discount`, `total`), géoloc livraison (`delivery_lat/lng`) + position livreur temps réel (`driver_lat/lng`), `promo_code`.
- **OrderItem** — snapshot (`name`, `unit_price`, `quantity`).
- **Review** — `rating` (1–5), `driver_rating`, `comment`. `save()` recalcule la note du restaurant.

### delivery
- **DriverProfile** — `user` (OneToOne), `restaurant` (FK nullable = livreur rattaché à un resto), `vehicle`, `is_available`, `current_lat/lng`, `service_radius_km` (défaut **10 km**), `deliveries_count`, `rating`.

### promotions
- **Promotion** — `restaurant`, `title` (thème), `discount_type` (percent / amount / fixed_price), `discount_value`, `dishes` (M2M), `starts_at`/`ends_at`, `banner_color`. `apply_to(price)` calcule le prix promo.
- **InfluencerProfile** — `handle`, `followers`, `reach_score` (note de portée /10), `total_redemptions`, `total_revenue`. `recompute_score()` recalcule la note selon l'usage des codes.
- **PromoCode** — `influencer`, `restaurant`, `code`, `percent`, `max_uses`, `uses`, validité.
- **PromoCodeRedemption** — trace chaque utilisation (code, user, order, montant remisé).

### core
- **ActivityLog** — journal de trafic (user, action, path, status_code, ip, level). Alimenté par `ActivityLogMiddleware`.
- **Notification** — notifications in-app.
- **PushSubscription** — abonnements Web Push (endpoint, p256dh, auth).

### Diagramme relationnel (simplifié)

```
User 1───* Restaurant 1───* MenuSection 1───* Dish
 │              │                              │
 │              *                              *
 │          Promotion *────────────────────────┘ (M2M dishes)
 │
 ├──* Order *──1 Restaurant      Order 1───* OrderItem
 │       │                       Order 1───1 Review
 │       └──1 driver (User)
 │
 ├──1 DriverProfile *──1 Restaurant
 └──1 InfluencerProfile 1───* PromoCode 1───* PromoCodeRedemption
```

---

## 3. Workflows métier

### A. Commande client
1. Client parcourt l'accueil / explorer → ouvre une page restaurant.
2. Ajoute des plats au **panier** (session, AJAX, badge live).
3. Checkout : adresse + **géolocalisation GPS**, paiement, code promo optionnel.
4. Le panier est **groupé par restaurant** → 1 commande par restaurant.
5. Application du code promo influenceur (remise %, incrément `uses`, recalcul score influenceur).
6. Notification push envoyée au restaurant.

### B. Cycle de vie d'une commande
```
pending → confirmed → preparing → ready → picked_up → on_the_way → delivered
                                                          └─(carte temps réel)
```
- **Restaurant** change le statut + assigne un livreur (dashboard).
- **Livreur** accepte une course (si dans son périmètre 10 km), démarre, marque livré.
- À chaque transition → notification push au client.
- Après `delivered` → le client peut **noter** (resto + livreur) et commenter.

### C. Géolocalisation & carte
- Restaurant définit sa position (`lat/lng`) dans « Personnaliser ma page ».
- Livreur partage sa position en continu (`watchPosition` → `POST /livreur/position/`), ce qui met à jour `driver_lat/lng` des commandes `on_the_way`.
- Le livreur ne voit que les commandes dont le restaurant est à **≤ 10 km** (Haversine).
- Client et livreur suivent la livraison sur une carte Leaflet (`/suivi/<number>/`), rafraîchie toutes les 8 s via l'API.

### D. Promotions & influenceurs
- Restaurant lance une promo (thème, type de remise, durée, plats concernés) → prix barré affiché côté client.
- Influenceur génère des codes `-X%` chez des restaurants partenaires.
- Chaque utilisation note l'influenceur (`reach_score`) selon le nombre d'usages et le CA généré.

---

## 4. API REST (`/api/`)

| Méthode | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/login/` | Token auth (email + mot de passe) |
| POST | `/api/auth/token/` | Token DRF standard |
| GET | `/api/categories/` | Catégories |
| GET | `/api/restaurants/?cat=&hood=&q=` | Liste restaurants (filtrable) |
| GET | `/api/restaurants/<slug>/` | Détail + menu (sections/plats) |
| GET | `/api/restaurants/<slug>/reviews/` | Avis |
| GET | `/api/orders/` | Mes commandes (auth) |
| GET | `/api/orders/<number>/` | Détail commande (suivi position livreur) |
| GET | `/api/delivery/nearby/` | Commandes dans le périmètre du livreur |

Auth : `Authorization: Token <key>`.

---

## 5. PWA (Android / iOS / desktop)

- **Manifest** dynamique `/manifest.webmanifest` (standalone, thème orange, icônes maskable, shortcuts).
- **Service Worker** `/sw.js` : précache du shell, *network-first* pour le HTML (fallback `/offline/`), *cache-first* pour les assets, gestion `push` + `notificationclick`.
- **Web Push** : VAPID via `pywebpush`. Compatible **iOS 16.4+** (PWA installée), Android, desktop. Abonnement enregistré via `/push/subscribe/`.
- Installable (« Ajouter à l'écran d'accueil »), plein écran, safe-area iOS gérée.

### Activer le push (prod)
```bash
pip install pywebpush py-vapid
vapid --gen           # génère les clés
# définir VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY dans l'environnement
```

---

## 6. Sécurité & logs

- Auth Django (mots de passe hashés), permissions par rôle dans chaque vue.
- `ActivityLogMiddleware` journalise les actions métier (POST/PUT/DELETE) + erreurs en base, et tout le trafic dans `oneeat.log` (handler fichier).
- CSRF sur tous les formulaires et appels AJAX.
- Le dashboard admin expose trafic, top plats, top restaurants, utilisateurs, logs.

---

## 7. Démarrage

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py seed --reset      # données de démo Douala
python manage.py runserver
```

### Comptes de démonstration
| Rôle | Email | Mot de passe |
|---|---|---|
| Admin | admin@oneeat.cm | admin123 |
| Client | client@oneeat.cm | client123 |
| Restaurant | resto1@oneeat.cm | resto123 |
| Livreur | livreur1@oneeat.cm | livreur123 |
| Influenceur | influenceur@oneeat.cm | influ123 |

---

## 8. Routes principales

| URL | Espace |
|---|---|
| `/` `/explorer/` `/restaurant/<slug>/` `/panier/` `/commandes/` | Client |
| `/connexion/` `/inscription/` `/profil/` | Auth |
| `/resto/…` | Dashboard restaurant |
| `/livreur/` `/suivi/<number>/` | Dashboard livreur + carte |
| `/influenceur/` | Dashboard influenceur |
| `/tableau-admin/` `/django-admin/` | Admin |
| `/r/<token>/` `/c/<token>/` | Liens de partage publics |
| `/legal/{cgu,confidentialite,cgv,mentions}/` | Pages légales |

---

## 9. Évolutions recommandées (prod)
- PostgreSQL + PostGIS pour des requêtes géospatiales indexées.
- WebSockets (Django Channels) pour le suivi livreur en temps réel (vs polling 8 s).
- Stockage objet (S3) pour médias, CDN.
- Tailwind compilé (au lieu du CDN), bundling JS.
- Intégration paiement Mobile Money réelle (MTN MoMo / Orange Money API).
- File d'attente (Celery) pour l'envoi des push.
```
