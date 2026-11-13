import json
from datetime import datetime
from database import get_connection


def consultar_historial_estudiante(codigo_estudiantil: str) -> str:
    """Consulta los vehículos registrados (incluyendo placa) y los últimos movimientos de un estudiante."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, propietario, tipo_vehiculo, placa, detalles, estado
        FROM vehiculos
        WHERE codigo_estudiantil = ?
        """,
        (codigo_estudiantil.strip(),),
    )
    vehiculos = [
        {
            "id": r[0],
            "propietario": r[1],
            "tipo_vehiculo": r[2],
            "placa": r[3] or "N/A",
            "detalles": r[4],
            "estado": r[5],
        }
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
    accesos = [
        {
            "tipo_vehiculo": r[0],
            "tipo_movimiento": r[1],
            "observacion": r[2],
            "timestamp": r[3],
        }
        for r in cursor.fetchall()
    ]

    conn.close()
    return json.dumps(
        {
            "codigo_estudiantil": codigo_estudiantil.strip(),
            "vehiculos_registrados": vehiculos,
            "ultimos_accesos": accesos,
        },
        ensure_ascii=False,
    )


def registrar_movimiento_estudiante(
    codigo_estudiantil: str,
    tipo_vehiculo: str,
    tipo_movimiento: str,
    observacion: str = "Registro supervisado por VigiBot-UIS",
) -> str:
    """Registra una ENTRADA o SALIDA vehicular en la tabla accesos de SQLite."""
    tipo_v = tipo_vehiculo.strip().capitalize()
    if tipo_v.lower() in ("monopatin", "monopatín"):
        tipo_v = "Monopatín"

    mov = tipo_movimiento.strip().upper()
    if mov not in ("ENTRADA", "SALIDA"):
        mov = "ENTRADA"

    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO accesos (codigo_estudiantil, tipo_vehiculo, tipo_movimiento, observacion, timestamp)
        VALUES (?, ?, ?, ?, ?)
        """,
        (codigo_estudiantil.strip(), tipo_v, mov, observacion.strip(), ahora),
    )
    conn.commit()
    conn.close()

    return (
        f"Movimiento guardado: {mov} | Código: {codigo_estudiantil.strip()} | "
        f"Vehículo: {tipo_v} | Obs: {observacion.strip()} | Hora: {ahora}"
    )


def ejecutar_consulta_sql_lectura(consulta_sql: str) -> str:
    """Ejecuta una consulta SQL de solo lectura (SELECT) sobre la base de datos de portería."""
    sql_limpio = consulta_sql.strip().rstrip(";")
    if not sql_limpio.upper().startswith("SELECT"):
        return "Error: Solo se permiten consultas de lectura que inicien con SELECT."

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql_limpio)
        columnas = [desc[0] for desc in cursor.description] if cursor.description else []
        filas = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
        return json.dumps(filas[:25], ensure_ascii=False)
    except Exception as e:
        return f"Error al ejecutar SQL: {str(e)}"
    finally:
        conn.close()