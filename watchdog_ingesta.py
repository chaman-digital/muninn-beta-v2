import os
import sqlite3
import hashlib
from datetime import datetime
import json
import time
import subprocess
from google import genai
from google.genai import types
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from tinytag import TinyTag
import mutagen

# Configuración
YEARS = range(2021, 2027)
DB_PATH = "muninn_memory.db"
SUPPORTED_IMAGE_FORMATS = ('.png', '.jpg', '.jpeg', '.webp')
SUPPORTED_AUDIO_FORMATS = ('.mp3', '.wav', '.ogg', '.m4a', '.flac')
SUPPORTED_VIDEO_FORMATS = ('.mov', '.mp4')
SUPPORTED_DOC_FORMATS = ('.pdf',)

def init_db():
    """Inicializa la base de datos SQLite con el esquema de Always-On Memory."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Tabla files
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            hash_sha256 TEXT UNIQUE NOT NULL,
            path TEXT NOT NULL,
            detected_date DATETIME NOT NULL,
            creation_date TEXT,
            gps_location TEXT
        )
    ''')

    # Intenta agregar las nuevas columnas si la tabla ya existe y no las tiene
    try:
        cursor.execute('ALTER TABLE files ADD COLUMN creation_date TEXT')
    except sqlite3.OperationalError:
        pass # Columna ya existe

    try:
        cursor.execute('ALTER TABLE files ADD COLUMN gps_location TEXT')
    except sqlite3.OperationalError:
        pass # Columna ya existe

    # Tabla memories
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            raw_text TEXT,
            visual_date TEXT,
            legal_classification TEXT,
            summary TEXT,
            entities TEXT,
            topics TEXT,
            importance INTEGER,
            connections TEXT,
            FOREIGN KEY (file_id) REFERENCES files (id)
        )
    ''')

    conn.commit()
    conn.close()

def create_folders():
    """Asegura que las carpetas de los años existan."""
    for year in YEARS:
        os.makedirs(str(year), exist_ok=True)

def calculate_sha256(filepath):
    """Calcula el hash SHA-256 de un archivo."""
    sha256_hash = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception as e:
        print(f"Error calculando hash para {filepath}: {e}")
        return None

def extract_apple_metadata(filepath):
    """Extrae metadatos de creación y GPS para archivos m4a y mov de Apple."""
    creation_date = None
    gps_location = None

    ext = os.path.splitext(filepath)[1].lower()
    try:
        if ext in ['.m4a', '.mp3', '.ogg', '.flac', '.wav']:
            tag = TinyTag.get(filepath)
            # Diferentes formatos pueden guardar año o fecha entera, se usa lo disponible.
            creation_date = tag.year if tag.year else None

        # Uso de mutagen/mp4 como fallback para m4a y mov donde sea posible
        if ext in ['.m4a', '.mov', '.mp4']:
            try:
                from mutagen.mp4 import MP4
                audio = MP4(filepath)
                # Intenta extraer la fecha de creación '©day'
                if '\xa9day' in audio:
                    creation_date = audio['\xa9day'][0]

                # GPS Location en .mov (apple specific - atom location) - simplificado
                # Mutagen no es la mejor opción para GPS de mov, pero capturamos el tag si está como info de texto.
                if '©xyz' in audio: # atom xyz suele guardar coordendas
                    gps_location = audio['©xyz'][0]
            except Exception as mp4_e:
                pass

    except Exception as e:
        print(f"Error extrayendo metadatos de {filepath}: {e}")

    return creation_date, gps_location

def process_file_with_gemini(filepath, file_type, creation_date=None, gps_location=None):
    """Procesa el archivo usando la API de Gemini para extraer información."""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_API_KEY no configurada.")
        return None

    client = genai.Client(api_key=api_key)

    filename = os.path.basename(filepath)

    metadata_context = ""
    if creation_date or gps_location:
        metadata_context = f"\n    Metadatos forenses extraídos del archivo:\n"
        if creation_date:
            metadata_context += f"    - Fecha de creación real (Apple): {creation_date}\n"
        if gps_location:
            metadata_context += f"    - Ubicación GPS real (Apple): {gps_location}\n"
        metadata_context += "    Usa esta información para cuadrar el tiempo del archivo con el de los eventos narrados o el contenido visual.\n"

    pdf_context = ""
    if file_type == "pdf":
        pdf_context = "\n    ATENCIÓN ESPECIAL A PDF: Este es un documento PDF. Utiliza tu visión nativa multimodal para no solo leer el texto, sino identificar e interpretar rigurosamente la presencia de SELLOS, FIRMAS, membretes y la jerarquía visual del documento. Inclúyelo en raw_text de forma descriptiva.\n"

    # Prompt de análisis basado en el catálogo de violencias y esquema de DB
    prompt = f"""
    Analiza este archivo (imagen de chat, audio, video o documento PDF) relacionado a un caso de violencia familiar y de género.
    Basándote en el catálogo de violencias de la Ley General de Acceso de las Mujeres a una Vida Libre de Violencia y los Derechos de Niñas, Niños y Adolescentes (Violencia Psicoemocional, Física, Patrimonial, Económica, Sexual, Vicaria, Institucional), extrae la siguiente información:

    El archivo se llama: {filename}
    {metadata_context}{pdf_context}

    {{
        "raw_text": "Transcripción completa y literal del audio (incluyendo diarización indicando quién habla) o el texto extraído visualmente. Si es PDF, describe explícitamente sellos, firmas, membretes. Si es audio, cita el nombre del archivo al inicio.",
        "visual_date": "Fecha y hora si es visible en el archivo. Formato YYYY-MM-DD HH:MM si es posible, de lo contrario null.",
        "legal_classification": "Categoría de violencia identificada (Ej: 'Violencia Psicoemocional', 'Violencia Económica', 'Ninguna'). Puede ser una lista de strings.",
        "summary": "Resumen breve de la evidencia y los hechos.",
        "entities": "Lista de entidades identificadas (personas, lugares, instituciones).",
        "topics": "Lista de temas principales (ej: 'amenazas', 'dinero', 'custodia').",
        "importance": "Nivel de importancia de la evidencia de 1 a 10, priorizando el Interés Superior de la Niñez (una hija de 15 años).",
        "connections": "Un objeto JSON que represente vínculos o referencias a eventos previos o personas (ej: {{'personas': ['agresor'], 'eventos_referidos': ['incidente_anterior']}} )."
    }}

    El pilar rector es el Interés Superior de la Niñez y la Autonomía Progresiva.
    """

    try:
        # Subir el archivo temporalmente
        print(f"Subiendo {filepath} a Gemini...")
        uploaded_file = client.files.upload(file=filepath)

        # Esperar si es un archivo que necesita procesamiento (como audio)
        while uploaded_file.state.name == "PROCESSING":
            print("Esperando procesamiento del archivo...")
            time.sleep(2)
            uploaded_file = client.files.get(name=uploaded_file.name)

        if uploaded_file.state.name == "FAILED":
             raise ValueError("Fallo en el procesamiento del archivo por Gemini.")

        # Realizar la solicitud de análisis usando Gemini 1.5 Flash
        print("Solicitando análisis a Gemini...")
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=[uploaded_file, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )

        # Eliminar archivo
        client.files.delete(name=uploaded_file.name)

        # Procesar respuesta JSON
        text_response = response.text.strip()
        data = json.loads(text_response)

        # Ajuste de listas y diccionarios a strings para SQLite
        if isinstance(data.get('legal_classification'), list):
             data['legal_classification'] = ", ".join(data['legal_classification'])
        if isinstance(data.get('entities'), list):
             data['entities'] = ", ".join(data['entities'])
        if isinstance(data.get('topics'), list):
             data['topics'] = ", ".join(data['topics'])
        if isinstance(data.get('connections'), dict):
             data['connections'] = json.dumps(data['connections'])

        return data

    except Exception as e:
        print(f"Error procesando {filepath} con Gemini: {e}")
        return None

def save_to_db(filepath, file_type, data, sha256_hash, creation_date=None, gps_location=None):
    """Guarda los resultados en la base de datos."""
    filename = os.path.basename(filepath)
    detected_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Insertar en tabla files con metadatos Apple
        cursor.execute('''
            INSERT INTO files (filename, hash_sha256, path, detected_date, creation_date, gps_location)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (filename, sha256_hash, filepath, detected_date, creation_date, gps_location))

        file_id = cursor.lastrowid

        # Insertar en tabla memories
        if data:
             cursor.execute('''
                 INSERT INTO memories (file_id, raw_text, visual_date, legal_classification, summary, entities, topics, importance, connections)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
             ''', (file_id, data.get('raw_text'), data.get('visual_date'), data.get('legal_classification'),
                   data.get('summary'), data.get('entities'), data.get('topics'), data.get('importance'),
                   data.get('connections')))
        else:
             print(f"Se guardó el archivo {filename} pero sin datos de memoria (falló el análisis).")

        conn.commit()
        print(f"[{detected_date}] Archivo {filename} procesado y guardado correctamente.")
    except sqlite3.IntegrityError:
        print(f"El archivo {filename} con hash {sha256_hash} ya existe en la base de datos.")
    except Exception as e:
         print(f"Error guardando en base de datos: {e}")
         conn.rollback()
    finally:
        conn.close()

def process_new_file(filepath):
    """Procesa de manera integral un nuevo archivo detectado."""
    ext = os.path.splitext(filepath)[1].lower()
    file_type = None
    if ext in SUPPORTED_IMAGE_FORMATS:
        file_type = "image"
    elif ext in SUPPORTED_AUDIO_FORMATS:
        file_type = "audio"
    elif ext in SUPPORTED_VIDEO_FORMATS:
        file_type = "video"
    elif ext in SUPPORTED_DOC_FORMATS:
        file_type = "pdf"
    else:
        return # Formato no soportado

    print(f"Procesando nuevo archivo: {filepath}")

    # 1. Calcular Hash
    sha256_hash = calculate_sha256(filepath)
    if not sha256_hash: return

    # Verificar si ya existe en la base de datos antes de procesar
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM files WHERE hash_sha256 = ?', (sha256_hash,))
    if cursor.fetchone():
        print(f"Archivo {filepath} ya procesado (hash duplicado).")
        conn.close()
        return
    conn.close()

    # 2. Extraer metadatos de Apple si es audio/video
    creation_date, gps_location = None, None
    if file_type in ["audio", "video"]:
        creation_date, gps_location = extract_apple_metadata(filepath)

    # 3. Procesar con Gemini (Visión, Transcripción, Clasificación)
    data = process_file_with_gemini(filepath, file_type, creation_date, gps_location)

    # 4. Guardar en SQLite
    save_to_db(filepath, file_type, data, sha256_hash, creation_date, gps_location)

class MuninnEventHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            # Pequeña pausa para asegurar que el archivo se copió completamente
            time.sleep(1)
            process_new_file(event.src_path)

def initial_ingestion():
    """Realiza la ingesta inicial de archivos existentes."""
    print("Iniciando ingesta inicial de archivos existentes...")
    directories_to_scan = ['.'] + [str(year) for year in YEARS]

    for directory in directories_to_scan:
        if os.path.exists(directory):
            for filename in os.listdir(directory):
                filepath = os.path.join(directory, filename)
                if os.path.isfile(filepath):
                    process_new_file(filepath)
    print("Ingesta inicial completada.")

def start_watchdog():
    """Inicia el monitoreo en tiempo real de las carpetas."""
    print("Iniciando monitoreo de carpetas...")
    observer = Observer()
    event_handler = MuninnEventHandler()

    # Monitorear raíz y cada carpeta de año de forma individual
    directories_to_watch = ['.'] + [str(year) for year in YEARS]

    for directory in directories_to_watch:
        if os.path.exists(directory):
            observer.schedule(event_handler, path=directory, recursive=False)

    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    init_db()
    create_folders()
    print("Entorno y base de datos inicializados correctamente.")
    initial_ingestion()
    start_watchdog()
