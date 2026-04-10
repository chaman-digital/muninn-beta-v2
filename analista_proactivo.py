#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔════════════════════════════════════════════════════════════════════╗
║  ANALISTA PROACTIVO FORENSE — MUNINN V2.3.1 (Pure Local Indexing)  ║
║                                                                    ║
║  Motor de Detección de Patrones con Gemini 1.5 Pro                ║
║  Protocolo: Lingüística Forense (texto verbatim, marcas de       ║
║  tiempo, cero jerga técnica)                                      ║
║                                                                    ║
║  Patrones Objetivo:                                                ║
║    1. Difamación y falsa denuncia                                  ║
║    2. Inacción educativa / negligencia escolar                     ║
║    3. Desacato al régimen de visitas / obstrucción de convivencia  ║
║                                                                    ║
║  Cadena de custodia: SHA-256 obligatorio por hallazgo              ║
╚════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import sqlite3
import hashlib
import json
import time
import re
import traceback
from datetime import datetime
from pathlib import Path

# Configurar salida estándar en UTF-8 para evitar errores de ascii codec con tildes
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

try:
    import ollama
    from ollama import Options
except ImportError:
    print("Error: Paquete 'ollama' no instalado. Ejecute: pip install ollama", flush=True)
    sys.exit(1)

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("Error: Paquete 'google-genai' no instalado. Ejecute: pip install google-genai", flush=True)
    sys.exit(1)

import gc

try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
except ImportError:
    print("Error: Paquete 'Pillow' no instalado. Ejecute: pip install Pillow", flush=True)
    sys.exit(1)

try:
    from mutagen import File as MutagenFile
except ImportError:
    MutagenFile = None

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    from tinytag import TinyTag
except ImportError:
    TinyTag = None

import subprocess
try:
    import docx
except ImportError:
    docx = None


# ═══════════════════════════════════════════════════════════════
#  CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "muninn_memory.db")
METADATA_JSON_PATH = os.path.join(BASE_DIR, "metadata_multimodal.json")

# ── Orden de procesamiento por carpetas (prioridad descendente) ──
# Raíz → 2026 desc. a 2021 → UVM/Legislación → Audios pesados
# NOTA: 'previo a 2015' EXCLUIDO permanentemente (V1.2+)
BATCH_PRIORITY_ORDER = [
    ("Raíz", BASE_DIR, False),
    ("2026", os.path.join(BASE_DIR, "2026"), True),
    ("2025", os.path.join(BASE_DIR, "2025"), True),
    ("2024", os.path.join(BASE_DIR, "2024"), True),
    ("2023", os.path.join(BASE_DIR, "2023"), True),
    ("2022", os.path.join(BASE_DIR, "2022"), True),
    ("2021", os.path.join(BASE_DIR, "2021"), True),
    # ("Previo a 2015", ...) — EXCLUIDO PERMANENTEMENTE
    ("Documentos IO", os.path.join(BASE_DIR, "Documentos IO"), True),
    ("PAGOS PENSIÓN", os.path.join(BASE_DIR, "PAGOS PENSIÓN"), True),
    ("VLV", os.path.join(BASE_DIR, "VLV"), True),
    ("UVM / Queen Mary", os.path.join(BASE_DIR, "Documentos IO", "IO UVM"), True),
    ("Legislación", os.path.join(BASE_DIR, "legislacion"), True),
    ("Grabaciones de Audio", os.path.join(BASE_DIR, "grabaciones de audio"), True),
]

# Archivos que se saltan en el escaneo automático (serán analizados en sesión dedicada)
SKIP_FILES = set()

IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.webp', '.heic'}
AUDIO_EXTS = {'.m4a', '.mp3'}
VIDEO_EXTS = {'.mp4', '.mov'}
DOC_EXTS = {'.pdf'}
TEXT_EXTS = {'.doc', '.docx'}

# NOTA: Carpetas y extensiones excluidas de manera rígida
EXCLUDED_EXTS = {'.txt', '.md', '.db', '.sql', '.py'}
ALL_SUPPORTED = IMAGE_EXTS | AUDIO_EXTS | VIDEO_EXTS | DOC_EXTS | TEXT_EXTS

# ── Protocolo de Ingesta Crítica V2.4B (Ollama Local + Gemini Vision) ──
# Orden estricto: A. Imágenes (Gemini) → B. PDF → C. Textos → D. Audios → E. Videos (Ollama Local)
SUB_BATCH_SIZE_IMAGES = 3       # Tamaño de lotes estricto para imágenes (evitar saturación API)
SUB_BATCH_SIZE_DOCS = 3         # Lotes para PDF y Texto (.doc/docx)
SUB_BATCH_SIZE_MEDIA = 1        # Archivo individual por lote para Audios y Videos

# Modelos Ollama
OLLAMA_MODEL = "gemma4:e4b"

# Control de Tiempo y Memoria
BATCH_PAUSE = 10         # Pausa entre sub-lotes para refrescar RAM (segundos)

# Patrones objetivo de detección
PATRON_DIFAMACION = "difamacion"
PATRON_INACCION_EDUCATIVA = "inaccion_educativa"
PATRON_DESACATO_VISITAS = "desacato_visitas"
PATRON_VIOLENCIA_VICARIA = "violencia_vicaria"
PATRON_ABANDONO_MEDICO = "abandono_medico"
PATRON_ALIENACION = "alienacion_parental"

PATRONES_CATALOG = {
    PATRON_DIFAMACION: {
        "nombre_judicial": "Difamación y Falsa Denuncia ante Autoridad",
        "leyes": [
            "Art. 311 del Código Penal para la CDMX (Difamación)",
            "Art. 309 del Código Penal para la CDMX (Calumnias)",
            "Art. 323 Séptimus del Código Civil para la CDMX (Violencia Familiar)",
        ],
        "tesis_scjn": "Tesis Aislada 1a. CCXLI/2018 — Derecho a la honra y el debido proceso familiar",
    },
    PATRON_INACCION_EDUCATIVA: {
        "nombre_judicial": "Negligencia Educativa e Incumplimiento del Deber de Crianza",
        "leyes": [
            "Art. 3° Constitucional (Derecho a la Educación)",
            "Arts. 57 y 103 de la Ley General de los Derechos de Niñas, Niños y Adolescentes (LGDNNA)",
            "Art. 323, Fracción II del Código Civil para la CDMX (Obligaciones de quien ejerce la patria potestad)",
            "Art. 444, Fracción III del Código Civil para la CDMX (Causales de pérdida de patria potestad por incumplimiento)",
        ],
        "tesis_scjn": "Jurisprudencia 1a./J. 12/2017 — Interés Superior del Menor: alcances y obligaciones educativas",
    },
    PATRON_DESACATO_VISITAS: {
        "nombre_judicial": "Desacato al Régimen de Visitas y Obstrucción de Convivencia",
        "leyes": [
            "Art. 416 del Código Civil para la CDMX (Régimen de convivencia)",
            "Art. 323 Quáter del Código Civil para la CDMX (Derecho de convivencia)",
            "Arts. 23 y 24 de la LGDNNA (Derecho a vivir en familia y a la convivencia)",
        ],
        "tesis_scjn": "Tesis Aislada 1a. CLXXXIV/2015 — La obstrucción reiterada de convivencias como causal de modificación de custodia",
    },
    PATRON_VIOLENCIA_VICARIA: {
        "nombre_judicial": "Violencia Vicaria: instrumentación de la menor para dañar al progenitor",
        "leyes": [
            "Art. 6, Fracción VI de la Ley General de Acceso de las Mujeres a una Vida Libre de Violencia (LGAMVLV) — Violencia Familiar",
            "Art. 323 Séptimus del Código Civil para la CDMX (Alienación Parental)",
            "Art. 444 Bis del Código Civil para la CDMX (Suspensión de patria potestad por conductas de alienación)",
        ],
        "tesis_scjn": "Amparo Directo en Revisión 4496/2022 SCJN — Violencia Vicaria como violencia de género agravada",
    },
    PATRON_ABANDONO_MEDICO: {
        "nombre_judicial": "Omisión de Cuidados Médicos y Abandono Terapéutico",
        "leyes": [
            "Art. 4° Constitucional (Derecho a la salud de niñas, niños y adolescentes)",
            "Arts. 50 y 52 de la LGDNNA (Derecho a la salud y a la protección de la integridad personal)",
            "Art. 323, Fracción II del Código Civil para la CDMX (Alimentos: comprende asistencia médica)",
        ],
        "tesis_scjn": "Tesis 1a. CCCXLII/2014 — Obligatoriedad del tratamiento de salud integral del menor",
    },
    PATRON_ALIENACION: {
        "nombre_judicial": "Alienación Parental e Interferencia en el Vínculo Paterno-Filial",
        "leyes": [
            "Art. 323 Séptimus del Código Civil para la CDMX (Transformación de conciencia del menor)",
            "Art. 444, Fracción VI del Código Civil para la CDMX (Pérdida de patria potestad por alienación)",
            "Art. 12 de la Convención sobre los Derechos del Niño (Derecho del niño a ser escuchado)",
        ],
        "tesis_scjn": "Jurisprudencia 1a./J. 42/2015 — Autonomía Progresiva y peso de la voluntad del menor en la Undécima Época",
    },
}


# ═══════════════════════════════════════════════════════════════
#  UTILIDADES
# ═══════════════════════════════════════════════════════════════

class ConsoleLog:
    """Logger con formato forense para consola."""

    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    END = "\033[0m"

    @staticmethod
    def timestamp():
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @classmethod
    def info(cls, msg):
        print(f"{cls.CYAN}[{cls.timestamp()}]{cls.END} {msg}", flush=True)

    @classmethod
    def success(cls, msg):
        print(f"{cls.GREEN}[{cls.timestamp()}] ✓{cls.END} {msg}", flush=True)

    @classmethod
    def warning(cls, msg):
        print(f"{cls.YELLOW}[{cls.timestamp()}] ⚠{cls.END} {msg}", flush=True)

    @classmethod
    def error(cls, msg):
        print(f"{cls.RED}[{cls.timestamp()}] ✗{cls.END} {msg}", flush=True)

    @classmethod
    def header(cls, msg):
        width = 64
        border = "═" * width
        print(f"\n{cls.BOLD}{cls.BLUE}╔{border}╗{cls.END}", flush=True)
        print(f"{cls.BOLD}{cls.BLUE}║{cls.END}  {msg:<{width - 2}}{cls.BOLD}{cls.BLUE}║{cls.END}", flush=True)
        print(f"{cls.BOLD}{cls.BLUE}╚{border}╝{cls.END}\n", flush=True)

    @classmethod
    def progress(cls, current, total, filename):
        pct = (current / total) * 100 if total > 0 else 0
        bar_len = 30
        filled = int(bar_len * current / total) if total > 0 else 0
        bar = "█" * filled + "░" * (bar_len - filled)
        name_short = filename[:40] + "…" if len(filename) > 40 else filename
        print(f"\r{cls.CYAN}[{bar}] {pct:5.1f}% ({current}/{total}){cls.END} {name_short:<45}", end="", flush=True)


log = ConsoleLog()


def calculate_sha256(filepath: str) -> str | None:
    """Calcula la huella digital SHA-256 de un archivo para la cadena de custodia."""
    sha = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for block in iter(lambda: f.read(8192), b""):
                sha.update(block)
        return sha.hexdigest()
    except Exception as e:
        log.error(f"Error calculando huella digital de {filepath}: {e}")
        return None


def extract_image_exif(filepath: str) -> dict:
    """Extrae metadatos EXIF de una imagen: GPS, fecha de creación, modelo de cámara."""
    metadata = {
        "fecha_creacion": None,
        "coordenadas_gps": None,
        "modelo_dispositivo": None,
        "orientacion": None,
    }
    try:
        img = Image.open(filepath)
        exif_data = img._getexif()
        if not exif_data:
            return metadata

        for tag_id, value in exif_data.items():
            tag_name = TAGS.get(tag_id, tag_id)
            if tag_name == "DateTimeOriginal":
                metadata["fecha_creacion"] = str(value)
            elif tag_name == "Model":
                metadata["modelo_dispositivo"] = str(value)
            elif tag_name == "Orientation":
                metadata["orientacion"] = str(value)
            elif tag_name == "GPSInfo":
                gps = {}
                for gps_tag_id, gps_value in value.items():
                    gps_tag = GPSTAGS.get(gps_tag_id, gps_tag_id)
                    gps[gps_tag] = gps_value
                metadata["coordenadas_gps"] = _parse_gps(gps)

    except Exception:
        pass  # Silently skip files without EXIF
    return metadata


def _parse_gps(gps_info: dict) -> str | None:
    """Convierte datos GPS EXIF a coordenadas legibles."""
    try:
        lat = gps_info.get("GPSLatitude")
        lat_ref = gps_info.get("GPSLatitudeRef", "N")
        lon = gps_info.get("GPSLongitude")
        lon_ref = gps_info.get("GPSLongitudeRef", "W")
        if not lat or not lon:
            return None

        def dms_to_dd(dms):
            d, m, s = [float(x) for x in dms]
            return d + m / 60 + s / 3600

        lat_dd = dms_to_dd(lat) * (-1 if lat_ref == "S" else 1)
        lon_dd = dms_to_dd(lon) * (-1 if lon_ref == "W" else 1)
        return f"{lat_dd:.6f}, {lon_dd:.6f}"
    except Exception:
        return None


def extract_mutagen_metadata(filepath: str) -> dict:
    """Extrae metadatos locales físicos usando mutagen para audio/video (Ruta 2)."""
    metadata = {"fecha_creacion": None, "coordenadas_gps": None, "duracion_sg": None, "formato": None}
    if MutagenFile:
        try:
            audio = MutagenFile(filepath)
            if audio:
                metadata["duracion_sg"] = str(getattr(audio.info, "length", ""))
                
                # Intentar leer GPS si está expuesto en tags
                tags_str = str(audio.tags)
                if "gps" in tags_str.lower():
                    metadata["coordenadas_gps"] = "GPS Tag present"
                    
                metadata["formato"] = str(type(audio).__name__)
        except Exception as e:
            log.warning(f"Error Mutagen en {filepath}: {e}")
    else:
        return extract_media_metadata(filepath)
            
    return metadata

def extract_pdf_texto(filepath: str) -> str:
    """Extrae todo el texto estático de un PDF físicamente usando pypdf (Ruta 2)."""
    texto = ""
    if PdfReader:
        try:
            reader = PdfReader(filepath)
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    texto += t + " "
        except Exception as e:
            log.error(f"Error pypdf al extraer texto de {filepath}: {e}")
    return texto.strip()

def extract_word_texto(filepath: str) -> str:
    """Extrae texto estático de documentos .docx (vía python-docx) y .doc (vía textutil en mac)."""
    texto = ""
    ext = os.path.splitext(filepath)[1].lower()
    
    if ext == '.docx' and docx is not None:
        try:
            doc = docx.Document(filepath)
            for para in doc.paragraphs:
                texto += para.text + "\n"
        except Exception as e:
            log.error(f"Error docx al extraer texto de {filepath}: {e}")
    elif ext == '.doc':
        try:
            # textutil nativo en MacOS
            result = subprocess.run(['textutil', '-convert', 'txt', filepath, '-stdout'], capture_output=True, text=True)
            if result.returncode == 0:
                texto = result.stdout
        except Exception as e:
            log.error(f"Error textutil al extraer texto de {filepath}: {e}")
            
    return texto.strip()

def extract_media_metadata(filepath: str) -> dict:
    """Extrae metadatos de archivos de audio/video Apple."""
    metadata = {"fecha_creacion": None, "coordenadas_gps": None}
    ext = os.path.splitext(filepath)[1].lower()

    if TinyTag and ext in AUDIO_EXTS:
        try:
            tag = TinyTag.get(filepath)
            if tag.year:
                metadata["fecha_creacion"] = str(tag.year)
        except Exception:
            pass

    return metadata


def get_file_type(filepath: str) -> str | None:
    """Determina el tipo de archivo por extensión. Todos los soportados se incluyen."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext in IMAGE_EXTS:
        return "imagen"
    elif ext in AUDIO_EXTS:
        return "audio"
    elif ext in VIDEO_EXTS:
        return "video"
    elif ext in DOC_EXTS:
        return "documento"
    elif ext in TEXT_EXTS:
        return "texto"
    return None


# ═══════════════════════════════════════════════════════════════
#  DESCUBRIMIENTO Y CLASIFICACIÓN DE ARCHIVOS (V2.3.1)
# ═══════════════════════════════════════════════════════════════

def _scan_single_dir(directory: str, recursive: bool, seen_paths: set) -> list[dict]:
    """Escanea un directorio individual y retorna archivos soportados."""
    files = []
    if not os.path.isdir(directory):
        return files

    if recursive:
        for root, dirs, filenames in os.walk(directory):
            dirs[:] = [d for d in dirs if d not in {'.git', '.venv', '__pycache__', 'node_modules', '.DS_Store', 'wiki'}]
            for fname in filenames:
                fpath = os.path.join(root, fname)
                abs_path = os.path.abspath(fpath)
                if abs_path in seen_paths or fname in SKIP_FILES:
                    continue
                ext = os.path.splitext(fname)[1].lower()
                if ext not in ALL_SUPPORTED:
                    continue
                try:
                    size = os.path.getsize(abs_path)
                except OSError:
                    continue
                seen_paths.add(abs_path)
                files.append({
                    "path": abs_path,
                    "relative_path": os.path.relpath(abs_path, BASE_DIR),
                    "filename": fname,
                    "extension": ext,
                    "type": get_file_type(abs_path),
                    "size_bytes": size,
                })
    else:
        try:
            for fname in os.listdir(directory):
                fpath = os.path.join(directory, fname)
                if not os.path.isfile(fpath):
                    continue
                abs_path = os.path.abspath(fpath)
                if abs_path in seen_paths:
                    continue
                ext = os.path.splitext(fname)[1].lower()
                if ext not in ALL_SUPPORTED:
                    continue
                try:
                    size = os.path.getsize(abs_path)
                except OSError:
                    continue
                seen_paths.add(abs_path)
                files.append({
                    "path": abs_path,
                    "relative_path": os.path.relpath(abs_path, BASE_DIR),
                    "filename": fname,
                    "extension": ext,
                    "type": get_file_type(abs_path),
                    "size_bytes": size,
                })
        except OSError:
            pass

    return files


def _classify_by_type(all_files: list[dict]) -> list[tuple[str, int, list[dict]]]:
    """Clasifica archivos por tipo en sub-lotes (Mimetype-Safe V2.4 Local):
    A. Textos Office → B. PDFs → C. Imágenes → D. Audios → E. Videos.
    Dentro de cada categoría: ordenados por tamaño ascendente (menor a mayor KB)."""

    # Separar por tipo 
    textos = [f for f in all_files if f["type"] == "texto"]
    docs = [f for f in all_files if f["type"] == "documento"
            and f["filename"] not in SKIP_FILES]
    images = [f for f in all_files if f["type"] == "imagen"]
    audios = [f for f in all_files if f["type"] == "audio"]
    videos = [f for f in all_files if f["type"] == "video"]

    # Ordenar cada categoría por tamaño ascendente (menor a mayor KB)
    textos.sort(key=lambda f: f["size_bytes"])
    docs.sort(key=lambda f: f["size_bytes"])
    images.sort(key=lambda f: f["size_bytes"])
    audios.sort(key=lambda f: f["size_bytes"])
    videos.sort(key=lambda f: f["size_bytes"])

    # Reportar archivos saltados
    skipped_explicit = [f for f in all_files if f["filename"] in SKIP_FILES]
    if skipped_explicit:
        log.warning(f"  {len(skipped_explicit)} archivo(s) saltados (sesión dedicada):")
        for sf in skipped_explicit:
            log.warning(f"    ▸ {sf['filename']} ({sf['size_bytes'] / (1024*1024):.1f} MB) — Sesión dedicada")

    # Construir sub-lotes
    sub_batches = []
    
    def chunk_list(lst, prefix, batch_size):
        for i in range(0, len(lst), batch_size):
            chunk = lst[i:i + batch_size]
            sub_batches.append((f"{prefix} [{i+1}-{i+len(chunk)}]", batch_size, chunk))
            
    chunk_list(images, "A. Imágenes", SUB_BATCH_SIZE_IMAGES)
    chunk_list(docs, "B. PDF", SUB_BATCH_SIZE_DOCS)
    chunk_list(textos, "C. Textos .doc/.docx", SUB_BATCH_SIZE_DOCS)
    chunk_list(audios, "D. Audios", SUB_BATCH_SIZE_MEDIA)
    chunk_list(videos, "E. Videos", SUB_BATCH_SIZE_MEDIA)

    return sub_batches


def discover_and_classify() -> tuple[list[tuple[str, int, list[dict]]], dict]:
    """Fase 1 del Protocolo V2.3.1: Descubre todos los archivos de las carpetas
    permitidas y los clasifica en sub-lotes por tipo con orden estricto."""
    log.header("FASE 1: Descubrimiento y Clasificación (Protocolo V2.3.1)")
    seen_paths = set()
    all_files = []

    for batch_name, directory, recursive in BATCH_PRIORITY_ORDER:
        files = _scan_single_dir(directory, recursive, seen_paths)
        if files:
            size_mb = sum(f["size_bytes"] for f in files) / (1024 * 1024)
            log.info(f"  Carpeta [{batch_name}]: {len(files)} archivos ({size_mb:.1f} MB)")
            all_files.extend(files)

    if not all_files:
        log.warning("No se encontraron archivos para analizar.")
        return [], {}

    # Desglose global por tipo
    by_type = {}
    for f in all_files:
        by_type[f["type"]] = by_type.get(f["type"], 0) + 1

    log.success(f"Descubiertos {len(all_files)} archivos en {len(BATCH_PRIORITY_ORDER)} carpetas")
    for t, c in sorted(by_type.items()):
        log.info(f"  {t}: {c} archivos")

    # Clasificar por tipo con sub-lotes
    log.header("Clasificación por Tipo (Mimetype-Safe V2.3.1)")
    log.info("  Prioridad: A. PDF(<15MB) → B. Imágenes(×20) → C. Audios(×3) → D. Videos(×1)")
    log.info("  Excluidos de API: .md, .py, .json (lectura local exclusiva)")
    sub_batches = _classify_by_type(all_files)
    log.success(f"Organizados en {len(sub_batches)} sub-lotes de procesamiento")

    return sub_batches, by_type


def _load_processed_hashes() -> tuple[set, set]:
    """Carga hashes ya procesados de la BD y de hallazgos_proactivos."""
    existing_hashes = set()
    proactive_hashes = set()
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT hash_sha256 FROM files")
        existing_hashes = {row[0] for row in cursor.fetchall()}
        try:
            cursor.execute("SELECT hash_sha256 FROM hallazgos_proactivos")
            proactive_hashes = {row[0] for row in cursor.fetchall()}
        except Exception:
            pass
        conn.close()
    except Exception:
        pass
    return existing_hashes, proactive_hashes


def filter_batch(files: list[dict], db_hashes: set, proactive_hashes: set) -> list[dict]:
    """Filtra archivos de un lote que ya fueron analizados por el sistema proactivo."""
    pending = []
    wiki_dir = os.path.join(BASE_DIR, "wiki")
    for file_info in files:
        sha = calculate_sha256(file_info["path"])
        if not sha:
            continue
        file_info["hash_sha256"] = sha
        
        # Si ya tiene hallazgo proactivo en BD, saltar
        if sha in proactive_hashes:
            continue
            
        # Protocolo V2.4 Resiliencia Wiki: Si la BD se borró pero el archivo 
        # .md existe completo en la carpeta wiki, saltarlo.
        wiki_path = os.path.join(wiki_dir, f"{sha}_meta.md")
        if os.path.exists(wiki_path):
            try:
                with open(wiki_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if "Análisis Forense Proactivo (Ollama Local)" in content:
                        continue  # Ya está completamente procesado localmente
            except Exception:
                pass
                
        # Si está en la BD de files, marcar
        if sha in db_hashes:
            file_info["in_db"] = True
        pending.append(file_info)
    return pending


# ═══════════════════════════════════════════════════════════════
#  MOTOR DE ANÁLISIS CON GEMINI 1.5 PRO
# ═══════════════════════════════════════════════════════════════

def build_proactive_prompt(filename: str, file_type: str,
                           exif_meta: dict | None = None) -> str:
    """Construye el prompt especializado en detección de patrones para CDMX 2026."""

    metadata_section = ""
    if exif_meta:
        parts = []
        if exif_meta.get("fecha_creacion"):
            parts.append(f"Fecha de creación del archivo (metadatos): {exif_meta['fecha_creacion']}")
        if exif_meta.get("coordenadas_gps"):
            parts.append(f"Ubicación GPS extraída: {exif_meta['coordenadas_gps']}")
        if exif_meta.get("modelo_dispositivo"):
            parts.append(f"Dispositivo de captura: {exif_meta['modelo_dispositivo']}")
        if parts:
            metadata_section = "\nMetadatos técnicos del archivo:\n" + "\n".join(f"  - {p}" for p in parts)

    type_instructions = ""
    if file_type == "imagen":
        type_instructions = """
INSTRUCCIONES PARA IMAGEN:
- Transcribe TODO el texto visible literalmente (OCR completo: mensajes, fechas, nombres, estados de lectura).
- REGLA ABSOLUTA: Entregar un `texto_verbatim` 100% íntegro. Cero resúmenes, cero extracciones parciales. Todo texto aparecerá íntegramente.
- Si es captura de chat: identifica remitente, destinatario, plataforma (WhatsApp, iMessage, etc.) y hora visible.
- Para los análisis de capturas de pantalla con mensajes, prioriza la fecha impresa sobre la fecha de la captura sin eliminar metadatos.
- Describe la escena fotográfica si NO es un chat: personas, entorno, deterioro, suciedad, contexto visible.
- Identifica SELLOS, FIRMAS, logotipos oficiales si los hay."""
    elif file_type == "audio":
        type_instructions = """
INSTRUCCIONES PARA AUDIO:
- Transcribe VERBATIM con marcas de tiempo (MM:SS) y diarización (quién habla).
- Nombres conocidos para Diarización (prioriza identificarlos): René, Viridiana, IO (Hija), Valeria Juárez, Carlos Alberto López.
- REGLA ABSOLUTA: Entregar un `texto_verbatim` 100% íntegro de la conversación. Cero resúmenes, cero omisiones de diálogo.
- Identifica tono emocional: llanto, gritos, sarcasmo, amenazas veladas.
- Cita el nombre del archivo en la narrativa."""
    elif file_type == "video":
        type_instructions = """
INSTRUCCIONES PARA VIDEO:
- Describe la escena visual con detalle (higiene, abandono, contexto) y transcribe el audio VERBATIM con marcas de tiempo.
- Nombres conocidos para Diarización: René, Viridiana, IO (Hija), Valeria Juárez, Carlos Alberto López.
- REGLA ABSOLUTA: Entregar un `texto_verbatim` 100% íntegro del diálogo. Cero resúmenes, cero recortes parciales.
- Identifica ubicación, personas presentes, estado emocional."""
    elif file_type == "documento":
        type_instructions = """
INSTRUCCIONES PARA DOCUMENTO PDF:
- Extrae texto con jerarquía visual: encabezados, sellos, firmas, membretes.
- REGLA ABSOLUTA: Entregar un `texto_verbatim` 100% íntegro de TODO el contenido del PDF. Cero resúmenes, cero exclusiones.
- Identifica la naturaleza del documento (oficio, demanda, acuse, recibo, etc.).
- Registra toda fecha y número de expediente visible."""

    return f"""Eres un Perito en Integración de Evidencia Multimodal adscrito a un Juzgado Familiar de la Ciudad de México.
Tu misión es analizar evidencia digital para un caso de Pérdida de Patria Potestad (Expediente 1784/2022).

Contexto del caso:
- Actor (padre): René Iván Anzorena Hernández
- Demandada (madre custodia): Viridiana López Valenzuela
- Menor: I.A.L. (adolescente de 15 años, cuya voluntad tiene peso vinculante según Autonomía Progresiva SCJN)
- Jurisdicción: Juzgado Familiar, Ciudad de México, 2026

Archivo analizado: {filename}
Tipo de archivo: {file_type}
{metadata_section}
{type_instructions}

DETECCIÓN DE PATRONES — Analiza si este archivo contiene evidencia de CUALQUIERA de los siguientes patrones:

1. DIFAMACIÓN Y FALSA DENUNCIA: La demandada fabrica hechos ante autoridades (policía, fiscalía, DIF) para perjudicar al padre. Incluye querellas por "sustracción" cuando ella misma estaba ausente.

2. INACCIÓN EDUCATIVA: Ausentismo escolar reiterado, falta de supervisión en tareas, omisión de citas escolares, abandono de seguimiento académico de la hija. Rastrea proactivamente cualquier nexo entre juntas mencionadas con "Valeria" y la baja escolar.

3. DESACATO AL RÉGIMEN DE VISITAS: Impedimento o boicot de la convivencia paterno-filial.

4. VIOLENCIA VICARIA, COACCIÓN E INDUCCIÓN TESTIMONIAL (Art. 323 Séptimus CC CDMX): ANÁLISIS SOBRE ANÁLISIS. Documenta cualquier aislamiento y maniobras para el descrédito del padre. Identifica proactivamente todo patrón de COACCIÓN directa dirigido a la INDUCCIÓN TESTIMONIAL (instrucciones de la madre a la menor sobre qué decir ante autoridades).

5. HIGIENE Y LIFESTYLE: ANÁLISIS SOBRE ANÁLISIS. Al describir escenas en fotos o videos, rastrea activamente patrones de desatención, abandono de cuidado personal, vivienda insalubre o negligencia.

6. VÍNCULO DE IDENTIDAD Y DESARTICULACIÓN DE COARTADA: Desarticula el alias "asesor inmobiliario" vinculándolo de facto con "HANSEL OLIVER ROJAS FIGUEROA" para revelar el ocultamiento.

7. FRAUDE DOMICILIAR: ANÁLISIS SOBRE ANÁLISIS. Cruza recibos de viajes de Uber, geolocalización GPS y elementos de video para probar que la demandada NO vive en el domicilio legal declarado.

8. INTERFERENCIA PROXY: ANÁLISIS SOBRE ANÁLISIS. Estudia meticulosamente los metadatos y comunicaciones para detectar instancias donde la menor ('I.A.L.') responde mensajes como proxy, dictados directamente por la madre.

9. CONTRADICCIONES TEMPORALES: Cruza fechas para detectar discrepancias entre denuncias pasadas (ej. Nov. 2022) y bitácoras de viajes de ocio o redes sociales de las mismas fechas.

FILTRO ESTRATÉGICO OBLIGATORIO:
Antes de registrar un hallazgo, evalúa: ¿Este hallazgo construye sustento legal eficiente para un juicio de Pérdida de Patria Potestad en la CDMX en 2026?
- Si es irrelevante o no tiene valor probatorio → marca como "sin_relevancia_procesal"
- Si tiene valor → clasifica el patrón y cita el fundamento legal aplicable

Responde ESTRICTAMENTE en JSON válido con esta estructura:

{{
    "descripcion_escena": "Descripción objetiva y completa de lo que muestra el archivo. Para fotografías, describe personas, lugar, contexto, estado emocional. Para chats, identifica interlocutores y plataforma.",
    "texto_verbatim": "Transcripción literal completa del texto/audio visible o audible. Para audio, incluye marcas de tiempo (MM:SS). Para chats, mantén el formato de conversación. Si no aplica, null.",
    "fecha_visible": "Fecha y hora visible en el archivo. Formato: YYYY-MM-DD HH:MM. Si no hay fecha visible, null.",
    "patrones_detectados": ["Lista de patrones detectados. Valores posibles: difamacion, inaccion_educativa, desacato_visitas, violencia_vicaria, higiene_lifestyle, fraude_domiciliar, interferencia_proxy, desarticulacion_coartada, contradicciones_temporales, sin_relevancia_procesal"],
    "clasificacion_violencia": "Categoría del catálogo: Violencia Psicoemocional, Física, Patrimonial, Económica, Vicaria, Institucional, o Ninguna. Puede ser lista.",
    "valor_probatorio": "Evaluación de 1 a 10 del valor de esta evidencia para el juicio de Pérdida de Patria Potestad en CDMX 2026. 10 = prueba contundente.",
    "resumen_pericial": "Resumen en lenguaje judicial profesional (no jerga técnica). Máximo 3 oraciones.",
    "personas_identificadas": "Lista de personas identificadas o mencionadas.",
    "fundamento_legal": "Si tiene relevancia, cita la ley o artículo aplicable del Código Civil CDMX, LGDNNA, o LGAMVLV. Si no aplica, null.",
    "conexiones": "Vínculos con otros hechos del expediente o patrones previos. Objeto JSON.",
    "filtro_estrategico": "APROBADO si construye sustento legal para CDMX 2026, RECHAZADO si es irrelevante. Justifica en una oración."
}}"""


def synthesize_analyses(analyses: list[dict]) -> dict:
    """Combina múltiples diagnósticos de Ollama provenientes de un solo archivo particionado en fragmentos."""
    if len(analyses) == 1:
        return analyses[0]
        
    merged = {
        "descripcion_escena": "Análisis consolidado por fragmentos: ",
        "texto_verbatim": "",
        "fecha_visible": analyses[0].get("fecha_visible"),
        "patrones_detectados": set(),
        "clasificacion_violencia": set(),
        "valor_probatorio": 0,
        "resumen_pericial": "",
        "personas_identificadas": set(),
        "fundamento_legal": set(),
        "conexiones": {},
        "filtro_estrategico": "RECHAZADO"
    }
    
    for a in analyses:
        if a.get("descripcion_escena"):
            merged["descripcion_escena"] += str(a["descripcion_escena"]) + " | "
        if a.get("texto_verbatim"):
            merged["texto_verbatim"] += str(a["texto_verbatim"]) + "\n...\n"
        
        # Merge de conjuntos
        patrones = a.get("patrones_detectados", [])
        if isinstance(patrones, str): patrones = [p.strip() for p in patrones.split(",")]
        for p in patrones: merged["patrones_detectados"].add(p.strip())
            
        if a.get("clasificacion_violencia"):
            for p in str(a["clasificacion_violencia"]).split(","): merged["clasificacion_violencia"].add(p.strip())
            
        val = int(a.get("valor_probatorio") or 0)
        if val > merged["valor_probatorio"]:
            merged["valor_probatorio"] = val
            
        if a.get("resumen_pericial"):
            merged["resumen_pericial"] += str(a["resumen_pericial"]) + " "
            
        if a.get("personas_identificadas"):
            for p in str(a["personas_identificadas"]).split(","): merged["personas_identificadas"].add(p.strip())
            
        if a.get("fundamento_legal"):
            for p in str(a["fundamento_legal"]).split(","): merged["fundamento_legal"].add(p.strip())
            
        if "APROBADO" in str(a.get("filtro_estrategico", "")).upper():
            merged["filtro_estrategico"] = "APROBADO"
            
    merged["patrones_detectados"] = [p for p in merged["patrones_detectados"] if p and p != "sin_relevancia_procesal"]
    if not merged["patrones_detectados"]: merged["patrones_detectados"] = ["sin_relevancia_procesal"]
    merged["clasificacion_violencia"] = ", ".join([p for p in merged["clasificacion_violencia"] if p and p != "Ninguna"])
    merged["personas_identificadas"] = ", ".join([p for p in merged["personas_identificadas"] if p])
    merged["fundamento_legal"] = ", ".join([p for p in merged["fundamento_legal"] if p and p != "null"])
    
    return merged


def analyze_with_ollama(filepath: str, file_type: str,
                        md_content: str) -> dict | None:
    """Envía un análisis a Ollama de forma local.
    Incluye protección de RAM con keep_alive=0 y captura de errores."""
    filename = os.path.basename(filepath)
    prompt = build_proactive_prompt(filename, file_type, None)
    
    prompt += f"\n\n--- CONTENIDO DEL ARCHIVO (METADATOS Y TEXTO) ---\n{md_content}"
        
    try:
        response = ollama.generate(
            model=OLLAMA_MODEL,
            prompt=prompt,
            format="json",
            options=Options(num_ctx=4096),
            keep_alive=0
        )

        # Limpiar y parsear
        text = response.get('response', '{}').strip()
        data = json.loads(text)

        # Normalizar listas a strings para persistencia
        for key in ("clasificacion_violencia", "personas_identificadas", "patrones_detectados"):
            if isinstance(data.get(key), list):
                if key == "patrones_detectados":
                    continue  # Mantener como lista para procesamiento interno
                data[key] = ", ".join(str(x) for x in data[key])

        if isinstance(data.get("conexiones"), dict):
            data["conexiones"] = json.dumps(data["conexiones"], ensure_ascii=False)

        return data

    except json.JSONDecodeError as e:
        log.error(f"  JSON inválido de Ollama para {filename}: {e}")
        return None
    except Exception as e:
        error_str = str(e).lower()
        if 'not found' in error_str or '404' in error_str:
            log.error(f"FATAL: Modelo de Ollama {OLLAMA_MODEL} no disponible. Instale el modelo o verifique Ollama.")
            sys.exit(1)
        log.error(f"  Error procesando {filename} con Ollama: {e}")
        return None

def analyze_with_gemini_multimodal(filepath: str, file_type: str, md_content: str) -> dict | None:
    """Envía un análisis multimodal a Gemini Flash de forma segura usando API de subida."""
    import tempfile
    import shutil
    
    filename = os.path.basename(filepath)
    prompt = build_proactive_prompt(filename, file_type, None)
    
    if file_type == "imagen":
        prompt += f"\n\n--- INSTRUCCIÓN ADICIONAL PARA IA VISUAL ---\nIgnora rostros privados si no son vitales para identificar ubicaciones. Lee toda letra, número o ticket visible."
    
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        log.error("FATAL: GEMINI_API_KEY no detectada en entorno. Abortando proceso visual.")
        sys.exit(1)
        
    client = genai.Client(api_key=api_key)
    
    # Manejo de reintentos y carga estratégica
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # WORKAROUND ASCII: Si la ruta original contiene acentos, httpx fallará en los headers al subirlo.
            # Copiamos temporalmente a ruta ASCII pura.
            ext = os.path.splitext(filepath)[1]
            temp_path = os.path.join(tempfile.gettempdir(), f"evidencia_multimodal_limpia{ext}")
            shutil.copy2(filepath, temp_path)
            
            log.info(f"    Subiendo media a Google Cloud para {filename} (Intento {attempt+1}/{max_retries})...")
            uploaded_file = client.files.upload(file=temp_path)
            
            # Polling si el archivo requiere procesamiento (ej. videos o audios pesados)
            while uploaded_file.state.name == "PROCESSING":
                log.info(f"    Google está procesando el archivo internamente, esperando 10s...")
                time.sleep(10)
                uploaded_file = client.files.get(name=uploaded_file.name)
                
            if uploaded_file.state.name == "FAILED":
                raise Exception("El servidor de Google falló al procesar el archivo.")
                
            log.info(f"    Invocando Gemini Flash para generar análisis multimodal de {filename}...")
            
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[
                    uploaded_file,
                    prompt
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0
                )
            )
            
            text = response.text.replace('```json', '').replace('```', '').strip()
            data = json.loads(text)

            for key in ("clasificacion_violencia", "personas_identificadas", "patrones_detectados"):
                if isinstance(data.get(key), list):
                    if key == "patrones_detectados":
                        continue
                    data[key] = ", ".join(str(x) for x in data[key])
            if isinstance(data.get("conexiones"), dict):
                data["conexiones"] = json.dumps(data["conexiones"], ensure_ascii=False)
                
            log.success(f"Extracción multimodal de {filename} completada exitosamente.")
            
            # Limpieza Forense (Eliminar archivo de servidores remotos)
            try:
                client.files.delete(name=uploaded_file.name)
            except Exception:
                pass
                
            # Pausa ajustada para Pay-As-You-Go
            log.info("Pausa estratégica: Guardando 15 segundos para estabilizar la cuota API...")
            time.sleep(15)
            
            # Limpiar archivo temporal
            try:
                os.remove(temp_path)
            except Exception:
                pass
                
            return data
            
        except json.JSONDecodeError as e:
            log.error(f"  JSON inválido devuelto por Gemini para {filename}: {e}")
            return None
        except Exception as e:
            log.warning(f"Error con Gemini (Intento {attempt+1}): {str(e)}")
            if attempt < max_retries - 1:
                log.info(f"Pausa mandatoria de 60s por error API en {filename}...")
                time.sleep(60)
            else:
                log.error(f"Descartando archivo {filename} tras {max_retries} intentos por error de API.")
                return None
    return None




# ═══════════════════════════════════════════════════════════════
#  PERSISTENCIA: metadata_multimodal.json
# ═══════════════════════════════════════════════════════════════

def load_metadata_json() -> list:
    """Carga o inicializa metadata_multimodal.json."""
    if os.path.exists(METADATA_JSON_PATH):
        try:
            with open(METADATA_JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_metadata_json(data: list):
    """Persiste metadata_multimodal.json con formato legible."""
    with open(METADATA_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def append_to_metadata(entry: dict, all_metadata: list):
    """Agrega una entrada de metadata evitando duplicados por hash."""
    existing_hashes = {m.get("hash_sha256") for m in all_metadata}
    if entry.get("hash_sha256") not in existing_hashes:
        all_metadata.append(entry)


# ═══════════════════════════════════════════════════════════════
#  PERSISTENCIA: BASE DE DATOS
# ═══════════════════════════════════════════════════════════════

def init_proactive_table():
    """Crea la tabla de hallazgos proactivos si no existe."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hash_sha256 TEXT UNIQUE,
            filename TEXT,
            path TEXT,
            file_type TEXT,
            size_bytes INTEGER,
            ingested_at TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER,
            content TEXT,
            created_at TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hallazgos_proactivos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER,
            hash_sha256 TEXT NOT NULL,
            filename TEXT NOT NULL,
            path TEXT NOT NULL,
            file_type TEXT,
            descripcion_escena TEXT,
            texto_verbatim TEXT,
            fecha_visible TEXT,
            patrones_detectados TEXT,
            clasificacion_violencia TEXT,
            valor_probatorio INTEGER,
            resumen_pericial TEXT,
            personas_identificadas TEXT,
            fundamento_legal TEXT,
            conexiones TEXT,
            filtro_estrategico TEXT,
            fecha_analisis TEXT NOT NULL,
            FOREIGN KEY (file_id) REFERENCES files(id)
        )
    """)
    conn.commit()
    conn.close()


def save_hallazgo(file_info: dict, analysis: dict) -> int | None:
    """Guarda un hallazgo aprobado en la base de datos."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Buscar file_id existente
    file_id = None
    cursor.execute("SELECT id FROM files WHERE hash_sha256 = ?", (file_info["hash_sha256"],))
    result = cursor.fetchone()
    if result:
        file_id = result[0]

    patrones = analysis.get("patrones_detectados", [])
    if isinstance(patrones, list):
        patrones_str = ", ".join(patrones)
    else:
        patrones_str = str(patrones)

    try:
        cursor.execute("""
            INSERT INTO hallazgos_proactivos
            (file_id, hash_sha256, filename, path, file_type,
             descripcion_escena, texto_verbatim, fecha_visible,
             patrones_detectados, clasificacion_violencia, valor_probatorio,
             resumen_pericial, personas_identificadas, fundamento_legal,
             conexiones, filtro_estrategico, fecha_analisis)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            file_id,
            file_info["hash_sha256"],
            file_info["filename"],
            file_info["relative_path"],
            file_info["type"],
            analysis.get("descripcion_escena"),
            analysis.get("texto_verbatim"),
            analysis.get("fecha_visible"),
            patrones_str,
            analysis.get("clasificacion_violencia"),
            analysis.get("valor_probatorio"),
            analysis.get("resumen_pericial"),
            analysis.get("personas_identificadas"),
            analysis.get("fundamento_legal"),
            analysis.get("conexiones"),
            analysis.get("filtro_estrategico"),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ))
        conn.commit()
        row_id = cursor.lastrowid
        conn.close()
        return row_id
    except Exception as e:
        log.error(f"  Error guardando hallazgo en BD: {e}")
        conn.rollback()
        conn.close()
        return None


# ═══════════════════════════════════════════════════════════════
#  GENERADOR DE REPORTES AUTOMÁTICOS
# ═══════════════════════════════════════════════════════════════

class PatternTracker:
    """Acumula hallazgos por patrón para detección de patrones nuevos."""

    def __init__(self):
        self.patterns: dict[str, list] = {}
        self.existing_patterns = self._load_existing_patterns()

    def _load_existing_patterns(self) -> set:
        """Lee patrones ya reportados de la BD."""
        existing = set()
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT patrones_detectados FROM hallazgos_proactivos")
            for row in cursor.fetchall():
                if row[0]:
                    for p in row[0].split(","):
                        existing.add(p.strip())
            conn.close()
        except Exception:
            pass
        return existing

    def register(self, file_info: dict, analysis: dict):
        """Registra un hallazgo y acumula por patrón."""
        patrones = analysis.get("patrones_detectados", [])
        if isinstance(patrones, str):
            patrones = [p.strip() for p in patrones.split(",")]

        for patron in patrones:
            if patron == "sin_relevancia_procesal":
                continue
            if patron not in self.patterns:
                self.patterns[patron] = []
            self.patterns[patron].append({
                "filename": file_info["filename"],
                "path": file_info["relative_path"],
                "hash_sha256": file_info["hash_sha256"],
                "resumen": analysis.get("resumen_pericial", ""),
                "texto_verbatim": analysis.get("texto_verbatim", ""),
                "fecha_visible": analysis.get("fecha_visible", ""),
                "valor_probatorio": analysis.get("valor_probatorio", 0),
                "clasificacion": analysis.get("clasificacion_violencia", ""),
                "fundamento_legal": analysis.get("fundamento_legal", ""),
                "personas": analysis.get("personas_identificadas", ""),
                "filtro": analysis.get("filtro_estrategico", ""),
            })

    def get_new_patterns(self) -> dict[str, list]:
        """Retorna patrones que no existían previamente o que ganaron masa crítica."""
        new = {}
        for patron, hallazgos in self.patterns.items():
            # Un patrón es "nuevo" si no existía antes O si acumuló ≥3 hallazgos nuevos
            if patron not in self.existing_patterns or len(hallazgos) >= 3:
                new[patron] = hallazgos
        return new


def generate_report(patron_key: str, hallazgos: list):
    """Genera un REPORTE_NUEVO_[FECHA].md con citación verbatim y leyes aplicables."""
    fecha_str = datetime.now().strftime("%Y-%m-%d")
    hora_str = datetime.now().strftime("%H:%M")

    catalog = PATRONES_CATALOG.get(patron_key, {})
    nombre_judicial = catalog.get("nombre_judicial", patron_key.replace("_", " ").title())
    leyes = catalog.get("leyes", [])
    tesis = catalog.get("tesis_scjn", "")

    # Ordenar hallazgos por valor probatorio descendente
    hallazgos_sorted = sorted(hallazgos, key=lambda x: x.get("valor_probatorio", 0), reverse=True)

    filename = f"REPORTE_NUEVO_{patron_key.upper()}_{fecha_str}.md"
    filepath = os.path.join(BASE_DIR, filename)

    # Construir contenido del reporte
    lines = []
    lines.append(f"# Hallazgo Pericial: {nombre_judicial}")
    lines.append("")
    lines.append(f"**Fecha de generación automática:** {fecha_str} a las {hora_str} hrs.")
    lines.append(f"**Generado por:** Analista Proactivo Forense (Muninn v2.0)")
    lines.append(f"**Total de evidencias analizadas que sustentan este patrón:** {len(hallazgos_sorted)}")
    lines.append("")

    # Objetivo estratégico
    lines.append(f"**Objetivo Estratégico:** Documentar y sustentar la existencia del patrón de "
                 f"«{nombre_judicial}» mediante evidencia digital verificada, con el propósito de "
                 f"fortalecer el sustento probatorio de la Demanda de Pérdida de Patria Potestad "
                 f"ante el Juzgado Familiar de la Ciudad de México (Expediente 1784/2022).")
    lines.append("")

    # Marco jurídico
    lines.append("---")
    lines.append("")
    lines.append("## Marco Jurídico Aplicable")
    lines.append("")
    for ley in leyes:
        lines.append(f"- {ley}")
    if tesis:
        lines.append(f"- **Criterio SCJN:** {tesis}")
    lines.append("")

    # Hallazgos individuales
    lines.append("---")
    lines.append("")
    lines.append(f"## Hallazgos Periciales ({len(hallazgos_sorted)} evidencias)")
    lines.append("")

    for idx, h in enumerate(hallazgos_sorted, 1):
        valor = h.get("valor_probatorio", 0)
        lines.append(f"### Evidencia {idx}: {h['filename']}")
        lines.append("")
        lines.append(f"- **Ruta de resguardo:** {h['path']}")
        lines.append(f"- **Huella digital (SHA-256):** `{h['hash_sha256']}`")
        if h.get("fecha_visible"):
            lines.append(f"- **Fecha visible en el archivo:** {h['fecha_visible']}")
        lines.append(f"- **Valor probatorio:** {valor}/10")
        lines.append(f"- **Clasificación:** {h.get('clasificacion', 'Sin clasificar')}")
        if h.get("personas"):
            lines.append(f"- **Personas identificadas:** {h['personas']}")

        # Resumen pericial
        if h.get("resumen"):
            lines.append("")
            lines.append(f"**Síntesis pericial:** {h['resumen']}")

        # Cita verbatim
        if h.get("texto_verbatim"):
            verbatim = h["texto_verbatim"]
            # Truncar si es excesivamente largo pero preservar integridad
            if len(verbatim) > 1500:
                verbatim = verbatim[:1500] + " [...] (Texto completo disponible en la base de datos)"
            lines.append("")
            lines.append("> **Citación textual (verbatim):**")
            for vline in verbatim.split("\n"):
                vline = vline.strip()
                if vline:
                    lines.append(f"> {vline}")

        # Fundamento legal específico
        if h.get("fundamento_legal"):
            lines.append("")
            lines.append(f"**Fundamento legal:** {h['fundamento_legal']}")

        lines.append("")

    # Conclusión operativa
    lines.append("---")
    lines.append("")
    lines.append("## Conclusión Operativa")
    lines.append("")

    high_value = [h for h in hallazgos_sorted if h.get("valor_probatorio", 0) >= 7]
    lines.append(
        f"Del universo de {len(hallazgos_sorted)} evidencias analizadas para este patrón, "
        f"{len(high_value)} poseen un valor probatorio igual o superior a 7/10, lo cual "
        f"configura un sustento sólido para la acreditación del patrón de «{nombre_judicial}» "
        f"ante el Juzgado Familiar de la Ciudad de México."
    )
    lines.append("")
    lines.append(
        f"Se recomienda la incorporación de estos hallazgos al material probatorio del "
        f"Expediente 1784/2022, particularmente aquellos con valor probatorio de 8 o superior, "
        f"por constituir prueba fehaciente del incumplimiento de los deberes inherentes a la patria potestad "
        f"por parte de la demandada, conforme a los artículos citados del Código Civil para la CDMX y la LGDNNA."
    )
    lines.append("")
    lines.append(
        "**Principio rector:** Esta valoración se realiza bajo el estándar del Interés Superior de la Niñez "
        "y la Autonomía Progresiva de la adolescente I.A.L. (15 años), cuya voluntad debe ser escuchada "
        "y ponderada con carácter vinculante conforme a jurisprudencia de la Undécima Época de la SCJN."
    )
    lines.append("")

    content = "\n".join(lines)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    log.success(f"Reporte generado: {filename} ({len(hallazgos_sorted)} evidencias)")
    return filepath


# ═══════════════════════════════════════════════════════════════
#  PIPELINE PRINCIPAL
# ═══════════════════════════════════════════════════════════════

def _process_single_file(file_info: dict, tracker, all_metadata: list) -> str:
    """Procesa un archivo individual. Retorna: 'aprobado', 'rechazado', o 'error'."""
    # Extraer metadatos y texto localmente (Ruta 2)
    exif_meta = None
    extracted_text = ""
    
    if file_info["type"] == "imagen":
        exif_meta = extract_image_exif(file_info["path"])
    elif file_info["type"] in ("audio", "video"):
        exif_meta = extract_mutagen_metadata(file_info["path"])
    elif file_info["type"] == "documento":
        extracted_text = extract_pdf_texto(file_info["path"])
    elif file_info["type"] == "texto":
        extracted_text = extract_word_texto(file_info["path"])

    # Wiki-Indexer: Guardar contenido localmente en markdown temporalmente en memoria
    wiki_dir = os.path.join(BASE_DIR, "wiki")
    os.makedirs(wiki_dir, exist_ok=True)
    
    safe_hash = file_info.get("hash_sha256", "nohash")
    wiki_path = os.path.join(wiki_dir, f"{safe_hash}_meta.md")
    
    # Preparar contenido base a analizar
    base_content = []
    base_content.append(f"# Archivo: {file_info['filename']}\n")
    base_content.append(f"- **Ruta original:** `{file_info['relative_path']}`\n")
    base_content.append(f"- **Tipo:** `{file_info['type']}`\n\n")
    
    if exif_meta:
        base_content.append("## Metadatos y Contexto Físico\n```json\n")
        base_content.append(json.dumps(exif_meta, ensure_ascii=False, indent=2))
        base_content.append("\n```\n\n")
        
    if extracted_text:
        base_content.append("## Texto Extraído Localmente (OCR/Texto Estático)\n")
        base_content.append(f"{extracted_text}\n\n")
        
    try:
        with open(wiki_path, "w", encoding="utf-8") as wf:
            wf.writelines(base_content)
    except Exception as e:
        log.error(f"Error generando archivo wiki local para {file_info['filename']}: {e}")
        return "error"

    # LÓGICA DE FRAGMENTACIÓN (CHUNKING) V2.4
    CHUNK_LIMIT = 15000
    text_chunks = []
    if extracted_text and len(extracted_text) > CHUNK_LIMIT:
        log.info(f"    Archivo pesado detectado ({len(extracted_text)} caracteres). Iniciando Chunking...")
        for i in range(0, len(extracted_text), CHUNK_LIMIT):
            chunk = extracted_text[i:i + CHUNK_LIMIT]
            text_chunks.append(chunk)
    else:
        text_chunks.append(extracted_text)
        
    all_analyses = []
    for idx, chunk in enumerate(text_chunks, 1):
        if len(text_chunks) > 1:
            log.info(f"    Procesando fragmento {idx}/{len(text_chunks)}...")
        
        md_content = "".join(base_content[:3])
        if exif_meta:
            md_content += json.dumps(exif_meta, ensure_ascii=False) + "\n"
        md_content += f"\n[FRAGMENTO {idx} / {len(text_chunks)}]:\n{chunk}"
        
        if file_info["type"] in ("imagen", "audio", "video", "documento"):
            analysis = analyze_with_gemini_multimodal(file_info["path"], file_info["type"], md_content)
        else:
            analysis = analyze_with_ollama(file_info["path"], file_info["type"], md_content)
            
        if analysis:
            all_analyses.append(analysis)

    if not all_analyses:
        return "error"
        
    analysis = synthesize_analyses(all_analyses)
        
    # Escribir análisis consolidado directo al .md
    try:
        with open(wiki_path, "a", encoding="utf-8") as wf:
            wf.write("## Análisis Forense Proactivo (Ollama Local)\n")
            if len(text_chunks) > 1:
                wf.write(f"*(Documento de gran volumen: Sintetizado a partir de {len(text_chunks)} fragmentos)*\n\n")
            wf.write("```json\n")
            wf.write(json.dumps(analysis, ensure_ascii=False, indent=2))
            wf.write("\n```\n\n")
            wf.write("### Conclusión Analítica Resumida:\n")
            wf.write(f"- Clasificación Violencia: {analysis.get('clasificacion_violencia')}\n")
            wf.write(f"- Valor Probatorio: {analysis.get('valor_probatorio')}/10\n")
            wf.write(f"- Estrategia: {analysis.get('filtro_estrategico')}\n")
    except Exception as e:
        log.error(f"No se pudo guardar la inferencia consolidada de Ollama en el MD del wiki: {e}")

    filtro = analysis.get("filtro_estrategico", "")

    # ── Filtro Estratégico ──
    if "RECHAZADO" in str(filtro).upper():
        return "rechazado"

    # Hallazgo aprobado → persistir
    save_hallazgo(file_info, analysis)
    tracker.register(file_info, analysis)

    # ── Persistir metadata multimodal para fotos ──
    if file_info["type"] == "imagen":
        meta_entry = {
            "hash_sha256": file_info["hash_sha256"],
            "filename": file_info["filename"],
            "path": file_info["relative_path"],
            "tipo": file_info["type"],
            "descripcion_escena": analysis.get("descripcion_escena", ""),
            "fecha_visible": analysis.get("fecha_visible"),
            "fecha_creacion_exif": exif_meta.get("fecha_creacion") if exif_meta else None,
            "coordenadas_gps": exif_meta.get("coordenadas_gps") if exif_meta else None,
            "modelo_dispositivo": exif_meta.get("modelo_dispositivo") if exif_meta else None,
            "valor_probatorio": analysis.get("valor_probatorio"),
            "clasificacion": analysis.get("clasificacion_violencia"),
            "patrones": analysis.get("patrones_detectados"),
            "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        append_to_metadata(meta_entry, all_metadata)

    return "aprobado"


def run_analysis():
    """Ejecuta el pipeline completo del Analista Proactivo Forense.
    Protocolo de Ingesta Crítica V2.3.1 (Ollama Local):
      A. Texto/MD → B. PDF(<15MB) → C. Imágenes → D. Audios → E. Videos
    Dentro de cada categoría: menor a mayor peso en KB."""

    log.header("ANALISTA PROACTIVO FORENSE — MUNINN V2.3.1 (Ingesta Local x Ollama)")
    start_time = time.time()

    # ── Inicializar BD ──
    init_proactive_table()
    log.success("Tabla 'hallazgos_proactivos' verificada en muninn_memory.db")

    # ── Fase 1: Descubrimiento y Clasificación ──
    sub_batches, by_type = discover_and_classify()
    if not sub_batches:
        log.warning("No se encontraron archivos para analizar.")
        return

    # ── Fase 2: Cargar hashes ya procesados ──
    log.header("FASE 2: Filtrado contra Base de Datos")
    db_hashes, proactive_hashes = _load_processed_hashes()
    log.info(f"  Hashes en BD (files): {len(db_hashes)}")
    log.info(f"  Hashes en hallazgos proactivos: {len(proactive_hashes)}")

    # ── Fase 3: Procesamiento por sub-lotes tipificados ──
    log.header("FASE 3: Procesamiento por Sub-Lotes (Protocolo V2.3.1 Local)")
    tracker = PatternTracker()
    all_metadata = load_metadata_json()
    global_processed = 0
    global_approved = 0
    global_rejected = 0
    global_errors = 0
    global_skipped = 0
    global_idx = 0

    total_sub_batches = len(sub_batches)
    total_files_all = sum(len(files) for _, _, files in sub_batches)

    for lote_num, (lote_name, lote_capacity, lote_files) in enumerate(sub_batches, 1):
        # Filtrar archivos ya procesados
        pending = filter_batch(lote_files, db_hashes, proactive_hashes)
        skipped = len(lote_files) - len(pending)
        global_skipped += skipped

        if not pending:
            log.info(f"  Sub-Lote [{lote_name}]: ya procesado. Saltando.")
            continue

        # ═══ FILTRO DE CALIDAD V2.3.1 ═══
        print(flush=True)
        print(f"{'='*60}", flush=True)
        print(f"  Iniciando Lote {lote_num}: {lote_name}", flush=True)
        print(f"  {len(pending)} archivos pendientes — Esperando balance de RAM", flush=True)
        print(f"{'='*60}", flush=True)
        time.sleep(2)  # Pausa breve para estabilización de RAM

        log.header(f"SUB-LOTE {lote_num}/{total_sub_batches}: {lote_name} "
                   f"({len(pending)} pendientes, {skipped} omitidos)")

        lote_approved = 0
        lote_rejected = 0
        lote_errors = 0

        for idx, file_info in enumerate(pending, 1):
            global_idx += 1
            size_kb = file_info["size_bytes"] / 1024
            log.progress(global_idx, total_files_all - global_skipped,
                         f"[{lote_name}] {file_info['filename']} ({size_kb:.0f}KB)")

            result = _process_single_file(file_info, tracker, all_metadata)

            if result == "aprobado":
                lote_approved += 1
                global_approved += 1
            elif result == "rechazado":
                lote_rejected += 1
                global_rejected += 1
            else:
                lote_errors += 1
                global_errors += 1

            global_processed += 1
            print(f" - Archivo {global_processed} procesado", flush=True)

            # Guardar metadata periódicamente
            if global_idx % 10 == 0:
                save_metadata_json(all_metadata)



        # Resumen del sub-lote
        print(flush=True)
        log.success(f"  Sub-Lote [{lote_name}] completado: "
                    f"{lote_approved} aprobados, {lote_rejected} rechazados, {lote_errors} errores")
        save_metadata_json(all_metadata)

        # Liberación estricta de memoria al terminar el lote
        gc.collect()

        # Pausa inter-lote para recuperación de recursos y enfriamiento de API
        if lote_num < total_sub_batches:
            current_pause = 30
            log.info(f"  Pausa inter-lote de {current_pause}s para estabilización RAM/API...")
            time.sleep(current_pause)

    # ── Guardar metadata final ──
    save_metadata_json(all_metadata)
    log.success(f"Metadata multimodal guardada en metadata_multimodal.json ({len(all_metadata)} entradas)")

    # ── Fase 4: Generación de Reportes ──
    log.header("FASE 4: Detección de Patrones y Generación de Reportes")

    new_patterns = tracker.get_new_patterns()
    reports_generated = []

    if new_patterns:
        log.success(f"Se detectaron {len(new_patterns)} patrón(es) con evidencia suficiente:")
        for patron_key, hallazgos in new_patterns.items():
            catalog = PATRONES_CATALOG.get(patron_key, {})
            nombre = catalog.get("nombre_judicial", patron_key)
            log.info(f"  ▸ {nombre}: {len(hallazgos)} evidencias")
            report_path = generate_report(patron_key, hallazgos)
            reports_generated.append(report_path)
    else:
        log.info("No se detectaron patrones nuevos con masa crítica suficiente para generar reportes.")

    # ── Resumen Final ──
    elapsed = time.time() - start_time
    log.header("RESUMEN DE EJECUCIÓN (Protocolo V2.3.1)")
    log.info(f"Tiempo total de ejecución:   {elapsed / 60:.1f} minutos")
    log.info(f"Sub-lotes procesados:        {total_sub_batches}")
    log.info(f"Archivos procesados:         {global_processed}")
    log.info(f"Archivos omitidos (previos): {global_skipped}")
    log.info(f"Hallazgos aprobados:         {global_approved} (Filtro Estratégico: APROBADO)")
    log.info(f"Hallazgos rechazados:        {global_rejected} (Filtro Estratégico: RECHAZADO)")
    log.info(f"Errores de procesamiento:    {global_errors}")
    log.info(f"Reportes generados:          {len(reports_generated)}")

    if reports_generated:
        log.success("Reportes generados:")
        for rp in reports_generated:
            log.info(f"  ▸ {os.path.basename(rp)}")

    log.success("Analista Proactivo Forense V2.3.1 finalizado correctamente.")


if __name__ == "__main__":
    run_analysis()
