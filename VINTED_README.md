# Búsqueda de portátiles clásicos en Vinted

Herramienta para localizar portátiles con **puerto serie (RS-232/DB9)** y/o
**paralelo (DB25/Centronics)** —nativos o vía dock/port replicator— pensados
para interfaz con equipos de campo e instrumentación.

Modelos objetivo:
- **ThinkPad clásicos**: serie 600, A2x (A20/A21/A22), T2x/T30 — muchos con serie + paralelo directo o por dock.
- **Dell Latitude C-series** (C600/C610/C640): serie y paralelo nativos.
- **Toshiba Tecra / Satellite Pro** (2000–2003).
- **Compaq Armada** (E500/M700, 2000–2003).
- **Panasonic Toughbook CF-27/CF-28**: la opción rugerizada, suele conservar serie de verdad.

## Por qué no se ejecuta en la nube

Vinted protege su API con Datadome y **rechaza (403) las IPs de datacenter**.
El entorno de ejecución en la nube, además, tiene `vinted.es` bloqueado por
política de red. Por eso la búsqueda en vivo hay que lanzarla **desde tu propia
máquina / red doméstica**.

## Opción 1 — Enlaces directos (sin instalar nada)

Abre [`vinted_busquedas.md`](./vinted_busquedas.md): enlaces de búsqueda ya
montados, ordenados por novedades. Cambia `.es` por tu país si hace falta.

## Opción 2 — Script (resultados agregados en JSON/CSV)

```bash
pip install requests
python3 vinted_search.py --max-price 150 --out resultados
```

Recorre todo el wishlist, deduplica, **puntúa los anuncios que mencionan
serie/paralelo/dock** y los ordena primero, y escribe `resultados.json` y
`resultados.csv`.

Ejemplos:

```bash
python3 vinted_search.py                       # todo, dominio .es
python3 vinted_search.py --only toughbook      # solo un grupo
python3 vinted_search.py --query "thinkpad t23" --pages 3
python3 vinted_search.py --domain www.vinted.fr --currency EUR
```

> Nota: el puntaje serie/paralelo es orientativo —muchos vendedores no
> describen los puertos aunque el equipo los tenga—. Sirve para priorizar,
> no para descartar.
