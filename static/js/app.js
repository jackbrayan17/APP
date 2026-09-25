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

  // ---- Partage plats & restaurants ----
  const shareSheet = document.getElementById("share-sheet");
  let sharePayload = { title: "ONE EAT", url: window.location.href };

  function closeShareSheet() {
    if (!shareSheet) return;
    shareSheet.classList.add("hidden");
    document.body.style.overflow = "";
  }

  function openShareSheet(trigger) {
    if (!shareSheet) return;
    sharePayload = {
      title: trigger.dataset.shareTitle || document.title,
      url: new URL(trigger.dataset.shareUrl || window.location.href, window.location.origin).href,
    };
    shareSheet.querySelector("[data-share-url-label]").textContent = sharePayload.url;
    shareSheet.querySelector("[data-copy-label]").textContent = "Copier le lien";
    shareSheet.classList.remove("hidden");
    document.body.style.overflow = "hidden";
    shareSheet.querySelector("[data-share-close]").focus();
  }

  async function copyShareLink() {
    try {
      await navigator.clipboard.writeText(sharePayload.url);
    } catch (error) {
      const input = document.createElement("textarea");
      input.value = sharePayload.url;
      input.style.position = "fixed";
      input.style.opacity = "0";
      document.body.appendChild(input);
      input.select();
      document.execCommand("copy");
      input.remove();
    }
    const label = shareSheet.querySelector("[data-copy-label]");
    label.textContent = "Lien copié !";
    setTimeout(() => { label.textContent = "Copier le lien"; }, 1800);
  }

  document.addEventListener("click", function (e) {
    const trigger = e.target.closest("[data-share-title]");
    if (trigger) {
      e.preventDefault();
      openShareSheet(trigger);
      return;
    }
    if (e.target.closest("[data-share-close]")) {
      closeShareSheet();
      return;
    }
    const channel = e.target.closest("[data-share-channel]")?.dataset.shareChannel;
    if (!channel) return;
    const url = encodeURIComponent(sharePayload.url);
    const text = encodeURIComponent(sharePayload.title);
    if (channel === "copy") return void copyShareLink();
    if (channel === "whatsapp") window.open(`https://wa.me/?text=${text}%20${url}`, "_blank", "noopener,noreferrer");
    if (channel === "facebook") window.open(`https://www.facebook.com/sharer/sharer.php?u=${url}`, "_blank", "noopener,noreferrer");
    if (channel === "x") window.open(`https://twitter.com/intent/tweet?text=${text}&url=${url}`, "_blank", "noopener,noreferrer");
    if (channel === "native") {
      if (navigator.share) navigator.share(sharePayload).catch(() => {});
      else copyShareLink();
    }
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && shareSheet && !shareSheet.classList.contains("hidden")) closeShareSheet();
  });

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
