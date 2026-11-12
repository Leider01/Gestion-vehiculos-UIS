import sqlite3

DB_NAME = "acceso_vehicular_uis.db"


def get_connection():
    return sqlite3.connect(DB_NAME)


def init_db():
    """Crea las tablas en SQLite e inserta registros de prueba para validar ambos flujos."""
    conn = get_connection()
    cursor = conn.cursor()

    # Tabla de vehículos registrados por estudiante
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vehiculos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_estudiantil TEXT NOT NULL,
            propietario TEXT NOT NULL,
            tipo_vehiculo TEXT NOT NULL,
            detalles TEXT NOT NULL,
            estado TEXT DEFAULT 'ACTIVO'
        )
    """)

    # Tabla histórica de entradas y salidas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accesos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_estudiantil TEXT NOT NULL,
            tipo_vehiculo TEXT NOT NULL,
            tipo_movimiento TEXT NOT NULL,
            observacion TEXT DEFAULT 'Registro automático QR',
            timestamp TEXT NOT NULL
        )
    """)

    # Datos de prueba:
    # - 2232504 tiene 1 solo vehículo -> Activa el flujo rápido determinista
    # - 2232503 tiene 2 vehículos -> Activa el Agente de IA por ambigüedad
    cursor.execute("""
        INSERT OR IGNORE INTO vehiculos (id, codigo_estudiantil, propietario, tipo_vehiculo, detalles)
        VALUES
        (1, '2232503', 'Leider Gómez', 'Bicicleta', 'GW All Black Marco 883'),
        (2, '2232503', 'Leider Gómez', 'Carro', 'Mazda 3 - Placa XYZ123'),
        (3, '2232504', 'Carlos Pérez', 'Moto', 'Yamaha FZ 2.0 - Placa ABC98D')
    """)

    conn.commit()
    conn.close()