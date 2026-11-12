import base64
import json
from datetime import datetime
from database import get_connection
from agent import invocar_agente_excepcion


def procesar_lectura_rapida(qr_base64: str, tipo_movimiento: str) -> str:
    """
    Capa 1 (Determinista): Decodifica el QR del carné UIS y ejecuta el registro directo
    si el caso es limpio. Delega al Agente de IA si detecta ambigüedad o anomalías.
    """
    try:
        datos_qr = json.loads(base64.b64decode(qr_base64.strip()).decode("utf-8"))
        documento = str(datos_qr.get("DOCUMENT", "")).strip()
        if not documento:
            raise ValueError("Campo DOCUMENT vacío")
    except Exception:
        return invocar_agente_excepcion(
            f"Se escaneó un código QR inválido o no institucional: '{qr_base64}'. Indica al vigilante cómo proceder."
        )

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT propietario, tipo_vehiculo, detalles FROM vehiculos WHERE codigo_estudiantil = ? AND estado = 'ACTIVO'",
        (documento,),
    )
    vehiculos = cursor.fetchall()

    cursor.execute(
        "SELECT tipo_vehiculo, tipo_movimiento, timestamp FROM accesos WHERE codigo_estudiantil = ? ORDER BY id DESC LIMIT 1",
        (documento,),
    )
    ultimo_movimiento = cursor.fetchone()
    conn.close()

    # Caso A: Sin vehículos registrados -> Delegar al Agente
    if not vehiculos:
        return invocar_agente_excepcion(
            f"El usuario con documento {documento} intenta registrar {tipo_movimiento.upper()}, "
            "pero no tiene vehículos registrados en la base de datos."
        )

    # Caso B: Múltiples vehículos -> Delegar al Agente
    if len(vehiculos) > 1:
        return invocar_agente_excepcion(
            f"El estudiante {documento} tiene múltiples vehículos registrados ({vehiculos}) "
            f"y está en portería para {tipo_movimiento.upper()}. Último registro: {ultimo_movimiento}. "
            "Determina qué vehículo corresponde y registra el movimiento."
        )

    # Caso C: Conflicto de estado (ej. dos ENTRADAS seguidas) -> Delegar al Agente
    if ultimo_movimiento and ultimo_movimiento[1] == tipo_movimiento.upper():
        return invocar_agente_excepcion(
            f"Conflicto de estado para {documento}: intenta realizar {tipo_movimiento.upper()}, "
            f"pero su último registro ({ultimo_movimiento[2]}) también fue {ultimo_movimiento[1]} "
            f"en {ultimo_movimiento[0]}. Resuelve la inconsistencia y registra el movimiento actual."
        )

    # Caso D: Flujo limpio (1 vehículo y estado coherente) -> Ejecución directa sin IA
    propietario, tipo_vehiculo, detalles = vehiculos[0]
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO accesos (codigo_estudiantil, tipo_vehiculo, tipo_movimiento, observacion, timestamp)
        VALUES (?, ?, ?, 'Registro automático QR', ?)
        """,
        (documento, tipo_vehiculo, tipo_movimiento.upper(), ahora),
    )
    conn.commit()
    conn.close()

    return (
        f"⚡ [REGISTRO DIRECTO <50ms] {tipo_movimiento.upper()}: "
        f"{propietario} ({documento}) | {tipo_vehiculo} ({detalles}) | {ahora}"
    )