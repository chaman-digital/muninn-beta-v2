import sqlite3
import hashlib
import os
import glob

def compute_hash(filepath):
    if not os.path.exists(filepath):
        return "not_found"
    with open(filepath, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()

def sync():
    conn = sqlite3.connect('muninn_memory.db')
    cursor = conn.cursor()

    # Index scripts and reports
    findings = [
        ("REPORTE_B_Matriz_Negligencia.md", "Reporte B_Matriz_de_Negligencia_Escolar", "Patrón de inasistencias en Queen Mary y UVM concentradas en jueves y viernes."),
        ("REPORTE_C_Triangulacion_Falsedades.md", "Reporte C_Triangulacion_Global_de_Falsedades", "Cronología de viajes a Mazatlán, Guadalajara, Guanajuato. Cruce con Guayabita y GPS vs denuncias de retención."),
        ("REPORTE_D_Historia_Clinica.md", "Reporte D_Bitacora_de_Salud", "Recetas médicas, bajo peso y omisión de terapias tras el accidente de 2019.")
    ]

    for fname, title, text in findings:
        h = compute_hash(fname)
        cursor.execute("INSERT OR IGNORE INTO files (filename, hash_sha256, path) VALUES (?, ?, ?)", (fname, h, fname))
        cursor.execute("SELECT id FROM files WHERE filename=?", (fname,))
        res = cursor.fetchone()
        if res:
            cursor.execute("INSERT OR REPLACE INTO memories (file_id, visual_date, summary, raw_text, legal_classification) VALUES (?, date('now'), ?, ?, 'Análisis Forense')", (res[0], title, text))

    # Transcripts for audios
    audios = [
        ("Boleo 62 11.m4a", "Transcripción Boleo 62 11", "Transcripción parcial: madre instruyendo de bloqueo comunicacional y justificando omisiones."),
        ("Boleo 62 12.m4a", "Transcripción Boleo 62 12", "Transcripción parcial: presiones sobre la menor y narrativa alienante hacia el padre.")
    ]

    for aname, title, text in audios:
        path = f"grabaciones de audio/{aname}"
        h = compute_hash(path)
        cursor.execute("INSERT OR IGNORE INTO files (filename, hash_sha256, path) VALUES (?, ?, ?)", (aname, h, path))
        cursor.execute("SELECT id FROM files WHERE filename=?", (aname,))
        res = cursor.fetchone()
        if res:
             cursor.execute("INSERT OR REPLACE INTO memories (file_id, visual_date, summary, raw_text, legal_classification) VALUES (?, date('now'), ?, ?, 'Evidencia Sonora')", (res[0], title, text))

    conn.commit()
    conn.close()
    print("Sincronizaci\u00f3n a muninn_memory.db exitosa.")

if __name__ == '__main__':
    sync()
