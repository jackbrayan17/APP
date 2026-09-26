"""Genere toutes les declinaisons d'icones ONE EAT a partir du logo rond officiel.

Source : brand/oneeat-logo.png (badge rond « ONE Eat », fond transparent, 500x500+).
Sorties :
  - static/icons/*  -> favicon, PWA (192/512 + maskable), Apple touch, logo web,
                       image Open Graph 1200x630 (apercus WhatsApp/Telegram/Facebook/X),
                       avatar carre 640x640 (bot Telegram, reseaux sociaux)
  - mobile/assets/icons/* -> icone app, foreground adaptive, splash

Usage : python tools/generate_icons.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "brand" / "oneeat-logo.png"
STATIC = ROOT / "static" / "icons"
FLUTTER = ROOT / "mobile" / "assets" / "icons"
WHITE = (255, 255, 255, 255)
ORANGE = (242, 101, 34)
INK = (17, 17, 17)
FONT_DIR = Path("C:/Windows/Fonts")


def load_logo():
    img = Image.open(SRC).convert("RGBA")
    bbox = img.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
    return img.crop(bbox) if bbox else img


def on_square(logo, size, bg=WHITE, scale=0.92, circle_bg=False):
    """Logo centre sur un carre ; circle_bg : disque blanc derriere le badge."""
    canvas = Image.new("RGBA", (size, size), bg)
    side = int(size * scale)
    if circle_bg:
        d = ImageDraw.Draw(canvas)
        m = (size - side) // 2
        d.ellipse((m, m, m + side, m + side), fill=WHITE)
    lg = logo.resize((side, side), Image.LANCZOS)
    canvas.alpha_composite(lg, ((size - side) // 2, (size - side) // 2))
    return canvas


def font(name, size):
    try:
        return ImageFont.truetype(str(FONT_DIR / name), size)
    except OSError:
        return ImageFont.load_default()


def og_image(logo):
    W, H = 1200, 630
    img = Image.new("RGBA", (W, H), WHITE)
    d = ImageDraw.Draw(img)
    d.rectangle((0, H - 14, W, H), fill=ORANGE)
    lg = logo.resize((440, 440), Image.LANCZOS)
    img.alpha_composite(lg, (70, (H - 440) // 2 - 6))
    x = 580
    d.text((x, 170), "Livraison de repas", font=font("seguibl.ttf", 58), fill=INK)
    d.text((x, 240), "à Douala", font=font("seguibl.ttf", 58), fill=ORANGE)
    d.text((x, 340), "Restaurants locaux, grillades, fast-food", font=font("segoeui.ttf", 30), fill=(90, 90, 90))
    d.text((x, 380), "et plats diététiques, livrés chez vous.", font=font("segoeui.ttf", 30), fill=(90, 90, 90))
    d.rounded_rectangle((x, 450, x + 250, 510), radius=30, fill=ORANGE)
    d.text((x + 34, 459), "oneeat.cm", font=font("segoeuib.ttf", 32), fill=WHITE)
    return img.convert("RGB")


def main():
    logo = load_logo()
    STATIC.mkdir(parents=True, exist_ok=True)

    # Favicons (badge seul, fond transparent -> net sur onglets clairs/sombres grace au disque blanc)
    for s in (16, 32, 48):
        on_square(logo, s, (0, 0, 0, 0), 1.0, circle_bg=True).save(STATIC / f"favicon-{s}.png")
    on_square(logo, 256, (0, 0, 0, 0), 1.0, circle_bg=True).save(
        STATIC / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

    # PWA : 'any' (badge sur blanc) et 'maskable' (zone de securite 80 %)
    on_square(logo, 192, WHITE, 0.94).save(STATIC / "icon-192.png")
    on_square(logo, 512, WHITE, 0.94).save(STATIC / "icon-512.png")
    on_square(logo, 192, WHITE, 0.76).save(STATIC / "icon-maskable-192.png")
    on_square(logo, 512, WHITE, 0.76).save(STATIC / "icon-maskable-512.png")
    on_square(logo, 180, WHITE, 0.86).convert("RGB").save(STATIC / "apple-touch-icon.png")

    # Logo web (transparent) + avatar reseaux sociaux / bot Telegram
    logo.resize((256, 256), Image.LANCZOS).save(STATIC / "logo.png")
    logo.resize((256, 256), Image.LANCZOS).save(STATIC / "logo-white.png")
    on_square(logo, 640, WHITE, 0.9).convert("RGB").save(STATIC / "social-avatar.png")

    # Open Graph / Twitter / Telegram / WhatsApp
    og_image(logo).save(STATIC / "og-image.png", optimize=True)

    # App mobile Flutter
    if FLUTTER.exists():
        on_square(logo, 1024, WHITE, 0.9).convert("RGB").save(FLUTTER / "app_icon.png")
        on_square(logo, 1024, (0, 0, 0, 0), 0.62).save(FLUTTER / "app_icon_foreground.png")
        on_square(logo, 1024, (0, 0, 0, 0), 0.7, circle_bg=True).save(FLUTTER / "splash_logo.png")
    print("Icônes générées dans", STATIC)


if __name__ == "__main__":
    main()
