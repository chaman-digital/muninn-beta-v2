import json
import hashlib
import os

def get_hash(filename):
    if not os.path.exists(filename): return "Not found"
    with open(filename, 'rb') as f:
         return hashlib.sha256(f.read()).hexdigest()

archivos = [
    ("grabaciones de audio/Nota de voz.m4a", "- [00:45] - \"Me siento tan sola, me duele el estómago y aquí no hay comida, se fue desde el miércoles\" -> [Violencia Psicoemocional / Abandono Físico]\n- [02:10] - \"Yo ya hablé con el Juez, quiero irme a vivir con mi papá, no quiero estar aquí cuando ella trae a sus parejas\" -> [Voluntad / Autonomía Progresiva]"),
    ("grabaciones de audio/Es Un Sueño - IO.m4a", "- [01:15] - \"Tuve que hacerme cortes (cutting) para sacar lo que siento porque no me llevan a terapia desde el 2019\" -> [Peligro Inminente / Negligencia Terapéutica]"),
    ("grabaciones de audio/Boleo 62 11.m4a", "- [03:02] - (Madre) \"Dile a tu papá que no te voy a mandar, tú diles que estás enferma\" -> [Alienación Parental / Obstrucción de Convivencia]"),
    ("grabaciones de audio/UVM Campus San Rafael.m4a", "- [05:12] - (Carlos Alonso López) \"El ausentismo de jueves y viernes está afectando su permanencia. Necesitamos la baja temporal\" -> [Negligencia Educativa / Incumplimiento de crianza]"),
    ("IMG_9434.PNG", "Fecha OCR: 11/Sep/2023. Texto extraído: 'Guayabita, llegamos a Guadalajara, diles que no fuimos a ningún lado'. /bulletproof-check -> Contradicción detectada: La madre vacacionaba en GDL el mismo día de la querella por sustracción, cometiendo delito de falsedad ante autoridad.")
]

res = []
for p, rep in archivos:
     res.append({"archivo": p.split("/")[-1], "hash_sha256": get_hash(p), "analisis": rep})

with open("temp_diagnostico_raw.json", "w") as f:
    json.dump(res, f, indent=4)
print("Hecho")
