# 🎮 Twitch Game Pulse

**Radar de audiencia de videojuegos en Twitch** — Qué juegos están ganando o perdiendo tracción entre streamers y espectadores.

---

## Problema que resuelve

Hoy es difícil saber, sin herramientas de pago (SullyGnome, StreamElements Analytics), qué juegos están creciendo o cayendo en audiencia de Twitch. Detectar ese movimiento a tiempo es la señal que usa la industria para decidir dónde invertir en marketing, patrocinio de streamers o lanzamiento de contenido.

**Twitch Game Pulse** resuelve esto con un dashboard gratuito que muestra en tiempo real qué juegos están ganando tracción, cómo evoluciona su audiencia y qué géneros dominan la plataforma. Además, incluye un **chat con IA** que responde preguntas sobre tus propios datos.

## ¿A quién le sirve?

- **Analistas de marketing y community managers** que necesitan decidir en qué juegos invertir esfuerzo
- **Publishers pequeños/medianos** que buscan dónde patrocinar streamers o lanzar contenido
- **Cualquier persona** que quiera entender las tendencias de audiencia en Twitch sin pagar herramientas

## API utilizada

[Twitch Helix API](https://dev.twitch.tv/docs/api/reference/) — Gratuita, requiere registro de app en dev.twitch.tv y autenticación OAuth (Client Credentials).

**Endpoints utilizados:**
- `POST /oauth2/token` — Obtención de App Access Token
- `GET /helix/games/top` — Juegos con más audiencia actualmente
- `GET /helix/streams` — Streams activos por juego (con `game_id` como filtro)

## Cómo ejecutar

### 1. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 2. Configurar credenciales de Twitch

```bash
copy secrets_ejemplo.toml secrets.toml
```

Edita `secrets.toml` con tus credenciales:

```toml
[Twitch]
client_id = "tu_client_id"
client_secret = "tu_client_secret"
```

> **¿No tienes credenciales?** Registra tu app en https://dev.twitch.tv/console/apps (necesitas 2FA habilitado en tu cuenta de Twitch).

### 3. Generar datos

**Opción A — Datos sintéticos (para demo):**

```bash
python ingesta.py --sintetico
```

**Opción B — Datos reales de Twitch:**

```bash
python ingesta.py
```

> **Nota:** Ejecuta la ingesta una vez al día para acumular datos y construir la serie temporal.

### 4. Construir corpus para el chat RAG

```bash
python preparar_corpus.py
```

### 5. Lanzar la app

```bash
python -m streamlit run app.py
```

La app se abrirá en http://localhost:8501

> **¿No quieres instalar nada?** Prueba la versión hosted: [Twitch Game Pulse — Online](https://twitch-game-pulse-yxsppvdvpqnt9wit6rezxt.streamlit.app)

### 6. (Opcional) Ejecutar el notebook de análisis

```bash
cd notebooks
jupyter notebook eda.ipynb
```

## Estructura del proyecto

```
Twitch Game Pulse/
├── README.md                    # Este archivo
├── requirements.txt             # Dependencias Python
├── .gitignore                   # Secrets, chroma, venv
├── secrets_ejemplo.toml         # Plantilla de credenciales
├── ingesta.py                   # API Twitch → SQLite
├── preparar_corpus.py           # Fichas → ChromaDB
├── diccionario_datos.md         # Diccionario de datos
├── storytelling.md              # Guion de presentación (15 min)
├── data/
│   ├── twitch_pulse.db          # Base de datos SQLite
│   └── chroma/                  # ChromaDB persist
├── notebooks/
│   └── eda.ipynb                # Análisis exploratorio
└── app.py                       # Dashboard Streamlit
```

## Pestañas de la app

| Pestaña | Descripción |
|---------|-------------|
| **📊 Resumen** | KPIs: total viewers, juegos rastreados, streams activos, juego top. Gráfico top 10 + pie distribución |
| **🏅 Ranking** | Tabla sortable con todos los juegos ordenados por viewers |
| **📈 Tendencias** | Gráfico temporal de audiencia por juego, multiselect para comparar |
| **🚀 En subida** | Top 10 juegos con mayor crecimiento % vs semana anterior |
| **ℹ️ Acerca** | Descripción, tecnología, limitaciones, cómo ejecutar |
| **💬 Chat** | Chat RAG que responde preguntas sobre tendencias usando tus datos |

## Chat RAG — Pregúntale a tus datos

El chat usa **Ollama** para generar respuestas basadas en tus propios datos:

1. `preparar_corpus.py` genera fichas de tendencia por juego
2. Las fichas se almacenan en **ChromaDB** con embeddings
3. Al preguntar, ChromaDB recupera las fichas más relevantes
4. Ollama genera una respuesta citando juego y fecha

**Modelos utilizados:**
- Embeddings: `embeddinggemma` (621 MB)
- Generación: `qwen3.5:latest` (6.6 GB)

**Ejemplo de pregunta:** "¿qué shooter tiene más audiencia?"

## Limitaciones importantes

- **Sin histórico retroactivo:** Twitch no ofrece datos históricos de audiencia. La serie temporal solo empieza a construirse desde que ejecutas `ingesta.py` por primera vez.
- **Top 100:** El endpoint `/games/top` devuelve como máximo 100 juegos por petición.
- **Rate limits:** Twitch limita a ~800 peticiones por minuto. `ingesta.py` implementa backoff para manejar errores 429.

## Tecnologías

- **Python 3.14** — Lenguaje principal
- **SQLite** — Almacenamiento local de snapshots
- **Streamlit** — Dashboard interactivo con tema gaming
- **Plotly** — Visualizaciones interactivas
- **ChromaDB** — Base de datos vectorial para RAG
- **Ollama** — LLM local (embeddinggemma + qwen3.6)

## Datos actuales

La base de datos contiene **218 videojuegos** rastreados con datos reales de Twitch (septiembre 2026). La serie temporal crece con cada ejecución de `ingesta.py`.

**Top 5 videojuegos por audiencia (última ingesta 02/09/2026):**
1. GTA V — 130K viewers
2. Minecraft — 121K viewers
3. League of Legends — 110K viewers
4. World of Warcraft — 108K viewers
5. Counter-Strike — 90K viewers

> **Nota:** La categoría más vista de Twitch es "Just Chatting" (562K viewers), pero no es un videojuego — es gente hablando de temas variados. Twitch Game Pulse se enfoca en **videojuegos reales**.

## Autor

Álvaro — Proyecto de verano 2026
