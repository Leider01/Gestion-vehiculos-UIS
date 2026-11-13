import os
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from google import genai
from google.genai import types
from dotenv import load_dotenv
from database import get_connection
from tools import (
    consultar_historial_estudiante,
    registrar_movimiento_estudiante,
    ejecutar_consulta_sql_lectura,
)

load_dotenv()

SYSTEM_INSTRUCTION = """
Eres VigiBot-UIS, el Agente supervisor del control vehicular de la Universidad Industrial de Santander.

Cuando el vigilante te envíe un reporte (incluso corto como "2232503 carro ABC123"):
1. Consulta primero `consultar_historial_estudiante` con el código recibido para verificar sus vehículos y placas registradas.
2. Si el vigilante NO especificó si es ENTRADA o SALIDA, dedúcelo del último movimiento de ese vehículo en `ultimos_accesos`: si el último movimiento fue ENTRADA, registra SALIDA; si no tiene registros previos o el último fue SALIDA, registra ENTRADA.
3. Si se indica una placa, verifica si coincide con la registrada en `vehiculos_registrados` e inclúyela en `observacion`.
4. Ejecuta siempre `registrar_movimiento_estudiante` de inmediato sin pedir confirmaciones.
5. Si el estudiante no tiene vehículos registrados, igual registra el movimiento con observacion "Ingreso excepcional - vehículo no registrado en portal".
6. Si es una pregunta sobre aforo o historial, usa `ejecutar_consulta_sql_lectura`.

Responde en español, de forma directa y operativa (máximo 3 líneas).
"""

MODELOS_RAPIDOS = [
    "gemini-3.8-flash",
    "gemini-3.8-flash-lite",
]


def _ejecutar_con_timeout(client: genai.Client, modelo: str, prompt: str, config: types.GenerateContentConfig, segundos: int = 7):
    """Ejecuta la llamada a Gemini con un límite estricto en segundos para evitar congelamientos."""
    executor = ThreadPoolExecutor(max_workers=1)
    futuro = executor.submit(
        client.models.generate_content,
        model=modelo,
        contents=prompt,
        config=config,
    )
    try:
        return futuro.result(timeout=segundos)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _respaldo_operativo_local(texto: str) -> str | None:
    """
    Respaldo determinista instantáneo (<10 ms) cuando Gemini tarda >7s o devuelve 503.
    Soporta registros ('2232503 carro ABC123') y consultas básicas de aforo.
    """
    texto_limpio = texto.strip()

    # 1. Soporte de consulta rápida de aforo si pregunta cuántos vehículos hay dentro
    if re.search(r"\b(aforo|cu[aá]ntos|dentro|ocupaci[oó]n)\b", texto_limpio, re.I):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT tipo_vehiculo, COUNT(*)
            FROM accesos
            WHERE id IN (SELECT MAX(id) FROM accesos GROUP BY codigo_estudiantil, tipo_vehiculo)
            AND tipo_movimiento = 'ENTRADA'
            GROUP BY tipo_vehiculo
        """)
        filas = cursor.fetchall()
        conn.close()
        if not filas:
            return "🛡️ [CONSULTA LOCAL]: Actualmente hay **0 vehículos** registrados dentro del campus."
        resumen = ", ".join(f"{cant} {tipo}(s)" for tipo, cant in filas)
        return f"🛡️ [CONSULTA LOCAL]: Vehículos dentro del campus: **{resumen}**."

    # 2. Registro supervisado de movimiento (código + tipo de vehículo + placa opcional)
    match_codigo = re.search(r"\b(\d{5,12})\b", texto_limpio)
    match_vehiculo = re.search(r"\b(carro|moto|bicicleta|bici|monopat[ií]n|patineta)\b", texto_limpio, re.I)

    if not match_codigo or not match_vehiculo:
        return None

    codigo = match_codigo.group(1)
    raw_tipo = match_vehiculo.group(1).lower()
    mapa_tipos = {
        "carro": "Carro",
        "moto": "Moto",
        "bicicleta": "Bicicleta",
        "bici": "Bicicleta",
        "monopatin": "Monopatín",
        "monopatín": "Monopatín",
        "patineta": "Monopatín",
    }
    tipo_vehiculo = mapa_tipos[raw_tipo]

    if re.search(r"\bsalida|sali[oó]|sale\b", texto_limpio, re.I):
        movimiento = "SALIDA"
    elif re.search(r"\bentrada|entr[oó]|entra|ingreso\b", texto_limpio, re.I):
        movimiento = "ENTRADA"
    else:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT tipo_movimiento FROM accesos
            WHERE codigo_estudiantil = ? AND LOWER(tipo_vehiculo) = LOWER(?)
            ORDER BY id DESC LIMIT 1
            """,
            (codigo, tipo_vehiculo),
        )
        ultimo = cursor.fetchone()
        conn.close()
        movimiento = "SALIDA" if (ultimo and ultimo[0] == "ENTRADA") else "ENTRADA"

    # Detectar placa (ej. ABC123, XYZ98F)
    match_placa = re.search(r"\b([A-Za-z]{3}\d{2}[A-Za-z0-9])\b", texto_limpio)
    placa_detectada = match_placa.group(1).upper() if match_placa else ""

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT placa FROM vehiculos
        WHERE codigo_estudiantil = ? AND LOWER(tipo_vehiculo) = LOWER(?)
        """,
        (codigo, tipo_vehiculo),
    )
    registros = cursor.fetchall()
    conn.close()

    if not registros:
        obs = f"Placa {placa_detectada} - Vehículo no inscrito en portal" if placa_detectada else "Vehículo no inscrito en portal"
    elif placa_detectada:
        placas_db = [(r[0] or "").upper() for r in registros]
        if placa_detectada in placas_db:
            obs = f"Placa {placa_detectada} verificada en base de datos"
        else:
            registradas = ", ".join(p for p in placas_db if p) or "sin placa"
            obs = f"Alerta: Placa {placa_detectada} no coincide con registrada ({registradas})"
    else:
        obs = "Registro supervisado en portería"

    registrar_movimiento_estudiante(codigo, tipo_vehiculo, movimiento, obs)
    detalle_placa = f" · Placa `{placa_detectada}`" if placa_detectada else ""
    return f"🛡️ [REGISTRO SUPERVISADO]: **{movimiento}** guardada para `{codigo}` — {tipo_vehiculo}{detalle_placa}. ({obs})"


def invocar_agente_excepcion(contexto_o_pregunta: str) -> str:
    """Activa VigiBot-UIS con timeout estricto de 7s y respaldo operativo inmediato."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        respaldo = _respaldo_operativo_local(contexto_o_pregunta)
        return respaldo or "⚠️ Error: No se encontró GEMINI_API_KEY en el archivo .env."

    try:
        http_opts = types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1))
        client = genai.Client(api_key=api_key, http_options=http_opts)
    except Exception:
        client = genai.Client(api_key=api_key)

    config_agente = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        tools=[
            consultar_historial_estudiante,
            registrar_movimiento_estudiante,
            ejecutar_consulta_sql_lectura,
        ],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(
            maximum_remote_calls=2
        ),
        temperature=0.1,
    )

    ultimo_error = ""
    for modelo in MODELOS_RAPIDOS:
        try:
            print(f"[VigiBot-UIS] Consultando {modelo} (máx 7s)...")
            response = _ejecutar_con_timeout(
                client, modelo, contexto_o_pregunta, config_agente, segundos=7
            )
            if response and response.text:
                print(f"[VigiBot-UIS] OK con {modelo}.")
                return f"🤖 [AGENTE VIGIBOT · {modelo}]: {response.text}"
        except FuturesTimeoutError:
            ultimo_error = f"Timeout (>7s) en {modelo}"
            print(f"[VigiBot-UIS] {ultimo_error}, pasando al respaldo...")
            break
        except Exception as e:
            ultimo_error = str(e)
            print(f"[VigiBot-UIS] Error en {modelo}: {ultimo_error}")
            continue

    respaldo = _respaldo_operativo_local(contexto_o_pregunta)
    if respaldo:
        return respaldo

    return (
        "⚠️ Gemini no respondió en 7 segundos (alta demanda temporal). "
        "Para registrar un movimiento escribe código, vehículo y placa (ej. `2232503 carro ABC123`)."
    )