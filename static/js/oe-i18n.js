/* ONE EAT — bilingue FR / EN.
   Langue détectée depuis la langue de l'appareil (navigator.languages).
   Choix manuel possible via [data-lang-toggle] (mémorisé dans localStorage). */
(function () {
  "use strict";

  var DICT = {
    deliver_to: { fr: "Livraison à", en: "Delivery to" },
    city_default: { fr: "Douala, Cameroun", en: "Douala, Cameroon" },
    locate: { fr: "Me localiser", en: "Locate me" },
    locating: { fr: "Localisation…", en: "Locating…" },
    loc_denied: { fr: "Localisation refusée ou indisponible", en: "Location denied or unavailable" },
    loc_outside: { fr: "Hors zone : ONE EAT livre au Cameroun", en: "Outside zone: ONE EAT delivers in Cameroon" },
    loc_unknown: { fr: "Position trouvée, quartier inconnu", en: "Position found, quarter unknown" },
    search_placeholder: { fr: "Pizza, poulet braisé, ndolé...", en: "Pizza, grilled chicken, ndolé..." },
    search_label: { fr: "Rechercher", en: "Search" },
    "cat_tous": { fr: "Tous", en: "All" },
    "cat_local": { fr: "Local", en: "Local" },
    "cat_fast-food": { fr: "Fastfood", en: "Fastfood" },
    "cat_restaurant-camerounais": { fr: "Local", en: "Local" },
    "cat_restaurant-italien": { fr: "Italien", en: "Italian" },
    "cat_dietetique": { fr: "Diététique", en: "Diet" },
    "cat_grillades": { fr: "Grillades", en: "Grills" },
    "cat_boissons": { fr: "Boissons", en: "Drinks" },
    "cat_cafe": { fr: "Café", en: "Coffee" },
    "cat_healthy": { fr: "Healthy", en: "Healthy" },
    "cat_snacks": { fr: "Snacks", en: "Snacks" },
    featured: { fr: "À la une", en: "Featured" },
    top_restaurants: { fr: "Top Restaurants dans la ville", en: "Top Restaurants in town" },
    see_more: { fr: "Voir plus", en: "See more" },
    all_restaurants: { fr: "Tous les restaurants", en: "All restaurants" },
    in_your_area: { fr: "Dans votre quartier", en: "In your area" },
    diet_eyebrow: { fr: "Nouveau · Espace diététique", en: "New · Diet space" },
    diet_title: { fr: "Manger léger à Douala", en: "Eat light in Douala" },
    diet_sub: { fr: "plats avec calories & macros · filtrez par objectif", en: "dishes with calories & macros · filter by goal" },
    showcase_title: { fr: "Promos du moment", en: "Deals of the moment" },
    showcase_tag: { fr: "Juteux, croustillant, à commander maintenant", en: "Juicy, crispy, order now" },
    order_now: { fr: "Commander", en: "Order" },
    sound_on: { fr: "Son activé", en: "Sound on" },
    sound_off: { fr: "Son coupé", en: "Sound off" },
    nav_home: { fr: "Accueil", en: "Home" },
    nav_explore: { fr: "Explorer", en: "Explore" },
    nav_diet: { fr: "Diète", en: "Diet" },
    nav_orders: { fr: "Commandes", en: "Orders" },
    nav_profile: { fr: "Profil", en: "Profile" },
    cart_view: { fr: "Voir le panier", en: "View cart" }
  };

  function detect() {
    try {
      var saved = localStorage.getItem("oeLang");
      if (saved === "fr" || saved === "en") return saved;
    } catch (e) {}
    var list = (navigator.languages && navigator.languages.length)
      ? navigator.languages : [navigator.language || "fr"];
    for (var i = 0; i < list.length; i++) {
      var code = String(list[i]).slice(0, 2).toLowerCase();
      if (code === "fr" || code === "en") return code;
    }
    return "en";
  }

  var lang = detect();

  function t(key) {
    var entry = DICT[key];
    return entry ? (entry[lang] || entry.fr) : null;
  }

  function apply() {
    document.documentElement.lang = lang;
    document.querySelectorAll("[data-i18n]").forEach(function (el) {
      if (el.hasAttribute("data-loc-set")) return;
      var value = t(el.getAttribute("data-i18n"));
      if (value !== null) el.textContent = value;
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach(function (el) {
      var value = t(el.getAttribute("data-i18n-placeholder"));
      if (value !== null) el.setAttribute("placeholder", value);
    });
    document.querySelectorAll("[data-i18n-aria]").forEach(function (el) {
      var value = t(el.getAttribute("data-i18n-aria"));
      if (value !== null) el.setAttribute("aria-label", value);
    });
    document.querySelectorAll("[data-lang-toggle]").forEach(function (btn) {
      btn.textContent = lang === "fr" ? "EN" : "FR";
      btn.setAttribute("aria-label", lang === "fr" ? "Switch to English" : "Passer en français");
    });
    window.dispatchEvent(new CustomEvent("oe:lang", { detail: lang }));
  }

  window.OE = window.OE || {};
  window.OE.lang = function () { return lang; };
  window.OE.t = t;
  window.OE.applyI18n = apply;
  window.OE.setLang = function (next) {
    lang = next === "en" ? "en" : "fr";
    try { localStorage.setItem("oeLang", lang); } catch (e) {}
    apply();
  };

  document.addEventListener("click", function (e) {
    if (e.target.closest("[data-lang-toggle]")) window.OE.setLang(lang === "fr" ? "en" : "fr");
  });

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", apply);
  else apply();
})();
