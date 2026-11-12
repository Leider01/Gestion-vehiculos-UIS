from datetime import datetime
from database import get_connection


def consultar_historial_estudiante(codigo_estudiantil: str) -> dict:
    """Consulta los vehículos registrados y los últimos 5 movimientos de un estudiante."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT propietario, tipo_vehiculo, detalles, estado FROM vehiculos WHERE codigo_estudiantil = ?",
        (codigo_estudiantil.strip(),),
    )
    vehiculos = [
        {"propietario": r[0], "tipo": r[1], "detalles": r[2], "estado": r[3]}
        for r in cursor.fetchall()
    ]

    cursor.execute(
        """
        SELECT tipo_vehiculo, tipo_movimiento, observacion, timestamp
        FROM accesos
        WHERE codigo_estudiantil = ?
        ORDER BY id DESC LIMIT 5
        """,
        (codigo_estudiantil.strip(),),
    )
    historial = [
        {"vehiculo": r[0], "movimiento": r[1], "observacion": r[2], "fecha_hora": r[3]}
        for r in cursor.fetchall()
    ]

    conn.close()
    return {
        "codigo_estudiantil": codigo_estudiantil,
        "vehiculos_registrados": vehiculos,
        "ultimos_movimientos": historial,
    }


def registrar_movimiento_estudiante(
    codigo_estudiantil: str,
    tipo_vehiculo: str,
    tipo_movimiento: str,
    observacion: str = "Gestionado por Agente VigiBot-UIS",
) -> dict:
    """Inserta un registro de ENTRADA, SALIDA o cierre administrativo en la tabla accesos."""
    conn = get_connection()
    cursor = conn.cursor()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute(
        """
        INSERT INTO accesos (codigo_estudiantil, tipo_vehiculo, tipo_movimiento, observacion, timestamp)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            codigo_estudiantil.strip(),
            tipo_vehiculo.strip(),
            tipo_movimiento.strip().upper(),
            observacion.strip(),
            ahora,
        ),
    )
    conn.commit()
    conn.close()

    return {
        "exito": True,
        "mensaje": f"Registro '{tipo_movimiento.upper()}' guardado para {codigo_estudiantil} ({tipo_vehiculo}) a las {ahora}.",
    }


def ejecutar_consulta_sql_lectura(consulta_sql: str) -> dict:
    """
    Ejecuta consultas SQL de solo lectura (SELECT) sobre la base de datos
    para responder preguntas administrativas o de ocupación del campus.
    Tablas disponibles:
    - vehiculos(id, codigo_estudiantil, propietario, tipo_vehiculo, detalles, estado)
    - accesos(id, codigo_estudiantil, tipo_vehiculo, tipo_movimiento, observacion, timestamp)
    """
    sql_limpio = consulta_sql.strip()
    if not sql_limpio.upper().startswith("SELECT"):
        return {"error": "Solo se permiten consultas de lectura que inicien con SELECT."}

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql_limpio)
        columnas = [desc[0] for desc in cursor.description] if cursor.description else []
        filas = cursor.fetchall()
        conn.close()
        return {"columnas": columnas, "resultados": filas}
    except Exception as e:
        return {"error": f"Error al ejecutar consulta SQL: {str(e)}"}