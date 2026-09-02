"""
preparar_corpus.py — Genera fichas de tendencia por juego y las almacena en ChromaDB.

Uso:
    python preparar_corpus.py

Requiere que exista data/twitch_pulse.db con datos de ingesta.py.
"""

import sqlite3
import os
import chromadb
from datetime import datetime, timezone

DB_PATH = "data/twitch_pulse.db"
CHROMA_PATH = "data/chroma"


def obtener_snapshots(db_path, dias=7):
    """Obtiene los snapshots de los últimos N días de cada juego."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    cutoff = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    from datetime import timedelta
    cutoff = cutoff - timedelta(days=dias)

    query = """
        SELECT s.juego_id, j.nombre, s.timestamp, s.viewers, s.num_streams
        FROM snapshots_audiencia s
        JOIN juegos j ON s.juego_id = j.id
        WHERE s.timestamp >= ?
        ORDER BY j.nombre, s.timestamp
    """
    rows = conn.execute(query, (cutoff.isoformat(),)).fetchall()
    conn.close()
    return rows


def calcular_tendencia(snapshots_juego):
    """Calcula la tendencia de un juego basándose en sus snapshots recientes."""
    if len(snapshots_juego) < 2:
        return "sin datos", 0.0

    viewers = [s["viewers"] for s in snapshots_juego]
    mitad = len(viewers) // 2
    primera_mitad = sum(viewers[:mitad]) / max(mitad, 1)
    segunda_mitad = sum(viewers[mitad:]) / max(len(viewers) - mitad, 1)

    if primera_mitad == 0:
        return "sin datos", 0.0

    cambio_pct = ((segunda_mitad - primera_mitad) / primera_mitad) * 100

    if cambio_pct > 10:
        return "creciente", cambio_pct
    elif cambio_pct < -10:
        return "decreciente", cambio_pct
    else:
        return "estable", cambio_pct


def generar_ficha(nombre, snapshots_juego, tendencia, cambio_pct):
    """Genera una ficha de texto descriptiva para un juego."""
    viewers_actual = snapshots_juego[-1]["viewers"]
    streams_actual = snapshots_juego[-1]["num_streams"]
    fecha_ultima = snapshots_juego[-1]["timestamp"][:10]

    viewers_max = max(s["viewers"] for s in snapshots_juego)
    viewers_min = min(s["viewers"] for s in snapshots_juego)

    ficha = f"""FICHA DE TENDENCIA — {nombre}
Fecha de consulta: {fecha_ultima}
Viewers actuales: {viewers_actual:,}
Streams activos: {streams_actual}
Tendencia: {tendencia} ({cambio_pct:+.1f}%)
Viewers máximos (período): {viewers_max:,}
Viewers mínimos (período): {viewers_min:,}
Número de snapshots analizados: {len(snapshots_juego)}
Resumen: El juego "{nombre}" tiene actualmente {viewers_actual:,} espectadores en {streams_actual} streams. 
Su tendencia es {tendencia} con un cambio del {cambio_pct:+.1f}% en el período analizado.
El rango de viewers fue entre {viewers_min:,} y {viewers_max:,}."""

    return ficha


def construir_corpus(db_path=DB_PATH, chroma_path=CHROMA_PATH):
    """Construye el corpus completo de fichas en ChromaDB."""
    print("=== Twitch Game Pulse — Construcción de corpus ===\n")

    if not os.path.exists(db_path):
        print(f"Error: No se encontró {db_path}")
        print("Ejecuta primero: python ingesta.py")
        return

    snapshots = obtener_snapshots(db_path, dias=14)
    if not snapshots:
        print("No hay datos suficientes. Ejecuta ingesta.py primero.")
        return

    # Agrupar por juego_id para evitar duplicados
    juegos = {}
    for s in snapshots:
        juego_id = s["juego_id"]
        if juego_id not in juegos:
            juegos[juego_id] = {"nombre": s["nombre"], "snaps": []}
        juegos[juego_id]["snaps"].append(s)

    print(f"Juegos únicos encontrados: {len(juegos)}")

    os.makedirs(chroma_path, exist_ok=True)
    client = chromadb.PersistentClient(path=chroma_path)

    try:
        client.delete_collection("twitch_games")
    except Exception:
        pass

    collection = client.create_collection(
        name="twitch_games",
        metadata={"hnsw:space": "cosine"},
    )

    fichas = []
    ids = []
    metadatas = []

    for juego_id, data in juegos.items():
        nombre = data["nombre"]
        snaps = data["snaps"]
        tendencia, cambio_pct = calcular_tendencia(snaps)
        ficha = generar_ficha(nombre, snaps, tendencia, cambio_pct)

        fichas.append(ficha)
        ids.append(f"juego_{juego_id}")
        metadatas.append({
            "nombre": nombre,
            "tendencia": tendencia,
            "cambio_pct": round(cambio_pct, 1),
            "viewers_actual": snaps[-1]["viewers"],
            "streams_actual": snaps[-1]["num_streams"],
            "fecha": snaps[-1]["timestamp"][:10],
        })

    batch_size = 100
    for i in range(0, len(fichas), batch_size):
        batch_fichas = fichas[i:i + batch_size]
        batch_ids = ids[i:i + batch_size]
        batch_meta = metadatas[i:i + batch_size]
        collection.add(documents=batch_fichas, ids=batch_ids, metadatas=batch_meta)

    print(f"Corpus construido: {len(fichas)} fichas en ChromaDB")
    print(f"Persistido en: {chroma_path}")
    print("\nListo para usar con el chat en app.py")


if __name__ == "__main__":
    construir_corpus()
