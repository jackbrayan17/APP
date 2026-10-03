/* ONE EAT — animations, sons (synthétisés, sans fichiers), diaporama et géolocalisation. */
(function () {
  "use strict";

  window.OE = window.OE || {};
  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---------- Sons (Web Audio) ----------
  var ctx = null;
  var soundOn = true;
  try { soundOn = localStorage.getItem("oeSound") !== "off"; } catch (e) {}

  function audio() {
    if (!ctx) {
      var AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return null;
      ctx = new AC();
    }
    if (ctx.state === "suspended") ctx.resume();
    return ctx;
  }

  function tone(a, f, t0, dur, type, toFreq, vol) {
    var o = a.createOscillator();
    var g = a.createGain();
    o.type = type || "sine";
    o.frequency.setValueAtTime(f, t0);
    if (toFreq) o.frequency.exponentialRampToValueAtTime(toFreq, t0 + dur);
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(vol || 0.22, t0 + 0.01);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    o.connect(g);
    g.connect(a.destination);
    o.start(t0);
    o.stop(t0 + dur + 0.05);
  }

  function crack(a, t0, dur, freq, vol) {
    var len = Math.max(1, Math.floor(a.sampleRate * dur));
    var buf = a.createBuffer(1, len, a.sampleRate);
    var d = buf.getChannelData(0);
    for (var i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * (1 - i / len);
    var src = a.createBufferSource();
    src.buffer = buf;
    var filter = a.createBiquadFilter();
    filter.type = "bandpass";
    filter.frequency.value = freq;
    var g = a.createGain();
    g.gain.value = vol || 0.3;
    src.connect(filter);
    filter.connect(g);
    g.connect(a.destination);
    src.start(t0);
  }

  // Un son par catégorie, lié à son univers. Clés = slug de la catégorie (secteur).
  var SOUNDS = {
    // Fastfood : le burger s'ouvre -> "pfff" de vapeur + croquant du pain
    "fast-food": function (a, t) {
      tone(a, 180, t, 0.2, "triangle", 420, 0.22);
      crack(a, t + 0.16, 0.05, 1800, 0.35);
      crack(a, t + 0.24, 0.1, 900, 0.25);
    },
    // Grillades : crépitement de braise + grosse basse
    "grillades": function (a, t) {
      tone(a, 120, t, 0.25, "sine", 70, 0.3);
      for (var i = 0; i < 9; i++) crack(a, t + i * 0.055 + Math.random() * 0.03, 0.035, 3200 + Math.random() * 2400, 0.3);
    },
    // Local : sauce qui bouillonne -> bulles qui montent
    "restaurant-camerounais": function (a, t) {
      [0, 0.09, 0.18, 0.3].forEach(function (d, i) { tone(a, 280 + i * 40, t + d, 0.1, "sine", 520 + i * 60, 0.26); });
    },
    // Italien : fromage qui glisse sur la pizza -> pincement + souffle
    "restaurant-italien": function (a, t) {
      tone(a, 520, t, 0.14, "triangle", 880, 0.2);
      crack(a, t + 0.04, 0.22, 700, 0.18);
    },
    // Diététique : goutte d'eau fraîche -> deux notes claires
    "dietetique": function (a, t) {
      tone(a, 1800, t, 0.12, "sine", 2400, 0.18);
      tone(a, 1200, t + 0.09, 0.16, "sine", 1500, 0.12);
    },
    // Boissons : glouglou
    "boissons": function (a, t) { tone(a, 700, t, 0.12, "sine", 350, 0.26); tone(a, 620, t + 0.1, 0.12, "sine", 300, 0.26); tone(a, 520, t + 0.22, 0.14, "sine", 260, 0.24); },
    // Café : petit carillon chaud
    "cafe": function (a, t) { tone(a, 880, t, 0.5, "sine", null, 0.18); tone(a, 1320, t + 0.05, 0.4, "sine", null, 0.1); },
    // Snacks : croquant
    "snacks": function (a, t) { for (var i = 0; i < 3; i++) crack(a, t + i * 0.06, 0.05, 2200, 0.4); },
    // Image du plat qui entre : pop net et court
    "pop": function (a, t) { tone(a, 660, t, 0.09, "sine", 990, 0.22); },
    // Tous : arpège
    "tous": function (a, t) { [523, 659, 784, 1047].forEach(function (f, i) { tone(a, f, t + i * 0.07, 0.25, "triangle", null, 0.2); }); }
  };

  function playSound(slug) {
    if (!soundOn) return;
    var a = audio();
    if (!a) return;
    (SOUNDS[slug] || function (x, t) { tone(x, 600, t, 0.1, "sine", 900, 0.2); })(a, a.currentTime + 0.01);
  }

  // ---------- Horloge commune son / image ----------
  // Le son est planifie sur l'horloge audio (ctx.currentTime) ; l'image est calee sur la
  // meme horloge, ramenee au temps reel du frame affiche (getOutputTimestamp, qui compense
  // la latence de sortie). Sans audio actif, on retombe sur performance.now().
  function audioRunning() { return !!ctx && ctx.state === "running"; }

  function frameClock() {
    if (!audioRunning()) return { t: performance.now() / 1000, audio: false };
    var ts = ctx.getOutputTimestamp ? ctx.getOutputTimestamp() : null;
    if (ts && ts.performanceTime) {
      return { t: ts.contextTime + (performance.now() - ts.performanceTime) / 1000, audio: true };
    }
    return { t: ctx.currentTime, audio: true };
  }

  var DISH_FRAMES = [
    { opacity: 0, transform: "translateY(14px) scale(1.12)", filter: "blur(10px)" },
    { opacity: 1, transform: "translateY(0) scale(1)", filter: "blur(0px)" }
  ];
  var DISH_MS = 900;
  var LEAD = 0.06; // secondes : delai commun de planification (son + image)

  // Fait entrer l'image du plat : son et mouvement partent du meme instant.
  function enterDish(img, soundSlug) {
    if (!img || reduceMotion || !img.animate) return;
    var clock = frameClock();
    var t0 = clock.t + LEAD;
    if (audioRunning() && soundOn) {
      // t0 est sur l'horloge audio : le son part exactement a cet instant
      (SOUNDS[soundSlug] || SOUNDS.pop)(ctx, t0);
    }
    var anim = img.animate(DISH_FRAMES, { duration: DISH_MS, easing: "cubic-bezier(.16,1,.3,1)", fill: "both" });
    anim.pause();
    anim.currentTime = 0;
    function frame() {
      var ms = (frameClock().t - t0) * 1000;
      if (ms >= DISH_MS) { anim.currentTime = DISH_MS; return; }
      anim.currentTime = Math.max(0, ms);
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  // Animation contextuelle par catégorie (classe posée sur l'icône, retirée à la fin).
  var CAT_FX = {
    "fast-food": "oe-fx-burger",          // burger : secousse + ouverture (voir burgerOpen)
    "grillades": "oe-fx-grill",           // braise : tremblement et flash de chaleur
    "restaurant-camerounais": "oe-fx-bubble", // sauce : rebonds comme une marmite
    "restaurant-italien": "oe-fx-slide",  // pizza : la part glisse et se rattrape
    "dietetique": "oe-fx-leaf",           // légume : balancement léger et frais
    "boissons": "oe-fx-pour",             // verre : inclinaison pour verser
    "cafe": "oe-fx-steam",                // tasse : la vapeur monte
    "snacks": "oe-fx-crunch",             // croquant : écrasement élastique
    "tous": "oe-fx-spin"                  // accueil : petit tour complet
  };

  // Burger qui s'ouvre : deux moitiés de l'image se séparent puis se referment.
  function burgerOpen(icon) {
    var img = icon.querySelector("img");
    if (!img || icon.querySelector(".oe-burger-split")) return;
    var wrap = document.createElement("span");
    wrap.className = "oe-burger-split";
    ["oe-half-top", "oe-half-bot"].forEach(function (cls) {
      var half = img.cloneNode();
      half.className = "oe-half " + cls;
      half.alt = "";
      wrap.appendChild(half);
    });
    img.style.visibility = "hidden";
    icon.appendChild(wrap);
    setTimeout(function () { wrap.remove(); img.style.visibility = ""; }, 1100);
  }

  var lastCat = null; // dernière catégorie touchée, rejouée si la liste est remplacée

  function playCategory(btn, withBurger) {
    var slug = btn.getAttribute("data-fx") || "";
    var icon = btn.querySelector("[data-fx-icon]");
    if (!icon) return;
    var cls = CAT_FX[slug] || "oe-fx-spin";
    if (withBurger && slug === "fast-food") burgerOpen(icon);
    icon.classList.remove(cls);
    void icon.offsetWidth; // redémarre l'animation si on retape vite
    icon.classList.add(cls);
    setTimeout(function () { icon.classList.remove(cls); }, 1000);
  }

  function animateCategory(btn) {
    lastCat = { slug: btn.getAttribute("data-fx") || "", at: Date.now() };
    playCategory(btn, true);
    playSound(lastCat.slug);
  }

  // Après le rechargement des catégories (fetch de la recherche), rejoue l'animation
  // sur le nouveau bouton, pour qu'elle ne soit pas coupée par le remplacement du DOM.
  function replayCategory() {
    if (!lastCat || Date.now() - lastCat.at > 1500) return;
    var btn = document.querySelector('[data-category-filter][data-fx="' + lastCat.slug + '"]');
    if (btn) playCategory(btn, true);
    lastCat = null;
  }

  // ---------- Son on/off ----------
  function paintSoundToggle() {
    document.querySelectorAll("[data-sound-toggle]").forEach(function (b) {
      b.textContent = soundOn ? "🔊" : "🔇";
      var label = window.OE.t ? window.OE.t(soundOn ? "sound_on" : "sound_off") : "";
      if (label) b.setAttribute("aria-label", label);
    });
  }

  // ---------- Rails (6 plats + défilement) ----------
  function scrollRail(id, dir) {
    var rail = document.getElementById(id);
    if (rail) rail.scrollBy({ left: dir * Math.round(rail.clientWidth * 0.8), behavior: "smooth" });
  }

  // ---------- Diaporama ----------
  function initShowcase(root) {
    if (root.dataset.fxInit) return;
    root.dataset.fxInit = "1";
    var slides = root.querySelectorAll("[data-slide]");
    if (slides.length < 2) { if (slides[0]) slides[0].classList.add("is-active"); return; }
    var dots = root.querySelector("[data-showcase-dots]");
    var index = 0;
    var timer = null;

    slides.forEach(function (_, i) {
      var dot = document.createElement("button");
      dot.type = "button";
      dot.className = "oe-dot" + (i === 0 ? " is-active" : "");
      dot.setAttribute("aria-label", String(i + 1));
      dot.addEventListener("click", function () { go(i); start(); });
      if (dots) dots.appendChild(dot);
    });

    function go(i) {
      index = (i + slides.length) % slides.length;
      slides.forEach(function (s, k) { s.classList.toggle("is-active", k === index); });
      var img = slides[index].querySelector("img");
      enterDish(img, "pop");
      if (dots) dots.querySelectorAll(".oe-dot").forEach(function (d, k) { d.classList.toggle("is-active", k === index); });
    }
    function start() {
      clearInterval(timer);
      if (!reduceMotion) timer = setInterval(function () { go(index + 1); }, 4800);
    }
    go(0);
    start();
    root.addEventListener("mouseenter", function () { clearInterval(timer); });
    root.addEventListener("mouseleave", start);
    root.addEventListener("touchstart", function () { clearInterval(timer); }, { passive: true });
    root.addEventListener("touchend", start, { passive: true });
  }

  // ---------- Géolocalisation : quartier, ville, pays ----------
  var STORE = "oeLoc";

  function norm(s) {
    return String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
  }

  function parseAddress(data) {
    var a = data.address || {};
    return {
      quartier: a.quarter || a.neighbourhood || a.suburb || a.city_district || a.borough || a.village || a.hamlet || "",
      ville: a.city || a.town || a.municipality || a.county || a.state_district || "",
      pays: a.country || "",
      cc: String(a.country_code || "").toLowerCase()
    };
  }

  function reverseGeocode(lat, lng) {
    var lang = window.OE.lang ? window.OE.lang() : "fr";
    var url = "https://nominatim.openstreetmap.org/reverse?format=jsonv2&addressdetails=1&zoom=18" +
      "&lat=" + encodeURIComponent(lat) + "&lon=" + encodeURIComponent(lng) +
      "&accept-language=" + (lang === "en" ? "en" : "fr");
    return fetch(url, { headers: { Accept: "application/json" } })
      .then(function (r) { if (!r.ok) throw new Error("geocode"); return r.json(); })
      .then(parseAddress);
  }

  function setLocLabel(text, saved) {
    var label = document.getElementById("oe-loc-label");
    if (!label) return;
    label.textContent = text;
    label.setAttribute("data-loc-set", "1");
    if (saved === false) label.removeAttribute("data-loc-set");
  }

  function setLocStatus(key) {
    var status = document.getElementById("oe-loc-status");
    if (!status) return;
    status.textContent = key ? window.OE.t(key) : "";
    status.classList.toggle("hidden", !key);
  }

  function renderLocation(place) {
    var parts = [place.quartier, place.ville, place.pays].filter(Boolean);
    if (!parts.length) return;
    setLocLabel(parts.join(", "));
    if (place.cc && place.cc !== "cm") setLocStatus("loc_outside");
    else if (!place.quartier) setLocStatus("loc_unknown");
    else setLocStatus("");
    try { localStorage.setItem(STORE, JSON.stringify(place)); } catch (e) {}
    highlightNeighbourhood(place.quartier);
  }

  function locate() {
    var btn = document.querySelector("[data-locate]");
    if (btn) btn.disabled = true;
    setLocStatus("locating");
    window.OE.getLocation()
      .then(function (p) { return reverseGeocode(p.lat, p.lng); })
      .then(renderLocation)
      .catch(function () { setLocStatus("loc_denied"); })
      .finally(function () { if (btn) btn.disabled = false; });
  }

  // Remonte en tête de liste les restaurants du quartier de l'utilisateur.
  function highlightNeighbourhood(quartier) {
    var list = document.getElementById("all-restaurants");
    if (!list || !quartier) return;
    var q = norm(quartier);
    var cards = Array.prototype.slice.call(list.querySelectorAll("[data-neighborhood]"));
    cards.forEach(function (card) {
      var n = norm(card.getAttribute("data-neighborhood"));
      var near = !!n && (n.indexOf(q) !== -1 || q.indexOf(n) !== -1);
      card.classList.toggle("oe-near", near);
      var badge = card.querySelector("[data-near-badge]");
      if (badge) badge.classList.toggle("hidden", !near);
      if (near) list.insertBefore(card, list.firstChild);
    });
  }

  function restoreLocation() {
    var saved = null;
    try { saved = JSON.parse(localStorage.getItem(STORE) || "null"); } catch (e) {}
    if (saved) renderLocation(saved);
  }

  // ---------- Délégation d'événements ----------
  // Le navigateur n'autorise le son qu'apres un geste : on prepare l'audio au premier toucher.
  document.addEventListener("pointerdown", function () { audio(); }, { once: true, passive: true });

  document.addEventListener("click", function (e) {
    var cat = e.target.closest("[data-category-filter]");
    if (cat) animateCategory(cat);

    if (e.target.closest("[data-sound-toggle]")) {
      soundOn = !soundOn;
      try { localStorage.setItem("oeSound", soundOn ? "on" : "off"); } catch (err) {}
      paintSoundToggle();
      if (soundOn) playSound("tous");
    }

    if (e.target.closest("[data-locate]")) locate();

    var prev = e.target.closest("[data-rail-prev]");
    if (prev) scrollRail(prev.getAttribute("data-rail-prev"), -1);
    var next = e.target.closest("[data-rail-next]");
    if (next) scrollRail(next.getAttribute("data-rail-next"), 1);
  });

  function init() {
    document.querySelectorAll("[data-showcase]").forEach(initShowcase);
    paintSoundToggle();
    restoreLocation();
  }

  function refresh() {
    init();
    replayCategory();
  }

  window.OE.fx = { init: init, refresh: refresh, playSound: playSound };
  window.addEventListener("oe:lang", function () { paintSoundToggle(); });

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
