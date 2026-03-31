import os
import time
from google import genai

# Configuración
INPUT_FOLDER = "documentos abogado/legislacion"
OUTPUT_FOLDER = "legislacion"

def convert_pdf_to_markdown(filepath):
    """
    Convierte un documento PDF de leyes a Markdown usando Gemini 1.5 Pro,
    respetando la estructura de artículos y fracciones.
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_API_KEY no configurada.")
        return None

    client = genai.Client(api_key=api_key)

    filename = os.path.basename(filepath)

    prompt = f"""
    Eres un asistente legal experto en legislación mexicana.
    A continuación se te proporciona un documento PDF que contiene un texto legal o ley: {filename}.

    Tu tarea es convertir de manera fiel y exacta todo el contenido del documento a formato Markdown (.md).
    Es CRÍTICO que respetes y mantengas la estructura original de:
    - Títulos, Capítulos y Secciones (usa encabezados Markdown #, ##, ###).
    - Artículos.
    - Fracciones (I, II, III...) e incisos (a, b, c...).

    No resumas, no omitas contenido, ni agregues opiniones o interpretaciones.
    Solo realiza la transcripción literal del documento manteniendo la jerarquía legal en formato Markdown.

    Devuelve estrictamente el código en Markdown sin ningún bloque adicional de código al inicio o al final.
    """

    try:
        print(f"Subiendo ley {filepath} a Gemini para conversión...")
        uploaded_file = client.files.upload(file=filepath)

        while uploaded_file.state.name == "PROCESSING":
            print("Esperando procesamiento del documento...")
            time.sleep(2)
            uploaded_file = client.files.get(name=uploaded_file.name)

        if uploaded_file.state.name == "FAILED":
             raise ValueError("Fallo en el procesamiento del documento por Gemini.")

        # Usamos gemini-1.5-pro según el requerimiento para mejor razonamiento sobre leyes extensas
        print("Solicitando conversión a Markdown usando Gemini 1.5 Pro...")
        response = client.models.generate_content(
            model='gemini-1.5-pro',
            contents=[uploaded_file, prompt],
        )

        client.files.delete(name=uploaded_file.name)

        return response.text.strip()

    except Exception as e:
        print(f"Error procesando {filepath} con Gemini: {e}")
        return None

def main():
    """Itera sobre la carpeta de origen y convierte cada PDF a MD."""
    # Asegurar que las carpetas existen
    os.makedirs(INPUT_FOLDER, exist_ok=True)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    pdfs = [f for f in os.listdir(INPUT_FOLDER) if f.lower().endswith(".pdf")]

    if not pdfs:
        print(f"No se encontraron archivos PDF en '{INPUT_FOLDER}'.")
        return

    print(f"Se encontraron {len(pdfs)} PDFs para procesar.")

    for pdf_name in pdfs:
        pdf_path = os.path.join(INPUT_FOLDER, pdf_name)
        md_name = os.path.splitext(pdf_name)[0] + ".md"
        md_path = os.path.join(OUTPUT_FOLDER, md_name)

        # Evitar reprocesar si ya existe el MD
        if os.path.exists(md_path):
            print(f"El archivo {md_name} ya existe. Omitiendo...")
            continue

        print(f"Procesando: {pdf_name}...")
        markdown_content = convert_pdf_to_markdown(pdf_path)

        if markdown_content:
            # Limpieza básica por si el modelo incluyó las tildes invertidas a pesar del prompt
            if markdown_content.startswith("```markdown"):
                 markdown_content = markdown_content[11:]
            elif markdown_content.startswith("```"):
                 markdown_content = markdown_content[3:]

            if markdown_content.endswith("```"):
                 markdown_content = markdown_content[:-3]

            with open(md_path, "w", encoding="utf-8") as f:
                f.write(markdown_content.strip())
            print(f"Guardado exitosamente: {md_path}")
        else:
            print(f"Fallo al convertir {pdf_name}.")

if __name__ == "__main__":
    main()
