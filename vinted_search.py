#!/usr/bin/env python3
"""
vinted_search.py — Buscador de portátiles clásicos con puerto serie / paralelo en Vinted.

Pensado para localizar equipos con RS-232 (DB9) y/o paralelo (DB25/Centronics)
nativos o vía dock, útiles para interfaz con equipos de campo / instrumentación.

IMPORTANTE: Vinted bloquea peticiones automatizadas desde datacenters (Datadome).
Ejecuta este script desde TU máquina / red doméstica, no desde un servidor cloud.

Uso rápido:
    python3 vinted_search.py                      # todo el wishlist, dominio .es
    python3 vinted_search.py --max-price 120      # solo <= 120 EUR
    python3 vinted_search.py --domain www.vinted.com --currency USD
    python3 vinted_search.py --only toughbook     # solo un grupo
    python3 vinted_search.py --query "thinkpad t23" --pages 3
    python3 vinted_search.py --out resultados     # escribe resultados.json y resultados.csv

Requisitos: Python 3.8+ y  `pip install requests`
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import dataclass, asdict, field

try:
    import requests
except ImportError:
    sys.exit("Falta 'requests'. Instala con:  pip install requests")


# --- Wishlist: modelos con serie/paralelo, agrupados por familia -----------------
# Cada grupo es una lista de cadenas de búsqueda. Conviene varias variantes porque
# los vendedores escriben los modelos de mil formas distintas.
WISHLIST: dict[str, list[str]] = {
    "thinkpad_clasicos": [
        "thinkpad 600", "thinkpad 600x", "thinkpad 600e",
        "thinkpad a20", "thinkpad a21", "thinkpad a22",
        "thinkpad t20", "thinkpad t21", "thinkpad t22", "thinkpad t23",
        "thinkpad t30",
        "ibm thinkpad dock", "thinkpad port replicator",
    ],
    "dell_latitude_c": [
        "dell latitude c600", "dell latitude c610", "dell latitude c640",
        "dell latitude cpi", "dell latitude cpx",
    ],
    "toshiba": [
        "toshiba tecra", "toshiba satellite pro", "toshiba tecra 8000",
        "toshiba portege 3",
    ],
    "compaq_armada": [
        "compaq armada", "compaq armada e500", "compaq armada m700",
    ],
    "panasonic_toughbook": [
        "panasonic toughbook cf-27", "panasonic toughbook cf-28",
        "toughbook cf-27", "toughbook cf-28", "panasonic toughbook",
    ],
}

# Términos que sugieren puerto serie/paralelo: solo sirven para puntuar/ordenar,
# NO para descartar (muchos anuncios no lo mencionan aunque lo tengan).
PORT_HINTS = (
    "serie", "serial", "rs232", "rs-232", "db9", "com port",
    "paralelo", "parallel", "db25", "lpt", "centronics",
    "dock", "port replicator", "replicador",
)


@dataclass
class Item:
    id: int
    title: str
    price: float
    currency: str
    brand: str
    size: str
    url: str
    photo: str
    group: str
    query: str
    score: int = 0
    hints: list[str] = field(default_factory=list)


def new_session(domain: str, timeout: int) -> requests.Session:
    """Crea una sesión y visita la home para obtener cookies (access_token_web)."""
    s = requests.Session()
    s.headers.update({
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0 Safari/537.36"),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    })
    r = s.get(f"https://{domain}/", timeout=timeout)
    r.raise_for_status()
    if "access_token_web" not in s.cookies.get_dict():
        # Algunas regiones necesitan una segunda visita para sembrar la cookie.
        s.get(f"https://{domain}/catalog", timeout=timeout)
    return s


def parse_price(raw) -> tuple[float, str]:
    """El campo price ha cambiado de formato; soporta string y objeto."""
    if isinstance(raw, dict):
        amount = raw.get("amount") or raw.get("amount_with_fees") or 0
        try:
            return float(amount), raw.get("currency_code", "")
        except (TypeError, ValueError):
            return 0.0, raw.get("currency_code", "")
    try:
        return float(raw), ""
    except (TypeError, ValueError):
        return 0.0, ""


def score_item(title: str) -> tuple[int, list[str]]:
    low = title.lower()
    found = [h for h in PORT_HINTS if h in low]
    return len(found), found


def search(session: requests.Session, domain: str, query: str, group: str,
           pages: int, per_page: int, max_price: float | None,
           currency: str, timeout: int, delay: float) -> list[Item]:
    out: list[Item] = []
    for page in range(1, pages + 1):
        params = {
            "search_text": query,
            "per_page": per_page,
            "page": page,
            "order": "newest_first",
        }
        if max_price is not None:
            params["price_to"] = max_price
            params["currency"] = currency
        url = f"https://{domain}/api/v2/catalog/items"
        for attempt in range(4):
            try:
                r = session.get(url, params=params, timeout=timeout)
                if r.status_code == 401:
                    # cookie expirada: re-sembrar
                    session.get(f"https://{domain}/", timeout=timeout)
                    continue
                if r.status_code in (403, 429):
                    wait = 2 ** attempt
                    print(f"  [{r.status_code}] backoff {wait}s ({query} p{page})",
                          file=sys.stderr)
                    time.sleep(wait)
                    continue
                r.raise_for_status()
                break
            except requests.RequestException as e:
                if attempt == 3:
                    print(f"  fallo '{query}' p{page}: {e}", file=sys.stderr)
                    return out
                time.sleep(2 ** attempt)
        else:
            continue

        items = r.json().get("items", [])
        if not items:
            break
        for it in items:
            price, cur = parse_price(it.get("price"))
            title = it.get("title", "")
            score, hints = score_item(title)
            out.append(Item(
                id=it.get("id"),
                title=title,
                price=price,
                currency=cur or currency,
                brand=it.get("brand_title", ""),
                size=it.get("size_title", ""),
                url=it.get("url", ""),
                photo=(it.get("photo") or {}).get("url", "") if isinstance(it.get("photo"), dict) else "",
                group=group,
                query=query,
                score=score,
                hints=hints,
            ))
        time.sleep(delay)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Buscador de portátiles clásicos en Vinted")
    ap.add_argument("--domain", default="www.vinted.es",
                    help="Dominio Vinted (www.vinted.es, www.vinted.fr, www.vinted.com, ...)")
    ap.add_argument("--currency", default="EUR")
    ap.add_argument("--max-price", type=float, default=None, help="Precio máximo")
    ap.add_argument("--pages", type=int, default=2, help="Páginas por búsqueda")
    ap.add_argument("--per-page", type=int, default=48)
    ap.add_argument("--only", help="Limitar a un grupo del wishlist (p.ej. toughbook)")
    ap.add_argument("--query", help="Búsqueda única en vez del wishlist")
    ap.add_argument("--timeout", type=int, default=25)
    ap.add_argument("--delay", type=float, default=1.0, help="Pausa entre páginas (s)")
    ap.add_argument("--out", help="Prefijo de salida: escribe <out>.json y <out>.csv")
    args = ap.parse_args()

    # Construir lista de (grupo, query)
    jobs: list[tuple[str, str]] = []
    if args.query:
        jobs = [("custom", args.query)]
    else:
        for group, queries in WISHLIST.items():
            if args.only and args.only.lower() not in group:
                continue
            jobs += [(group, q) for q in queries]
    if not jobs:
        print("Nada que buscar (¿--only no coincide?)", file=sys.stderr)
        return 1

    print(f"Sembrando sesión en {args.domain} ...", file=sys.stderr)
    try:
        session = new_session(args.domain, args.timeout)
    except requests.RequestException as e:
        print(f"No pude inicializar sesión: {e}", file=sys.stderr)
        print("Si ves 403: Vinted bloquea IPs de datacenter. Ejecuta desde tu red.",
              file=sys.stderr)
        return 2

    seen: dict[int, Item] = {}
    for group, q in jobs:
        print(f"-> {group}: '{q}'", file=sys.stderr)
        for item in search(session, args.domain, q, group, args.pages,
                           args.per_page, args.max_price, args.currency,
                           args.timeout, args.delay):
            if item.id and item.id not in seen:
                seen[item.id] = item

    results = sorted(seen.values(), key=lambda x: (-x.score, x.price))
    print(f"\n{len(results)} anuncios únicos encontrados.\n")

    for it in results:
        tag = f" [serie/paralelo? {','.join(it.hints)}]" if it.hints else ""
        print(f"{it.price:>7.2f} {it.currency}  {it.title[:60]:<60}{tag}")
        print(f"         {it.url}")

    if args.out:
        with open(f"{args.out}.json", "w", encoding="utf-8") as f:
            json.dump([asdict(i) for i in results], f, ensure_ascii=False, indent=2)
        with open(f"{args.out}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["price", "currency", "title", "brand", "size",
                        "group", "score", "hints", "url"])
            for i in results:
                w.writerow([i.price, i.currency, i.title, i.brand, i.size,
                            i.group, i.score, "|".join(i.hints), i.url])
        print(f"\nGuardado: {args.out}.json y {args.out}.csv", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
