import os
from google import genai
from google.genai import types
from dotenv import load_dotenv
from tools import (
    consultar_historial_estudiante,
    registrar_movimiento_estudiante,
    ejecutar_consulta_sql_lectura,
)

load_dotenv()

SYSTEM_INSTRUCTION = """
Eres VigiBot-UIS, el Agente de Inteligencia Artificial supervisor del control vehicular de la Universidad Industrial de Santander.

El sistema base determinista (scanner.py) te delega únicamente los casos que requieren razonamiento:
1. Ambigüedad: Estudiantes con más de un vehículo registrado (revisa su historial para inferir cuál vehículo entra o sale).
2. Conflictos de estado: Entradas o salidas duplicadas (si olvidó registrar salida previa, cierra el ciclo anterior con observacion 'Cierre automático por inconsistencia' y registra el movimiento actual).
3. Excepciones reportadas por el vigilante en lenguaje natural: Visitantes, domiciliarios o estudiantes sin batería en el celular (verifica sus datos antes de registrar).
4. Consultas operativas: Preguntas sobre aforo, vehículos dentro del campus o historial mediante consultas SELECT.

Responde siempre en español, de forma directa, operativa y concisa para la pantalla del vigilante en portería.
"""


def invocar_agente_excepcion(contexto_o_pregunta: str) -> str:
    """Activa el razonamiento del Agente de IA para resolver excepciones, conflictos o consultas."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "⚠️ Error: No se encontró GEMINI_API_KEY en el archivo .env."

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contexto_o_pregunta,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=[
                consultar_historial_estudiante,
                registrar_movimiento_estudiante,
                ejecutar_consulta_sql_lectura,
            ],
            temperature=0.1,
        ),
    )
    return f"🤖 [AGENTE VIGIBOT]: {response.text}"