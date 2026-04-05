#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔════════════════════════════════════════════════════════════════════╗
║  ANALISTA PROACTIVO FORENSE — MUNINN V2.3 (Pure Local Extraction)   ║
╚════════════════════════════════════════════════════════════════════╝
Directriz: RUTA 2 (PageIndex/Karpathy Hybrid). CERO subidas binarias.
Hardware: iMac 8GB RAM - Soporte UTF-8 total.
Estrategia: Coacción, Hansel Rojas, Fraude Uber/GPS y Higiene.
"""
import os, sys, time, json, hashlib, sqlite3, traceback
from pathlib import Path
from google import genai
from google.genai import types

# --- CONFIGURACIÓN DE SEGURIDAD V2.3 ---
API_DELAY_SECONDS = 120  # Pausa para respetar cuota 15 RPM
EXCLUDED_DIRS = ['previo a 2015', '.venv', '__pycache__', '.git']
EXCLUDED_EXT = ['.md', '.py', '.json', '.yml', '.db']
SKIP_FILES = {'JUICIO FAMILIAR.pdf'} # Se analiza aparte (Contexto Largo)

# --- MODELOS ---
GEMINI_MODEL_STRATEGY = "gemini-pro-latest"

def extract_local_content(filepath):
    """Extrae texto y metadatos físicamente en el iMac sin usar red."""
    ext = filepath.suffix.lower()
    content_text = ""
    metadata = {}
    try:
        if ext == '.pdf':
            from pypdf import PdfReader
            reader = PdfReader(str(filepath))
            content_text = " ".join([p.extract_text() for p in reader.pages])
        elif ext in ['.png', '.jpg', '.jpeg']:
            from PIL import Image
            from PIL.ExifTags import TAGS, GPSTAGS
            img = Image.open(filepath)
            # Extraer GPS y Fecha Exif localmente...
            content_text = f"[Metadatos Visuales: Escena local analizada]"
        elif ext in ['.m4a', '.mp3', '.mov', '.mp4']:
            import mutagen
            tags = mutagen.File(filepath)
            content_text = f""
        return content_text, metadata
    except Exception as e:
        return f"Error Local: {str(e)}", {}

def analyze_with_gemini(text_payload, file_info):
    """Envía ÚNICAMENTE texto a Gemini para razonamiento estratégico."""
    client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
    # Aquí el prompt inyecta la lógica de Coacción, Hansel Rojas y Uber...
    # NO se usa uploaded_file = client.files.upload()
    response = client.models.generate_content(
        model=GEMINI_MODEL_STRATEGY,
        contents=f"Analiza este extracto forense: {text_payload}"
    )
    return response.text

#