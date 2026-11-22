#!/usr/bin/env python3
"""Lee los GPX de la Expedición Caminos de Lengerke y genera data/route.json.

Por día de trekking calcula: distancia, D+, D−, altura mín/máx, perfil de
elevación (~300 puntos) y la traza remuestreada cada ~50 m (con km acumulado)
para dibujar/animar la ruta en el mapa. Agrega los lugares marcados y los
datos del itinerario (tiempos, noches, costos) para que la página lea todo
de un solo archivo.

Uso: python3 scripts/build_route.py   (sólo librería estándar)
"""
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NS = {"g": "http://www.topografix.com/GPX/1/1"}

SPLIT_VILLANUEVA = (6.672146, -73.174005)  # donde el autor pasó la noche
GUANE = (6.678214, -73.240098)             # parada del autor en Guane (km 6.6)
BUCARAMANGA = (7.1193, -73.1227)

SMOOTH_WINDOW = 5      # puntos del promedio móvil centrado
HYSTERESIS_M = 3.0     # umbral para contar subida/bajada
PROFILE_POINTS = 300
TRACK_STEP_M = 50

ITINERARY = {
    1: {"title": "Los Santos → Villanueva",
        "subtitle": "Bucaramanga → Los Santos en carro; bajada a Jordán y subida a Villanueva",
        "time": "7–8 h", "night": "camping", "night_place": "cerca de Villanueva",
        "cost": None},
    2: {"title": "Villanueva → Barichara",
        "subtitle": "Etapa corta por la meseta hasta Barichara",
        "time": "2,5–3 h", "night": "hotel", "night_place": "Barichara · con desayuno",
        "cost": 60000},
    3: {"title": "Descanso en Barichara",
        "subtitle": "Día libre para recuperar piernas antes de la etapa larga",
        "time": None, "night": "hotel", "night_place": "Barichara · con desayuno",
        "cost": 60000},
    4: {"title": "Barichara → Guane → Zapatoca",
        "subtitle": "Bajada a Guane, cruce del río Suárez por Puente Ruedas y subida a Zapatoca",
        "time": "10–12 h", "night": "camping", "night_place": "Zapatoca",
        "cost": None},
    5: {"title": "Zapatoca → Bucaramanga",
        "subtitle": "Regreso en bus",
        "time": "2–2,5 h", "night": None, "night_place": None, "cost": None,
        "transport": {"mode": "bus", "distance_km": 70}},
}


def read_gpx(path):
    root = ET.parse(path).getroot()
    pts = []
    for p in root.iterfind(".//g:trkpt", NS):
        ele = p.find("g:ele", NS)
        if ele is not None:
            pts.append((float(p.get("lat")), float(p.get("lon")), float(ele.text)))
    meta = root.find("g:metadata", NS)
    author = meta.find("g:author", NS)
    credit = {
        "title": meta.findtext("g:name", "", NS).replace("Wikiloc - ", "", 1),
        "author": author.findtext("g:name", "", NS),
        "author_url": author.find("g:link", NS).get("href"),
        "track_url": meta.find("g:link", NS).get("href"),
    }
    return pts, credit


def haversine(a, b):
    r = 6371008.8
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (math.sin((la2 - la1) / 2) ** 2
         + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(h))


def nearest_index(pts, target):
    return min(range(len(pts)), key=lambda i: haversine(pts[i], target))


def moving_average(vals, w):
    half = w // 2
    out = []
    for i in range(len(vals)):
        seg = vals[max(0, i - half): i + half + 1]
        out.append(sum(seg) / len(seg))
    return out


def gain_loss(ele, threshold):
    """D+/D− con histéresis: sólo cuenta cambios que superan el umbral."""
    up = down = 0.0
    ref = ele[0]
    for e in ele[1:]:
        d = e - ref
        if d >= threshold:
            up += d
            ref = e
        elif d <= -threshold:
            down -= d
            ref = e
    return up, down


def resample(cum, series, xs):
    """Interpola cada serie de `series` en las distancias `xs`."""
    out, j = [], 0
    for x in xs:
        while j < len(cum) - 2 and cum[j + 1] < x:
            j += 1
        span = cum[j + 1] - cum[j] or 1
        t = min(max((x - cum[j]) / span, 0), 1)
        out.append([s[j] + t * (s[j + 1] - s[j]) for s in series])
    return out


def build_day(pts):
    cum = [0.0]
    for a, b in zip(pts, pts[1:]):
        cum.append(cum[-1] + haversine(a, b))
    ele = moving_average([p[2] for p in pts], SMOOTH_WINDOW)
    up, down = gain_loss(ele, HYSTERESIS_M)
    total = cum[-1]

    xs = [total * k / (PROFILE_POINTS - 1) for k in range(PROFILE_POINTS)]
    profile = [[round(x / 1000, 3), round(e)]
               for x, (e,) in zip(xs, resample(cum, [ele], xs))]

    n = max(2, int(total // TRACK_STEP_M) + 1)
    xs = [total * k / (n - 1) for k in range(n)]
    lats, lons = [p[0] for p in pts], [p[1] for p in pts]
    track = [[round(lo, 5), round(la, 5), round(x / 1000, 3)]
             for x, (la, lo) in zip(xs, resample(cum, [lats, lons], xs))]

    stats = {
        "distance_km": round(total / 1000, 1),
        "gain_m": round(up / 10) * 10,
        "loss_m": round(down / 10) * 10,
        "min_ele_m": round(min(ele)),
        "max_ele_m": round(max(ele)),
        "profile": profile,
        "track": track,
    }
    return stats, cum, ele


def place(name, kind, pts, cum, ele, i, day, note=None):
    d = {"name": name, "type": kind, "day": day,
         "lon": round(pts[i][1], 5), "lat": round(pts[i][0], 5),
         "ele": round(ele[i]), "km": round(cum[i] / 1000, 1)}
    if note:
        d["note"] = note
    return d


def main():
    p12, credit12 = read_gpx(ROOT / "gpx/dia1-2.gpx")
    p4, credit4 = read_gpx(ROOT / "gpx/dia4.gpx")
    cut = nearest_index(p12, SPLIT_VILLANUEVA)
    p1, p2 = p12[: cut + 1], p12[cut:]

    d1, c1, e1 = build_day(p1)
    d2, c2, e2 = build_day(p2)
    d4, c4, e4 = build_day(p4)
    jordan = min(range(len(e1)), key=e1.__getitem__)       # fondo del cañón
    ruedas = min(range(len(e4)), key=e4.__getitem__)       # río Suárez
    guane = nearest_index(p4, GUANE)

    places = [
        place("Los Santos", "pueblo", p1, c1, e1, 0, 1, "Inicio del trekking"),
        place("Jordán", "destacado", p1, c1, e1, jordan, 1,
              "Fondo del cañón del Chicamocha · recargar agua"),
        place("Villanueva", "camping", p1, c1, e1, len(p1) - 1, 1,
              "Camping cerca de Villanueva"),
        place("Barichara", "hotel", p2, c2, e2, len(p2) - 1, 2,
              "Hotel con desayuno · 2 noches"),
        place("Guane", "pueblo", p4, c4, e4, guane, 4, "Recargar agua"),
        place("Puente Ruedas", "destacado", p4, c4, e4, ruedas, 4,
              "Cruce del río Suárez"),
        place("Zapatoca", "camping", p4, c4, e4, len(p4) - 1, 4, "Camping"),
    ]

    days = []
    for n in range(1, 6):
        day = {"day": n, **ITINERARY[n]}
        if n in (1, 2, 4):
            day.update({1: d1, 2: d2, 4: d4}[n])
            day["credit"] = 0 if n < 4 else 1
        days.append(day)
    days[4]["transport"]["line"] = [[places[-1]["lon"], places[-1]["lat"]],
                                    [BUCARAMANGA[1], BUCARAMANGA[0]]]

    walk = [d for d in days if "track" in d]
    nights = [d["night"] for d in days if d["night"]]
    summary = {
        "walk_km": round(sum(d["distance_km"] for d in walk), 1),
        "gain_m": sum(d["gain_m"] for d in walk),
        "loss_m": sum(d["loss_m"] for d in walk),
        "days": len(days),
        "nights": len(nights),
        "camping_nights": nights.count("camping"),
        "hotel_nights": nights.count("hotel"),
        "lodging_cost": sum(d["cost"] or 0 for d in days),
    }

    out = {
        "generated_by": "scripts/build_route.py",
        "method": {"smoothing_window_pts": SMOOTH_WINDOW,
                   "hysteresis_m": HYSTERESIS_M,
                   "split_point": list(SPLIT_VILLANUEVA)},
        "summary": summary,
        "credits": [credit12, credit4],
        "places": places,
        "bucaramanga": [BUCARAMANGA[1], BUCARAMANGA[0]],
        "days": days,
    }
    (ROOT / "data").mkdir(exist_ok=True)
    payload = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    (ROOT / "data/route.json").write_text(payload)
    # Copia como script: permite abrir index.html con doble clic (file://),
    # donde el navegador bloquea fetch() de archivos locales.
    (ROOT / "data/route.js").write_text(f"window.ROUTE_DATA={payload};\n")

    for d in walk:
        print(f"Día {d['day']}: {d['distance_km']} km  +{d['gain_m']} / "
              f"-{d['loss_m']} m  [{d['min_ele_m']}–{d['max_ele_m']} m]  "
              f"{len(d['track'])} pts traza")
    for p in places:
        print(f"  {p['name']:<14} día {p['day']} km {p['km']:>5}  {p['ele']} m")
    print(summary)


if __name__ == "__main__":
    main()
