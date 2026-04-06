# RECONSTRUCCIÓN DEL SISTEMA: BALANCE DE 36 HORAS (MUNINN V2.3.1)

Este documento centraliza las lecciones críticas de arquitectura, estabilidad y seguridad judicial descubiertas durante el refactor intensivo de Muninn: del colapso por "Resource Exhausted" al blindaje de la "Minería Silenciosa" (V2.3.1). 

---

## 🟢 LO QUE SÍ FUNCIONÓ: LOS PILARES DEL ESTÁNDAR OFICIAL
Estas directrices han demostrado ser estables bajo estrés (procesamiento de 2,079 archivos) y cumplen con los protocolos NOM-151 para la preservación de evidencia. **Son inmutables.**

1. **Ruta 2 (Local Extraction Pura):** 
   - El iMac asume la carga física del pre-procesamiento. 
   - Se utiliza `pypdf`, `Pillow` (EXIF) y `mutagen` para extraer metadatos, geolocalización, duración y texto *antes* de involucrar cualquier API externa. 

2. **Wiki-Indexer (Patrón Karpathy):**
   - Todos los hallazgos destilados localmente se persisten de manera plana en el directorio `/wiki/` como archivos formato `.md`. 
   - Se establece una separación total entre la fuente binaria y la metadata extraída. 
   - La API de Gemini **sólo** procesa estas fichas textuales puras. Alivio inmediato de RAM y networking.

3. **Dashboard Funcional e Independiente (Nornas):**
   - Puerto `8501`, desacoplado de la pesada ingesta de datos. 
   - Identidad visual consolidada (Cuervo 🐦‍⬛, menú auto-cierre, sticky bars). 
   - Interfaz que consume estáticamente los resultados persistidos en `muninn_memory.db` y `/wiki/`.

4. **Cadena de Custodia Legal (NOM-151):**
   - Extracción de llaves SHA-256 obligatorias sobre cada archivo físico de evidencia, integradas inamoviblemente a su ficha `.md`.

---

## 🔴 LO QUE DEBEMOS EVITAR: ANTI-PATRONES Y CAUSALES DE FALLO
Estos escenarios paralizaron la plataforma en la Beta V1.3 y quedan estrictamente prohibidos en la arquitectura V2.x.

1. **PROHIBIDO: Subidas Binarias a la API:**
   - La ejecución de métodos como `client.files.upload()` para archivos en masa provoca agotamiento recursivo de cuota (Rate Limit / Error 429), cuelgues del intérprete y fuga de memoria RAM severa. 
   - Ningún binario o PDF pesado debe enviarse codificado por aire. Toda extracción se hace en disco local.

2. **PROHIBIDO: Duplicidad y Falta de Formato en Reportes:**
   - Los reportes de hallazgos (`.md`) no pueden tener espacios en el filename. Deben emplear snake_case estricto (ej. `REPORTE_NUEVO_COACCION_2026-04-06.md`). 
   - Archivos fantasma y duplicados quiebran la organización del Wiki-Indexer.

3. **PROHIBIDO: Compresión de Lógica sin Refactor (Inercia):**
   - Fallos "silenciosos" donde scripts pesados de 1300 líneas ignoraban la lógica de extracción local sin emitir logs de quiebre. En adelante, todo módulo de extracción como el pipeline estratégico de Gemini-Pro debe validarse vía `py_compile`.

---
**Dictamen Operativo:** La versión V2.3.1 de *Minería Silenciosa* ha estabilizado todos los módulos críticos. El iMac puede ahora operar indefinidamente procesando la evidencia sin interrupciones ni recargas pesadas de API.
