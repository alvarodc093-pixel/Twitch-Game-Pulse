"""
app.py — Dashboard de Twitch Game Pulse con Streamlit.

Pestañas: Resumen, Ranking, Tendencias, En subida, Acerca del proyecto, Chat.

Ejecutar: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
import os
import chromadb
import ollama
from datetime import datetime, timedelta, timezone

DB_PATH = "data/twitch_pulse.db"
CHROMA_PATH = "data/chroma"

st.set_page_config(
    page_title="Twitch Game Pulse",
    page_icon="🎮",
    layout="wide",
)


def cargar_datos():
    """Carga los snapshots de la base de datos y los devuelve como DataFrame."""
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT s.id, s.juego_id, j.nombre, s.timestamp, s.viewers, s.num_streams
        FROM snapshots_audiencia s
        JOIN juegos j ON s.juego_id = j.id
        ORDER BY s.timestamp DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"], format="ISO8601", utc=True)
        df["fecha"] = df["timestamp"].dt.date
    return df


def obtener_ultimo_snapshot(df):
    """Obtiene el snapshot más reciente por juego."""
    if df.empty:
        return pd.DataFrame()
    idx = df.groupby("nombre")["timestamp"].idxmax()
    return df.loc[idx].sort_values("viewers", ascending=False)


def calcular_crecimiento(df, dias=7):
    """Calcula el crecimiento % entre la última semana y la anterior."""
    if df.empty:
        return pd.DataFrame()

    ahora = df["timestamp"].max()
    inicio_semana_actual = ahora - timedelta(days=dias)
    inicio_semana_anterior = inicio_semana_actual - timedelta(days=dias)

    semana_actual = df[(df["timestamp"] > inicio_semana_actual) & (df["timestamp"] <= ahora)]
    semana_anterior = df[(df["timestamp"] > inicio_semana_anterior) & (df["timestamp"] <= inicio_semana_actual)]

    agg_actual = semana_actual.groupby("nombre")["viewers"].mean().reset_index()
    agg_actual.columns = ["nombre", "viewers_actual"]

    agg_anterior = semana_anterior.groupby("nombre")["viewers"].mean().reset_index()
    agg_anterior.columns = ["nombre", "viewers_anterior"]

    merged = agg_actual.merge(agg_anterior, on="nombre", how="left")
    merged["viewers_anterior"] = merged["viewers_anterior"].fillna(0)
    merged["crecimiento_pct"] = merged.apply(
        lambda r: ((r["viewers_actual"] - r["viewers_anterior"]) / r["viewers_anterior"] * 100)
        if r["viewers_anterior"] > 0 else 0,
        axis=1,
    )
    return merged.sort_values("crecimiento_pct", ascending=False)


def sidebar_filtros(df):
    """Muestra filtros en la sidebar y devuelve las selecciones."""
    st.sidebar.title("🎮 Twitch Game Pulse")
    st.sidebar.markdown("---")

    if not df.empty:
        min_date = df["fecha"].min()
        max_date = df["fecha"].max()
        fecha_inicio, fecha_fin = st.sidebar.date_input(
            "Rango de fechas",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )
    else:
        fecha_inicio, fecha_fin = None, None

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**Última actualización:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC")

    return fecha_inicio, fecha_fin


def pestaña_resumen(df):
    """Pestaña de resumen con KPIs y top 5."""
    st.header("Resumen")

    if df.empty:
        st.warning("No hay datos disponibles. Ejecuta primero: `python ingesta.py`")
        return

    ultimo = obtener_ultimo_snapshot(df)
    total_viewers = ultimo["viewers"].sum()
    total_juegos = len(ultimo)
    juego_top = ultimo.iloc[0] if not ultimo.empty else None

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total viewers activos", f"{total_viewers:,.0f}")
    with col2:
        st.metric("Juegos rastreados", total_juegos)
    with col3:
        if juego_top is not None:
            st.metric("Juego top", juego_top["nombre"], f"{juego_top['viewers']:,} viewers")

    st.markdown("---")
    st.subheader("Top 10 juegos por viewers")

    top10 = ultimo.head(10)
    fig = px.bar(
        top10,
        x="nombre",
        y="viewers",
        color="viewers",
        color_continuous_scale="viridis",
        labels={"nombre": "Juego", "viewers": "Viewers"},
    )
    fig.update_layout(xaxis_tickangle=-45, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)


def pestaña_ranking(df, fecha_inicio, fecha_fin):
    """Pestaña de ranking con tabla sortable."""
    st.header("Ranking de juegos")

    if df.empty:
        st.warning("No hay datos disponibles.")
        return

    if fecha_inicio and fecha_fin:
        df_filtrado = df[(df["fecha"] >= fecha_inicio) & (df["fecha"] <= fecha_fin)]
    else:
        df_filtrado = df

    ultimo = obtener_ultimo_snapshot(df_filtrado)
    mostrar = ultimo[["nombre", "viewers", "num_streams", "timestamp"]].copy()
    mostrar.columns = ["Juego", "Viewers", "Streams", "Última actualización"]
    mostrar["Última actualización"] = mostrar["Última actualización"].dt.strftime("%Y-%m-%d %H:%M")
    mostrar = mostrar.reset_index(drop=True)
    mostrar.index = mostrar.index + 1
    mostrar.index.name = "#"

    st.dataframe(mostrar, use_container_width=True)


def pestaña_tendencias(df, fecha_inicio, fecha_fin):
    """Pestaña de tendencias con gráfico temporal."""
    st.header("Tendencias de audiencia")

    if df.empty:
        st.warning("No hay datos disponibles.")
        return

    nombres_juegos = sorted(df["nombre"].unique())
    juegos_seleccionados = st.multiselect(
        "Selecciona juegos para comparar",
        nombres_juegos,
        default=nombres_juegos[:3] if len(nombres_juegos) >= 3 else nombres_juegos,
    )

    if not juegos_seleccionados:
        st.info("Selecciona al menos un juego.")
        return

    df_filtrado = df[df["nombre"].isin(juegos_seleccionados)]

    if fecha_inicio and fecha_fin:
        df_filtrado = df_filtrado[(df_filtrado["fecha"] >= fecha_inicio) & (df_filtrado["fecha"] <= fecha_fin)]

    df_diario = (
        df_filtrado.groupby(["fecha", "nombre"])["viewers"]
        .mean()
        .reset_index()
    )

    fig = px.line(
        df_diario,
        x="fecha",
        y="viewers",
        color="nombre",
        labels={"fecha": "Fecha", "viewers": "Viewers (media)", "nombre": "Juego"},
        markers=True,
    )
    fig.update_layout(legend_title_text="Juego")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Detalle diario")
    tabla_detalle = df_filtrado.pivot_table(
        index="fecha",
        columns="nombre",
        values="viewers",
        aggfunc="mean",
    ).fillna(0).astype(int)
    st.dataframe(tabla_detalle, use_container_width=True)


def pestaña_en_subida(df):
    """Pestaña de juegos con mayor crecimiento."""
    st.header("Juegos en subida")

    if df.empty:
        st.warning("No hay datos disponibles.")
        return

    crecimiento = calcular_crecimiento(df, dias=7)

    if crecimiento.empty:
        st.info("No hay suficientes datos para calcular crecimiento.")
        return

    st.subheader("Top 10 mayor crecimiento (%) — última semana vs anterior")

    top_crecimiento = crecimiento.head(10)
    mostrar = top_crecimiento[["nombre", "viewers_actual", "viewers_anterior", "crecimiento_pct"]].copy()
    mostrar.columns = ["Juego", "Viewers (esta semana)", "Viewers (semana anterior)", "Crecimiento %"]
    mostrar["Crecimiento %"] = mostrar["Crecimiento %"].apply(lambda x: f"{x:+.1f}%")
    mostrar = mostrar.reset_index(drop=True)
    mostrar.index = mostrar.index + 1
    mostrar.index.name = "#"

    st.dataframe(mostrar, use_container_width=True)

    fig = px.bar(
        top_crecimiento,
        x="nombre",
        y="crecimiento_pct",
        color="crecimiento_pct",
        color_continuous_scale="RdYlGn",
        labels={"nombre": "Juego", "crecimiento_pct": "Crecimiento %"},
    )
    fig.update_layout(xaxis_tickangle=-45, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)


def pestaña_acerca():
    """Pestaña de información sobre el proyecto."""
    st.header("Acerca del proyecto")

    st.markdown("""
    ### 🎮 Twitch Game Pulse

    **Radar de audiencia de videojuegos en Twitch**

    #### Problema que resuelve
    Hoy es difícil saber, sin herramientas de pago (SullyGnome, StreamElements Analytics),
    qué juegos están creciendo o cayendo en audiencia de Twitch. Detectar ese movimiento a tiempo
    es lo que usa la industria para decidir dónde invertir en marketing, patrocinio de streamers
    o lanzamiento de contenido.

    #### ¿A quién le sirve?
    - Analistas de marketing y community managers
    - Publishers pequeños/medianos
    - Cualquier persona que necesite decidir en qué juegos invertir esfuerzo

    #### API utilizada
    [Twitch Helix API](https://dev.twitch.tv/helix/docs) — Gratuita, requiere registro de app
    en dev.twitch.tv y autenticación OAuth (Client Credentials).

    #### Limitaciones
    - **Sin histórico retroactivo:** Twitch no ofrece datos históricos de audiencia. La serie
      temporal solo empieza a construirse desde que se ejecuta `ingesta.py` por primera vez.
    - **Top 100:** El endpoint `/games/top` devuelve como máximo 100 juegos por petición.

    #### Cómo ejecutar
    ```bash
    # 1. Instalar dependencias
    pip install -r requirements.txt

    # 2. Configurar credenciales
    copy secrets_ejemplo.toml secrets.toml
    # Editar secrets.toml con tus credenciales de Twitch

    # 3. Generar datos (sintéticos o reales)
    python ingesta.py --sintetico   # Para demo
    python ingesta.py               # Datos reales de Twitch

    # 4. Construir corpus para el chat
    python preparar_corpus.py

    # 5. Lanzar la app
    streamlit run app.py
    ```

    #### Tecnologías
    - **Python 3.14** — Lenguaje principal
    - **SQLite** — Almacenamiento local
    - **Streamlit** — Dashboard interactivo
    - **Plotly** — Visualizaciones
    - **ChromaDB** — Base de datos vectorial para RAG
    - **Ollama** — LLM local (embeddinggemma + qwen)
    """)


def pestaña_chat():
    """Pestaña de chat RAG con Ollama + ChromaDB."""
    st.header("Chat — Pregúntale a tus datos")

    if "historial" not in st.session_state:
        st.session_state.historial = []

    k_fichas = st.slider("Número de fichas a recuperar (k)", 1, 10, 3)

    for msg in st.session_state.historial:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    pregunta = st.chat_input("Pregunta sobre tendencias de juegos en Twitch...")

    if pregunta:
        st.session_state.historial.append({"role": "user", "content": pregunta})
        with st.chat_message("user"):
            st.markdown(pregunta)

        with st.chat_message("assistant"):
            with st.spinner("Buscando en los datos..."):
                respuesta = generar_respuesta_rag(pregunta, k_fichas)
            st.markdown(respuesta)

        st.session_state.historial.append({"role": "assistant", "content": respuesta})

    if st.button("Borrar conversación"):
        st.session_state.historial = []
        st.rerun()


def generar_respuesta_rag(pregunta, k=3):
    """Genera una respuesta usando RAG con ChromaDB + Ollama."""
    if not os.path.exists(CHROMA_PATH):
        return "⚠️ No hay corpus disponible. Ejecuta primero: `python preparar_corpus.py`"

    try:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        collection = client.get_collection("twitch_games")

        resultados = collection.query(query_texts=[pregunta], n_results=k)

        if not resultados["documents"] or not resultados["documents"][0]:
            return "No encontré información relevante en los datos."

        contexto = "\n\n".join(resultados["documents"][0])
    except Exception as e:
        return f"Error al consultar ChromaDB: {e}"

    prompt = f"""Eres un analista de audiencia de Twitch. Responde preguntas sobre tendencias
de videojuegos basándote ÚNICAMENTE en los datos proporcionados.

Si los datos no son suficientes para responder, di que no hay información suficiente.
Cita siempre las fuentes (nombre del juego y fecha) cuando sea posible.

DATOS DISPONIBLES:
{contexto}

PREGUNTA: {pregunta}

RESPUESTA (en español, concisa y basada en los datos):"""

    try:
        response = ollama.chat(
            model="qwen3:1.7b",
            messages=[{"role": "user", "content": prompt}],
        )
        return response["message"]["content"]
    except Exception as e:
        return f"Error al conectar con Ollama: {e}\n\nAsegúrate de que Ollama está ejecutándose: `ollama serve`"


def main():
    """Función principal de la app Streamlit."""
    df = cargar_datos()
    fecha_inicio, fecha_fin = sidebar_filtros(df)

    tab_resumen, tab_ranking, tab_tendencias, tab_subida, tab_acerca, tab_chat = st.tabs([
        "Resumen", "Ranking", "Tendencias", "En subida", "Acerca del proyecto", "Chat",
    ])

    with tab_resumen:
        pestaña_resumen(df)

    with tab_ranking:
        pestaña_ranking(df, fecha_inicio, fecha_fin)

    with tab_tendencias:
        pestaña_tendencias(df, fecha_inicio, fecha_fin)

    with tab_subida:
        pestaña_en_subida(df)

    with tab_acerca:
        pestaña_acerca()

    with tab_chat:
        pestaña_chat()


if __name__ == "__main__":
    main()
