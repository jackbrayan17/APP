"""QR code de validation de livraison (SVG inline, sans dependance front)."""
import base64
import io

import qrcode
import qrcode.image.svg
from django.urls import reverse


def validation_url(request, order):
    """URL absolue ouverte par le scan : le client arrive sur la page de validation."""
    path = reverse("orders:validate", args=[order.number])
    return request.build_absolute_uri(f"{path}?code={order.delivery_code}")


def delivery_qr_data_uri(request, order):
    """Data-URI SVG du QR de livraison, a afficher sur l'ecran du livreur."""
    img = qrcode.make(validation_url(request, order), image_factory=qrcode.image.svg.SvgPathImage,
                      box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return "data:image/svg+xml;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
