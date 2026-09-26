"""Catalogue de demonstration ONE EAT (Douala).

Chaque plat : (nom, description, prix FCFA, prepa min, populaire, image, nutrition)
nutrition = (diete, kcal, proteines g, glucides g, lipides g, fibres g, tags, conseil)
Valeurs nutritionnelles estimees par portion servie (indicatives).
Photos reelles sous licences Creative Commons : voir media/dishes/demo/CREDITS.json.
"""

HOODS = {
    "Bonanjo": (4.0469, 9.6890),
    "Akwa": (4.0500, 9.7000),
    "Bonapriso": (4.0300, 9.7050),
    "Bali": (4.0420, 9.6960),
    "Deido": (4.0650, 9.7100),
}

CATEGORIES = [
    # nom, emoji, ordre
    ("Tous", "🍽️", 0),
    ("Local", "🍲", 1),
    ("Healthy", "🥗", 2),
    ("Fast Food", "🍔", 3),
    ("Grillades", "🔥", 4),
    ("Snacks", "🥪", 5),
    ("Boissons", "🥤", 6),
]

ALL_DAY = {str(d): ["00:00", "23:59"] for d in range(7)}
LUNCH_DINNER = {str(d): ["09:00", "23:30"] for d in range(7)}
LATE_NIGHT = {str(d): ["10:00", "02:00"] for d in range(7)}
HEALTHY_HOURS = {**{str(d): ["07:00", "22:00"] for d in range(6)}, "6": ["08:00", "20:00"]}

RESTAURANTS = [
    {
        "name": "Le Ndolé d'Or", "tagline": "Cuisine Locale", "hood": "Bonanjo",
        "bio": "Spécialiste du Ndolé depuis 1998. Recette traditionnelle camerounaise.",
        "rating": 4.9, "fee": 800, "tmin": 25, "tmax": 40, "featured": True, "pro": True,
        "cats": ["Local", "Healthy"], "hours": LUNCH_DINNER, "brand": "#FF6B1A",
        "sections": {
            "Cuisine Camerounaise": [
                ("Ndolé Spécial + Riz", "Notre recette signature depuis 1998. Ndolé aux crevettes géantes et bœuf, servi avec riz blanc parfumé.", 4000, 35, True, "ndole-special-riz",
                 (True, 620, 34, 62, 24, 9, "riche en protéines, fibres, cuisine locale", "Repas complet : demandez « peu d'huile » pour l'alléger.")),
                ("Okok + Bâton de Manioc", "Feuilles d'okok pilées aux graines de courge. Cuisson lente, saveur profonde du terroir.", 2800, 40, False, "okok-baton-de-manioc",
                 (True, 540, 16, 70, 20, 11, "fibres, végétarien, traditionnel", "Très riche en fibres, rassasiant sans friture.")),
                ("Sanga (Maïs + Haricots)", "Maïs doux et haricots blancs cuits ensemble avec feuilles de morelle et une touche d'huile de palme.", 2500, 30, False, "sanga-mais-haricots",
                 (True, 480, 18, 68, 14, 12, "végétarien, fibres, énergie lente", "Glucides lents + fibres : tient au corps tout l'après-midi.")),
            ],
            "Riz & Accompagnements": [
                ("Riz sauté au poulet", "Riz sauté maison, petits pois, poivrons croquants et poulet émincé.", 3000, 25, False, "riz-saute-au-poulet",
                 (False, 690, 31, 88, 22, 4, "protéiné, copieux", "Ajoutez une salade pour équilibrer l'assiette.")),
                ("Poisson braisé + Miondo", "Bar braisé au feu de bois, pommes sautées ou miondo, piment à part.", 4500, 30, True, "poisson-braise-miondo",
                 (True, 610, 42, 55, 20, 5, "protéiné, grillé, oméga-3", "Excellent choix protéiné ; gardez le piment et la sauce à part.")),
            ],
            "Snacks": [
                ("Beignets Haricots", "Beignets moelleux servis avec une sauce tomate pimentée maison.", 1000, 15, False, "beignets-haricots",
                 (False, 520, 14, 64, 24, 7, "snack, végétarien, frit", "Petite faim ; accompagnez d'eau plutôt que de soda.")),
            ],
        },
    },
    {
        "name": "Chicken & Grill Akwa", "tagline": "Premium", "hood": "Akwa",
        "bio": "Les meilleures grillades de Douala. Poulet braisé, poisson et brochettes. Ouvert 24h/24.",
        "rating": 4.8, "fee": 500, "tmin": 15, "tmax": 25, "featured": True, "pro": True, "premium": True,
        "cats": ["Grillades", "Fast Food"], "hours": ALL_DAY, "brand": "#E4572E",
        "sections": {
            "Grillades": [
                ("Poulet braisé entier", "Poulet mariné 24h, braisé au charbon. Servi avec frites et piment.", 6000, 25, True, "poulet-braise-entier",
                 (False, 980, 72, 60, 48, 5, "très protéiné, grillé, à partager", "Pensé pour 2 : partagez-le ou remplacez les frites par une salade.")),
                ("Demi-poulet grillé", "Demi-poulet grillé, riz, haricots noirs et crudités.", 3500, 20, True, "demi-poulet-grille",
                 (True, 580, 45, 48, 20, 8, "protéiné, grillé, faible en sucre", "Assiette équilibrée : protéines, féculents et légumes.")),
                ("Brochettes de bœuf (x5)", "Brochettes de bœuf tendres marinées aux épices locales (soya).", 2500, 15, False, "brochettes-de-buf-x5",
                 (True, 420, 38, 6, 26, 2, "protéiné, grillé, pauvre en glucides", "Idéal low-carb ; ajoutez des légumes plutôt que des frites.")),
            ],
            "Accompagnements": [
                ("Frites de plantain", "Plantains mûrs frits, croustillants à souhait.", 1000, 10, False, "frites-de-plantain",
                 (False, 430, 3, 62, 18, 4, "accompagnement, frit", "Accompagnement plaisir : une portion suffit.")),
                ("Alloco", "Bananes plantain frites, sauce tomate pimentée.", 1200, 12, False, "alloco",
                 (False, 470, 3, 66, 20, 4, "accompagnement, frit", "Très énergétique : à associer à une protéine grillée.")),
            ],
        },
    },
    {
        "name": "Mama Africa Kitchen", "tagline": "Cuisine Locale", "hood": "Bonapriso",
        "bio": "Cuisine camerounaise authentique. Ndolé, Eru, Koki et plus.",
        "rating": 4.7, "fee": 700, "tmin": 20, "tmax": 35, "featured": False, "pro": False,
        "cats": ["Local"], "hours": LUNCH_DINNER, "brand": "#C2410C",
        "sections": {
            "Plats du jour": [
                ("Eru + Water Fufu", "Eru aux feuilles fraîches, viande et poisson fumé. Servi avec water fufu.", 3000, 30, True, "eru-water-fufu",
                 (True, 650, 32, 70, 26, 10, "fibres, protéines, traditionnel", "Repas complet riche en feuilles ; demandez moins d'huile si besoin.")),
                ("Koki + Plantain", "Gâteau de haricots cuit à la vapeur dans des feuilles de bananier, plantain bouilli.", 2000, 35, False, "koki-plantain",
                 (True, 520, 19, 72, 16, 13, "végétarien, vapeur, fibres", "Cuisson vapeur et plantain bouilli : un local léger et rassasiant.")),
                ("Poulet DG", "Poulet Directeur Général : poulet, plantains mûrs et légumes sautés.", 5000, 30, True, "poulet-dg",
                 (False, 820, 38, 86, 34, 7, "copieux, protéiné", "Très généreux : parfait en plat unique.")),
            ],
        },
    },
    {
        "name": "Grill Master Bonapriso", "tagline": "Premium", "hood": "Bonapriso",
        "bio": "Viandes premium grillées au charbon. Côtes de bœuf, agneau et plus.",
        "rating": 4.7, "fee": 700, "tmin": 20, "tmax": 30, "featured": False, "pro": True, "premium": True,
        "cats": ["Grillades"], "hours": LUNCH_DINNER, "brand": "#7C2D12",
        "sections": {
            "Viandes Premium": [
                ("Côtes de bœuf (500g)", "Côte de bœuf maturée, grillée au charbon de bois, purée maison.", 9000, 30, True, "cotes-de-buf-500g",
                 (False, 1050, 70, 30, 68, 3, "très protéiné, premium", "Riche : préférez des légumes grillés en accompagnement.")),
                ("Gigot d'agneau", "Gigot d'agneau rôti lentement, herbes de Provence.", 8500, 30, False, "gigot-dagneau",
                 (False, 920, 62, 35, 56, 4, "protéiné, premium", "Option gourmande ; une portion modérée suffit.")),
                ("Mixed Grill", "Assortiment de bœuf, poulet et merguez sur plaque. Idéal à partager.", 12000, 25, True, "mixed-grill",
                 (False, 1180, 78, 20, 84, 3, "à partager, très protéiné", "À partager à deux ou trois.")),
            ],
        },
    },
    {
        "name": "Pizza Roma Akwa", "tagline": "Fast Food", "hood": "Akwa",
        "bio": "Pizzas au feu de bois, pâtes fraîches et tiramisu maison.",
        "rating": 4.6, "fee": 600, "tmin": 20, "tmax": 30, "featured": False, "pro": False,
        "cats": ["Fast Food"], "hours": LUNCH_DINNER, "brand": "#B91C1C",
        "sections": {
            "Pizzas": [
                ("Pizza Margherita", "Tomate, mozzarella, basilic frais.", 5000, 20, True, "pizza-margherita",
                 (False, 760, 30, 96, 26, 5, "végétarien, fromage", "La plus légère de nos pizzas.")),
                ("Pizza Reine", "Tomate, mozzarella, jambon, champignons.", 6000, 22, False, "pizza-reine",
                 (False, 840, 38, 96, 32, 5, "copieux, fromage", "Partagez-la ou ajoutez une salade.")),
                ("Pizza 4 Fromages", "Mozzarella, gorgonzola, parmesan, chèvre.", 6500, 22, True, "pizza-4-fromages",
                 (False, 910, 40, 90, 44, 4, "végétarien, fromage, riche", "Option plaisir, à équilibrer sur la journée.")),
            ],
        },
    },
    {
        "name": "Burger House Bali", "tagline": "Fast Food", "hood": "Bali",
        "bio": "Burgers gourmets, frites maison et milkshakes. Ouvert tard le soir.",
        "rating": 4.5, "fee": 500, "tmin": 15, "tmax": 25, "featured": False, "pro": False,
        "cats": ["Fast Food", "Snacks"], "hours": LATE_NIGHT, "brand": "#EA580C",
        "sections": {
            "Burgers": [
                ("Classic Beef Burger", "Steak haché, cheddar, salade, tomate, oignon rouge, sauce maison.", 4000, 18, True, "classic-beef-burger",
                 (False, 820, 39, 58, 46, 3, "protéiné, fast food", "Demandez la sauce à part.")),
                ("Chicken Crispy", "Poulet pané croustillant, coleslaw et sauce barbecue.", 3500, 18, True, "chicken-crispy",
                 (False, 790, 35, 70, 40, 3, "poulet, croustillant, frit", "Plus riche : eau ou boisson sans sucre recommandée.")),
                ("Double Cheese", "Double steak, double cheddar, oignons caramélisés.", 5500, 20, False, "double-cheese",
                 (False, 1040, 55, 60, 62, 3, "très copieux, fromage", "Très rassasiant : évitez de multiplier les sides.")),
            ],
            "Sides": [
                ("Frites maison", "Frites fraîches coupées à la main.", 1500, 10, False, "frites-maison",
                 (False, 430, 5, 56, 20, 5, "accompagnement, frit", "Portion plaisir, à partager.")),
                ("Milkshake vanille", "Milkshake crémeux à la vanille, chantilly.", 2000, 8, False, "milkshake-vanille",
                 (False, 520, 11, 70, 22, 0, "dessert, sucré", "Un dessert plutôt qu'une boisson.")),
            ],
        },
    },
    {
        "name": "Green Bowl Bonapriso", "tagline": "Diététique", "hood": "Bonapriso",
        "bio": "Cuisine diététique conçue avec une nutritionniste : bowls, salades complètes, vapeur et jus frais. Calories et macros affichées pour chaque plat.",
        "rating": 4.8, "fee": 600, "tmin": 20, "tmax": 30, "featured": True, "pro": True,
        "cats": ["Healthy", "Boissons"], "hours": HEALTHY_HOURS, "brand": "#059669",
        "owner_index": 7,
        "sections": {
            "Bowls & plats complets": [
                ("Bowl quinoa & poulet grillé", "Pilons de poulet grillés sans peau, quinoa aux herbes, haricots rouges et maïs grillé.", 4500, 20, True, "bowl-quinoa-poulet-grille",
                 (True, 540, 42, 52, 16, 9, "protéiné, fibres, sans friture", "Assiette idéale après le sport : protéines + glucides lents.")),
                ("Poulet grillé & légumes verts", "Poulet grillé au citron, épinards sautés, boulgour complet et sauce chimichurri.", 4000, 20, True, "poulet-grille-legumes-verts",
                 (True, 480, 44, 38, 15, 7, "protéiné, grillé, sans friture", "Rapport protéines/calories excellent pour la perte de poids.")),
                ("Poisson vapeur & légumes", "Bar cuit à la vapeur, gingembre, oignons verts et légumes croquants.", 5000, 25, False, "poisson-vapeur-legumes",
                 (True, 390, 38, 18, 16, 5, "vapeur, oméga-3, pauvre en glucides", "Cuisson vapeur : léger, digeste et riche en oméga-3.")),
                ("Pepper soup maison", "Bouillon épicé au pèbè et au poivre de Penja, viande de chèvre maigre, pain à part.", 3000, 25, False, "pepper-soup-maison",
                 (True, 320, 32, 14, 14, 3, "bouillon, épicé, pauvre en glucides", "Réconfortant et léger ; laissez le pain de côté pour un repas low-carb.")),
            ],
            "Salades": [
                ("Salade avocat & crevettes", "Crevettes décortiquées, avocat, laitue, tomates cerises, vinaigrette citron.", 4500, 12, True, "salade-avocat-crevettes",
                 (True, 420, 28, 16, 26, 9, "pauvre en glucides, bons gras, fibres", "Bons lipides de l'avocat + protéines maigres des crevettes.")),
                ("Salade haricots rouges & maïs", "Haricots rouges, maïs, poivrons jaunes, feta et cumin toasté.", 3000, 10, False, "salade-haricots-rouges-mais",
                 (True, 390, 18, 50, 12, 14, "végétarien, fibres, protéines végétales", "Record de fibres : parfait pour la digestion et la satiété.")),
                ("Omelette blancs d'œufs & épinards", "Omelette de blancs d'œufs aux épinards, mesclun, pain complet grillé.", 2500, 12, False, "omelette-blancs-doeufs-legumes",
                 (True, 290, 30, 18, 10, 4, "protéiné, végétarien, petit-déjeuner", "Petit-déjeuner protéiné et léger pour bien démarrer.")),
            ],
            "Jus & fruits": [
                ("Smoothie vert détox", "Épinards, banane, ananas, gingembre et citron vert. Sans sucre ajouté.", 1800, 5, False, "smoothie-vert-detox",
                 (True, 210, 4, 46, 2, 6, "végétarien, sans sucre ajouté, vitamines", "Sucres naturels des fruits uniquement, riche en vitamine C.")),
                ("Salade de fruits frais", "Ananas, papaye, mangue, fraises et raisins du marché.", 1500, 5, False, "salade-de-fruits-frais",
                 (True, 180, 2, 42, 1, 5, "végétarien, vitamines, dessert léger", "Le dessert le plus léger de Douala.")),
            ],
        },
    },
]

# Livreurs de test cites dans le cahier des charges (section 8.2).
DRIVERS = [
    ("Emmanuel", "T.", "Bonanjo", "moto"),
    ("Narcisse", "K.", "Akwa", "moto"),
    ("Brice", "M.", "Bonapriso", "bike"),
]
