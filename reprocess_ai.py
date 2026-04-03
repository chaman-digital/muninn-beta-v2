import os
import sqlite3
import json
import time
from google import genai
from google.genai import types

# Configuración
DB_PATH = "muninn_memory.db"
SUPPORTED_IMAGE_FORMATS = ('.png', '.jpg', '.jpeg', '.webp')
SUPPORTED_AUDIO_FORMATS = ('.mp3', '.wav', '.ogg', '.m4a', '.flac')

def process_file_with_gemini(filepath, file_type):
    """Procesa el archivo usando la API de Gemini para extraer información."""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_API_KEY no configurada en el entorno.")
        return None

    client = genai.Client(api_key=api_key)

    filename = os.path.basename(filepath)
    # Prompt de análisis basado en el catálogo de violencias y esquema de DB
    prompt = f"""
    Analiza este archivo (imagen de chat o audio) relacionado a un caso de violencia familiar y de género.
    Basándote en el catálogo de violencias de la Ley General de Acceso de las Mujeres a una Vida Libre de Violencia y los Derechos de Niñas, Niños y Adolescentes (Violencia Psicoemocional, Física, Patrimonial, Económica, Sexual, Vicaria, Institucional), extrae la siguiente información:

    El archivo se llama: {filename}

    {{
        "raw_text": "Transcripción completa y literal del audio (incluyendo diarización si es audio, indicando quién habla) o el texto extraído (OCR) de la imagen. Si es audio, asegúrate de citar el nombre del archivo en la narrativa inicial.",
        "visual_date": "Fecha y hora si es visible en la imagen (o inferida del audio). Formato YYYY-MM-DD HH:MM si es posible, de lo contrario null.",
        "legal_classification": "Categoría de violencia identificada (Ej: 'Violencia Psicoemocional', 'Violencia Económica', 'Ninguna'). Puede ser una lista de strings.",
        "summary": "Resumen breve de la evidencia y los hechos.",
        "entities": "Lista de entidades identificadas (personas, lugares, instituciones).",
        "topics": "Lista de temas principales (ej: 'amenazas', 'dinero', 'custodia').",
        "importance": "Nivel de importancia de la evidencia de 1 a 10, priorizando el Interés Superior de la Niñez (una hija de 15 años).",
        "connections": "Un objeto JSON que represente vínculos o referencias a eventos previos o personas (ej: {{'personas': ['agresor'], 'eventos_referidos': ['incidente_anterior']}} )."
    }}

    El pilar rector es el Interés Superior de la Niñez y la Autonomía Progresiva.
    Responde estrictamente en formato JSON válido, sin delimitadores blockcode extra como ```json, solo el objeto JSON crudo en texto plano o con los delimitadores que tu decidas pero extraíble.
    """

    try:
        if not os.path.exists(filepath):
            print(f"Error: Archivo no se encuentra en la ruta: {filepath}")
            return None

        # Subir el archivo
        print(f"Subiendo {filepath} a Gemini...")
        uploaded_file = client.files.upload(file=filepath)

        # Esperar si es un archivo que necesita procesamiento (como audio)
        while uploaded_file.state.name == "PROCESSING":
            print("Esperando procesamiento del archivo...")
            time.sleep(2)
            uploaded_file = client.files.get(name=uploaded_file.name)

        if uploaded_file.state.name == "FAILED":
             raise ValueError("Fallo en el procesamiento del archivo por Gemini.")

        # Selección de Modelo según instrucción del usuario
        model_name = 'gemini-pro-latest' if file_type == 'audio' else 'gemini-flash-latest'
        print(f"Solicitando análisis a Gemini ({model_name})...")

        response = client.models.generate_content(
            model=model_name,
            contents=[uploaded_file, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )

        # Eliminar archivo de Gemini para limpiar espacio
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

    except json.JSONDecodeError as e:
        print(f"Error decodificando el JSON devuelto por Gemini para {filepath}: {e}\nRespuesta recibida: {response.text if 'response' in locals() else 'N/A'}")
        return None
    except Exception as e:
        print(f"Error procesando {filepath} con Gemini: {e}")
        return None

def main():
    if not os.environ.get("GOOGLE_API_KEY"):
         print("Error crítico: GOOGLE_API_KEY no está definida. Saliendo.")
         return

    print("Iniciando reprocesamiento de archivos en muninn_memory.db sin registro en memories...")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Obtener archivos que no están en memories
    cursor.execute('''
        SELECT files.id, files.path FROM files 
        LEFT JOIN memories ON files.id = memories.file_id 
        WHERE memories.id IS NULL
    ''')
    
    pending_files = cursor.fetchall()
    print(f"Se encontraron {len(pending_files)} archivos pendientes de análisis AI.")

    for file_id, filepath in pending_files:
        ext = os.path.splitext(filepath)[1].lower()
        file_type = None
        
        if ext in SUPPORTED_IMAGE_FORMATS:
            file_type = "image"
        elif ext in SUPPORTED_AUDIO_FORMATS:
            file_type = "audio"
        else:
            print(f"Archivo no soportado: {filepath}. Saltando.")
            continue
            
        print(f"\\n[{file_id}] Procesando: {filepath} ({file_type})")
        
        data = process_file_with_gemini(filepath, file_type)
        
        if data:
            try:
                cursor.execute('''
                     INSERT INTO memories (file_id, raw_text, visual_date, legal_classification, summary, entities, topics, importance, connections)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                 ''', (file_id, data.get('raw_text'), data.get('visual_date'), data.get('legal_classification'),
                       data.get('summary'), data.get('entities'), data.get('topics'), data.get('importance'),
                       data.get('connections')))
                conn.commit()
                print(f"  -> Guardado exitosamente en base de datos para ID: {file_id}")
            except Exception as e:
                print(f"  -> Error guardando en BD para {file_id}: {e}")
                conn.rollback()
        else:
            print(f"  -> Falló el análisis de Gemini para {file_id}. No se guardó.")
            
        # Pequeña pausa para no saturar API rate limits (si aplica)
        time.sleep(2)

    conn.close()
    print("\\nProceso completado.")

if __name__ == "__main__":
    main()
