import base64
import json
import os
import re
from datetime import datetime
import cv2
import numpy as np
import pandas as pd
import streamlit as st
from database import init_db, get_connection, hash_password, verify_password

st.set_page_config(
    page_title="Portal Vehicular Estudiante UIS",
    page_icon="🎓",
    layout="wide",
)

UPLOAD_DIR = "uploads/vehiculos"
os.makedirs(UPLOAD_DIR, exist_ok=True)
init_db()


def extraer_codigo_desde_qr(archivo_imagen) -> str | None:
    """Lee el QR del carné digital UIS con OpenCV y extrae el campo DOCUMENT."""
    bytes_imagen = np.asarray(bytearray(archivo_imagen.getvalue()), dtype=np.uint8)
    img = cv2.imdecode(bytes_imagen, cv2.IMREAD_COLOR)
    if img is None:
        return None

    detector = cv2.QRCodeDetector()
    datos, _, _ = detector.detectAndDecode(img)
    if not datos:
        gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        datos, _, _ = detector.detectAndDecode(gris)

    if not datos:
        return None

    try:
        payload = json.loads(base64.b64decode(datos.strip()).decode("utf-8"))
        documento = str(payload.get("DOCUMENT", "")).strip()
        return documento if documento else None
    except Exception:
        return datos.strip()


def registrar_cuenta_usuario(codigo: str, nombre: str, password: str) -> tuple[bool, str]:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT 1 FROM usuarios WHERE codigo_estudiantil = ?",
        (codigo.strip(),),
    )
    if cursor.fetchone():
        conn.close()
        return False, "Este código estudiantil ya tiene una cuenta registrada. Inicia sesión en la otra pestaña."

    pwd_hash, salt = hash_password(password)
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute(
        """
        INSERT INTO usuarios (codigo_estudiantil, nombre, password_hash, salt, fecha_registro)
        VALUES (?, ?, ?, ?, ?)
        """,
        (codigo.strip(), nombre.strip(), pwd_hash, salt, ahora),
    )
    conn.commit()
    conn.close()
    return True, "Cuenta creada correctamente."


def autenticar_usuario(codigo: str, password: str) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT codigo_estudiantil, nombre, password_hash, salt FROM usuarios WHERE codigo_estudiantil = ?",
        (codigo.strip(),),
    )
    fila = cursor.fetchone()
    conn.close()

    if not fila:
        return None

    cod_db, nombre_db, hash_db, salt_db = fila
    if verify_password(password, hash_db, salt_db):
        return {"codigo": cod_db, "nombre": nombre_db}
    return None


def guardar_foto_vehiculo(codigo: str, archivo_foto) -> str:
    """Guarda la imagen en disco y retorna la ruta relativa."""
    extension = os.path.splitext(archivo_foto.name)[1].lower() or ".jpg"
    marca_tiempo = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    nombre_archivo = f"{codigo.strip()}_{marca_tiempo}{extension}"
    ruta_completa = os.path.join(UPLOAD_DIR, nombre_archivo)

    with open(ruta_completa, "wb") as f:
        f.write(archivo_foto.getbuffer())

    return ruta_completa


def registrar_vehiculo_usuario(
    codigo: str,
    propietario: str,
    tipo_vehiculo: str,
    placa: str,
    detalles: str,
    foto_path: str,
) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO vehiculos (codigo_estudiantil, propietario, tipo_vehiculo, placa, detalles, foto_path, estado)
        VALUES (?, ?, ?, ?, ?, ?, 'ACTIVO')
        """,
        (
            codigo.strip(),
            propietario.strip(),
            tipo_vehiculo.strip(),
            placa.strip().upper(),
            detalles.strip(),
            foto_path,
        ),
    )
    conn.commit()
    conn.close()


def obtener_datos_estudiante(codigo: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    conn = get_connection()
    df_vehiculos = pd.read_sql_query(
        """
        SELECT id, tipo_vehiculo, placa, detalles, foto_path, estado
        FROM vehiculos
        WHERE codigo_estudiantil = ?
        ORDER BY id DESC
        """,
        conn,
        params=(codigo,),
    )
    df_historial = pd.read_sql_query(
        """
        SELECT tipo_vehiculo, tipo_movimiento, observacion, timestamp
        FROM accesos
        WHERE codigo_estudiantil = ?
        ORDER BY id DESC LIMIT 10
        """,
        conn,
        params=(codigo,),
    )
    conn.close()
    return df_vehiculos, df_historial


def cambiar_estado_vehiculo(vehiculo_id: int, nuevo_estado: str) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE vehiculos SET estado = ? WHERE id = ?",
        (nuevo_estado, vehiculo_id),
    )
    conn.commit()
    conn.close()


def eliminar_vehiculo(vehiculo_id: int, foto_path: str) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vehiculos WHERE id = ?", (vehiculo_id,))
    conn.commit()
    conn.close()

    if foto_path and os.path.exists(foto_path):
        os.remove(foto_path)


st.title("🎓 Portal Vehicular — Estudiantes UIS")
st.caption("Registro seguro con contraseña para administrar tus vehículos autorizados en portería.")

usuario_actual = st.session_state.get("usuario_autenticado")

# ==============================================================================
# VISTA 1: PANTALLA DE ACCESO Y REGISTRO CON CONTRASEÑA
# ==============================================================================
if not usuario_actual:
    col_auth, col_info = st.columns([1.3, 1], gap="large")

    with col_auth:
        usar_qr = st.toggle("📷 Autocompletar mi código escaneando el QR del carné UIS")
        if usar_qr:
            foto_carne = st.camera_input("Enfoca tu carné UIS")
            if foto_carne is not None:
                foto_hash = hash(foto_carne.getvalue())
                if st.session_state.get("ultimo_qr_auth") != foto_hash:
                    st.session_state["ultimo_qr_auth"] = foto_hash
                    cod_detectado = extraer_codigo_desde_qr(foto_carne)
                    if cod_detectado:
                        st.session_state["codigo_prefill"] = cod_detectado
                        st.success(f"Código detectado del carné: {cod_detectado}")
                    else:
                        st.warning("No se detectó el QR. Acerca más el carné o ingrésalo manualmente.")

        codigo_sugerido = st.session_state.get("codigo_prefill", "")

        tab_login, tab_registro = st.tabs(["🔑 Iniciar Sesión", "📝 Crear Cuenta Nueva"])

        with tab_login:
            with st.form("form_login"):
                cod_login = st.text_input(
                    "Código estudiantil / Documento:",
                    value=codigo_sugerido,
                    placeholder="Ej. 2232503",
                )
                pwd_login = st.text_input("Contraseña:", type="password")
                btn_login = st.form_submit_button("Ingresar a mi portal", use_container_width=True)

                if btn_login:
                    if not cod_login.strip() or not pwd_login:
                        st.error("Ingresa tu código y contraseña.")
                    else:
                        user = autenticar_usuario(cod_login, pwd_login)
                        if user:
                            st.session_state["usuario_autenticado"] = user
                            st.rerun()
                        else:
                            st.error("Código o contraseña incorrectos.")

        with tab_registro:
            with st.form("form_registro"):
                cod_reg = st.text_input(
                    "Código estudiantil / Documento:",
                    value=codigo_sugerido,
                    placeholder="Ej. 2232522",
                )
                nom_reg = st.text_input("Nombre completo:", placeholder="Ej. Camilo Andrés Torres")
                pwd_reg = st.text_input(
                    "Crea una contraseña (mínimo 4 caracteres):",
                    type="password",
                )
                pwd_reg_conf = st.text_input("Confirma tu contraseña:", type="password")
                btn_reg = st.form_submit_button("Registrarme e ingresar", use_container_width=True)

                if btn_reg:
                    if not cod_reg.strip() or not nom_reg.strip() or not pwd_reg:
                        st.error("Completa todos los campos.")
                    elif len(pwd_reg) < 4:
                        st.error("La contraseña debe tener al menos 4 caracteres.")
                    elif pwd_reg != pwd_reg_conf:
                        st.error("Las contraseñas no coinciden.")
                    else:
                        ok, msg = registrar_cuenta_usuario(cod_reg, nom_reg, pwd_reg)
                        if ok:
                            st.session_state["usuario_autenticado"] = {
                                "codigo": cod_reg.strip(),
                                "nombre": nom_reg.strip(),
                            }
                            st.rerun()
                        else:
                            st.error(msg)

    with col_info:
        st.info(
            "**Requisitos de inscripción vehicular:**\n\n"
            "• **Carros y Motos:** Requieren número de placa vigente y fotografía clara del vehículo.\n"
            "• **Bicicletas y Monopatines:** Requieren marca/color/serial del marco y fotografía obligatoria.\n"
            "• **Control diario:** Activa o desactiva el vehículo que uses cada día para agilizar el paso en portería.\n\n"
            "*Cuentas de prueba precargadas: `2232503` y `2232504` (clave: `uis2026`).*"
        )

    st.stop()

# ==============================================================================
# VISTA 2: PANEL PRIVADO DEL ESTUDIANTE AUTENTICADO
# ==============================================================================
codigo_actual = usuario_actual["codigo"]
nombre_actual = usuario_actual["nombre"]

col_bienvenida, col_salir = st.columns([4, 1])
with col_bienvenida:
    st.markdown(f"### 👤 {nombre_actual} · Código `{codigo_actual}`")
with col_salir:
    if st.button("🚪 Cerrar sesión", use_container_width=True):
        del st.session_state["usuario_autenticado"]
        st.rerun()

st.divider()

df_vehiculos, df_historial = obtener_datos_estudiante(codigo_actual)
col_registro, col_lista = st.columns([1, 1.2], gap="large")

with col_registro:
    st.subheader("1. Registrar Nuevo Vehículo")
    if "msg_portal_ok" in st.session_state:
        st.success(st.session_state.pop("msg_portal_ok"))

    # Selector fuera del form para mostrar/ocultar el campo de placa dinámicamente
    tipo_input = st.selectbox(
        "Tipo de vehículo:",
        ["Bicicleta", "Monopatín", "Moto", "Carro"],
    )
    es_motorizado = tipo_input in ["Moto", "Carro"]

    with st.form("form_registro_propio", clear_on_submit=True):
        placa_input = ""
        if es_motorizado:
            ejemplo_placa = "Ej. ABC123" if tipo_input == "Carro" else "Ej. XYZ98F"
            placa_input = st.text_input(
                "Número de placa (obligatorio):",
                placeholder=ejemplo_placa,
                max_chars=10,
            )

        detalles_input = st.text_input(
            "Marca, color y serial / características (obligatorio):",
            placeholder="Ej. Yamaha FZ 2.0 Azul" if es_motorizado else "Ej. GW Azul Marco #40219",
        )

        foto_vehiculo = st.file_uploader(
            "Foto del vehículo (obligatoria — JPG, PNG o WEBP):",
            type=["jpg", "jpeg", "png", "webp"],
        )

        guardar = st.form_submit_button("Guardar vehículo", use_container_width=True)

        if guardar:
            placa_limpia = re.sub(r"[^A-Za-z0-9]", "", placa_input).upper()

            if es_motorizado and len(placa_limpia) < 5:
                st.error(f"Para registrar una {tipo_input.lower()} debes ingresar un número de placa válido (ej. ABC123 o XYZ98F).")
            elif not detalles_input.strip():
                st.error("Escribe la marca, color o características del vehículo.")
            elif foto_vehiculo is None:
                st.error("Debes adjuntar al menos una foto del vehículo para completar el registro.")
            else:
                ruta_foto = guardar_foto_vehiculo(codigo_actual, foto_vehiculo)
                registrar_vehiculo_usuario(
                    codigo_actual,
                    nombre_actual,
                    tipo_input,
                    placa_limpia if es_motorizado else "",
                    detalles_input,
                    ruta_foto,
                )
                texto_placa = f" · Placa {placa_limpia}" if placa_limpia else ""
                st.session_state["msg_portal_ok"] = (
                    f"✅ {tipo_input}{texto_placa} ({detalles_input.strip()}) registrada con fotografía."
                )
                st.rerun()

with col_lista:
    st.subheader("2. Mis Vehículos Registrados")
    if df_vehiculos.empty:
        st.warning("Aún no tienes vehículos inscritos. Registra uno en el formulario de la izquierda.")
    else:
        activos = len(df_vehiculos[df_vehiculos["estado"] == "ACTIVO"])
        if activos == 1:
            st.caption("⚡ Tienes **1 vehículo activo**: paso rápido automático (<50 ms) en portería.")
        elif activos > 1:
            st.caption("🤖 Tienes **varios vehículos activos**: VigiBot-UIS validará en cuál ingresas.")

        for _, fila in df_vehiculos.iterrows():
            with st.container(border=True):
                c_foto, c_info, c_acciones = st.columns([1.2, 2.3, 1.1])

                with c_foto:
                    ruta = fila["foto_path"]
                    if ruta and os.path.exists(ruta):
                        st.image(ruta, use_container_width=True)
                    else:
                        st.caption("Sin foto")

                with c_info:
                    estado_actual = fila["estado"]
                    icono = "🟢" if estado_actual == "ACTIVO" else "⚪"
                    etiqueta_placa = f" · **Placa:** `{fila['placa']}`" if fila["placa"] else ""
                    st.markdown(f"{icono} **{fila['tipo_vehiculo']}**{etiqueta_placa}")
                    st.caption(fila["detalles"])

                with c_acciones:
                    if estado_actual == "ACTIVO":
                        if st.button("Desactivar", key=f"off_{fila['id']}", use_container_width=True):
                            cambiar_estado_vehiculo(int(fila["id"]), "INACTIVO")
                            st.rerun()
                    else:
                        if st.button("Activar", key=f"on_{fila['id']}", use_container_width=True):
                            cambiar_estado_vehiculo(int(fila["id"]), "ACTIVO")
                            st.rerun()

                    if st.button("🗑️ Eliminar", key=f"del_{fila['id']}", use_container_width=True):
                        eliminar_vehiculo(int(fila["id"]), fila["foto_path"])
                        st.rerun()

st.divider()

st.subheader("3. Mis Últimos Movimientos en el Campus")
if df_historial.empty:
    st.caption("Todavía no tienes entradas ni salidas registradas en portería.")
else:
    st.dataframe(df_historial, use_container_width=True, hide_index=True)