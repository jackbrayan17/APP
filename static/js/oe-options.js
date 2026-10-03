/* ONE EAT — feuille du bas « Personnaliser » : complements, supplements et boissons.
   Ouverte par le bouton + d'un plat qui a des options. Le total se calcule en direct
   (prix du plat, promo comprise, + options choisies) x quantite. Le serveur recalcule le
   prix a l'ajout : le total affiche n'est qu'une estimation fidele. */
(function () {
  "use strict";

  var sheet = null, panel = null, body = null, addBtn = null, totalEl = null, qtyEl = null, errEl = null;
  var titleEl = null, descEl = null, restoEl = null, imgEl = null;
  var cache = {};
  var current = null;        // { id, base, options: [], trigger }
  var picked = {};           // id -> true
  var qty = 1;
  var busy = false;

  function fmt(n) { return Number(n || 0).toLocaleString("fr-FR").replace(/\s/g, " "); }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function computeTotal() {
    if (!current) return 0;
    var sum = current.base;
    current.options.forEach(function (o) { if (picked[o.id]) sum += o.price; });
    return sum * qty;
  }

  var lastTotal = null;
  function paintTotal() {
    var total = computeTotal();
    totalEl.textContent = fmt(total);
    if (lastTotal !== null && lastTotal !== total && totalEl.animate && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
      totalEl.animate([{ transform: "scale(1.12)" }, { transform: "scale(1)" }], { duration: 200, easing: "cubic-bezier(.2,.8,.2,1)" });
    }
    lastTotal = total;
    qtyEl.textContent = String(qty);
  }

  function setError(msg) {
    errEl.textContent = msg || "";
    errEl.classList.toggle("hidden", !msg);
  }

  function skeleton() {
    body.innerHTML = "";
    for (var i = 0; i < 3; i++) body.appendChild(el("div", "oe-skel h-16"));
  }

  function renderOptions() {
    body.innerHTML = "";
    if (!current.options.length) {
      body.appendChild(el("p", "text-sm text-gray-500", "Aucune option pour ce plat : ajoutez-le directement."));
      return;
    }
    var groups = {};
    var order = [];
    current.options.forEach(function (o) {
      if (!groups[o.group]) { groups[o.group] = []; order.push(o.group); }
      groups[o.group].push(o);
    });
    order.forEach(function (g) {
      var section = el("section", "space-y-2.5");
      var head = el("div", "flex items-center justify-between");
      head.appendChild(el("h3", "text-xs font-extrabold uppercase tracking-wider text-gray-500", g));
      head.appendChild(el("span", "text-[11px] font-semibold text-gray-400", "Facultatif"));
      section.appendChild(head);
      groups[g].forEach(function (o) {
        var b = el("button", "oe-opt flex w-full min-h-[56px] items-center gap-3 rounded-2xl border-2 border-gray-100 bg-white px-4 py-3 text-left");
        b.type = "button";
        b.setAttribute("aria-pressed", picked[o.id] ? "true" : "false");
        b.setAttribute("data-option", String(o.id));
        var tick = el("span", "oe-tick flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full border-2 border-gray-300");
        tick.setAttribute("aria-hidden", "true");
        tick.innerHTML = '<svg class="h-3.5 w-3.5 text-white" fill="none" stroke="currentColor" stroke-width="3" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>';
        b.appendChild(tick);
        b.appendChild(el("span", "min-w-0 flex-1 text-[15px] font-semibold text-gray-900", o.name));
        b.appendChild(el("span", "flex-shrink-0 text-sm font-bold tabular-nums text-gray-600",
          o.price ? "+" + fmt(o.price) + " F" : "Offert"));
        b.addEventListener("click", function () {
          picked[o.id] = !picked[o.id];
          if (!picked[o.id]) delete picked[o.id];
          b.setAttribute("aria-pressed", picked[o.id] ? "true" : "false");
          paintTotal();
        });
        section.appendChild(b);
      });
      body.appendChild(section);
    });
  }

  function loadDish(id) {
    if (cache[id]) return Promise.resolve(cache[id]);
    return fetch("/plat/" + id + "/options.json", { headers: { Accept: "application/json" } })
      .then(function (r) { if (!r.ok) throw new Error("http " + r.status); return r.json(); })
      .then(function (d) { cache[id] = d; return d; });
  }

  function showError(msg) {
    body.innerHTML = "";
    var box = el("div", "rounded-2xl bg-red-50 p-4 text-sm font-semibold text-red-700", msg);
    var retry = el("button", "mt-3 rounded-xl bg-white px-4 py-2 text-sm font-bold text-red-700 shadow-sm", "Réessayer");
    retry.type = "button";
    retry.addEventListener("click", function () { if (current) open(current.id, current.trigger); });
    box.appendChild(retry);
    body.appendChild(box);
  }

  function open(id, trigger) {
    current = { id: id, base: 0, options: [], trigger: trigger || null };
    picked = {};
    qty = 1;
    lastTotal = null;
    setError("");
    titleEl.textContent = "";
    descEl.textContent = "";
    restoEl.textContent = "";
    imgEl.classList.add("hidden");
    addBtn.disabled = true;
    totalEl.textContent = "0";
    qtyEl.textContent = "1";
    skeleton();

    sheet.classList.add("is-open");
    sheet.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    document.body.classList.add("oe-sheet-open");
    setTimeout(function () { addBtn.focus({ preventScroll: true }); }, 60);

    loadDish(id).then(function (d) {
      if (!current || current.id !== id) return;
      current.base = d.price;
      current.options = d.options || [];
      titleEl.textContent = d.name;
      descEl.textContent = d.description || "";
      restoEl.textContent = d.restaurant || "";
      if (d.image) { imgEl.src = d.image; imgEl.alt = d.name; imgEl.classList.remove("hidden"); }
      renderOptions();
      addBtn.disabled = false;
      paintTotal();
    }).catch(function () {
      if (current && current.id === id) showError("Impossible de charger ce plat. Vérifiez votre connexion.");
    });
  }

  function close() {
    if (!sheet || !sheet.classList.contains("is-open")) return;
    sheet.classList.remove("is-open");
    sheet.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
    document.body.classList.remove("oe-sheet-open");
    var back = current && current.trigger;
    current = null;
    if (back && back.focus) back.focus({ preventScroll: true });
  }

  // Jeton CSRF : rendu dans la feuille (cookie garanti sur chaque page client)
  function csrfValue() {
    var field = sheet && sheet.querySelector("input[name=csrfmiddlewaretoken]");
    return (field && field.value) || window.OE.csrftoken || "";
  }

  function submit() {
    if (!current || busy) return;
    busy = true;
    addBtn.disabled = true;
    setError("");
    var body2 = new URLSearchParams();
    Object.keys(picked).forEach(function (oid) { if (picked[oid]) body2.append("options", oid); });
    body2.append("qty", String(qty));
    fetch("/panier/ajouter/" + current.id + "/", {
      method: "POST",
      headers: { "X-CSRFToken": csrfValue() },
      body: body2,
    })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
      .then(function (res) {
        if (res.ok && res.d.ok) {
          window.OE.updateCartBadge(res.d.count);
          window.OE.toast("✓ " + qty + " × " + (res.d.name || "Plat") + " ajouté au panier");
          close();
        } else {
          setError(res.d.error || "Impossible d'ajouter ce plat.");
        }
      })
      .catch(function () { setError("Réseau indisponible. Réessayez."); })
      .finally(function () { busy = false; addBtn.disabled = false; });
  }

  function init() {
    sheet = document.getElementById("oe-sheet");
    if (!sheet) return;
    panel = sheet.querySelector(".oe-sheet-panel");
    body = document.getElementById("oe-sheet-body");
    addBtn = document.getElementById("oe-sheet-add");
    totalEl = document.getElementById("oe-sheet-total");
    qtyEl = document.getElementById("oe-sheet-qty");
    errEl = document.getElementById("oe-sheet-error");
    titleEl = document.getElementById("oe-sheet-title");
    descEl = document.getElementById("oe-sheet-desc");
    restoEl = document.getElementById("oe-sheet-resto");
    imgEl = document.getElementById("oe-sheet-img");

    document.addEventListener("click", function (e) {
      var opener = e.target.closest("[data-options-sheet]");
      if (opener) { e.preventDefault(); open(opener.getAttribute("data-options-sheet"), opener); return; }
      if (e.target.closest("[data-sheet-close]")) { close(); return; }
      var q = e.target.closest("[data-qty]");
      if (q && sheet.contains(q)) {
        qty = Math.max(1, Math.min(50, qty + Number(q.getAttribute("data-qty"))));
        paintTotal();
        return;
      }
      if (e.target.closest("#oe-sheet-add")) submit();
    });

    document.addEventListener("keydown", function (e) {
      if (!sheet.classList.contains("is-open")) return;
      if (e.key === "Escape") { close(); return; }
      if (e.key === "Tab") {
        // Piege le focus dans la feuille tant qu'elle est ouverte
        var focusables = Array.prototype.slice.call(panel.querySelectorAll("button:not([disabled])"));
        if (!focusables.length) return;
        var first = focusables[0], last = focusables[focusables.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    });
  }

  window.OE = window.OE || {};
  window.OE.options = { open: open, close: close };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
