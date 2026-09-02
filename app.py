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

CATEGORIAS_NO_JUEGOS = [
    "Just Chatting", "IRL", "Slots", "Sports", "Music", "Art",
    "ASMR", "Crypto", "Talk Shows & Podcasts", "DJs", "Poker",
    "Animals, Aquariums, and Zoos", "Co-working & Studying",
    "Pools, Hot Tubs, and Beaches", "Politics", "Software and Game Development",
    "Special Events", "Science & Technology", "Science Technology",
    "Games + Demos", "Retro", "Education",
]

GENROS_CONOCIDOS = {
    "shooter": ["Counter-Strike", "VALORANT", "Apex Legends", "Call of Duty: Warzone",
                "Call of Duty: Modern Warfare 4", "Overwatch", "Rainbow Six Siege",
                "Fortnite", "PUBG: BATTLEGROUNDS", " Battlefield 6", "Delta Force",
                "Hunt: Showdown 1896", "Escape from Tarkov", "Deadlock",
                "Arena Breakout: Infinite", "Tom Clancy's The Division 2"],
    "moba": ["League of Legends", "Dota 2", "Teamfight Tactics"],
    "mmorpg": ["World of Warcraft", "FINAL FANTASY XIV ONLINE", "Albion Online",
               "Black Desert", "Old School RuneScape", "Tibia", "Guildrun"],
    "battle_royale": ["Fortnite", "PUBG: BATTLEGROUNDS", "Apex Legends", "Warzone"],
    "racing": ["F1 25", "iRacing", "Trackmania", "Rocket League"],
    "fighting": ["Street Fighter 6", "Mortal Shell II"],
    "survival": ["Rust", "DayZ", "ARK: Survival Ascended", "Project Zomboid",
                  "Once Human", "Palworld"],
    "horror": ["Dead by Daylight", "Phasmophobia", "Outlast II", "RESIDENT EVIL: requiem"],
    "strategy": ["Age of Empires II", "Heroes of Might and Magic III"],
    "sports": ["NBA 2K27", "EA Sports FC 26"],
}

st.set_page_config(
    page_title="Twitch Game Pulse",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS personalizado - tema gaming / Twitch
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    :root {
        --twitch-purple: #9146FF;
        --twitch-purple-dark: #7B2FCC;
        --twitch-purple-light: #BF94FF;
        --bg-primary: #0E0B16;
        --bg-secondary: #1A1525;
        --bg-card: #231D30;
        --text-primary: #EFEFEF;
        --text-secondary: #ADADB8;
    }

    .stApp {
        background: linear-gradient(135deg, #0E0B16 0%, #1A1525 50%, #150F20 100%);
    }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1A1525 0%, #0E0B16 100%);
        border-right: 1px solid rgba(145, 70, 255, 0.2);
    }

    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stMarkdown h1,
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown h3 {
        color: #EFEFEF;
    }

    .main-header {
        background: linear-gradient(135deg, #9146FF 0%, #7B2FCC 100%);
        padding: 1.5rem 2rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        box-shadow: 0 8px 32px rgba(145, 70, 255, 0.3);
        border: 1px solid rgba(145, 70, 255, 0.4);
    }

    .main-header h1 {
        color: white;
        font-family: 'Inter', sans-serif;
        font-weight: 700;
        font-size: 2rem;
        margin: 0;
        text-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
    }

    .main-header p {
        color: rgba(255, 255, 255, 0.85);
        font-family: 'Inter', sans-serif;
        font-size: 1rem;
        margin: 0.3rem 0 0 0;
    }

    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #231D30 0%, #2A2240 100%);
        border: 1px solid rgba(145, 70, 255, 0.25);
        border-radius: 12px;
        padding: 1.2rem;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }

    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 24px rgba(145, 70, 255, 0.25);
        border-color: rgba(145, 70, 255, 0.5);
    }

    div[data-testid="stMetric"] label {
        color: #BF94FF !important;
        font-weight: 600 !important;
    }

    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: #EFEFEF !important;
        font-weight: 700 !important;
    }

    button[data-baseweb="tab"] {
        font-family: 'Inter', sans-serif;
        font-weight: 500;
        color: #ADADB8;
        border-bottom: 2px solid transparent;
        transition: all 0.2s ease;
    }

    button[data-baseweb="tab"]:hover {
        color: #BF94FF;
    }

    button[data-baseweb="tab"][aria-selected="true"] {
        color: #9146FF;
        border-bottom: 3px solid #9146FF;
        font-weight: 600;
    }

    h2, h3 {
        color: #EFEFEF !important;
        font-family: 'Inter', sans-serif;
    }

    h3 {
        color: #BF94FF !important;
    }

    .stDataFrame {
        border: 1px solid rgba(145, 70, 255, 0.2);
        border-radius: 8px;
        overflow: hidden;
    }

    .stButton > button {
        background: linear-gradient(135deg, #9146FF 0%, #7B2FCC 100%);
        color: white;
        border: none;
        border-radius: 8px;
        font-family: 'Inter', sans-serif;
        font-weight: 600;
        padding: 0.5rem 1.5rem;
        transition: all 0.2s ease;
        box-shadow: 0 4px 12px rgba(145, 70, 255, 0.3);
    }

    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 20px rgba(145, 70, 255, 0.4);
    }

    hr {
        border-color: rgba(145, 70, 255, 0.2);
    }

    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-track { background: #0E0B16; }
    ::-webkit-scrollbar-thumb { background: #9146FF; border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: #BF94FF; }

    .stAlert {
        border-left: 4px solid #9146FF;
        background: rgba(35, 29, 48, 0.8);
        border-radius: 0 8px 8px 0;
    }
</style>
""", unsafe_allow_html=True)


def cargar_datos():
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
        df = df[~df["nombre"].isin(CATEGORIAS_NO_JUEGOS)]
        df["timestamp"] = pd.to_datetime(df["timestamp"], format="ISO8601", utc=True)
        df["fecha"] = df["timestamp"].dt.date
    return df


def obtener_ultimo_snapshot(df):
    if df.empty:
        return pd.DataFrame()
    idx = df.groupby("nombre")["timestamp"].idxmax()
    return df.loc[idx].sort_values("viewers", ascending=False)


def calcular_crecimiento(df, dias=7):
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
        if r["viewers_anterior"] > 0 else 0, axis=1,
    )
    return merged.sort_values("crecimiento_pct", ascending=False)


def header():
    st.markdown("""
    <div style="position: relative; border-radius: 16px; overflow: hidden; margin-bottom: 2rem;
                box-shadow: 0 8px 32px rgba(145, 70, 255, 0.3);">
        <img src="https://images.unsplash.com/photo-1542751371-adc38448a05e?w=1200&q=80"
             style="width: 100%; height: 250px; object-fit: cover; filter: brightness(0.4);">
        <div style="position: absolute; top: 0; left: 0; right: 0; bottom: 0;
                    background: linear-gradient(135deg, rgba(145,70,255,0.85) 0%, rgba(123,47,204,0.7) 50%, rgba(145,70,255,0.6) 100%);
                    display: flex; flex-direction: column; justify-content: center; align-items: center; padding: 2rem;">
            <h1 style="color: white; font-family: 'Inter', sans-serif; font-weight: 700;
                       font-size: 2.5rem; margin: 0; text-shadow: 0 2px 12px rgba(0,0,0,0.5);
                       letter-spacing: -0.5px;">
                🎮 Twitch Game Pulse
            </h1>
            <p style="color: rgba(255,255,255,0.9); font-family: 'Inter', sans-serif;
                      font-size: 1.15rem; margin: 0.5rem 0 0 0; font-weight: 400;
                      text-shadow: 0 1px 4px rgba(0,0,0,0.4);">
                Radar de audiencia de videojuegos en Twitch — Detecta tendencias antes que nadie
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)


def sidebar_filtros(df):
    with st.sidebar:
        st.markdown("""
        <div style="text-align:center; padding: 1rem 0;">
            <span style="font-size: 2.5rem;">🎮</span>
            <h2 style="color: #BF94FF; margin-top: 0.5rem; font-family: Inter, sans-serif;">Game Pulse</h2>
            <p style="color: #ADADB8; font-size: 0.85rem;">Filtros de datos</p>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("---")
        if not df.empty:
            min_date = df["fecha"].min()
            max_date = df["fecha"].max()
            fecha_inicio, fecha_fin = st.date_input(
                "📅 Rango de fechas", value=(min_date, max_date),
                min_value=min_date, max_value=max_date,
            )
        else:
            fecha_inicio, fecha_fin = None, None
        st.markdown("---")
        st.markdown(f"""
        <div style="background: rgba(145,70,255,0.1); border: 1px solid rgba(145,70,255,0.3);
                    border-radius: 8px; padding: 0.8rem; text-align: center;">
            <p style="color: #ADADB8; font-size: 0.8rem; margin: 0;">Última actualización</p>
            <p style="color: #BF94FF; font-size: 0.95rem; margin: 0.2rem 0 0 0; font-weight: 600;">
                {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M')} UTC
            </p>
        </div>
        """, unsafe_allow_html=True)
    return fecha_inicio, fecha_fin


def pestaña_resumen(df):
    if df.empty:
        st.warning("⚠️ No hay datos disponibles. Ejecuta primero: `python ingesta.py`")
        return
    ultimo = obtener_ultimo_snapshot(df)
    total_viewers = ultimo["viewers"].sum()
    total_juegos = len(ultimo)
    total_streams = ultimo["num_streams"].sum()
    juego_top = ultimo.iloc[0] if not ultimo.empty else None

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("👁️ Viewers activos", f"{total_viewers:,.0f}")
    with col2:
        st.metric("🎮 Juegos rastreados", total_juegos)
    with col3:
        st.metric("📡 Streams activos", f"{total_streams:,.0f}")
    with col4:
        if juego_top is not None:
            st.metric("🏆 Juego top", juego_top["nombre"], f"{juego_top['viewers']:,} viewers")

    st.markdown("---")
    col_izq, col_der = st.columns([2, 1])

    with col_izq:
        st.markdown("### 📊 Top 10 juegos por viewers")
        top10 = ultimo.head(10)
        fig = px.bar(top10, x="nombre", y="viewers", color="viewers",
            color_continuous_scale=[[0, "#231D30"], [0.5, "#7B2FCC"], [1, "#BF94FF"]],
            labels={"nombre": "Juego", "viewers": "Viewers"})
        fig.update_layout(xaxis_tickangle=-45, showlegend=False,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#EFEFEF"),
            xaxis=dict(gridcolor="rgba(145,70,255,0.1)"),
            yaxis=dict(gridcolor="rgba(145,70,255,0.1)"))
        st.plotly_chart(fig, use_container_width=True)

    with col_der:
        st.markdown("### 🎯 Distribución top 5")
        top5 = ultimo.head(5).copy()
        fig_pie = px.pie(top5, values="viewers", names="nombre",
            color_discrete_sequence=["#9146FF", "#BF94FF", "#7B2FCC", "#448AFF", "#00C853"])
        fig_pie.update_layout(paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#EFEFEF"),
            showlegend=True, legend=dict(font=dict(color="#ADADB8")))
        fig_pie.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig_pie, use_container_width=True)


def pestaña_ranking(df, fecha_inicio, fecha_fin):
    st.markdown("### 🏅 Ranking de juegos")
    if df.empty:
        st.warning("⚠️ No hay datos disponibles.")
        return
    if fecha_inicio and fecha_fin:
        df_filtrado = df[(df["fecha"] >= fecha_inicio) & (df["fecha"] <= fecha_fin)]
    else:
        df_filtrado = df
    ultimo = obtener_ultimo_snapshot(df_filtrado)
    mostrar = ultimo[["nombre", "viewers", "num_streams", "timestamp"]].copy()
    mostrar.columns = ["Juego", "Viewers", "Streams", "Última actualización"]
    mostrar["Última actualización"] = mostrar["Última actualización"].dt.strftime("%d/%m/%Y %H:%M")
    mostrar = mostrar.reset_index(drop=True)
    mostrar.index = mostrar.index + 1
    mostrar.index.name = "#"
    st.dataframe(mostrar, use_container_width=True)


def pestaña_tendencias(df, fecha_inicio, fecha_fin):
    st.markdown("### 📈 Tendencias de audiencia")
    if df.empty:
        st.warning("⚠️ No hay datos disponibles.")
        return
    nombres_juegos = sorted(df["nombre"].unique())
    juegos_seleccionados = st.multiselect("Selecciona juegos para comparar",
        nombres_juegos, default=nombres_juegos[:3] if len(nombres_juegos) >= 3 else nombres_juegos)
    if not juegos_seleccionados:
        st.info("Selecciona al menos un juego para ver su tendencia.")
        return
    df_filtrado = df[df["nombre"].isin(juegos_seleccionados)]
    if fecha_inicio and fecha_fin:
        df_filtrado = df_filtrado[(df_filtrado["fecha"] >= fecha_inicio) & (df_filtrado["fecha"] <= fecha_fin)]
    df_diario = df_filtrado.groupby(["fecha", "nombre"])["viewers"].mean().reset_index()
    fig = px.line(df_diario, x="fecha", y="viewers", color="nombre",
        labels={"fecha": "Fecha", "viewers": "Viewers (media)", "nombre": "Juego"}, markers=True)
    fig.update_layout(legend_title_text="Juego", paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#EFEFEF"),
        xaxis=dict(gridcolor="rgba(145,70,255,0.1)"), yaxis=dict(gridcolor="rgba(145,70,255,0.1)"))
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("### 📋 Detalle diario")
    tabla_detalle = df_filtrado.pivot_table(index="fecha", columns="nombre",
        values="viewers", aggfunc="mean").fillna(0).astype(int)
    st.dataframe(tabla_detalle, use_container_width=True)


def pestaña_en_subida(df):
    st.markdown("### 🚀 Juegos en subida")
    if df.empty:
        st.warning("⚠️ No hay datos disponibles.")
        return
    crecimiento = calcular_crecimiento(df, dias=7)
    if crecimiento.empty:
        st.info("No hay suficientes datos para calcular crecimiento.")
        return
    st.markdown("#### Top 10 mayor crecimiento (%) — última semana vs anterior")
    top_crecimiento = crecimiento.head(10)
    mostrar = top_crecimiento[["nombre", "viewers_actual", "viewers_anterior", "crecimiento_pct"]].copy()
    mostrar.columns = ["Juego", "Viewers (esta semana)", "Viewers (semana anterior)", "Crecimiento %"]
    mostrar["Crecimiento %"] = mostrar["Crecimiento %"].apply(lambda x: f"{x:+.1f}%")
    mostrar = mostrar.reset_index(drop=True)
    mostrar.index = mostrar.index + 1
    mostrar.index.name = "#"
    st.dataframe(mostrar, use_container_width=True)
    fig = px.bar(top_crecimiento, x="nombre", y="crecimiento_pct", color="crecimiento_pct",
        color_continuous_scale="RdYlGn", labels={"nombre": "Juego", "crecimiento_pct": "Crecimiento %"})
    fig.update_layout(xaxis_tickangle=-45, showlegend=False, paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#EFEFEF"))
    st.plotly_chart(fig, use_container_width=True)


def pestaña_acerca():
    st.markdown("### ℹ️ Acerca del proyecto")
    st.markdown("""
    <div style="background: linear-gradient(135deg, #231D30 0%, #2A2240 100%);
                border: 1px solid rgba(145,70,255,0.25); border-radius: 12px;
                padding: 1.5rem; margin-bottom: 1rem;">
        <h3 style="color: #BF94FF; margin-top: 0;">🎮 Twitch Game Pulse</h3>
        <p style="color: #EFEFEF;"><strong>Radar de audiencia de videojuegos en Twitch</strong></p>
        <p style="color: #ADADB8;">Hoy es difícil saber, sin herramientas de pago (SullyGnome, StreamElements Analytics),
        qué juegos están creciendo o cayendo en audiencia de Twitch. Detectar ese movimiento a tiempo
        es lo que usa la industria para decidir dónde invertir en marketing, patrocinio de streamers
        o lanzamiento de contenido.</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("""
    **¿A quién le sirve?**
    - Analistas de marketing y community managers
    - Publishers pequeños/medianos
    - Cualquier persona que necesite decidir en qué juegos invertir esfuerzo

    **API utilizada:** [Twitch Helix API](https://dev.twitch.tv/helix/docs)

    **Categorías excluidas:** Just Chatting, IRL, Slots, Sports, Music, Art y otras que no son videojuegos.

    **Limitaciones:**
    - Sin histórico retroactivo — la serie temporal empieza desde la primera ejecución
    - Top 100 máximo por petición

    **Cómo ejecutar:**
    ```bash
    pip install -r requirements.txt
    python ingesta.py --sintetico    # datos para demo
    python ingesta.py                # datos reales
    python preparar_corpus.py
    python -m streamlit run app.py
    ```

    **Tecnologías:** Python, SQLite, Streamlit, Plotly, ChromaDB, Ollama
    """)


def pestaña_chat():
    st.markdown("### 💬 Chat — Pregúntale a tus datos")
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
    if st.button("🗑️ Borrar conversación"):
        st.session_state.historial = []
        st.rerun()


def detectar_genero(pregunta):
    pregunta_lower = pregunta.lower()
    for genero, juegos in GENROS_CONOCIDOS.items():
        if genero.replace("_", " ") in pregunta_lower or genero in pregunta_lower:
            return genero, juegos
    return None, []


def generar_respuesta_rag(pregunta, k=3):
    if not os.path.exists(CHROMA_PATH):
        return "No hay corpus. Ejecuta: python preparar_corpus.py"
    genero, juegos_genero = detectar_genero(pregunta)
    try:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        collection = client.get_collection("twitch_games")
        if genero and juegos_genero:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT DATE(MAX(timestamp)) FROM snapshots_audiencia")
            fecha_max = cur.fetchone()[0]
            placeholders = ",".join(["?" for _ in juegos_genero])
            query = f'''
                SELECT j.nombre, s.viewers, s.num_streams
                FROM snapshots_audiencia s
                JOIN juegos j ON j.id = s.juego_id
                WHERE j.nombre IN ({placeholders})
                AND DATE(s.timestamp) = ?
                ORDER BY s.viewers DESC
                LIMIT ?
            '''
            cur.execute(query, juegos_genero + [fecha_max, k])
            rows = cur.fetchall()
            conn.close()
            if not rows:
                return "No encontre juegos de ese genero en los datos."
            respuesta = "**Resultados encontrados:**\n\n"
            for i, (nombre, viewers, streams) in enumerate(rows, 1):
                respuesta += f"**{i}. {nombre}**\n"
                respuesta += f"   - Viewers: {viewers:,}\n"
                respuesta += f"   - Streams: {streams:,}\n\n"
            return respuesta
        else:
            resultados = collection.query(query_texts=[pregunta], n_results=k)
            if not resultados["documents"] or not resultados["documents"][0]:
                return "No encontre informacion relevante."
            docs = resultados["documents"][0]
            respuesta = "**Resultados encontrados:**\n\n"
            for i, doc in enumerate(docs[:k], 1):
                lineas = doc.split("\n")
                nombre = ""
                viewers = ""
                for linea in lineas:
                    if "FICHA DE TENDENCIA" in linea:
                        nombre = linea.replace("FICHA DE TENDENCIA", "").replace("—", "").strip()
                    elif "Viewers actuales" in linea:
                        viewers = linea.split(":")[1].strip()
                if nombre:
                    respuesta += f"**{i}. {nombre}**\n"
                    respuesta += f"   - Viewers: {viewers}\n\n"
            return respuesta
    except Exception as e:
        return f"Error: {e}"


def main():
    header()
    df = cargar_datos()
    fecha_inicio, fecha_fin = sidebar_filtros(df)
    tab_resumen, tab_ranking, tab_tendencias, tab_subida, tab_acerca, tab_chat = st.tabs([
        "📊 Resumen", "🏅 Ranking", "📈 Tendencias", "🚀 En subida", "ℹ️ Acerca", "💬 Chat",
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
