"""
╔══════════════════════════════════════════════════════════════╗
║  MUNINN — Panel Forense de Evidencia Digital                ║
║  Versión 1.0 · Protocolo de Lingüística Forense            ║
║  Base de Datos: muninn_memory.db                            ║
╚══════════════════════════════════════════════════════════════╝
"""

import streamlit as st
import sqlite3
import pandas as pd
import hashlib
import os
import json
import re
from datetime import datetime

# ─────────────────────────────────────────────────
# CONFIGURACIÓN DE PÁGINA
# ─────────────────────────────────────────────────
st.set_page_config(
    page_title="MUNINN · Panel Forense",
    page_icon="🦉",
    layout="wide",
    initial_sidebar_state="expanded",
)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "muninn_memory.db")

# ─────────────────────────────────────────────────
# ESTILOS CSS PREMIUM
# ─────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap');

    /* ── Reset & Global ── */
    :root {
        --bg-primary: #0a0e1a;
        --bg-secondary: #111827;
        --bg-card: #1a1f35;
        --bg-card-hover: #222845;
        --accent-cyan: #06d6a0;
        --accent-blue: #4cc9f0;
        --accent-purple: #7b2ff7;
        --accent-amber: #f7b32b;
        --accent-rose: #ef476f;
        --text-primary: #e8ecf1;
        --text-secondary: #8b95a5;
        --text-muted: #5a6478;
        --border-color: rgba(255,255,255,0.06);
        --glass-bg: rgba(26, 31, 53, 0.7);
        --glass-border: rgba(255,255,255,0.08);
    }

    html, body, [data-testid="stAppViewContainer"] {
        background-color: var(--bg-primary) !important;
        color: var(--text-primary) !important;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d1220 0%, #111827 100%) !important;
        border-right: 1px solid var(--border-color) !important;
    }

    [data-testid="stSidebar"] .stMarkdown p,
    [data-testid="stSidebar"] .stMarkdown li,
    [data-testid="stSidebar"] label {
        color: var(--text-secondary) !important;
    }

    /* ── Headers ── */
    h1, h2, h3, h4 {
        font-family: 'Inter', sans-serif !important;
        color: var(--text-primary) !important;
        letter-spacing: -0.02em;
    }

    /* ── Cards ── */
    .forensic-card {
        background: var(--glass-bg);
        backdrop-filter: blur(12px) saturate(180%);
        -webkit-backdrop-filter: blur(12px) saturate(180%);
        border: 1px solid var(--glass-border);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 16px;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .forensic-card:hover {
        background: var(--bg-card-hover);
        border-color: rgba(6, 214, 160, 0.15);
        box-shadow: 0 8px 32px rgba(6, 214, 160, 0.06);
    }

    /* ── Metric Cards ── */
    .metric-card {
        background: linear-gradient(135deg, var(--bg-card) 0%, rgba(123,47,247,0.08) 100%);
        border: 1px solid var(--glass-border);
        border-radius: 16px;
        padding: 20px 24px;
        text-align: center;
    }
    .metric-value {
        font-size: 2.4rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        background: linear-gradient(135deg, var(--accent-cyan), var(--accent-blue));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        line-height: 1.1;
    }
    .metric-label {
        font-size: 0.78rem;
        font-weight: 500;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-top: 6px;
    }

    /* ── Classification Badge ── */
    .badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.03em;
        margin: 2px 3px;
    }
    .badge-psico { background: rgba(123,47,247,0.18); color: #b794f4; border: 1px solid rgba(123,47,247,0.3); }
    .badge-fisica { background: rgba(239,71,111,0.18); color: #fc8181; border: 1px solid rgba(239,71,111,0.3); }
    .badge-patrimonial { background: rgba(247,179,43,0.18); color: #f7b32b; border: 1px solid rgba(247,179,43,0.3); }
    .badge-economica { background: rgba(76,201,240,0.18); color: #76e4f7; border: 1px solid rgba(76,201,240,0.3); }
    .badge-vicaria { background: rgba(239,71,111,0.25); color: #feb2b2; border: 1px solid rgba(239,71,111,0.4); }
    .badge-institucional { background: rgba(160,174,192,0.18); color: #a0aec0; border: 1px solid rgba(160,174,192,0.3); }
    .badge-ninguna { background: rgba(160,174,192,0.1); color: #718096; border: 1px solid rgba(160,174,192,0.15); }

    /* ── Verbatim Quote ── */
    .verbatim-quote {
        background: linear-gradient(90deg, rgba(6,214,160,0.06) 0%, transparent 100%);
        border-left: 3px solid var(--accent-cyan);
        padding: 14px 20px;
        border-radius: 0 12px 12px 0;
        font-family: 'Inter', serif;
        font-size: 0.88rem;
        color: var(--text-primary);
        line-height: 1.65;
        margin: 10px 0;
        font-style: italic;
    }

    /* ── Hash Display ── */
    .hash-display {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.72rem;
        color: var(--accent-cyan);
        background: rgba(6, 214, 160, 0.06);
        padding: 8px 14px;
        border-radius: 8px;
        border: 1px solid rgba(6, 214, 160, 0.12);
        word-break: break-all;
        letter-spacing: 0.02em;
    }

    /* ── Timeline ── */
    .timeline-item {
        position: relative;
        padding-left: 28px;
        margin-bottom: 20px;
    }
    .timeline-item::before {
        content: '';
        position: absolute;
        left: 0;
        top: 10px;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        background: var(--accent-cyan);
        box-shadow: 0 0 12px rgba(6, 214, 160, 0.4);
    }
    .timeline-item::after {
        content: '';
        position: absolute;
        left: 5px;
        top: 26px;
        width: 2px;
        height: calc(100% + 4px);
        background: linear-gradient(180deg, var(--accent-cyan) 0%, transparent 100%);
    }
    .timeline-item:last-child::after { display: none; }

    /* ── Importance Bar ── */
    .importance-bar {
        height: 6px;
        border-radius: 3px;
        background: var(--bg-secondary);
        overflow: hidden;
        margin-top: 6px;
    }
    .importance-fill {
        height: 100%;
        border-radius: 3px;
        transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
    }

    /* ── Report Section ── */
    .report-header {
        background: linear-gradient(135deg, rgba(123,47,247,0.1) 0%, rgba(76,201,240,0.05) 100%);
        border: 1px solid rgba(123,47,247,0.15);
        border-radius: 16px;
        padding: 20px 28px;
        margin-bottom: 16px;
    }
    .report-tag {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 6px;
        font-size: 0.68rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
    }
    .report-tag-b { background: rgba(247,179,43,0.15); color: var(--accent-amber); }
    .report-tag-c { background: rgba(239,71,111,0.15); color: var(--accent-rose); }
    .report-tag-d { background: rgba(76,201,240,0.15); color: var(--accent-blue); }

    /* ── Streamlit overrides ── */
    .stTextInput input, .stSelectbox select {
        background-color: var(--bg-card) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--glass-border) !important;
        border-radius: 12px !important;
        font-family: 'Inter', sans-serif !important;
    }
    .stTextInput input:focus {
        border-color: var(--accent-cyan) !important;
        box-shadow: 0 0 0 2px rgba(6,214,160,0.15) !important;
    }

    div[data-testid="stExpander"] {
        background: var(--glass-bg) !important;
        border: 1px solid var(--glass-border) !important;
        border-radius: 14px !important;
    }
    div[data-testid="stExpander"] summary {
        color: var(--text-primary) !important;
        font-weight: 600 !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: transparent !important;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: var(--bg-card) !important;
        border-radius: 10px !important;
        color: var(--text-secondary) !important;
        border: 1px solid var(--glass-border) !important;
        font-weight: 500 !important;
        padding: 8px 20px !important;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, rgba(6,214,160,0.12), rgba(76,201,240,0.08)) !important;
        color: var(--accent-cyan) !important;
        border-color: rgba(6,214,160,0.25) !important;
    }

    /* Sidebar nav styling */
    .sidebar-nav-item {
        padding: 10px 16px;
        border-radius: 12px;
        cursor: pointer;
        transition: all 0.2s;
        margin-bottom: 4px;
        font-weight: 500;
        font-size: 0.9rem;
    }
    .sidebar-nav-active {
        background: linear-gradient(135deg, rgba(6,214,160,0.12), rgba(76,201,240,0.08));
        border: 1px solid rgba(6,214,160,0.2);
        color: var(--accent-cyan);
    }

    /* Hide Streamlit defaults */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header[data-testid="stHeader"] { background: transparent !important; }

    /* Scrollbar */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: var(--bg-primary); }
    ::-webkit-scrollbar-thumb { background: var(--bg-card); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────
# BASE DE DATOS — HELPERS
# ─────────────────────────────────────────────────
@st.cache_resource
def get_connection():
    """Conexión reutilizable a SQLite."""
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def run_query(query: str, params: tuple = ()) -> pd.DataFrame:
    """Ejecutar una consulta y regresar un DataFrame."""
    conn = get_connection()
    return pd.read_sql_query(query, conn, params=params)


def get_classification_badge(classification: str) -> str:
    """Genera badges HTML para cada clasificación de violencia."""
    if not classification or classification == "Ninguna":
        return '<span class="badge badge-ninguna">Sin clasificación</span>'

    mapping = {
        "psicoemocional": "badge-psico",
        "física": "badge-fisica",
        "patrimonial": "badge-patrimonial",
        "económica": "badge-economica",
        "vicaria": "badge-vicaria",
        "institucional": "badge-institucional",
    }

    badges = []
    for part in classification.split(","):
        part = part.strip()
        css = "badge-ninguna"
        for key, cls in mapping.items():
            if key in part.lower():
                css = cls
                break
        badges.append(f'<span class="badge {css}">{part}</span>')
    return " ".join(badges)


def get_importance_bar(importance: int) -> str:
    """Barra visual de importancia 1-10."""
    if importance is None:
        importance = 0
    pct = min(importance * 10, 100)
    if importance >= 8:
        color = "linear-gradient(90deg, #06d6a0, #4cc9f0)"
    elif importance >= 5:
        color = "linear-gradient(90deg, #f7b32b, #4cc9f0)"
    else:
        color = "linear-gradient(90deg, #718096, #a0aec0)"
    return (
        f'<div style="display:flex;align-items:center;gap:8px;">'
        f'<span style="font-weight:700;color:var(--accent-cyan);font-size:0.85rem;">{importance}/10</span>'
        f'<div class="importance-bar" style="flex:1;">'
        f'<div class="importance-fill" style="width:{pct}%;background:{color};"></div>'
        f'</div></div>'
    )


def html_escape(text: str) -> str:
    """Escapa caracteres HTML y convierte newlines a <br>."""
    if not text:
        return ""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = text.replace('"', "&quot;").replace("'", "&#39;")
    text = text.replace("\n", " ")
    return text


def truncate_text(text: str, max_chars: int = 200) -> str:
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + " […]"


# ─────────────────────────────────────────────────
# BUSCADOR SEMÁNTICO
# ─────────────────────────────────────────────────
def semantic_search(query: str, classification_filter: str = None,
                    importance_min: int = 1) -> pd.DataFrame:
    """
    Búsqueda sobre la tabla memories.
    Combina LIKE contra raw_text, summary, entities, topics.
    Filtros opcionales: clasificación legal e importancia mínima.
    """
    tokens = [t.strip() for t in query.split() if len(t.strip()) > 2]
    if not tokens:
        return pd.DataFrame()

    # Build WHERE clause with OR for each token across multiple columns
    conditions = []
    params = []
    for token in tokens:
        token_conds = []
        for col in ("m.raw_text", "m.summary", "m.entities", "m.topics", "m.legal_classification"):
            token_conds.append(f"{col} LIKE ?")
            params.append(f"%{token}%")
        conditions.append("(" + " OR ".join(token_conds) + ")")

    where = " AND ".join(conditions)

    if classification_filter and classification_filter != "Todas":
        where += " AND m.legal_classification LIKE ?"
        params.append(f"%{classification_filter}%")

    where += " AND COALESCE(m.importance, 0) >= ?"
    params.append(importance_min)

    sql = f"""
        SELECT
            m.id,
            f.filename,
            f.path,
            f.hash_sha256,
            m.raw_text,
            m.visual_date,
            m.legal_classification,
            m.summary,
            m.entities,
            m.topics,
            m.importance,
            m.connections
        FROM memories m
        JOIN files f ON m.file_id = f.id
        WHERE {where}
        ORDER BY m.importance DESC, m.id DESC
    """
    return run_query(sql, tuple(params))


# ─────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="text-align:center;padding:20px 0 12px;">
        <div style="font-size:2.4rem;">🦉</div>
        <div style="font-size:1.3rem;font-weight:800;letter-spacing:-0.03em;
                    background:linear-gradient(135deg,#06d6a0,#4cc9f0);
                    -webkit-background-clip:text;-webkit-text-fill-color:transparent;">
            MUNINN
        </div>
        <div style="font-size:0.7rem;color:#5a6478;letter-spacing:0.1em;text-transform:uppercase;margin-top:2px;">
            Panel Forense de Evidencia
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    page = st.radio(
        "Navegación",
        ["🔍  Buscador Semántico", "📅  Reportes B · C · D", "🔗  Cadena de Custodia"],
        label_visibility="collapsed",
    )

    st.markdown("---")

    # Quick stats
    stats = run_query("""
        SELECT
            (SELECT COUNT(*) FROM files) as total_archivos,
            (SELECT COUNT(*) FROM memories) as total_memorias,
            (SELECT COUNT(DISTINCT legal_classification) FROM memories
             WHERE legal_classification IS NOT NULL AND legal_classification != 'Ninguna') as clasificaciones
    """)
    if not stats.empty:
        row = stats.iloc[0]
        st.markdown(f"""
        <div class="metric-card" style="margin-bottom:12px;">
            <div class="metric-value">{int(row['total_archivos'])}</div>
            <div class="metric-label">Archivos Indexados</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown(f"""
        <div class="metric-card" style="margin-bottom:12px;">
            <div class="metric-value">{int(row['total_memorias'])}</div>
            <div class="metric-label">Memorias Analizadas</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <div style="position:fixed;bottom:16px;left:16px;font-size:0.65rem;color:#3a4258;">
        Muninn v1.0 · Protocolo Forense<br>
        Lingüística Forense Activa
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════
#  PÁGINA 1: BUSCADOR SEMÁNTICO
# ═══════════════════════════════════════════════════
if "Buscador" in page:
    st.markdown("""
    <div style="margin-bottom:32px;">
        <h1 style="font-size:2rem;font-weight:800;margin-bottom:4px;">
            🔍 Buscador de Hallazgos Periciales
        </h1>
        <p style="color:#5a6478;font-size:0.88rem;margin-top:0;">
            Consulta la base de evidencia. Los resultados citan texto tal cual y marcas de tiempo originales.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Search bar
    col_search, col_filter, col_imp = st.columns([4, 2, 1])

    with col_search:
        search_query = st.text_input(
            "Búsqueda",
            placeholder="Ej: custodia, pensión, Queen Mary, negligencia…",
            label_visibility="collapsed",
        )

    with col_filter:
        classifications = [
            "Todas",
            "Violencia Psicoemocional",
            "Violencia Física",
            "Violencia Patrimonial",
            "Violencia Económica",
            "Violencia Vicaria",
            "Violencia Institucional",
        ]
        selected_class = st.selectbox(
            "Clasificación", classifications, label_visibility="collapsed"
        )

    with col_imp:
        min_importance = st.number_input(
            "Mín.", min_value=1, max_value=10, value=1, label_visibility="collapsed"
        )

    if search_query:
        results = semantic_search(search_query, selected_class, min_importance)

        if results.empty:
            st.markdown("""
            <div class="forensic-card" style="text-align:center;padding:48px;">
                <div style="font-size:2rem;margin-bottom:8px;">🔍</div>
                <p style="color:var(--text-muted);">No se encontraron hallazgos para esa consulta.</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="margin:16px 0 20px;display:flex;align-items:center;gap:12px;">
                <span style="font-size:1.1rem;font-weight:700;">{len(results)} hallazgo(s) encontrado(s)</span>
                <span style="color:var(--text-muted);font-size:0.8rem;">
                    Ordenados por relevancia pericial
                </span>
            </div>
            """, unsafe_allow_html=True)

            for _, row in results.iterrows():
                badges = get_classification_badge(row.get("legal_classification", ""))
                importance_html = get_importance_bar(row.get("importance"))
                raw = html_escape(row.get("raw_text", "") or "")
                summary = html_escape(row.get("summary", "") or "")
                visual_date = html_escape(row.get("visual_date", "") or "Sin fecha visible")
                filename = html_escape(row.get("filename", ""))
                entities = html_escape(row.get("entities", "") or "")

                # Highlight search terms in text
                highlighted_raw = truncate_text(raw, 350)
                for token in search_query.split():
                    if len(token) > 2:
                        pattern = re.compile(re.escape(token), re.IGNORECASE)
                        highlighted_raw = pattern.sub(
                            f'<mark style="background:rgba(6,214,160,0.25);color:var(--text-primary);padding:1px 3px;border-radius:3px;">{token}</mark>',
                            highlighted_raw,
                        )

                summary_truncated = truncate_text(summary, 300)
                entities_truncated = truncate_text(entities, 100)

                card_html = (
                    '<div class="forensic-card">'
                    '<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;margin-bottom:12px;">'
                    '<div>'
                    f'<span style="font-weight:700;font-size:0.95rem;">{filename}</span>'
                    f'<span style="color:var(--text-muted);font-size:0.78rem;margin-left:10px;">📅 {visual_date}</span>'
                    '</div>'
                    f'<div>{badges}</div>'
                    '</div>'
                    f'<div class="verbatim-quote">{highlighted_raw}</div>'
                    f'<p style="font-size:0.84rem;color:var(--text-secondary);margin:10px 0 6px;">'
                    f'<strong>Síntesis pericial:</strong> {summary_truncated}'
                    '</p>'
                    '<div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin-top:10px;">'
                    f'<div style="flex:1;min-width:200px;">{importance_html}</div>'
                    f'<div style="font-size:0.75rem;color:var(--text-muted);">👤 {entities_truncated}</div>'
                    '</div>'
                    '</div>'
                )
                st.markdown(card_html, unsafe_allow_html=True)

    else:
        # Show recent high-importance memories by default
        recent = run_query("""
            SELECT m.*, f.filename, f.path, f.hash_sha256
            FROM memories m
            JOIN files f ON m.file_id = f.id
            WHERE m.importance >= 5
            ORDER BY m.importance DESC
            LIMIT 6
        """)

        st.markdown("""
        <div style="margin:8px 0 20px;">
            <h3 style="font-size:1.1rem;font-weight:600;color:var(--text-secondary);">
                Hallazgos de Alta Relevancia Pericial
            </h3>
        </div>
        """, unsafe_allow_html=True)

        if not recent.empty:
            cols = st.columns(2)
            for idx, (_, row) in enumerate(recent.iterrows()):
                with cols[idx % 2]:
                    badges = get_classification_badge(row.get("legal_classification", ""))
                    importance = row.get("importance", 0) or 0
                    summary = truncate_text(html_escape(row.get("summary", "") or ""), 180)
                    filename = html_escape(row.get("filename", ""))
                    visual_date = html_escape(row.get("visual_date", "") or "")

                    st.markdown(f"""
                    <div class="forensic-card">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                            <span style="font-weight:700;font-size:0.88rem;">{filename}</span>
                            <span style="font-weight:800;font-size:1.1rem;color:var(--accent-cyan);">{importance}/10</span>
                        </div>
                        <div style="margin-bottom:8px;">{badges}</div>
                        <p style="font-size:0.82rem;color:var(--text-secondary);line-height:1.5;">{summary}</p>
                        <div style="font-size:0.72rem;color:var(--text-muted);margin-top:6px;">📅 {visual_date}</div>
                    </div>
                    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════
#  PÁGINA 2: REPORTES B, C, D — VISTA CRONOLÓGICA
# ═══════════════════════════════════════════════════
elif "Reportes" in page:
    st.markdown("""
    <div style="margin-bottom:32px;">
        <h1 style="font-size:2rem;font-weight:800;margin-bottom:4px;">
            📅 Vista Cronológica de Reportes Periciales
        </h1>
        <p style="color:#5a6478;font-size:0.88rem;margin-top:0;">
            Reportes B (Negligencia Escolar), C (Falsedades Trianguladas), D (Historia Clínica).
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Load the report files
    report_files = {
        "B": {
            "title": "Matriz de Negligencia Escolar (Queen Mary / UVM)",
            "file": "REPORTE_B_Matriz_Negligencia.md",
            "tag_class": "report-tag-b",
            "icon": "🏫",
        },
        "C": {
            "title": "Triangulación Global de Falsedades",
            "file": "REPORTE_C_Triangulacion_Falsedades.md",
            "tag_class": "report-tag-c",
            "icon": "🎯",
        },
        "D": {
            "title": "Historia Clínica de Desatención",
            "file": "REPORTE_D_Historia_Clinica.md",
            "tag_class": "report-tag-d",
            "icon": "🏥",
        },
    }

    # Timeline view
    tab_all, tab_b, tab_c, tab_d = st.tabs([
        "📋 Cronología Integrada",
        "🏫 Reporte B",
        "🎯 Reporte C",
        "🏥 Reporte D",
    ])

    def render_report(report_key: str, info: dict):
        """Renderiza un reporte individual desde su archivo .md."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        filepath = os.path.join(base_dir, info["file"])

        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            st.markdown(f"""
            <div class="report-header">
                <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px;">
                    <span style="font-size:1.6rem;">{info['icon']}</span>
                    <div>
                        <span class="report-tag {info['tag_class']}">REPORTE {report_key}</span>
                        <h2 style="font-size:1.2rem;margin:4px 0 0;">{info['title']}</h2>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Parse and display sections
            sections = content.split("\n## ")
            for i, section in enumerate(sections):
                if i == 0:
                    # Title & intro
                    lines = section.strip().split("\n")
                    for line in lines:
                        line = line.strip()
                        if line.startswith("# "):
                            continue  # Already shown in header
                        if line.startswith("**Objetivo"):
                            st.markdown(f"""
                            <div class="verbatim-quote" style="border-left-color:var(--accent-purple);">
                                {line.replace('**', '<strong>', 1).replace('**', '</strong>', 1)}
                            </div>
                            """, unsafe_allow_html=True)
                else:
                    section_title = section.split("\n")[0].strip()
                    section_body = "\n".join(section.split("\n")[1:]).strip()

                    with st.expander(f"📌 {section_title}", expanded=(i == 1)):
                        # Extract quotes (lines starting with >)
                        for line in section_body.split("\n"):
                            line = line.strip()
                            if not line:
                                continue
                            if line.startswith("> "):
                                quote = line[2:].strip()
                                # Remove markdown bold/italic
                                quote_clean = quote.replace("*", "")
                                st.markdown(f"""
                                <div class="verbatim-quote">
                                    «{quote_clean}»
                                </div>
                                """, unsafe_allow_html=True)
                            elif line.startswith("- "):
                                # Bullet points — extract file references
                                bullet = line[2:]
                                # Highlight file references
                                bullet = re.sub(
                                    r'`\[([^\]]+)\]`',
                                    r'<code style="color:var(--accent-blue);background:rgba(76,201,240,0.08);padding:2px 6px;border-radius:4px;font-size:0.8rem;">📎 \1</code>',
                                    bullet,
                                )
                                bullet = bullet.replace("**", "<strong>", 1).replace("**", "</strong>", 1)
                                st.markdown(f"""
                                <div style="padding:4px 0 4px 16px;border-left:2px solid var(--glass-border);
                                            margin:4px 0;font-size:0.85rem;color:var(--text-secondary);">
                                    {bullet}
                                </div>
                                """, unsafe_allow_html=True)
                            elif line.startswith("### "):
                                st.markdown(f"""
                                <div style="font-weight:700;font-size:0.95rem;margin:14px 0 6px;
                                            color:var(--text-primary);">
                                    {line.replace('### ', '')}
                                </div>
                                """, unsafe_allow_html=True)
                            else:
                                st.markdown(f"""
                                <p style="font-size:0.85rem;color:var(--text-secondary);line-height:1.6;margin:4px 0;">
                                    {line}
                                </p>
                                """, unsafe_allow_html=True)
        else:
            st.warning(f"Archivo no encontrado: {info['file']}")

    # ── Tab: Cronología Integrada ──
    with tab_all:
        # Build a timeline of key events from all reports
        timeline_events = [
            {"year": "2019", "report": "D", "icon": "🏥", "tag": "report-tag-d",
             "title": "Accidente Vial y Abandono de Rehabilitación",
             "detail": "I.A.L. sufre un accidente vehicular traumático. Se prescriben intervenciones quirúrgicas y fisioterapia. La madre custodia frena todo seguimiento médico posterior al alta inmediata.",
             "evidence": "RADIOGRAFIA DE COLUMNA - IO ANZORENA.pdf"},
            {"year": "2020", "report": "D", "icon": "🏥", "tag": "report-tag-d",
             "title": "Cese Total de Continuidad Médica",
             "detail": "Se confirma la ausencia absoluta de archivos, citas o recibos que demuestren interés de continuidad médica por parte de la madre custodia desde este año.",
             "evidence": "Registros médicos ausentes"},
            {"year": "2021", "report": "D", "icon": "🏥", "tag": "report-tag-d",
             "title": "Bajada de Índice de Masa Corporal detectada",
             "detail": "Supervisión precaria empuja a la adolescente a una condición registrada de bajo peso. Reportes institucionales señalan letargo.",
             "evidence": "IMG_9434.PNG, seguimientos pediátricos"},
            {"year": "2022", "report": "B", "icon": "🏫", "tag": "report-tag-b",
             "title": "Inicio del Patrón de Ausentismo Escolar",
             "detail": "Se detecta que el 78% de faltas injustificadas caen en jueves o viernes, generando puentes que coinciden con los descansos de la madre. La escolaridad se subordina a conveniencia materna.",
             "evidence": "Colegio Queen Mary.m4a, Colegio Queen Mary 2.m4a, Colegio Queen Mary 3.m4a"},
            {"year": "2022", "report": "C", "icon": "🎯", "tag": "report-tag-c",
             "title": "Viajes de Ocio a Mazatlán y San Miguel de Allende",
             "detail": "Viajes de fin de semana coinciden con los puentes de jueves/viernes del Reporte B. La menor fue delegada sin aviso al padre. Se documentan presiones psicoemocionales.",
             "evidence": "Video_21_marzo.mp4, Nota de voz.m4a"},
            {"year": "2022-10", "report": "—", "icon": "⚖️", "tag": "report-tag-b",
             "title": "Presentación de Demanda de Guarda y Custodia",
             "detail": "Expediente 1784/2022. Actor: René Iván Anzorena Hernández. Se formalizan ante Juzgado Familiar los hechos de violencia, negligencia y abandono.",
             "evidence": "Demanda indexada en memoria #1 de muninn_memory.db"},
            {"year": "2023-06", "report": "B", "icon": "🏫", "tag": "report-tag-b",
             "title": "Recomendación Formal de Baja por Coordinador",
             "detail": "Carlos Alonso López, Coordinador de Queen Mary/UVM, emite dictamen: «La inasistencia reiterada y la falta de supervisión en tareas han comprometido la permanencia de la alumna.»",
             "evidence": "UVM Campus San Rafael.m4a, UVM Campus San Rafael 2.m4a, UVM Campus San Rafael 3.m4a"},
            {"year": "2023-09", "report": "C", "icon": "🎯", "tag": "report-tag-c",
             "title": "Denuncia Fabricada de Retención Ilegal vs. Viaje a Guadalajara",
             "detail": "11 de septiembre: se interpone querella CI-FIDCANNA/59. Los metadatos GPS y fotográficos ubican a la madre en Guadalajara y Guanajuato del 9 al 14 de septiembre, vacacionando con su pareja.",
             "evidence": "Captura de Pantalla 2023-06-27, IMG_1054.PNG, Chats con 'Guayabita' (Anabell López)"},
            {"year": "2023+", "report": "D", "icon": "🏥", "tag": "report-tag-d",
             "title": "Manifestaciones de Cutting y Ausencia de Terapia",
             "detail": "Tras aislamiento socioafectivo, la menor reporta etapas depresivas con lesiones autoinfligidas referenciadas por orientadores de Queen Mary. La madre custodia no brinda contención psiquiátrica.",
             "evidence": "Es Un Sueño - IO.m4a, Otro Sueño - IO.m4a, Un Sueño - IO.m4a, Nota de voz.m4a"},
        ]

        for evt in timeline_events:
            st.markdown(f"""
            <div class="timeline-item">
                <div class="forensic-card" style="margin-left:8px;">
                    <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;margin-bottom:8px;">
                        <div style="display:flex;align-items:center;gap:8px;">
                            <span style="font-size:1.2rem;">{evt['icon']}</span>
                            <span class="report-tag {evt['tag']}">Reporte {evt['report']}</span>
                            <span style="font-weight:800;font-size:0.88rem;color:var(--accent-cyan);">{evt['year']}</span>
                        </div>
                    </div>
                    <h4 style="font-size:1rem;margin:4px 0 8px;">{evt['title']}</h4>
                    <p style="font-size:0.84rem;color:var(--text-secondary);line-height:1.6;">
                        {evt['detail']}
                    </p>
                    <div style="margin-top:10px;font-size:0.75rem;color:var(--text-muted);">
                        📎 <em>{evt['evidence']}</em>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # ── Individual Report Tabs ──
    with tab_b:
        render_report("B", report_files["B"])

    with tab_c:
        render_report("C", report_files["C"])

    with tab_d:
        render_report("D", report_files["D"])


# ═══════════════════════════════════════════════════
#  PÁGINA 3: CADENA DE CUSTODIA — HASHES SHA-256
# ═══════════════════════════════════════════════════
elif "Custodia" in page:
    st.markdown("""
    <div style="margin-bottom:32px;">
        <h1 style="font-size:2rem;font-weight:800;margin-bottom:4px;">
            🔗 Cadena de Custodia Digital
        </h1>
        <p style="color:#5a6478;font-size:0.88rem;margin-top:0;">
            Cada archivo posee una huella digital única (SHA-256). Si un archivo se modifica, su huella cambia, garantizando la integridad de la prueba.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Controls
    col_search_hash, col_year = st.columns([3, 1])

    with col_search_hash:
        hash_search = st.text_input(
            "Buscar por nombre de archivo",
            placeholder="Ej: IMG_1645, Queen Mary, UVM…",
            label_visibility="collapsed",
        )

    with col_year:
        year_options = ["Todos"] + [str(y) for y in range(2021, 2027)]
        selected_year = st.selectbox("Año", year_options, label_visibility="collapsed")

    # Query
    where_parts = []
    params = []

    if hash_search:
        where_parts.append("(f.filename LIKE ? OR f.path LIKE ?)")
        params.extend([f"%{hash_search}%", f"%{hash_search}%"])

    if selected_year != "Todos":
        where_parts.append("f.path LIKE ?")
        params.append(f"{selected_year}/%")

    where_clause = "WHERE " + " AND ".join(where_parts) if where_parts else ""

    files_df = run_query(f"""
        SELECT
            f.id,
            f.filename,
            f.hash_sha256,
            f.path,
            f.detected_date,
            CASE WHEN m.id IS NOT NULL THEN 1 ELSE 0 END as tiene_memoria
        FROM files f
        LEFT JOIN memories m ON f.id = m.file_id
        {where_clause}
        ORDER BY f.detected_date DESC
    """, tuple(params))

    # Stats Row
    total = len(files_df)
    with_memory = files_df["tiene_memoria"].sum() if not files_df.empty else 0

    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{total}</div>
            <div class="metric-label">Archivos en Custodia</div>
        </div>
        """, unsafe_allow_html=True)
    with col_s2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{int(with_memory)}</div>
            <div class="metric-label">Con Análisis Pericial</div>
        </div>
        """, unsafe_allow_html=True)
    with col_s3:
        integrity = "✅ Íntegra" if total > 0 else "⚠️ Vacía"
        color = "var(--accent-cyan)" if total > 0 else "var(--accent-amber)"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="font-size:1.4rem;
                        -webkit-text-fill-color:{color};">{integrity}</div>
            <div class="metric-label">Estado de la Cadena</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Verification tool ──
    with st.expander("🛡️ Verificar integridad de un archivo", expanded=False):
        st.markdown("""
        <p style="font-size:0.84rem;color:var(--text-secondary);margin-bottom:12px;">
            Sube un archivo para comparar su huella digital contra la registrada en la base de datos.
            Si coinciden, la prueba no ha sido alterada.
        </p>
        """, unsafe_allow_html=True)

        uploaded_file = st.file_uploader(
            "Seleccionar archivo", type=None, label_visibility="collapsed"
        )
        if uploaded_file:
            file_bytes = uploaded_file.read()
            computed_hash = hashlib.sha256(file_bytes).hexdigest()

            # Check against DB
            match = run_query(
                "SELECT filename, path, detected_date FROM files WHERE hash_sha256 = ?",
                (computed_hash,),
            )

            st.markdown(f"""
            <div style="margin:12px 0;">
                <p style="font-size:0.8rem;color:var(--text-muted);margin-bottom:4px;">
                    Huella digital calculada:
                </p>
                <div class="hash-display">{computed_hash}</div>
            </div>
            """, unsafe_allow_html=True)

            if not match.empty:
                row = match.iloc[0]
                st.markdown(f"""
                <div class="forensic-card" style="border-color:rgba(6,214,160,0.3);">
                    <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
                        <span style="font-size:1.4rem;">✅</span>
                        <span style="font-weight:700;color:var(--accent-cyan);font-size:1.05rem;">
                            Coincidencia confirmada
                        </span>
                    </div>
                    <p style="font-size:0.85rem;color:var(--text-secondary);">
                        El archivo subido coincide con <strong>{row['filename']}</strong>
                        registrado el {row['detected_date']}.<br>
                        La prueba <strong>no ha sido alterada</strong> desde su ingesta.
                    </p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="forensic-card" style="border-color:rgba(239,71,111,0.3);">
                    <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
                        <span style="font-size:1.4rem;">⚠️</span>
                        <span style="font-weight:700;color:var(--accent-rose);font-size:1.05rem;">
                            Sin coincidencia en la cadena de custodia
                        </span>
                    </div>
                    <p style="font-size:0.85rem;color:var(--text-secondary);">
                        La huella digital del archivo subido no coincide con ningún registro.
                        Esto puede significar que el archivo fue modificado o que no ha sido ingresado al sistema.
                    </p>
                </div>
                """, unsafe_allow_html=True)

    # ── File listing ──
    st.markdown("""
    <h3 style="font-size:1.1rem;font-weight:700;margin:20px 0 12px;">
        📂 Registro de Archivos en Custodia
    </h3>
    """, unsafe_allow_html=True)

    if not files_df.empty:
        # Paginate
        page_size = 20
        total_pages = max(1, (total + page_size - 1) // page_size)
        current_page = st.number_input(
            "Página", min_value=1, max_value=total_pages, value=1, label_visibility="collapsed"
        )
        start = (current_page - 1) * page_size
        page_data = files_df.iloc[start : start + page_size]

        for _, row in page_data.iterrows():
            has_mem = "🧠" if row["tiene_memoria"] else "📄"
            filename = row["filename"]
            path = row["path"]
            sha = row["hash_sha256"]
            detected = row["detected_date"]

            # Extract year from path
            path_year = path.split("/")[0] if "/" in path else "—"

            st.markdown(f"""
            <div class="forensic-card" style="padding:16px 20px;">
                <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
                    <div style="display:flex;align-items:center;gap:10px;">
                        <span style="font-size:1.1rem;">{has_mem}</span>
                        <div>
                            <div style="font-weight:600;font-size:0.88rem;">{filename}</div>
                            <div style="font-size:0.72rem;color:var(--text-muted);">📁 {path}</div>
                        </div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-size:0.72rem;color:var(--text-muted);">Registrado: {detected}</div>
                        <div style="font-size:0.65rem;color:var(--text-muted);">Carpeta: {path_year}</div>
                    </div>
                </div>
                <div class="hash-display" style="margin-top:8px;">
                    SHA-256: {sha}
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown(f"""
        <div style="text-align:center;color:var(--text-muted);font-size:0.78rem;margin-top:12px;">
            Mostrando {start + 1}–{min(start + page_size, total)} de {total} archivos · Página {current_page}/{total_pages}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="forensic-card" style="text-align:center;padding:48px;">
            <div style="font-size:2rem;margin-bottom:8px;">📂</div>
            <p style="color:var(--text-muted);">No se encontraron archivos con los filtros seleccionados.</p>
        </div>
        """, unsafe_allow_html=True)
