/* ONE EAT — logique front commune */
(function () {
  "use strict";

  // ---- CSRF ----
  function getCookie(name) {
    const v = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return v ? v.pop() : "";
  }
  const csrftoken = getCookie("csrftoken");
  window.OE = window.OE || {};
  window.OE.csrftoken = csrftoken;

  // ---- Panier ----
  function updateCartBadge(count) {
    const badge = document.getElementById("nav-cart-badge");
    if (!badge) return;
    badge.textContent = count;
    badge.classList.toggle("hidden", !count);
    if (count) { badge.classList.add("pop"); setTimeout(() => badge.classList.remove("pop"), 250); }
  }
  window.OE.updateCartBadge = updateCartBadge;

  document.addEventListener("click", function (e) {
    const btn = e.target.closest("[data-add-cart]");
    if (!btn) return;
    e.preventDefault();
    const id = btn.getAttribute("data-add-cart");
    fetch(`/panier/ajouter/${id}/`, {
      method: "POST",
      headers: { "X-CSRFToken": csrftoken },
    })
      .then((r) => r.json())
      .then((d) => {
        if (d.ok) {
          updateCartBadge(d.count);
          btn.classList.add("pop");
          setTimeout(() => btn.classList.remove("pop"), 250);
        }
      });
  });

  // ---- Geolocalisation ----
  window.OE.getLocation = function () {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) return reject("non supporte");
      navigator.geolocation.getCurrentPosition(
        (p) => resolve({ lat: p.coords.latitude, lng: p.coords.longitude }),
        (err) => reject(err),
        { enableHighAccuracy: true, timeout: 10000 }
      );
    });
  };

  // ---- PWA : Service Worker ----
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {});
    });
  }

  // ---- Web Push ----
  function urlBase64ToUint8Array(base64String) {
    const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
    const raw = atob(base64);
    return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
  }

  window.OE.enablePush = async function (vapidKey) {
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
      alert("Notifications non supportées sur cet appareil.");
      return;
    }
    const perm = await Notification.requestPermission();
    if (perm !== "granted") return;
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(vapidKey),
    });
    await fetch("/push/subscribe/", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrftoken },
      body: JSON.stringify({ subscription: sub }),
    });
    alert("Notifications activées ✅");
  };
})();
