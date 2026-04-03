import sqlite3
import json

def extract_patterns():
    conn = sqlite3.connect('muninn_memory.db')
    cursor = conn.cursor()
    
    queries = {
        "report_b_school": "SELECT f.filename, m.visual_date, m.summary, m.raw_text FROM files f JOIN memories m ON f.id = m.file_id WHERE m.summary LIKE '%Queen Mary%' OR m.summary LIKE '%UVM%' OR m.summary LIKE '%Carlos Alonso%' OR m.raw_text LIKE '%Queen Mary%' OR m.raw_text LIKE '%UVM%'",
        "report_c_trips": "SELECT f.filename, m.visual_date, m.summary, m.gps_location, m.raw_text FROM files f JOIN memories m ON f.id = m.file_id WHERE m.summary LIKE '%Mazatlan%' OR m.summary LIKE '%Guadalajara%' OR m.summary LIKE '%Guanajuato%' OR m.summary LIKE '%Guayabita%' OR m.summary LIKE '%Anabell%' OR m.raw_text LIKE '%Mazatlan%' OR m.raw_text LIKE '%Guadalajara%'",
        "report_d_health": "SELECT f.filename, m.visual_date, m.summary, m.raw_text, f.creation_date FROM files f JOIN memories m ON f.id = m.file_id WHERE m.summary LIKE '%receta%' OR m.summary LIKE '%peso%' OR m.summary LIKE '%accidente%' OR m.summary LIKE '%terapia%' OR m.raw_text LIKE '%accidente%' OR m.raw_text LIKE '%terapia%'"
    }
    
    results = {}
    for key, q in queries.items():
        try:
            cursor.execute(q)
            rows = cursor.fetchall()
            results[key] = rows
        except sqlite3.OperationalError as e:
            results[key] = f"Error: {e}"
            
    with open('pattern_data.json', 'w') as f:
        json.dump(results, f, indent=4)
        
    conn.close()
    print("Extracci\u00f3n en JSON completada.")

if __name__ == '__main__':
    extract_patterns()
