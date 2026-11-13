import base64
import json
import cv2
import numpy as np
import pandas as pd
import streamlit as st
from database import init_db, get_connection
from scanner import procesar_lectura_rapida
from agent import invocar_agente_excepcion

st.set_page_config(
    page_title="Control Vehicular UIS — VigiBot",
    page_icon="🛡️",
    layout="wide",
)

init_db()


def generar_qr_simulado(codigo_estudiantil: str) -> str:
    payload = {
        "ID": 34520,
        "VERIFICATION": 105295998,
        "ID_DEVICE": "V74n7egxW5sMs7UC9fo6AtP17J8u0L",
        "DOCUMENT": codigo_estudiantil.strip(),
    }
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")


def decodificar_qr_imagen(archivo_imagen) -> str | None:
    """Convierte la captura de cámara en matriz OpenCV y extrae el contenido del QR."""
    bytes_imagen = np.asarray(bytearray(archivo_imagen.getvalue()), dtype=np.uint8)
    img = cv2.imdecode(bytes_imagen, cv2.IMREAD_COLOR)
    if img is None:
        return None

    detector = cv2.QRCodeDetector()
    datos, _, _ = detector.detectAndDecode(img)

    # Segundo intento en escala de grises si el brillo de pantalla dificulta la lectura
    if not datos:
        gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        datos, _, _ = detector.detectAndDecode(gris)

    return datos.strip() if datos else None


def cargar_tabla(query: str) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


st.title("🛡️ Control de Acceso Vehicular UIS — VigiBot-UIS")
st.caption("Arquitectura Híbrida: Capa 1 Determinista (<50 ms) + Capa 2 Agente Supervisor IA")

col_izq, col_der = st.columns(2, gap="large")

# --- COLUMNA IZQUIERDA: ESCÁNER DE PORTERÍA ---
with col_izq:
    st.subheader("1. Escaneo de Carné Digital UIS")
    tipo_movimiento = st.radio(
        "Dirección del flujo:",
        ["ENTRADA", "SALIDA"],
        horizontal=True,
    )

    tab_camara, tab_simulador = st.tabs(["📷 Cámara en Vivo (OpenCV)", "⌨️ Simulación / Manual"])

    with tab_camara:
        foto_qr = st.camera_input("Enfoca el código QR del carné digital UIS y toma la captura")
        if foto_qr is not None:
            foto_hash = hash(foto_qr.getvalue())
            if st.session_state.get("ultimo_foto_hash") != foto_hash:
                st.session_state["ultimo_foto_hash"] = foto_hash
                contenido_qr = decodificar_qr_imagen(foto_qr)
                if contenido_qr:
                    with st.spinner("QR decodificado, validando acceso..."):
                        st.session_state["resultado_escaneo"] = procesar_lectura_rapida(
                            contenido_qr, tipo_movimiento
                        )
                else:
                    st.session_state["resultado_escaneo"] = (
                        "⚠️ No se detectó ningún código QR en la imagen. Acerca más el carné o reduce el brillo de la pantalla."
                    )

    with tab_simulador:
        st.markdown("**Simulación rápida de carné:**")
        b1, b2 = st.columns(2)

        if b1.button("⚡ Escanear 2232504 (1 vehículo)", use_container_width=True):
            qr = generar_qr_simulado("2232504")
            with st.spinner("Procesando lectura..."):
                st.session_state["resultado_escaneo"] = procesar_lectura_rapida(qr, tipo_movimiento)

        if b2.button("🤖 Escanear 2232503 (2 vehículos)", use_container_width=True):
            qr = generar_qr_simulado("2232503")
            with st.spinner("Ambigüedad detectada, consultando a VigiBot-UIS..."):
                st.session_state["resultado_escaneo"] = procesar_lectura_rapida(qr, tipo_movimiento)

        with st.form("form_qr_manual"):
            codigo_manual = st.text_input(
                "O ingresa un código estudiantil / cadena QR Base64:",
                placeholder="Ej. 2232504 o eyJJRCI6...",
            )
            enviar_qr = st.form_submit_button("Registrar acceso", use_container_width=True)

            if enviar_qr and codigo_manual.strip():
                entrada = codigo_manual.strip()
                qr_final = entrada if entrada.startswith("eyJ") else generar_qr_simulado(entrada)
                with st.spinner("Validando en portería..."):
                    st.session_state["resultado_escaneo"] = procesar_lectura_rapida(qr_final, tipo_movimiento)

    if "resultado_escaneo" in st.session_state:
        res = st.session_state["resultado_escaneo"]
        if res.startswith("⚡"):
            st.success(res)
        elif res.startswith("⚠️"):
            st.warning(res)
        else:
            st.info(res)

# --- COLUMNA DERECHA: AGENTE SUPERVISOR EN LENGUAJE NATURAL ---
with col_der:
    st.subheader("2. Reportes y Consultas a VigiBot-UIS")
    st.markdown("Usa lenguaje natural para excepciones, visitantes o consultas de aforo.")

    with st.form("form_agente"):
        mensaje_vigilante = st.text_area(
            "Mensaje para el Agente:",
            placeholder="Ej. El estudiante 2232503 tiene el celular descargado y entra en su bicicleta GW",
            height=110,
        )
        consultar_agente = st.form_submit_button("Enviar a VigiBot-UIS", use_container_width=True)

        if consultar_agente and mensaje_vigilante.strip():
            with st.spinner("VigiBot-UIS analizando contexto y ejecutando herramientas..."):
                st.session_state["respuesta_agente"] = invocar_agente_excepcion(mensaje_vigilante.strip())

    if "respuesta_agente" in st.session_state:
        st.warning(st.session_state["respuesta_agente"])

st.divider()

# --- MONITOR EN TIEMPO REAL DE SQLITE ---
st.subheader("📊 Monitor en Vivo de Base de Datos (SQLite)")
tab_accesos, tab_vehiculos = st.tabs(["Historial de Accesos", "Vehículos Registrados"])

with tab_accesos:
    df_accesos = cargar_tabla(
        "SELECT id, codigo_estudiantil, tipo_vehiculo, tipo_movimiento, observacion, timestamp "
        "FROM accesos ORDER BY id DESC LIMIT 15"
    )
    if df_accesos.empty:
        st.caption("Aún no hay movimientos registrados.")
    else:
        st.dataframe(df_accesos, use_container_width=True, hide_index=True)

with tab_vehiculos:
    df_vehiculos = cargar_tabla(
        "SELECT codigo_estudiantil, propietario, tipo_vehiculo, detalles, estado FROM vehiculos"
    )
    st.dataframe(df_vehiculos, use_container_width=True, hide_index=True)