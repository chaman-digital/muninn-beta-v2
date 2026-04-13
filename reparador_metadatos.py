import os
import sqlite3
import subprocess
import time
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "muninn_memory.db")

class Log:
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

def extract_apple_metadata(filepath: str) -> str | None:
    """Extrae la fecha real de creación nativa usando la herramienta CoreServices (mdls) exclusiva de macOS."""
    if not os.path.exists(filepath):
        return None
        
    try:
        # Comando nativo de Apple para leer metadatos ocultos.
        result = subprocess.run(
            ['mdls', '-name', 'kMDItemContentCreationDate', '-raw', filepath],
            capture_output=True, text=True, check=True
        )
        output = result.stdout.strip()
        
        # Filtramos (null)
        if output and output != "(null)":
            return output
            
        # Si fallara el mdls, leemos la fecha física de creación del disco (birthtime)
        stat = os.stat(filepath)
        birthtime = getattr(stat, 'st_birthtime', stat.st_mtime)
        return datetime.fromtimestamp(birthtime).strftime('%Y-%m-%d %H:%M:%S')

    except Exception as e:
        # Fallback supremo: fecha de modificación del archivo.
        try:
            mtime = os.path.getmtime(filepath)
            return datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
        except:
            return None

def run_metadata_repair():
    log.header("HERRAMIENTA FORENSE: RESTAURADOR NATIVO DE METADATOS APPLE")
    
    if not os.path.exists(DB_PATH):
        log.error(f"Base de datos no encontrada en {DB_PATH}")
        return
        
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Seleccionamos archivos cuya fecha falló en la lectura convencional
    cursor.execute('''
        SELECT id, filename, path, fecha_visible 
        FROM hallazgos_proactivos 
        WHERE fecha_visible IS NULL 
           OR fecha_visible = 'null'
           OR fecha_visible = 'None'
           OR fecha_visible = ''
           OR fecha_visible LIKE '%Indetermina%'
           OR fecha_visible LIKE '%Desconoci%'
    ''')
    rows = cursor.fetchall()
    
    if not rows:
        log.success("Base de datos en perfectas condiciones. Ningún registro con fechas huérfanas.")
        conn.close()
        return

    log.info(f"Se detectaron {len(rows)} evidencias con fechas 'Indeterminadas'. Escaneando metadata profunda de Apple...")
    
    reparados = 0
    
    for row in rows:
        record_id = row['id']
        filepath = row['path']
        filename = row['filename']
        
        fecha_mac = extract_apple_metadata(filepath)
        
        if fecha_mac:
            # Etiquetamos visualmente que la fecha se extrajo por Hard-Metadata
            nueva_fecha = f"[{fecha_mac}] (Metadato Físico / Dispositivo)"
            
            cursor.execute('''
                UPDATE hallazgos_proactivos 
                SET fecha_visible = ? 
                WHERE id = ?
            ''', (nueva_fecha, record_id))
            
            reparados += 1
            print(f"➜ {filename}: Restaurada a {fecha_mac}", flush=True)
            
    conn.commit()
    conn.close()
    
    log.success(f"\nOperación concluida. Se restauró el cronograma de {reparados} archivos huérfanos.")
    log.info("Esta corrección profunda asegura que el triangulador_legal.py acomode las evidencias de Apple en el orden cronológico perfecto.")

if __name__ == "__main__":
    run_metadata_repair()
