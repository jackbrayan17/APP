/* ONE EAT — parcours guidés (coach marks) par page et par rôle.
   - Langue : choix manuel (localStorage oeLang) sinon langue de l'appareil. FR / EN / ES.
   - Rôle : attribut data-oe-role sur <body> (guest, client, restaurant, driver, influencer, admin).
   - Un parcours se lance une seule fois par page et par rôle (localStorage), puis via le bouton « ? ».
   - Étapes sans élément visible ignorées : un parcours ne casse jamais la page. */
(function () {
  "use strict";

  var BRAND = "#FF6B1A";
  var LOCALES = ["fr", "en", "es"];

  function locale() {
    var saved = null;
    try { saved = localStorage.getItem("oeLang"); } catch (e) {}
    if (saved === "fr" || saved === "en" || saved === "es") return saved;
    var list = (navigator.languages && navigator.languages.length)
      ? navigator.languages : [navigator.language || "fr"];
    for (var i = 0; i < list.length; i++) {
      var code = String(list[i] || "").slice(0, 2).toLowerCase();
      if (LOCALES.indexOf(code) > -1) return code;
    }
    return "fr";
  }

  var LANG = locale();
  function t(map) { return (map && (map[LANG] || map.fr)) || ""; }

  // Route -> parcours. Le premier motif qui correspond gagne.
  var ROUTES = [
    [/^\/$/, "home"],
    [/^\/restaurant\/[^/]+\/?$/, "restaurant"],
    [/^\/plat\/\d+\/?$/, "dish"],
    [/^\/panier\/?$/, "cart"],
    [/^\/commandes\/?$/, "orders"],
    [/^\/commande\/[^/]+\/?$/, "order"],
    [/^\/explorer\/?$/, "explore"],
    [/^\/favoris\/?$/, "favorites"],
    [/^\/dietetique\/?$/, "diet"],
    [/^\/profil\/?$/, "profile"],
    [/^\/resto\/?$/, "resto_home"],
    [/^\/resto\/menu\/?$/, "resto_menu"],
    [/^\/resto\/commandes\/?$/, "resto_orders"],
    [/^\/resto\/personnaliser\/?$/, "resto_customize"],
    [/^\/resto\/promos\/?$/, "resto_promos"],
    [/^\/resto\/livreurs\/?$/, "resto_drivers"],
    [/^\/livreur\/?$/, "driver"],
    [/^\/influenceur\/?$/, "influencer"],
    [/^\/tableau-admin\/?$/, "admin"],
    [/^\/tableau-admin\/codes\/?$/, "admin_codes"]
  ];

  // Etapes : sel = selecteur CSS, t = titre (2-4 mots), b = description (1-2 phrases)
  var TOURS = {
    home: [
      { sel: "input[name=q]", t: { fr: "Trouvez votre plat", en: "Find your dish", es: "Encuentra tu plato" },
        b: { fr: "Cherchez un plat, un restaurant ou une envie. Les résultats s'affichent tout de suite.",
             en: "Search a dish, a restaurant or a craving. Results appear instantly.",
             es: "Busca un plato, un restaurante o un antojo. Los resultados aparecen al instante." } },
      { sel: "#home-categories", t: { fr: "Filtrez par secteur", en: "Filter by sector", es: "Filtra por sector" },
        b: { fr: "Choisissez un type de cuisine : camerounaise, italienne, grillades ou fast food.",
             en: "Pick a cuisine type: Cameroonian, Italian, grills or fast food.",
             es: "Elige un tipo de cocina: camerunesa, italiana, parrillas o comida rápida." } },
      { sel: "#oe-loc-label", t: { fr: "Votre adresse", en: "Your address", es: "Tu dirección" },
        b: { fr: "Votre zone de livraison s'affiche ici pour voir les restaurants qui vous servent.",
             en: "Your delivery area is shown here so you see the restaurants that serve you.",
             es: "Tu zona de entrega aparece aquí para ver los restaurantes que te atienden." } },
      { sel: "#all-restaurants", t: { fr: "Comparez et commandez", en: "Compare and order", es: "Compara y pide" },
        b: { fr: "Notes, délais et frais de livraison vous aident à choisir en quelques secondes.",
             en: "Ratings, delivery times and fees help you choose in seconds.",
             es: "Valoraciones, tiempos y tarifas te ayudan a elegir en segundos." } },
      { sel: "[aria-label='Navigation principale']", t: { fr: "Tout est à portée", en: "Everything within reach", es: "Todo al alcance" },
        b: { fr: "Accueil, explorer, diète, commandes et profil restent accessibles en bas de l'écran.",
             en: "Home, explore, diet, orders and profile stay one tap away at the bottom.",
             es: "Inicio, explorar, dieta, pedidos y perfil siempre accesibles abajo." } }
    ],
    restaurant: [
      { sel: "[data-add-cart]", t: { fr: "Ajoutez au panier", en: "Add to cart", es: "Añade al carrito" },
        b: { fr: "Touchez + sur un plat. Votre panier se met à jour immédiatement.",
             en: "Tap + on a dish. Your cart updates straight away.",
             es: "Toca + en un plato. Tu carrito se actualiza al momento." } },
      { sel: "[data-share-title]", t: { fr: "Partagez ce restaurant", en: "Share this restaurant", es: "Comparte este restaurante" },
        b: { fr: "Envoyez la fiche à vos proches par WhatsApp ou par lien.",
             en: "Send the page to friends via WhatsApp or a link.",
             es: "Envía la ficha a tus contactos por WhatsApp o enlace." } },
      { sel: "#cart-fab", t: { fr: "Voir votre panier", en: "View your cart", es: "Ver tu carrito" },
        b: { fr: "Ce bouton récapitule vos plats et mène directement au paiement.",
             en: "This button sums up your dishes and leads straight to checkout.",
             es: "Este botón resume tus platos y lleva directo al pago." } }
    ],
    dish: [
      { sel: "#options", t: { fr: "Personnalisez le plat", en: "Customise the dish", es: "Personaliza el plato" },
        b: { fr: "Choisissez vos options avant d'ajouter le plat à votre panier.",
             en: "Choose your options before adding the dish to your cart.",
             es: "Elige tus opciones antes de añadir el plato al carrito." } },
      { sel: "#nutri-title", t: { fr: "Repères nutrition", en: "Nutrition facts", es: "Datos nutricionales" },
        b: { fr: "Calories et macronutriments estimés par portion, pour mieux choisir.",
             en: "Estimated calories and macros per serving, to help you choose.",
             es: "Calorías y macronutrientes estimados por ración para elegir mejor." } },
      { sel: "[data-add-cart]", t: { fr: "Ajoutez en un geste", en: "Add in one tap", es: "Añade con un toque" },
        b: { fr: "Une touche suffit. Ajustez la quantité dans le panier.",
             en: "One tap is enough. Adjust the quantity in your cart.",
             es: "Basta un toque. Ajusta la cantidad en el carrito." } }
    ],
    cart: [
      { sel: "[name=payment_method]", t: { fr: "Choisissez le paiement", en: "Pick a payment", es: "Elige el pago" },
        b: { fr: "Espèces à la livraison ou Mobile Money : le choix se fait ici.",
             en: "Cash on delivery or Mobile Money: choose here.",
             es: "Efectivo al recibir o Mobile Money: elige aquí." } },
      { sel: "[name=promo_code]", t: { fr: "Un code promo ?", en: "Have a promo code?", es: "¿Tienes un código?" },
        b: { fr: "Saisissez le code de votre influenceur préféré pour obtenir la remise.",
             en: "Enter your favourite influencer's code to get the discount.",
             es: "Introduce el código de tu influencer favorito para obtener el descuento." } },
      { sel: "#checkout-form", t: { fr: "Confirmez la commande", en: "Confirm the order", es: "Confirma el pedido" },
        b: { fr: "Adresse, paiement et total sont regroupés ici avant de valider.",
             en: "Address, payment and total are grouped here before you confirm.",
             es: "Dirección, pago y total están juntos aquí antes de confirmar." } }
    ],
    orders: [
      { sel: "a[href*='/commande/']", t: { fr: "Suivez vos commandes", en: "Track your orders", es: "Sigue tus pedidos" },
        b: { fr: "Touchez une commande pour voir son statut en direct.",
             en: "Tap an order to see its live status.",
             es: "Toca un pedido para ver su estado en vivo." } },
      { sel: "[aria-label='Navigation principale']", t: { fr: "Recommandez en un tap", en: "Reorder in one tap", es: "Repite en un toque" },
        b: { fr: "Dans une commande passée, « Commander à nouveau » remet les plats dans le panier.",
             en: "On a past order, « Order again » puts the dishes back in your cart.",
             es: "En un pedido anterior, « Pedir de nuevo » vuelve a poner los platos en el carrito." } }
    ],
    order: [
      { sel: "#status-text", t: { fr: "Suivi en direct", en: "Live tracking", es: "Seguimiento en vivo" },
        b: { fr: "Le statut se met à jour seul, sans recharger la page.",
             en: "The status updates on its own, without reloading.",
             es: "El estado se actualiza solo, sin recargar la página." } },
      { sel: "a[href*='/valider/']", t: { fr: "Validez la livraison", en: "Confirm delivery", es: "Confirma la entrega" },
        b: { fr: "Quand le livreur arrive, donnez-lui votre code ou scannez son QR code.",
             en: "When the driver arrives, give them your code or scan their QR code.",
             es: "Cuando llegue el repartidor, dale tu código o escanea su QR." } },
      { sel: "form[action*='/annuler/'] button", t: { fr: "Abandonner si besoin", en: "Cancel if needed", es: "Cancela si hace falta" },
        b: { fr: "Vous pouvez abandonner la commande tant que le livreur ne l'a pas récupérée.",
             en: "You can cancel the order until the driver has picked it up.",
             es: "Puedes cancelar el pedido mientras el repartidor no lo haya recogido." } }
    ],
    explore: [
      { sel: "input[name=q]", t: { fr: "Cherchez partout", en: "Search everywhere", es: "Busca en todas partes" },
        b: { fr: "Recherchez un plat, un restaurant ou un ingrédient dans toute la ville.",
             en: "Search a dish, a restaurant or an ingredient across the city.",
             es: "Busca un plato, un restaurante o un ingrediente en toda la ciudad." } },
      { sel: "select[name=hood], a[href*='hood=']", t: { fr: "Filtrez par quartier", en: "Filter by area", es: "Filtra por barrio" },
        b: { fr: "Limitez les résultats au quartier où vous souhaitez être livré.",
             en: "Limit results to the area where you want delivery.",
             es: "Limita los resultados al barrio donde quieres recibir el pedido." } }
    ],
    favorites: [
      { sel: "a[href^='/restaurant/']", t: { fr: "Vos favoris", en: "Your favourites", es: "Tus favoritos" },
        b: { fr: "Retrouvez ici les restaurants que vous aimez. Touchez ♥ pour en retirer un.",
             en: "Find the restaurants you love here. Tap ♥ to remove one.",
             es: "Aquí están los restaurantes que te gustan. Toca ♥ para quitar uno." } },
      { sel: "[aria-label='Navigation principale']", t: { fr: "Commandez en un instant", en: "Order in a moment", es: "Pide en un momento" },
        b: { fr: "Ouvrez un favori puis ajoutez vos plats : le parcours reste court.",
             en: "Open a favourite and add your dishes: the path stays short.",
             es: "Abre un favorito y añade tus platos: el recorrido es corto." } }
    ],
    diet: [
      { sel: "#tri", t: { fr: "Triez selon vos besoins", en: "Sort by your needs", es: "Ordena según tus necesidades" },
        b: { fr: "Classez les plats par calories, protéines ou fibres.",
             en: "Sort dishes by calories, protein or fibre.",
             es: "Ordena los platos por calorías, proteínas o fibra." } },
      { sel: "select[name=objectif], a[href*='objectif=']", t: { fr: "Choisissez un objectif", en: "Pick a goal", es: "Elige un objetivo" },
        b: { fr: "Léger, protéiné, végétarien : chaque filtre répond à un besoin précis.",
             en: "Light, high-protein, vegetarian: each filter answers a specific need.",
             es: "Ligero, rico en proteínas, vegetariano: cada filtro responde a una necesidad." } }
    ],
    profile: [
      { sel: "form", t: { fr: "Vos informations", en: "Your details", es: "Tus datos" },
        b: { fr: "Gardez votre nom, votre téléphone et votre adresse à jour pour des livraisons fluides.",
             en: "Keep your name, phone and address up to date for smooth deliveries.",
             es: "Mantén tu nombre, teléfono y dirección al día para entregas sin problemas." } }
    ],
    resto_home: [
      { sel: "header form button", t: { fr: "Ouvert ou fermé", en: "Open or closed", es: "Abierto o cerrado" },
        b: { fr: "Un tap suspend les commandes en cas de fermeture exceptionnelle.",
             en: "One tap pauses orders during an unexpected closure.",
             es: "Un toque pausa los pedidos si cierras de forma excepcional." } },
      { sel: "a[href*='/resto/commandes/']", t: { fr: "Commandes en direct", en: "Live orders", es: "Pedidos en vivo" },
        b: { fr: "Les nouvelles commandes arrivent ici, avec une alerte sonore.",
             en: "New orders arrive here with a sound alert.",
             es: "Los nuevos pedidos llegan aquí con una alerta sonora." } },
      { sel: "main", t: { fr: "Vos chiffres du jour", en: "Today's numbers", es: "Tus cifras de hoy" },
        b: { fr: "Chiffre d'affaires et commandes sur 1, 7 et 30 jours.",
             en: "Revenue and orders over 1, 7 and 30 days.",
             es: "Ingresos y pedidos de 1, 7 y 30 días." } }
    ],
    resto_menu: [
      { sel: "main button.bg-brand", t: { fr: "Ajoutez un plat", en: "Add a dish", es: "Añade un plato" },
        b: { fr: "Nom, prix, photo et valeurs nutritionnelles se règlent dans cette fiche.",
             en: "Name, price, photo and nutrition values are set in this form.",
             es: "Nombre, precio, foto y valores nutricionales se ajustan en esta ficha." } },
      { sel: "main h2", t: { fr: "Organisez votre menu", en: "Organise your menu", es: "Organiza tu menú" },
        b: { fr: "Rangez les plats par section ; les catégories suivent le secteur de votre restaurant.",
             en: "Group dishes into sections; categories follow your restaurant's sector.",
             es: "Agrupa los platos en secciones; las categorías siguen el sector de tu restaurante." } }
    ],
    resto_orders: [
      { sel: "a[href*='tab=']", t: { fr: "Suivez chaque étape", en: "Follow each step", es: "Sigue cada etapa" },
        b: { fr: "Nouvelles, en cuisine, prêtes, en livraison : changez d'onglet pour piloter.",
             en: "New, in kitchen, ready, out for delivery: switch tabs to manage.",
             es: "Nuevos, en cocina, listos, en reparto: cambia de pestaña para gestionar." } },
      { sel: "main button[class*='bg-brand']", t: { fr: "Acceptez vite", en: "Accept fast", es: "Acepta rápido" },
        b: { fr: "Acceptez, lancez la cuisine, puis marquez la commande prête : le livreur est prévenu.",
             en: "Accept, start cooking, then mark the order ready: the driver is alerted.",
             es: "Acepta, empieza a cocinar y marca el pedido listo: el repartidor recibe aviso." } }
    ],
    resto_customize: [
      { sel: "#f-tagline", t: { fr: "Votre identité", en: "Your identity", es: "Tu identidad" },
        b: { fr: "Le slogan et la bio apparaissent sur votre page client.",
             en: "The tagline and bio appear on your customer page.",
             es: "El eslogan y la bio aparecen en tu página de cliente." } },
      { sel: "#f-sector", t: { fr: "Votre secteur", en: "Your sector", es: "Tu sector" },
        b: { fr: "Il détermine les catégories proposées pour classer vos plats.",
             en: "It determines the categories offered to sort your dishes.",
             es: "Determina las categorías disponibles para clasificar tus platos." } },
      { sel: "#f-max", t: { fr: "Limite journalière", en: "Daily limit", es: "Límite diario" },
        b: { fr: "Fixez le nombre maximum de commandes par jour. 0 signifie illimité.",
             en: "Set the maximum orders per day. 0 means unlimited.",
             es: "Define el máximo de pedidos al día. 0 significa ilimitado." } }
    ],
    resto_promos: [
      { sel: "main form", t: { fr: "Lancez une promo", en: "Launch a promo", es: "Lanza una promo" },
        b: { fr: "Choisissez les plats concernés, ou cochez « tous les plats » pour tout le menu.",
             en: "Pick the dishes, or tick « all dishes » for the whole menu.",
             es: "Elige los platos, o marca « todos los platos » para todo el menú." } },
      { sel: "form[action*='/resto/codes/']", t: { fr: "Codes influenceurs", en: "Influencer codes", es: "Códigos de influencers" },
        b: { fr: "Votre code part en validation chez ONE EAT avant d'être mis en ligne.",
             en: "Your code goes to ONE EAT for review before going live.",
             es: "Tu código se envía a ONE EAT para revisión antes de publicarse." } }
    ],
    resto_drivers: [
      { sel: "main", t: { fr: "Vos livreurs", en: "Your drivers", es: "Tus repartidores" },
        b: { fr: "ONE EAT affecte les livreurs à vos commandes. Contactez l'équipe pour toute modification.",
             en: "ONE EAT assigns drivers to your orders. Contact the team for any change.",
             es: "ONE EAT asigna los repartidores a tus pedidos. Contacta al equipo para cambios." } }
    ],
    driver: [
      { sel: "#availBtn", t: { fr: "Passez en ligne", en: "Go online", es: "Conéctate" },
        b: { fr: "Activez « Disponible » pour recevoir des missions autour de vous.",
             en: "Turn on « Available » to receive missions near you.",
             es: "Activa « Disponible » para recibir misiones cerca de ti." } },
      { sel: "#map", t: { fr: "Votre zone", en: "Your zone", es: "Tu zona" },
        b: { fr: "La carte affiche les restaurants et les missions proches de votre position.",
             en: "The map shows restaurants and missions near your position.",
             es: "El mapa muestra los restaurantes y misiones cerca de tu posición." } },
      { sel: "img[alt^='QR code']", t: { fr: "Faites scanner le QR", en: "Let them scan the QR", es: "Deja que escaneen el QR" },
        b: { fr: "À l'arrivée, le client scanne ce code ou saisit son code à 4 chiffres.",
             en: "On arrival, the customer scans this code or enters their 4-digit code.",
             es: "Al llegar, el cliente escanea este código o escribe su código de 4 cifras." } }
    ],
    influencer: [
      { sel: ".bg-brand", t: { fr: "Votre note de portée", en: "Your reach score", es: "Tu puntuación de alcance" },
        b: { fr: "Elle progresse avec les utilisations de vos codes et le chiffre d'affaires généré.",
             en: "It grows with uses of your codes and the revenue they generate.",
             es: "Sube con los usos de tus códigos y los ingresos que generan." } },
      { sel: "h2", t: { fr: "Vos codes", en: "Your codes", es: "Tus códigos" },
        b: { fr: "Les restaurants créent vos codes ; ONE EAT les valide avant mise en ligne.",
             en: "Restaurants create your codes; ONE EAT validates them before they go live.",
             es: "Los restaurantes crean tus códigos; ONE EAT los valida antes de publicarlos." } }
    ],
    admin: [
      { sel: "#overview", t: { fr: "Vue d'ensemble", en: "Overview", es: "Resumen" },
        b: { fr: "Les indicateurs clés de la période. Changez-la en haut de page.",
             en: "Key figures for the period. Change it at the top of the page.",
             es: "Indicadores clave del periodo. Cámbialo en la parte superior." } },
      { sel: "#quality", t: { fr: "Abandon et avis", en: "Abandon & reviews", es: "Abandono y reseñas" },
        b: { fr: "Suivez les commandes abandonnées par les clients et la satisfaction.",
             en: "Track customer cancellations and satisfaction.",
             es: "Sigue las cancelaciones de clientes y la satisfacción." } },
      { sel: "#insights", t: { fr: "Points d'attention", en: "Points to watch", es: "Puntos de atención" },
        b: { fr: "Alertes sur les commandes actives, le CA et les modes de paiement.",
             en: "Alerts on active orders, revenue and payment methods.",
             es: "Alertas sobre pedidos activos, ingresos y métodos de pago." } },
      { sel: "#ranking", t: { fr: "Classement par avis", en: "Ranking by reviews", es: "Ranking por reseñas" },
        b: { fr: "Les restaurants classés par note, puis par nombre d'avis.",
             en: "Restaurants ranked by rating, then by number of reviews.",
             es: "Restaurantes ordenados por valoración y luego por número de reseñas." } }
    ],
    admin_codes: [
      { sel: ".tabs", t: { fr: "Filtrez les codes", en: "Filter the codes", es: "Filtra los códigos" },
        b: { fr: "Commencez par « En attente » : ce sont les codes à valider.",
             en: "Start with « Pending »: these codes need your approval.",
             es: "Empieza por « Pendientes »: estos códigos necesitan tu aprobación." } },
      { sel: ".card", t: { fr: "Validez ou refusez", en: "Approve or reject", es: "Aprueba o rechaza" },
        b: { fr: "Validez pour mettre en ligne, ou refusez avec un motif clair.",
             en: "Approve to publish, or reject with a clear reason.",
             es: "Aprueba para publicar, o rechaza indicando un motivo claro." } }
    ]
  };

  var UI = {
    next: { fr: "Suivant", en: "Next", es: "Siguiente" },
    back: { fr: "Retour", en: "Back", es: "Atrás" },
    done: { fr: "Terminer", en: "Done", es: "Listo" },
    skip: { fr: "Passer", en: "Skip", es: "Omitir" },
    help: { fr: "Revoir le guide", en: "Replay the guide", es: "Repetir la guía" }
  };

  var STYLE = [
    ".oet-hl{position:fixed;z-index:9998;border:3px solid " + BRAND + ";border-radius:16px;pointer-events:none;",
    "box-shadow:0 0 0 9999px rgba(17,24,39,.6);transition:all .25s ease}",
    ".oet-dim{position:fixed;inset:0;z-index:9998;background:rgba(17,24,39,.6)}",
    ".oet-card{position:fixed;z-index:9999;width:min(340px,calc(100vw - 32px));background:#fff;color:#111827;",
    "border-radius:20px;box-shadow:0 20px 50px rgba(0,0,0,.25);padding:18px 18px 14px;",
    "font-family:Inter,ui-sans-serif,system-ui,-apple-system,'Segoe UI',sans-serif;box-sizing:border-box}",
    ".oet-title{font-size:17px;font-weight:800;margin:0 0 6px;line-height:1.25;color:#111827}",
    ".oet-body{font-size:14px;line-height:1.5;color:#4b5563;margin:0}",
    ".oet-dots{display:flex;gap:5px;margin:14px 0 12px}",
    ".oet-dot{height:6px;width:6px;border-radius:999px;background:#e5e7eb;transition:all .2s}",
    ".oet-dot.on{width:18px;background:" + BRAND + "}",
    ".oet-row{display:flex;align-items:center;justify-content:space-between;gap:8px}",
    ".oet-btn{border:0;border-radius:12px;padding:10px 16px;font:inherit;font-size:14px;font-weight:700;cursor:pointer}",
    ".oet-primary{background:" + BRAND + ";color:#fff;box-shadow:0 6px 16px rgba(255,107,26,.35)}",
    ".oet-ghost{background:#FFF1E8;color:#D94807}",
    ".oet-skip{background:none;color:#6b7280;padding:10px 4px;font-size:13px}",
    ".oet-help{position:fixed;right:16px;bottom:calc(88px + env(safe-area-inset-bottom));z-index:9000;",
    "width:44px;height:44px;border-radius:999px;border:0;background:" + BRAND + ";color:#fff;font-size:20px;font-weight:800;",
    "box-shadow:0 8px 20px rgba(255,107,26,.4);cursor:pointer}",
    ".oet-help.dash{bottom:20px}",
    "@media (prefers-reduced-motion: reduce){.oet-hl{transition:none}}"
  ].join("");

  var state = { key: null, steps: [], index: 0, hl: null, dim: null, card: null, onKey: null, onMove: null };

  function injectStyle() {
    if (document.getElementById("oet-style")) return;
    var s = document.createElement("style");
    s.id = "oet-style";
    s.textContent = STYLE;
    document.head.appendChild(s);
  }

  function role() {
    return (document.body && document.body.getAttribute("data-oe-role")) || "guest";
  }

  function routeKey() {
    var path = location.pathname;
    for (var i = 0; i < ROUTES.length; i++) {
      if (ROUTES[i][0].test(path)) return ROUTES[i][1];
    }
    return null;
  }

  function visibleTarget(sel) {
    var list = document.querySelectorAll(sel);
    for (var i = 0; i < list.length; i++) {
      var r = list[i].getBoundingClientRect();
      if (r.width > 0 && r.height > 0) return list[i];
    }
    return null;
  }

  function usableSteps(key) {
    return (TOURS[key] || []).filter(function (s) { return !!visibleTarget(s.sel); });
  }

  function seenKey(key) { return "oe_tour_seen_v1:" + role() + ":" + key; }
  function isSeen(key) {
    try { return localStorage.getItem(seenKey(key)) === "1"; } catch (e) { return false; }
  }
  function markSeen(key) {
    try { localStorage.setItem(seenKey(key), "1"); } catch (e) {}
  }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function cleanup() {
    [state.hl, state.dim, state.card].forEach(function (n) { if (n && n.parentNode) n.parentNode.removeChild(n); });
    window.removeEventListener("keydown", state.onKey);
    window.removeEventListener("resize", state.onMove);
    window.removeEventListener("scroll", state.onMove, true);
    state.hl = state.dim = state.card = null;
    state.key = null;
  }

  function finish(markAsSeen) {
    if (markAsSeen && state.key) markSeen(state.key);
    cleanup();
  }

  function place() {
    if (!state.card) return;
    var step = state.steps[state.index];
    var target = step && visibleTarget(step.sel);
    var card = state.card;
    var vw = window.innerWidth, vh = window.innerHeight;
    if (!target) {
      state.hl.style.display = "none";
      state.dim.style.display = "block";
      card.style.left = "50%";
      card.style.top = "50%";
      card.style.transform = "translate(-50%,-50%)";
      return;
    }
    state.dim.style.display = "none";
    state.hl.style.display = "block";
    var r = target.getBoundingClientRect();
    state.hl.style.left = (r.left - 6) + "px";
    state.hl.style.top = (r.top - 6) + "px";
    state.hl.style.width = (r.width + 12) + "px";
    state.hl.style.height = (r.height + 12) + "px";
    card.style.transform = "none";
    var ch = card.offsetHeight, cw = card.offsetWidth;
    var top = r.bottom + 16;
    if (top + ch > vh - 16) top = r.top - ch - 16;
    if (top < 16) top = Math.max(16, Math.min(vh - ch - 16, vh / 2 - ch / 2));
    var left = Math.min(Math.max(16, r.left + r.width / 2 - cw / 2), vw - cw - 16);
    card.style.top = top + "px";
    card.style.left = left + "px";
  }

  function render() {
    var step = state.steps[state.index];
    var card = state.card;
    card.innerHTML = "";
    var total = state.steps.length;
    var last = state.index === total - 1;

    card.appendChild(el("h2", "oet-title", t(step.t)));
    card.appendChild(el("p", "oet-body", t(step.b)));

    var dots = el("div", "oet-dots");
    dots.setAttribute("aria-hidden", "true");
    for (var i = 0; i < total; i++) dots.appendChild(el("span", "oet-dot" + (i === state.index ? " on" : "")));
    card.appendChild(dots);

    var row = el("div", "oet-row");
    var skip = el("button", "oet-btn oet-skip", t(UI.skip));
    skip.type = "button";
    skip.addEventListener("click", function () { finish(true); });
    row.appendChild(skip);

    var right = el("div", "oet-row");
    if (state.index > 0) {
      var back = el("button", "oet-btn oet-ghost", t(UI.back));
      back.type = "button";
      back.addEventListener("click", function () { go(-1); });
      right.appendChild(back);
    }
    var next = el("button", "oet-btn oet-primary", t(last ? UI.done : UI.next));
    next.type = "button";
    next.addEventListener("click", function () { if (last) finish(true); else go(1); });
    right.appendChild(next);
    row.appendChild(right);
    card.appendChild(row);
    card.setAttribute("aria-label", (state.index + 1) + " / " + total);

    var target = visibleTarget(step.sel);
    if (target) target.scrollIntoView({ block: "center", behavior: "smooth" });
    setTimeout(place, 320);
    setTimeout(function () { next.focus(); }, 60);
  }

  function go(delta) {
    state.index = Math.max(0, Math.min(state.steps.length - 1, state.index + delta));
    render();
  }

  function start(key, force) {
    if (!TOURS[key]) return false;
    if (state.key) cleanup();
    if (!force && isSeen(key)) return false;
    var steps = usableSteps(key);
    if (!steps.length) return false;
    injectStyle();
    state.key = key;
    state.steps = steps;
    state.index = 0;
    state.hl = el("div", "oet-hl");
    state.hl.style.display = "none";
    state.dim = el("div", "oet-dim");
    state.dim.style.display = "none";
    state.card = el("div", "oet-card");
    state.card.setAttribute("role", "dialog");
    state.card.setAttribute("aria-modal", "true");
    document.body.appendChild(state.dim);
    document.body.appendChild(state.hl);
    document.body.appendChild(state.card);
    state.onKey = function (e) {
      if (e.key === "Escape") finish(true);
      else if (e.key === "ArrowRight") go(1);
      else if (e.key === "ArrowLeft") go(-1);
    };
    state.onMove = function () { place(); };
    window.addEventListener("keydown", state.onKey);
    window.addEventListener("resize", state.onMove);
    window.addEventListener("scroll", state.onMove, true);
    render();
    return true;
  }

  function addHelpButton(key) {
    if (document.getElementById("oet-help")) return;
    var b = el("button", "oet-help", "?");
    b.id = "oet-help";
    b.type = "button";
    b.setAttribute("aria-label", t(UI.help));
    b.title = t(UI.help);
    if (/^\/(resto|livreur|influenceur|tableau-admin)/.test(location.pathname)) b.classList.add("dash");
    b.addEventListener("click", function () { start(key, true); });
    document.body.appendChild(b);
  }

  function init() {
    var key = routeKey();
    if (!key || !TOURS[key] || !usableSteps(key).length) return;
    addHelpButton(key);
    if (!isSeen(key)) setTimeout(function () { start(key, false); }, 900);
  }

  window.OETour = {
    start: function (key) { return start(key, true); },
    locale: LANG
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
