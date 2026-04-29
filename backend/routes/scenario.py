from __future__ import annotations

import os
from math import asin, cos, radians, sin, sqrt
from typing import Any, Dict
from urllib import parse, request
from urllib.error import URLError

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


router = APIRouter()


class ScenarioSimulationRequest(BaseModel):
    start: str
    destination: str
    vehicle_type: str = "van"


def _fetch_json(url: str) -> Dict[str, Any]:
    with request.urlopen(url, timeout=20) as response:
        import json

        return json.loads(response.read().decode("utf-8"))


def _geocode(address: str, api_key: str) -> Dict[str, Any]:
    qs = parse.urlencode({"address": address, "key": api_key})
    data = _fetch_json(f"https://maps.googleapis.com/maps/api/geocode/json?{qs}")
    results = data.get("results", [])
    if data.get("status") != "OK" or not results:
        raise HTTPException(status_code=400, detail=f"Unable to geocode address: {address}")
    result = results[0]
    location = result.get("geometry", {}).get("location", {})
    lat = location.get("lat")
    lng = location.get("lng")
    if lat is None or lng is None:
        raise HTTPException(status_code=400, detail=f"Missing geocode coordinates for: {address}")
    country_code = "SG"
    for comp in result.get("address_components", []):
        if "country" in comp.get("types", []):
            country_code = comp.get("short_name", "SG")
            break
    return {
        "lat": float(lat),
        "lng": float(lng),
        "formatted_address": result.get("formatted_address", address),
        "country_code": country_code,
    }


def _geocode_fallback(address: str) -> Dict[str, Any]:
    # Open-Meteo geocoding is free/no-key and useful for demo fallback.
    qs = parse.urlencode({"name": address, "count": 1, "language": "en", "format": "json"})
    try:
        data = _fetch_json(f"https://geocoding-api.open-meteo.com/v1/search?{qs}")
        results = data.get("results", [])
        if results:
            result = results[0]
            country_code = str(result.get("country_code", "SG")).upper()
            return {
                "lat": float(result.get("latitude")),
                "lng": float(result.get("longitude")),
                "formatted_address": result.get("name", address),
                "country_code": country_code,
            }
    except (URLError, TimeoutError, ValueError):
        pass

    # Offline-safe deterministic fallback for restricted/demo environments.
    seed = sum(ord(ch) for ch in address)
    lat = 1.20 + (seed % 120) / 1000.0
    lng = 103.60 + (seed % 180) / 1000.0
    return {
        "lat": round(lat, 6),
        "lng": round(lng, 6),
        "formatted_address": address,
        "country_code": "SG",
    }


def _distance_matrix(origin: Dict[str, Any], destination: Dict[str, Any], api_key: str, vehicle_type: str) -> Dict[str, Any]:
    vehicle = vehicle_type.lower()
    # Distance Matrix doesn't provide explicit motorcycle mode; we attempt vehicle-aware routing
    # using Directions API first, then fallback to driving matrix with adjustment.
    directions_mode = "driving" if vehicle == "van" else "two_wheeler"
    qs_dir = parse.urlencode(
        {
            "origin": f"{origin['lat']},{origin['lng']}",
            "destination": f"{destination['lat']},{destination['lng']}",
            "mode": directions_mode,
            "departure_time": "now",
            "traffic_model": "best_guess",
            "key": api_key,
        }
    )
    try:
        dir_data = _fetch_json(f"https://maps.googleapis.com/maps/api/directions/json?{qs_dir}")
        if dir_data.get("status") == "OK":
            routes = dir_data.get("routes", [])
            legs = routes[0].get("legs", []) if routes else []
            if legs:
                leg = legs[0]
                distance_m = float(leg.get("distance", {}).get("value", 0))
                duration_s = float(leg.get("duration", {}).get("value", 0))
                duration_in_traffic_s = float(leg.get("duration_in_traffic", {}).get("value", duration_s))
                return {
                    "distance_km": round(distance_m / 1000.0, 2),
                    "duration_min": round(duration_s / 60.0, 1),
                    "duration_in_traffic_min": round(duration_in_traffic_s / 60.0, 1),
                    "source_mode": directions_mode,
                }
    except Exception:
        pass

    # Fallback to driving matrix and adjust time for motorcycle routing efficiency.
    qs = parse.urlencode(
        {
            "origins": f"{origin['lat']},{origin['lng']}",
            "destinations": f"{destination['lat']},{destination['lng']}",
            "departure_time": "now",
            "traffic_model": "best_guess",
            "key": api_key,
        }
    )
    data = _fetch_json(f"https://maps.googleapis.com/maps/api/distancematrix/json?{qs}")
    if data.get("status") != "OK":
        raise HTTPException(status_code=400, detail="Google Distance Matrix request failed.")
    rows = data.get("rows", [])
    if not rows or not rows[0].get("elements"):
        raise HTTPException(status_code=400, detail="No distance matrix elements returned.")
    element = rows[0]["elements"][0]
    if element.get("status") != "OK":
        raise HTTPException(status_code=400, detail=f"Distance matrix element error: {element.get('status')}")
    distance_m = float(element.get("distance", {}).get("value", 0))
    duration_s = float(element.get("duration", {}).get("value", 0))
    duration_in_traffic_s = float(element.get("duration_in_traffic", {}).get("value", duration_s))
    if vehicle == "motorcycle":
        duration_s *= 0.82
        duration_in_traffic_s *= 0.78
    return {
        "distance_km": round(distance_m / 1000.0, 2),
        "duration_min": round(duration_s / 60.0, 1),
        "duration_in_traffic_min": round(duration_in_traffic_s / 60.0, 1),
        "source_mode": "driving_matrix_adjusted_motorcycle" if vehicle == "motorcycle" else "driving_matrix",
    }


def _distance_fallback(origin: Dict[str, Any], destination: Dict[str, Any], vehicle_type: str) -> Dict[str, Any]:
    # Haversine + conservative city-speed heuristic for demo fallback.
    lat1 = radians(float(origin["lat"]))
    lon1 = radians(float(origin["lng"]))
    lat2 = radians(float(destination["lat"]))
    lon2 = radians(float(destination["lng"]))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    earth_km = 6371.0
    distance_km = earth_km * c

    # 30 km/h urban baseline, then apply a modest traffic multiplier.
    vehicle = vehicle_type.lower()
    speed_kmh = 30.0 if vehicle == "van" else 36.0
    duration_min = (distance_km / speed_kmh) * 60.0
    duration_in_traffic_min = duration_min * (1.2 if vehicle == "van" else 1.1)
    return {
        "distance_km": round(distance_km, 2),
        "duration_min": round(duration_min, 1),
        "duration_in_traffic_min": round(duration_in_traffic_min, 1),
        "source_mode": "offline_fallback",
    }


def _weather(lat: float, lng: float) -> Dict[str, Any]:
    qs = parse.urlencode(
        {
            "latitude": lat,
            "longitude": lng,
            "current": "weather_code",
            "timezone": "auto",
        }
    )
    try:
        data = _fetch_json(f"https://api.open-meteo.com/v1/forecast?{qs}")
        current = data.get("current", {})
        weather_code = int(current.get("weather_code", 0))
    except (URLError, TimeoutError, ValueError):
        # Offline-safe fallback weather code (clear).
        weather_code = 0
    # Open-Meteo weather code mapping simplified for simulator controls.
    if weather_code in {95, 96, 99}:
        weather = "storm"
    elif weather_code in {51, 53, 55, 61, 63, 65, 80, 81, 82}:
        weather = "rain"
    else:
        weather = "clear"
    return {"weather_code": weather_code, "weather": weather}


def _traffic_level(duration_min: float, duration_in_traffic_min: float) -> str:
    if duration_min <= 0:
        return "medium"
    ratio = duration_in_traffic_min / duration_min
    if ratio <= 1.10:
        return "low"
    if ratio <= 1.35:
        return "medium"
    return "high"


def _estimate_demand_index(distance_km: float, traffic_level: str, weather: str) -> Dict[str, Any]:
    traffic_factor = {"low": 0.00, "medium": 0.12, "high": 0.25}.get(traffic_level, 0.12)
    weather_factor = {"clear": 0.00, "rain": 0.08, "storm": 0.16}.get(weather, 0.00)
    distance_factor = min(0.25, max(0.0, (distance_km - 8.0) * 0.006))
    value = 1.0 + traffic_factor + weather_factor + distance_factor
    demand_index = round(min(1.8, max(0.6, value)), 2)
    return {
        "value": demand_index,
        "factors": {
            "traffic_factor": round(traffic_factor, 3),
            "weather_factor": round(weather_factor, 3),
            "distance_factor": round(distance_factor, 3),
        },
        "formula": "1.0 + traffic_factor + weather_factor + distance_factor",
    }


def _estimate_fleet_health_index(distance_km: float, traffic_level: str, weather: str) -> Dict[str, Any]:
    # Higher route stress lowers available fleet health/readiness for this scenario.
    traffic_stress = {"low": 0.03, "medium": 0.08, "high": 0.16}.get(traffic_level, 0.08)
    weather_stress = {"clear": 0.02, "rain": 0.07, "storm": 0.14}.get(weather, 0.02)
    distance_stress = min(0.12, max(0.0, (distance_km - 10.0) * 0.003))
    total_stress = traffic_stress + weather_stress + distance_stress
    value = 0.97 - total_stress
    fleet_health_index = round(min(1.0, max(0.5, value)), 2)
    return {
        "value": fleet_health_index,
        "factors": {
            "traffic_stress": round(traffic_stress, 3),
            "weather_stress": round(weather_stress, 3),
            "distance_stress": round(distance_stress, 3),
            "total_stress": round(total_stress, 3),
        },
        "formula": "0.97 - (traffic_stress + weather_stress + distance_stress)",
    }


@router.post("/simulate")
def simulate_scenario(request_body: ScenarioSimulationRequest):
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    simulation_mode = "google_maps_live" if api_key else "fallback_no_google_key"
    if api_key:
        start = _geocode(request_body.start, api_key=api_key)
        dest = _geocode(request_body.destination, api_key=api_key)
        distance = _distance_matrix(start, dest, api_key=api_key, vehicle_type=request_body.vehicle_type)
    else:
        start = _geocode_fallback(request_body.start)
        dest = _geocode_fallback(request_body.destination)
        distance = _distance_fallback(start, dest, vehicle_type=request_body.vehicle_type)

    weather = _weather(dest["lat"], dest["lng"])
    traffic_level = _traffic_level(distance["duration_min"], distance["duration_in_traffic_min"])
    demand = _estimate_demand_index(distance["distance_km"], traffic_level, weather["weather"])
    fleet = _estimate_fleet_health_index(distance["distance_km"], traffic_level, weather["weather"])

    suggested_payload = {
        "region": dest["country_code"],
        "origin": start["formatted_address"],
        "destination": dest["formatted_address"],
        "weather": weather["weather"],
        "traffic_level": traffic_level,
        "route_distance_km": distance["distance_km"],
        "vehicle_type": request_body.vehicle_type,
        "urgency_mix": "express",
        "demand_index": demand["value"],
        "fleet_health_index": fleet["value"],
    }

    return {
        "status": "ok",
        "simulation_mode": simulation_mode,
        "distance": distance,
        "weather": weather,
        "traffic_level": traffic_level,
        "estimated_indices": {
            "demand_index": demand,
            "fleet_health_index": fleet,
        },
        "suggested_payload": suggested_payload,
    }

