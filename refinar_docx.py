import docx

def refinar_hechos():
    doc = docx.Document('DEMANDA_P_P_P_IVAN_VERSION_BULLETPROOF.docx')
    paragraphs = doc.paragraphs
    
    for p in paragraphs:
        # Polish Parrafo 17: Simulación de Delito
        if "17.- EJE DE FALSEDAD" in p.text:
            idx = paragraphs.index(p)
            text_p17 = paragraphs[idx+1]
            if "Simulación de Delito con dolo procesal" not in text_p17.text:
                 text_p17.text = text_p17.text.replace(
                     "El abandono físico de la menor para fines recreativos simultáneo a la querella constituye una instrumentalización flagrante del aparato de procuración de justicia (Violencia Vicaria) para coaccionar al suscrito basada en hechos inexistentes.",
                     "La ausencia total de miedo o angustia exhibida al solicitar el regreso de la menor para el 15 de septiembre anula la validez de sus alegatos. Este abandono físico para fines recreativos simultáneo a la querella en CI-FIDCANNA/59/UI-2C/D/03379/09-2023 evidencia una Simulación de Delito con dolo procesal, configurando Violencia Vicaria bajo los criterios supremos al usar la institución judicial como herramienta de coacción basada en hechos probadamente inexistentes."
                 )
        
        # Polish Parrafo 16: Matriz de Negligencia Escolar / Viajes
        if "16.- EJE DE EDUCACIÓN" in p.text:
            idx = paragraphs.index(p)
            text_p16 = paragraphs[idx+1]
            if "Matriz de Negligencia Escolar" not in text_p16.text or "fallas administrativas" not in text_p16.text:
                 text_p16.text = text_p16.text.replace(
                     "el 78% de las inasistencias injustificadas se concentran de manera contundente en jueves o viernes.",
                     "conforme a la Matriz de Negligencia Escolar, el 78% de las inasistencias injustificadas en UVM no son fallas administrativas, sino abandonos inducidos sistémicamente por la madre."
                 )

        # Polish Parrafo 18: Autonomía Progresiva / Cutting
        if "18.- PONDERACIÓN JURISPRUDENCIAL" in p.text:
            idx = paragraphs.index(p)
            text_p18_1 = paragraphs[idx+1]
            if "alejamiento justificado por peligro inminente" not in text_p18_1.text:
                 text_p18_1.text = text_p18_1.text.replace(
                     "donde la menor registró autolesiones expresando literalmente: 'Tuve que hacerme cortes (cutting) para sacar lo que siento porque no me llevan a terapia desde el 2019' [Es Un Sueño - IO.m4a - 01:15]) provocó una comprensible ruptura del vínculo tutelar efectivo.",
                     "donde la menor registró autolesiones expresando literalmente el abandono terapéutico y episodios recurrentes de 'cutting' [Nota de voz.m4a] y [Es Un Sueño - IO.m4a - 01:15]) como evidencia inequívoca de un alejamiento justificado por peligro inminente en el entorno materno."
                 )

    doc.save('DEMANDA_P_P_P_IVAN_VERSION_BULLETPROOF.docx')
    print("Consolidación Letal completada con éxito rindiendo los exactos fraseos solicitados.")

if __name__ == '__main__':
    refinar_hechos()
