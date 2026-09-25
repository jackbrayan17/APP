"""Lightweight road routing helpers for delivery tracking.

The app uses OSRM-compatible routing when available and falls back to a direct
line with conservative ETA estimates. This keeps tracking responsive without
requiring paid map keys in development.
"""
from __future__ import annotations

import logging

import requests
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist

from .geo import haversine_km

logger = logging.getLogger("oneeat")

DEFAULT_ROUTE_PROVIDER_URL = "http://router.project-osrm.org/route/v1/driving"
ROUTE_CACHE_SECONDS = 90
ROUTE_TIMEOUT_SECONDS = 1.6
FALLBACK_SPEED_KMH = 24


def _valid_point(lat, lng):
    return lat is not None and lng is not None


def _point(lat, lng):
    return {"lat": round(float(lat), 6), "lng": round(float(lng), 6)}


def fallback_route(start_lat, start_lng, end_lat, end_lng):
    distance = haversine_km(start_lat, start_lng, end_lat, end_lng) or 0
    # Add a small road-network factor so fallback ETA is less optimistic.
    distance *= 1.25
    duration = (distance / FALLBACK_SPEED_KMH) * 60 if distance else 0
    return {
        "provider": "fallback",
        "is_fallback": True,
        "distance_km": round(distance, 2),
        "duration_min": max(1, round(duration)) if distance else None,
        "points": [_point(start_lat, start_lng), _point(end_lat, end_lng)],
        "traffic": {
            "available": False,
            "label": "Trafic indisponible",
            "delay_min": None,
        },
    }


def road_route(start_lat, start_lng, end_lat, end_lng):
    """Return route geometry, distance, ETA and traffic metadata."""
    if not (_valid_point(start_lat, start_lng) and _valid_point(end_lat, end_lng)):
        return {
            "provider": "none",
            "is_fallback": True,
            "distance_km": None,
            "duration_min": None,
            "points": [],
            "traffic": {
                "available": False,
                "label": "Coordonnees incompletes",
                "delay_min": None,
            },
        }

    key = "route:%s:%s:%s:%s" % (
        round(float(start_lat), 4),
        round(float(start_lng), 4),
        round(float(end_lat), 4),
        round(float(end_lng), 4),
    )
    cached = cache.get(key)
    if cached:
        return cached

    base = getattr(settings, "ROUTING_PROVIDER_URL", DEFAULT_ROUTE_PROVIDER_URL)
    url = f"{base}/{start_lng},{start_lat};{end_lng},{end_lat}"
    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "false",
        "alternatives": "false",
    }
    try:
        response = requests.get(url, params=params, timeout=ROUTE_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
        route = (payload.get("routes") or [None])[0]
        coords = ((route or {}).get("geometry") or {}).get("coordinates") or []
        if not route or len(coords) < 2:
            raise ValueError("Routing provider returned no geometry")
        result = {
            "provider": "osrm",
            "is_fallback": False,
            "distance_km": round((route.get("distance") or 0) / 1000, 2),
            "duration_min": max(1, round((route.get("duration") or 0) / 60)),
            "points": [
                {"lat": round(float(lat), 6), "lng": round(float(lng), 6)}
                for lng, lat in coords
            ],
            "traffic": {
                "available": False,
                "label": "Trafic non fourni par OSRM",
                "delay_min": None,
            },
        }
    except Exception as exc:  # network/provider failures should never block tracking
        logger.warning("route fallback used: %s", exc)
        result = fallback_route(start_lat, start_lng, end_lat, end_lng)

    cache.set(key, result, ROUTE_CACHE_SECONDS)
    return result


def tracking_payload(order):
    """Build the canonical realtime tracking payload for web and mobile."""
    restaurant = order.restaurant
    try:
        profile = order.driver.driver_profile if order.driver else None
    except ObjectDoesNotExist:
        profile = None
    driver_lat = order.driver_lat or (profile.current_lat if profile else None)
    driver_lng = order.driver_lng or (profile.current_lng if profile else None)

    delivery_lat, delivery_lng = order.delivery_lat, order.delivery_lng
    restaurant_lat, restaurant_lng = restaurant.lat, restaurant.lng

    if _valid_point(driver_lat, driver_lng) and _valid_point(delivery_lat, delivery_lng):
        start_label = "driver"
        route = road_route(driver_lat, driver_lng, delivery_lat, delivery_lng)
    elif _valid_point(restaurant_lat, restaurant_lng) and _valid_point(delivery_lat, delivery_lng):
        start_label = "restaurant"
        route = road_route(restaurant_lat, restaurant_lng, delivery_lat, delivery_lng)
    else:
        start_label = "none"
        route = road_route(None, None, None, None)

    return {
        "order": None,  # filled by API serializers where request context is available
        "number": order.number,
        "status": order.status,
        "status_label": order.status_label,
        "updated_at": order.updated_at.isoformat() if hasattr(order, "updated_at") else None,
        "restaurant": {
            "name": restaurant.name,
            "lat": restaurant_lat,
            "lng": restaurant_lng,
            "address": restaurant.address,
        },
        "delivery": {
            "lat": delivery_lat,
            "lng": delivery_lng,
            "address": order.delivery_address,
        },
        "driver": {
            "name": order.driver.display_name if order.driver else "",
            "lat": driver_lat,
            "lng": driver_lng,
            "last_seen": profile.last_seen.isoformat() if profile and profile.last_seen else None,
            "is_available": profile.is_available if profile else False,
        },
        "route": route,
        "route_start": start_label,
    }
