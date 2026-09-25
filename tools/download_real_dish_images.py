"""Download real dish photos for the ONE EAT demo menu from Wikimedia Commons."""
import os
import sys
import time
from io import BytesIO
from pathlib import Path

import django
import requests
from PIL import Image
from django.conf import settings
from django.utils.text import slugify

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "oneeat.settings")
django.setup()

from apps.restaurants.models import Dish  # noqa: E402


COMMONS_API = "https://commons.wikimedia.org/w/api.php"
HEADERS = {"User-Agent": "ONEEAT demo image downloader/1.0"}
SEARCH_TERMS = {
    "Ndolé Spécial + Riz": "ndole dish",
    "Okok + Bâton de Manioc": "african cassava leaves dish",
    "Sanga (Maïs + Haricots)": "beans corn dish",
    "Riz sauté au poulet": "chicken fried rice",
    "Poisson braisé + Miondo": "grilled fish food",
    "Beignets Haricots": "bean fritters food",
    "Poulet braisé entier": "grilled chicken whole",
    "Demi-poulet grillé": "grilled chicken plate",
    "Brochettes de bœuf (x5)": "beef skewers",
    "Frites de plantain": "fried plantain",
    "Alloco": "alloco fried plantain",
    "Eru + Water Fufu": "eru water fufu",
    "Koki + Plantain": "bean pudding plantain",
    "Poulet DG": "chicken plantain dish",
    "Côtes de bœuf (500g)": "grilled beef rib steak",
    "Gigot d'agneau": "roast leg of lamb",
    "Mixed Grill": "mixed grill plate",
    "Pizza Margherita": "pizza margherita",
    "Pizza Reine": "ham mushroom pizza",
    "Pizza 4 Fromages": "four cheese pizza",
    "Classic Beef Burger": "beef burger",
    "Chicken Crispy": "crispy chicken burger",
    "Double Cheese": "double cheeseburger",
    "Frites maison": "french fries",
    "Milkshake vanille": "vanilla milkshake",
}


def commons_image_url(term):
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": f"{term} filetype:bitmap",
        "gsrnamespace": 6,
        "gsrlimit": 8,
        "prop": "imageinfo",
        "iiprop": "url|mime",
        "iiurlwidth": 1200,
        "format": "json",
    }
    for attempt in range(4):
        response = requests.get(COMMONS_API, params=params, timeout=25, headers=HEADERS)
        if response.status_code != 429:
            break
        time.sleep(5 + attempt * 5)
    response.raise_for_status()
    data = response.json()
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        mime = info.get("mime", "")
        url = info.get("thumburl") or info.get("url")
        if url and mime.startswith("image/"):
            return url
    return None


def save_square_image(url, dish):
    response = requests.get(url, timeout=35, headers=HEADERS)
    response.raise_for_status()
    img = Image.open(BytesIO(response.content)).convert("RGB")
    width, height = img.size
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    img = img.crop((left, top, left + side, top + side)).resize((900, 900), Image.LANCZOS)

    rel_path = os.path.join("dishes", "demo", f"{slugify(dish.name)}.jpg")
    abs_path = settings.MEDIA_ROOT / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(abs_path, "JPEG", quality=86, optimize=True)
    dish.image = rel_path.replace("\\", "/")
    dish.save(update_fields=["image"])


def main():
    for dish in Dish.objects.order_by("name"):
        if dish.image and str(dish.image).endswith(".jpg"):
            print(f"SKIP {dish.name}: already downloaded")
            continue
        term = SEARCH_TERMS.get(dish.name, dish.name)
        url = commons_image_url(term)
        if not url:
            print(f"MISS {dish.name}: no image for {term}")
            continue
        save_square_image(url, dish)
        print(f"OK {dish.name}: {url}")


if __name__ == "__main__":
    main()
