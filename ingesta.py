"""
ingesta.py — Ingesta de datos desde la API de Twitch Helix a SQLite.

Uso:
    python ingesta.py                 # Ingesta real desde la API
    python ingesta.py --sintetico     # Genera datos sintéticos para demo
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

import sqlite3
import time
import toml
import requests
from datetime import datetime, timedelta, timezone
import random

BASE_URL = "https://api.twitch.tv/helix"
DB_PATH = "data/twitch_pulse.db"


def cargar_configuracion():
    """Carga las credenciales de Twitch desde secrets.toml."""
    secrets = toml.load("secrets.toml")
    return secrets["Twitch"]["client_id"], secrets["Twitch"]["client_secret"]


def obtener_token(client_id, client_secret):
    """Obtiene un App Access Token via OAuth Client Credentials."""
    url = "https://id.twitch.tv/oauth2/token"
    params = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials",
    }
    resp = requests.post(url, params=params)
    resp.raise_for_status()
    return resp.json()["access_token"]


def cabeceras(client_id, token):
    """Devuelve las cabeceras necesarias para las peticiones a la API."""
    return {
        "Client-ID": client_id,
        "Authorization": f"Bearer {token}",
    }


def peticion_con_reintentos(url, headers, params=None, max_reintentos=5):
    """Realiza una petición GET con backoff exponencial ante errores 429."""
    for intento in range(max_reintentos):
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code == 429:
            espera = int(resp.headers.get("Retry-After", 2 ** (intento + 1)))
            print(f"  Rate limit alcanzado. Esperando {espera}s...")
            time.sleep(espera)
            continue
        resp.raise_for_status()
        return resp.json()
    raise Exception("Demasiados reintentos por rate limit")


def obtener_top_games(token, client_id, first=100):
    """Obtiene los juegos con más audiencia actualmente (máx. 100)."""
    headers = cabeceras(client_id, token)
    all_games = []
    cursor = None

    while len(all_games) < first:
        params = {"first": min(first - len(all_games), 100)}
        if cursor:
            params["after"] = cursor

        data = peticion_con_reintentos(f"{BASE_URL}/games/top", headers, params)
        games = data.get("data", [])
        if not games:
            break
        all_games.extend(games)
        cursor = data.get("pagination", {}).get("cursor")

    return all_games[:first]


def obtener_streams_por_juego(token, client_id, game_id):
    """Obtiene todos los streams activos de un juego y agrega viewers + streams."""
    headers = cabeceras(client_id, token)
    total_viewers = 0
    total_streams = 0
    cursor = None

    while True:
        params = {"game_id": game_id, "first": 100}
        if cursor:
            params["after"] = cursor

        data = peticion_con_reintentos(f"{BASE_URL}/streams", headers, params)
        streams = data.get("data", [])
        if not streams:
            break

        for s in streams:
            total_viewers += s.get("viewer_count", 0)
        total_streams += len(streams)

        cursor = data.get("pagination", {}).get("cursor")
        if not cursor:
            break

    return total_viewers, total_streams


def inicializar_db(db_path):
    """Crea las tablas si no existen."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS juegos (
            id INTEGER PRIMARY KEY,
            nombre TEXT NOT NULL,
            box_art_url TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS snapshots_audiencia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            juego_id INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            viewers INTEGER NOT NULL,
            num_streams INTEGER NOT NULL,
            FOREIGN KEY (juego_id) REFERENCES juegos(id)
        )
    """)
    conn.commit()
    return conn


def guardar_juego(conn, juego):
    """Inserta o actualiza un juego en la tabla juegos."""
    conn.execute(
        "INSERT OR REPLACE INTO juegos (id, nombre, box_art_url) VALUES (?, ?, ?)",
        (juego["id"], juego["name"], juego.get("box_art_url", "")),
    )
    conn.commit()


def guardar_snapshot(conn, juego_id, viewers, num_streams):
    """Guarda un snapshot de audiencia con timestamp UTC."""
    timestamp = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO snapshots_audiencia (juego_id, timestamp, viewers, num_streams) VALUES (?, ?, ?, ?)",
        (juego_id, timestamp, viewers, num_streams),
    )
    conn.commit()


def ejecutar_ingesta():
    """Ejecuta la ingesta completa desde la API de Twitch."""
    print("=== Twitch Game Pulse — Ingesta de datos ===")
    print(f"Fecha: {datetime.now(timezone.utc).isoformat()}Z\n")

    client_id, client_secret = cargar_configuracion()
    token = obtener_token(client_id, client_secret)
    print("Token OAuth obtenido correctamente.\n")

    conn = inicializar_db(DB_PATH)

    print("Obteniendo top 100 juegos...")
    juegos = obtener_top_games(token, client_id, first=100)
    print(f"  {len(juegos)} juegos obtenidos.\n")

    for i, juego in enumerate(juegos, 1):
        guardar_juego(conn, juego)
        viewers, num_streams = obtener_streams_por_juego(token, client_id, juego["id"])
        guardar_snapshot(conn, juego["id"], viewers, num_streams)
        print(f"  [{i:3d}/{len(juegos)}] {juego['name']:30s} | {viewers:>8,} viewers | {num_streams:>5} streams")

    conn.close()
    print(f"\nIngesta completada. Datos guardados en {DB_PATH}")


def generar_datos_sinteticos(db_path=DB_PATH, dias=14):
    """
    Genera datos sintéticos realistas para demo.
    Simula ~50 juegos reales con patrones de audiencia variados.
    """
    print("=== Twitch Game Pulse — Generando datos SINTÉTICOS ===\n")

    JUEGOS_SIMULADOS = [
        ("Fortnite", 30000, 400), ("League of Legends", 25000, 350),
        ("Valorant", 20000, 300), ("Grand Theft Auto V", 18000, 250),
        ("Minecraft", 15000, 200), ("Counter-Strike 2", 14000, 180),
        ("Apex Legends", 12000, 160), ("Dota 2", 11000, 150),
        ("Overwatch 2", 10000, 130), ("Call of Duty: MW III", 9500, 120),
        ("Rust", 8000, 110), ("PUBG: BATTLEGROUNDS", 7500, 100),
        ("Escape from Tarkov", 7000, 95), ("Dead by Daylight", 6500, 90),
        ("Palworld", 6000, 85), ("Genshin Impact", 5500, 80),
        ("World of Warcraft", 5000, 75), ("Rocket League", 4800, 70),
        ("FIFA 24", 4500, 65), ("Red Dead Redemption 2", 4200, 60),
        ("Cyberpunk 2077", 4000, 55), ("The Sims 4", 3800, 50),
        ("Stardew Valley", 3500, 48), ("Terraria", 3300, 45),
        ("Baldur's Gate 3", 3200, 43), ("Elden Ring", 3000, 40),
        ("Diablo IV", 2800, 38), ("Path of Exile", 2600, 35),
        ("Warframe", 2400, 33), ("Fall Guys", 2200, 30),
        ("Among Us", 2000, 28), ("Hogwarts Legacy", 1800, 25),
        ("Starfield", 1600, 23), ("The Finals", 1500, 22),
        ("Lethal Company", 1400, 20), ("Content Warning", 1300, 19),
        ("Satisfactory", 1200, 18), ("Manor Lords", 1100, 17),
        ("Helldivers 2", 1000, 16), ("Black Myth: Wukong", 950, 15),
        ("Frostpunk 2", 900, 14), ("Hades II", 850, 13),
        ("Silent Hill 2 Remake", 800, 12), ("Dragon Age: The Veilguard", 750, 11),
        ("Metaphor: ReFantazio", 700, 10), ("Plucky Squire", 650, 9),
        ("Astro Bot", 600, 8), ("Deadlock", 550, 7),
        ("Satisfactory 1.0", 500, 6), ("Delta Force", 450, 5),
    ]

    conn = inicializar_db(db_path)
    ahora = datetime.now(timezone.utc)

    print(f"Generando {dias} días de datos para {len(JUEGOS_SIMULADOS)} juegos...\n")

    for dia in range(dias):
        fecha = ahora - timedelta(days=dias - 1 - dia)
        es_fin_semana = fecha.weekday() >= 5

        for nombre, viewers_base, streams_base in JUEGOS_SIMULADOS:
            juego_id = hash(nombre) % 100000

            conn.execute(
                "INSERT OR REPLACE INTO juegos (id, nombre, box_art_url) VALUES (?, ?, ?)",
                (juego_id, nombre, ""),
            )

            factor_dia = 1.0 + (0.15 if es_fin_semana else 0.0)
            factor_tendencia = 1.0 + (dia / dias) * random.uniform(-0.3, 0.5)
            ruido = random.uniform(0.85, 1.15)

            viewers_finales = int(viewers_base * factor_dia * factor_tendencia * ruido)
            streams_finales = max(1, int(streams_base * factor_dia * ruido))

            timestamp = fecha.isoformat()
            conn.execute(
                "INSERT INTO snapshots_audiencia (juego_id, timestamp, viewers, num_streams) VALUES (?, ?, ?, ?)",
                (juego_id, timestamp, viewers_finales, streams_finales),
            )

        conn.commit()
        print(f"  Día {dia + 1:2d}/{dias} — {fecha.strftime('%Y-%m-%d')} ({'fin de semana' if es_fin_semana else 'laborable'})")

    conn.close()
    print(f"\nDatos sintéticos generados en {db_path}")


if __name__ == "__main__":
    if "--sintetico" in sys.argv:
        generar_datos_sinteticos()
    else:
        ejecutar_ingesta()
