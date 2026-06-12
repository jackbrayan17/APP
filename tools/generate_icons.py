"""Génère toutes les déclinaisons d'icônes ONE EAT à partir du logo source.

Source : brand/oneeat-logo.png  (logo « OneEat », emblème assiette+couverts + texte).
Sorties :
  - static/icons/*        -> favicon, PWA (192/512 maskable), Apple touch, OG SEO, logo web
  - mobile/assets/icons/* -> app_icon (iOS/Android), foreground adaptatif, splash

Usage : python tools/generate_icons.py
Requiert Pillow (déjà dans requirements.txt).
"""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "brand" / "oneeat-logo.png"
STATIC = ROOT / "static" / "icons"
FLUTTER = ROOT / "mobile" / "assets" / "icons"
STATIC.mkdir(parents=True, exist_ok=True)
FLUTTER.mkdir(parents=True, exist_ok=True)

BRAND = (255, 107, 26, 255)   # #FF6B1A
WHITE = (255, 255, 255, 255)


def ink_bbox(img):
    """Boîte englobante des pixels « encre » (ni transparents ni quasi-blancs)."""
    rgba = img.convert("RGBA")
    px = rgba.load()
    w, h = rgba.size
    minx, miny, maxx, maxy = w, h, 0, 0
    found = False
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a > 16 and not (r > 235 and g > 235 and b > 235):
                found = True
                minx, miny = min(minx, x), min(miny, y)
                maxx, maxy = max(maxx, x), max(maxy, y)
    if not found:
        return (0, 0, w, h)
    return (minx, miny, maxx + 1, maxy + 1)


def trim(img):
    return img.convert("RGBA").crop(ink_bbox(img))


def _ink_alpha(img):
    """Masque L : 255 sur l'encre (pixels non quasi-blancs), 0 sur le fond blanc.
    Gère un fond blanc opaque comme un fond transparent."""
    rgba = img.convert("RGBA")
    px = rgba.load()
    w, h = rgba.size
    mask = Image.new("L", (w, h), 0)
    mpx = mask.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a > 16 and not (r > 232 and g > 232 and b > 232):
                mpx[x, y] = 255
    return mask


def to_white(img):
    """Silhouette blanche basée sur le masque d'encre (fond transparent)."""
    rgba = img.convert("RGBA")
    white = Image.new("RGBA", rgba.size, (255, 255, 255, 0))
    white.putalpha(_ink_alpha(rgba))
    return white


def key_white(img):
    """Couleurs d'origine, mais le fond blanc devient transparent."""
    rgba = img.convert("RGBA")
    rgba.putalpha(_ink_alpha(rgba))
    return rgba


def place_square(content, size, bg, scale):
    """Centre `content` (mis à l'échelle `scale`) sur un carré `size` de fond `bg`."""
    canvas = Image.new("RGBA", (size, size), bg)
    cw, ch = content.size
    f = (size * scale) / max(cw, ch)
    new = content.resize((max(1, round(cw * f)), max(1, round(ch * f))), Image.LANCZOS)
    canvas.alpha_composite(new, ((size - new.width) // 2, (size - new.height) // 2))
    return canvas


def place_fit(content, w, h, bg, pad=0.14):
    canvas = Image.new("RGBA", (w, h), bg)
    cw, ch = content.size
    f = min(w * (1 - pad) / cw, h * (1 - pad) / ch)
    new = content.resize((round(cw * f), round(ch * f)), Image.LANCZOS)
    canvas.alpha_composite(new, ((w - new.width) // 2, (h - new.height) // 2))
    return canvas


def save_rgb(img, path):
    """Aplati sur fond blanc et enregistre sans canal alpha (Apple/iOS)."""
    bg = Image.new("RGB", img.size, (255, 255, 255))
    bg.paste(img.convert("RGBA"), mask=img.convert("RGBA").getchannel("A"))
    bg.save(path)


def main():
    src = Image.open(SRC).convert("RGBA")
    full = trim(src)                       # logo complet, rogné
    # Emblème = portion gauche (assiette + couverts), puis re-rogné.
    emblem = trim(full.crop((0, 0, round(full.width * 0.30), full.height)))
    white_full = to_white(full)
    white_emblem = to_white(emblem)

    # ---- Web / PWA (fond orange, emblème blanc -> identité forte) ----
    place_square(white_emblem, 192, BRAND, 0.60).save(STATIC / "icon-192.png")
    place_square(white_emblem, 512, BRAND, 0.60).save(STATIC / "icon-512.png")
    # Apple touch (sans alpha)
    place_square(white_emblem, 180, BRAND, 0.60).convert("RGB").save(STATIC / "apple-touch-icon.png")
    # Favicons
    place_square(white_emblem, 32, BRAND, 0.66).save(STATIC / "favicon-32.png")
    place_square(white_emblem, 16, BRAND, 0.70).save(STATIC / "favicon-16.png")
    # favicon.ico multi-tailles
    place_square(white_emblem, 48, BRAND, 0.66).save(
        STATIC / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    # Logo web (couleurs d'origine, fond transparent) pour l'entête
    key_white(full).save(STATIC / "logo.png")
    to_white(full).save(STATIC / "logo-white.png")
    # Image de partage SEO (Open Graph 1200x630, logo original sur blanc)
    place_fit(full, 1200, 630, (255, 255, 255, 255)).convert("RGB").save(STATIC / "og-image.png")

    # ---- Flutter (iOS + Android) ----
    # Icône principale : fond orange, emblème blanc, sans alpha (iOS).
    save_rgb(place_square(white_emblem, 1024, BRAND, 0.62), FLUTTER / "app_icon.png")
    # Avant-plan adaptatif Android : emblème blanc dans la zone de sécurité (transparent).
    place_square(white_emblem, 1024, (0, 0, 0, 0), 0.58).save(FLUTTER / "app_icon_foreground.png")
    # Splash : logo complet en blanc (centré sur fond orange par flutter_native_splash).
    place_square(white_full, 1024, (0, 0, 0, 0), 0.72).save(FLUTTER / "splash_logo.png")

    print("OK — icônes générées :")
    for p in sorted(STATIC.glob("*")) + sorted(FLUTTER.glob("*.png")):
        print("  ", p.relative_to(ROOT))


if __name__ == "__main__":
    main()
