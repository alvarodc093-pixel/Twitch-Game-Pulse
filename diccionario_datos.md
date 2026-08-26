# Diccionario de Datos — Twitch Game Pulse

## Base de datos: `data/twitch_pulse.db` (SQLite)

### Tabla: `juegos`

| Campo | Tipo | Descripción | Origen |
|-------|------|-------------|--------|
| `id` | INTEGER PK | Identificador del juego en Twitch | Twitch API: `/helix/games/top` → `id` |
| `nombre` | TEXT NOT NULL | Nombre del juego | Twitch API: `/helix/games/top` → `name` |
| `box_art_url` | TEXT | URL de la imagen del juego | Twitch API: `/helix/games/top` → `box_art_url` |

### Tabla: `snapshots_audiencia`

| Campo | Tipo | Descripción | Origen |
|-------|------|-------------|--------|
| `id` | INTEGER PK AUTO | Identificador único del snapshot | Generado por `ingesta.py` |
| `juego_id` | INTEGER FK | Referencia al juego (`juegos.id`) | Twitch API: `/helix/streams` → `game_id` |
| `timestamp` | TEXT NOT NULL | Fecha/hora UTC del snapshot (ISO 8601) | `ingesta.py`: `datetime.utcnow().isoformat()` |
| `viewers` | INTEGER NOT NULL | Total de espectadores en streams de ese juego | Agregado: `SUM(stream.viewer_count)` de `/helix/streams` |
| `num_streams` | INTEGER NOT NULL | Número de streams activos para ese juego | `COUNT(*)` de `/helix/streams` |

## Fuentes de datos

- **API:** Twitch Helix API (`https://dev.twitch.tv/helix/docs`)
- **Autenticación:** OAuth 2.0 Client Credentials (App Access Token)
- **Endpoints utilizados:**
  - `POST /oauth2/token` → obtención de token
  - `GET /helix/games/top` → juegos con más audiencia
  - `GET /helix/streams` → streams activos por juego (con `game_id` como filtro)
- **Frecuencia de ingesta:** Manual (`python ingesta.py`) o programada (cron / GitHub Actions)
- **Paginación:** Controlada mediante cursor de Twitch (`pagination.cursor`)
- **Rate limits:** Manejo con backoff exponencial en respuesta HTTP 429

## Limitaciones importantes

- **Sin histórico retroactivo:** Twitch no ofrece datos históricos de audiencia. La serie temporal solo comienza a construirse desde la primera ejecución de `ingesta.py`.
- **Top 100 máximo:** El endpoint `/games/top` devuelve como máximo 100 juegos por petición.
- **Rate limits:** Twitch limita a ~800 peticiones por minuto para Client Credentials. `ingesta.py` implementa backoff para evitar errores 429.
