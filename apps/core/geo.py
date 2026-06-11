"""Utilitaires de geolocalisation (sans dependance GIS lourde)."""
import math


def haversine_km(lat1, lng1, lat2, lng2):
    """Distance en km entre deux points (formule de Haversine)."""
    if None in (lat1, lng1, lat2, lng2):
        return None
    r = 6371.0  # rayon Terre km
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2)
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def within_radius(lat1, lng1, lat2, lng2, radius_km):
    d = haversine_km(lat1, lng1, lat2, lng2)
    return d is not None and d <= radius_km
