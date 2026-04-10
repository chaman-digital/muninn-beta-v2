import os
import sqlite3
import json
import time
from datetime import datetime
from google import genai
from google.genai import types

# ═══════════════════════════════════════════════════════════════
#  CONFIGURACIÓN INICIAL
# ═══════════════════════════════════════════════════════════════

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "muninn_memory.db")
LEGISLACION_DIR = os.path.join(BASE_DIR, "legislacion")
REPORTES_DIR = os.path.join(BASE_DIR, "reportes_finales")

# Crear carpeta de reportes si no existe
os.makedirs(REPORTES_DIR, exist_ok=True)

class Log:
    """Clase sencilla para logs formateados en terminal."""
    @staticmethod
    def info(msg): print(f"\033[94m[INFO]\033[0m {msg}")
    @staticmethod
    def success(msg): print(f"\033[92m[ÉXITO]\033[0m {msg}")
    @staticmethod
    def warning(msg): print(f"\033[93m[ALERTA]\033[0m {msg}")
    @staticmethod
    def error(msg): print(f"\033[91m[ERROR]\033[0m {msg}")
    @staticmethod
    def header(msg): print(f"\n\033[95m{msg}\033[0m\n{'='*60}")

log = Log()

# ═══════════════════════════════════════════════════════════════
#  1. EXTRACCIÓN DE EVIDENCIA
# ═══════════════════════════════════════════════════════════════

def extraer_hechos_probatorios() -> list:
    """Extrae de la base de datos los hallazgos con valor probatorio superior al umbral (>=7)."""
    if not os.path.exists(DB_PATH):
        log.error(f"Base de datos no encontrada en {DB_PATH}")
        return []
        
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Filtramos por alto valor probatorio
        cursor.execute('''
            SELECT 
                filename, 
                path, 
                file_type, 
                descripcion_escena, 
                texto_verbatim, 
                fecha_visible, 
                patrones_detectados, 
                clasificacion_violencia, 
                valor_probatorio, 
                resumen_pericial, 
                personas_identificadas
            FROM hallazgos_proactivos 
            WHERE valor_probatorio >= 7
            ORDER BY fecha_visible ASC, valor_probatorio DESC
        ''')
        rows = cursor.fetchall()
        
        hallazgos = [dict(row) for row in rows]
        conn.close()
        
        log.success(f"Se extrajeron {len(hallazgos)} hallazgos probatorios con valor >= 7.")
        return hallazgos
    except Exception as e:
        log.error(f"Error al extraer hechos de la base de datos: {e}")
        return []

def formatear_evidencia_para_ia(hallazgos: list) -> str:
    """Convierte la lista de hallazgos en un documento estructurado para el analizador."""
    if not hallazgos:
        return "No hay evidencias procesadas aún con valor probatorio suficiente."
        
    md_content = "# BASE DE DATOS DE EVIDENCIA FACTUAL (Extracto de Alto Valor Probatorio)\n\n"
    
    for idx, h in enumerate(hallazgos, 1):
        md_content += f"## Evidencia {idx} | Archivo: {h['filename']}\n"
        md_content += f"- **Tipo:** {h['file_type']}\n"
        md_content += f"- **Fecha Identificada:** {h['fecha_visible'] or 'Indeterminada'}\n"
        md_content += f"- **Clasificación / Patrón:** {h['clasificacion_violencia']} / {h['patrones_detectados']}\n"
        md_content += f"- **Personas Identificadas:** {h['personas_identificadas']}\n\n"
        
        if h['descripcion_escena']:
            md_content += f"**Contexto/Escena (Peritaje):**\n{h['descripcion_escena']}\n\n"
            
        if h['texto_verbatim']:
            md_content += f"**Citas Textuales y Diálogos (Verbatim):**\n```\n{h['texto_verbatim']}\n```\n\n"
            
        md_content += "---\n\n"
        
    return md_content

# ═══════════════════════════════════════════════════════════════
#  2. MOTOR DE TRIANGULACIÓN (GEMINI)
# ═══════════════════════════════════════════════════════════════

def subir_ley_a_gemini(client, filepath: str):
    """Sube un archivo legislativo a Gemini y hace polling hasta que esté disponible."""
    filename = os.path.basename(filepath)
    log.info(f"Subiendo instrumento jurídico a servidores seguros: {filename}...")
    
    uploaded_file = client.files.upload(file=filepath)
    
    # Polling state
    while uploaded_file.state.name == "PROCESSING":
        log.info(f"  Google está procesando {filename}, esperando 10s...")
        time.sleep(10)
        uploaded_file = client.files.get(name=uploaded_file.name)
        
    if uploaded_file.state.name == "FAILED":
        raise Exception(f"Fallo al procesar {filename} en Google Cloud.")
        
    log.success(f"Instrumento jurídico {filename} activo en memoria (URI: {uploaded_file.uri})")
    return uploaded_file

def redactar_proyecto_demanda(api_key: str, evidencias_md: str):
    """Coordina el Analysis over Analysis utilizando los PDFs de las Leyes y el JSON de base de datos."""
    client = genai.Client(api_key=api_key)
    uploaded_files = []
    
    try:
        # 1. Cargar las leyes
        leyes = ["CC_CDMX.pdf", "CP_CDMX.pdf", "LGDNNA.pdf"]
        for ley in leyes:
            filepath = os.path.join(LEGISLACION_DIR, ley)
            if not os.path.exists(filepath):
                log.error(f"Falta archivo jurídico: {filepath}")
                continue
            f = subir_ley_a_gemini(client, filepath)
            uploaded_files.append(f)
            
        if not uploaded_files:
            log.error("No se pudo cargar ningún instrumento legislativo. Abortando triangulación.")
            return

        # 2. Configurar el Agente Proyectista
        instruccion_juridica = """
ERES UN ABOGADO LITIGANTE DE ALTO NIVEL EN MATERIA FAMILIAR (Tribunal Superior de Justicia de la CDMX).
Estás redactando el proyecto (borrador) de Demanda de Pérdida de Patria Potestad para tu cliente (actor) debido a Violencia Vicaria, Psicoemocional, Negligencia y posible Delito cometido por la contraparte.

METODOLOGÍA DE TRABAJO (Analysis over Analysis):
1. Tienes adjuntos 3 instrumentos normativos (Código Civil CDMX, Código Penal CDMX y la LGDNNA). CRUZA TODOS LOS HECHOS con las hipótesis legales vigentes.
2. Tienes una "BASE DE DATOS DE EVIDENCIA FACTUAL" (en tu prompt base).
3. Redacta el borrador en PRIMERA PERSONA ("Que por medio del presente escrito vengo a demandar...").
4. Tu tono debe ser 100% FUNDADO, MOTIVADO, SEVERO pero JURÍDICAMENTE IMPECABLE y OBJETIVO.

ESTRUCTURA DEL PROYECTO OBLIGATORIA:
A. PROEMIO Y PRESTACIONES: (Establece qué se demanda y a quién de forma genérica).
B. CAPÍTULO DE HECHOS (Cronología Probatoria):
   - Agrupa y narra los hechos organizados por tipología de violencia y de forma cronológica.
   - REGLA DE ORO PROBATORIA: En cada hecho narrado, OBLIGATORIAMENTE debes sustentar la narración indicando de qué evidencia se desprende. Debes incluir el `Nombre del Archivo Fuente`, y anexar las `CITAS VERBATIM TEXTUALES` exactas que lo demuestran (incluyendo marcas de tiempo MM:SS si las posee el texto base).
C. CAPÍTULO DE DERECHO Y SUBSUNCIÓN:
   - Aquí enlaza específicamente qué artículos del Código Civil, Penal o de la LGDNNA aplican a la conducta probada, citando la fracción normativa.
D. CONCLUSIONES PERICIALES / PETICIONES FINALES.

ADVERTENCIA:
Nunca resumas la cita verbatim en tus pruebas. Exponla literalmente como sustento irrebatible.
No inventes datos. Usa estrictamente las pruebas que te he anexado.
"""

        log.header("Iniciando Triangulación y Redacción Asistida. Esta operación tomará procesar miles de páginas normativas...")
        
        response = client.models.generate_content(
            model='gemini-2.5-pro', # Usaremos 2.5-pro para redacción compleja de alto nivel legal
            contents=uploaded_files + [instruccion_juridica, evidencias_md],
            config=types.GenerateContentConfig(
                temperature=0.2, # Baja temperatura para análisis determinístico
            )
        )
        
        contenido_demanda = response.text
        
        # 3. Guardar el output
        fecha_str = datetime.now().strftime("%Y-%m-%d_%H%M")
        output_file = os.path.join(REPORTES_DIR, f"Demanda_Triangulada_{fecha_str}.md")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(contenido_demanda)
            
        log.success(f"\n¡Proyecto Jurídico Terminado!\nArchivo guardado en: {output_file}")
        log.info("Este archivo Markdown (.md) puede ser copiado directamente a Microsoft Word para el pulido de la firma de abogados.")

    except Exception as e:
        log.error(f"Error mortal durante la triangulación con Gemini: {str(e)}")
    finally:
        # 4. Limpieza Forense Obligatoria
        log.header("LIMPIEZA FORENSE (CERRANDO CADENA DE CUSTODIA)")
        for f in uploaded_files:
            try:
                log.info(f"Eliminando {f.name} de los servidores de inteligencia remotos...")
                client.files.delete(name=f.name)
            except Exception as e:
                log.warning(f"No se pudo eliminar {f.name}: {e}")
        log.success("Superficie remota purgada correctamente. Archivos destruidos.")


# ═══════════════════════════════════════════════════════════════
#  EJECUCIÓN
# ═══════════════════════════════════════════════════════════════

def run():
    log.header("TRIANGULADOR LEGAL - ANALYSIS OVER ANALYSIS (Gemini 2.5 Pro)")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        log.error("Variable de entorno GEMINI_API_KEY no detectada.")
        return

    # Paso 1: Local
    hallazgos = extraer_hechos_probatorios()
    if not hallazgos:
        log.warning("Debe correr el 'analista_proactivo.py' primero para poblar la DB con evidencia de alto valor (>=7).")
        return
        
    evidencias_md = formatear_evidencia_para_ia(hallazgos)
    
    # Paso 2 & 3 & 4: Nube Legal + Purga
    redactar_proyecto_demanda(api_key, evidencias_md)

if __name__ == "__main__":
    run()
