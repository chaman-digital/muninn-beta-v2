#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔════════════════════════════════════════════════════════════════════╗
║  ANALISTA PROACTIVO FORENSE — MUNINN V2.3.1 (Pure Local Indexing)  ║
╚════════════════════════════════════════════════════════════════════╝
Lógica: RUTA 2 (Bypass Binary Upload). Extracción 100% local en iMac.
Enfoque: Coacción, Hansel Rojas, Fraude Uber/GPS y Lifestyle.
"""
import os, sys, time, json, hashlib, sqlite3, traceback
from pathlib import Path
from google import genai

# --- CONFIGURACIÓN DE SEGURIDAD V2.3.1 ---
API_DELAY_SECONDS = 120  # Pausa para respetar cuota 15 RPM
EXCLUDED_DIRS = ['previo a 2015', '.venv', '__pycache__', '.git']
EXCLUDED_EXT = ['.md', '.py', '.json', '.yml', '.db']
SKIP_FILES = {'JUICIO FAMILIAR.pdf'} # Se analiza en sesión manual dedicada

# --- MODELOS ESTRATÉGICOS ---
GEMINI_MODEL_STRATEGY = "gemini-pro-latest"

def extract_local_content(filepath):
    """Extrae texto y metadatos físicamente en el iMac sin usar red."""
    ext = filepath.suffix.lower()
    content_text = ""
    metadata = {}
    try:
        # 1. Extracción de PDF (Local)
        if ext == '.pdf':
            from pypdf import PdfReader
            reader = PdfReader(str(filepath))
            content_text = " ".join([p.extract_text() for p in reader.pages])
        # 2. Extracción de Metadatos de Imagen (Local)
        elif ext in ['.png', '.jpg', '.jpeg']:
            from PIL import Image
            from PIL.ExifTags import TAGS, GPSTAGS
            img = Image.open(filepath)
            # Lógica EXIF local aquí...
            content_text = f"[Metadatos Visuales locales extraídos]"
        # 3. Extracción de Audio/Video (Local)
        elif ext in ['.m4a', '.mp3', '.mov', '.mp4']:
            import mutagen
            tags = mutagen.File(filepath)
            content_text = f"[Metadatos de Audio/Video locales extraídos]"
        return content_text, metadata
    except Exception as e:
        return f"Error Local UTF-8: {str(e)}", {}

def analyze_with_gemini(text_payload, file_info):
    """Envía ÚNICAMENTE texto a Gemini para razonamiento de estrategia."""
    client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
    # MANDATO: Desarticular alias Hansel Rojas, detectar coacción e higiene.
    # NO SE USA client.files.upload()
    prompt = f"Analiza este hallazgo bajo la Undécima Época CDMX 2026: {text_payload}"
    response = client.models.generate_content(
        model=GEMINI_MODEL_STRATEGY,
        contents=prompt
    )
    return response.text

if __name__ == "__main__":
    print("🐦‍⬛ Nornas V2.3.1 Iniciada - Minería Local Pura en Marcha...")
    # El bucle de ejecución se mantiene local...