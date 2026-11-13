import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime

DB_NAME = "acceso_vehicular_uis.db"


def get_connection():
    return sqlite3.connect(DB_NAME, timeout=10)


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """Genera un hash seguro PBKDF2-SHA256 con salt aleatorio."""
    if salt is None:
        salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    ).hex()
    return pwd_hash, salt


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """Verifica de forma segura si la contraseña ingresada coincide con el hash."""
    calc_hash, _ = hash_password(password, salt)
    return hmac.compare_digest(calc_hash, stored_hash)


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            codigo_estudiantil TEXT PRIMARY KEY,
            nombre TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            fecha_registro TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vehiculos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_estudiantil TEXT NOT NULL,
            propietario TEXT NOT NULL,
            tipo_vehiculo TEXT NOT NULL,
            placa TEXT DEFAULT '',
            detalles TEXT NOT NULL,
            foto_path TEXT DEFAULT '',
            estado TEXT DEFAULT 'ACTIVO'
        )
    """)

    # Migración segura si la tabla ya existía sin las columnas placa o foto_path
    cursor.execute("PRAGMA table_info(vehiculos)")
    columnas_existentes = [col[1] for col in cursor.fetchall()]
    if "placa" not in columnas_existentes:
        cursor.execute("ALTER TABLE vehiculos ADD COLUMN placa TEXT DEFAULT ''")
    if "foto_path" not in columnas_existentes:
        cursor.execute("ALTER TABLE vehiculos ADD COLUMN foto_path TEXT DEFAULT ''")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accesos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_estudiantil TEXT NOT NULL,
            tipo_vehiculo TEXT NOT NULL,
            tipo_movimiento TEXT NOT NULL,
            observacion TEXT,
            timestamp TEXT NOT NULL
        )
    """)

    cursor.execute("SELECT COUNT(*) FROM vehiculos")
    if cursor.fetchone()[0] == 0:
        datos_prueba = [
            ("2232503", "Leider Gómez", "Bicicleta", "", "GW Todoterreno Negra/Verde", "", "ACTIVO"),
            ("2232503", "Leider Gómez", "Carro", "ABC123", "Chevrolet Spark GT Gris", "", "ACTIVO"),
            ("2232504", "María Fernanda Pérez", "Moto", "XYZ98F", "Yamaha FZ 2.0 Azul", "", "ACTIVO"),
        ]
        cursor.executemany(
            """
            INSERT INTO vehiculos (codigo_estudiantil, propietario, tipo_vehiculo, placa, detalles, foto_path, estado)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            datos_prueba,
        )

    cursor.execute("SELECT COUNT(*) FROM usuarios")
    if cursor.fetchone()[0] == 0:
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        h1, s1 = hash_password("uis2026")
        h2, s2 = hash_password("uis2026")
        usuarios_prueba = [
            ("2232503", "Leider Gómez", h1, s1, ahora),
            ("2232504", "María Fernanda Pérez", h2, s2, ahora),
        ]
        cursor.executemany(
            "INSERT INTO usuarios (codigo_estudiantil, nombre, password_hash, salt, fecha_registro) VALUES (?, ?, ?, ?, ?)",
            usuarios_prueba,
        )

    conn.commit()
    conn.close()