import base64
import json
import os
from datetime import datetime
import cv2
import numpy as np
import pandas as pd
import streamlit as st
from database import init_db, get_connection
from scanner import procesar_lectura_rapida
from agent import invocar_agente_excepcion

st.set_page_config(
    page_title="Portería UIS — VigiBot",
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


def extraer_documento_qr(contenido_qr: str) -> str | None:
    try:
        datos = json.loads(base64.b64decode(contenido_qr.strip()).decode("utf-8"))
        doc = str(datos.get("DOCUMENT", "")).strip()
        return doc if doc else None
    except Exception:
        return None


def decodificar_qr_imagen(archivo_imagen) -> str | None:
    bytes_imagen = np.asarray(bytearray(archivo_imagen.getvalue()), dtype=np.uint8)
    img = cv2.imdecode(bytes_imagen, cv2.IMREAD_COLOR)
    if img is None:
        return None

    detector = cv2.QRCodeDetector()
    datos, _, _ = detector.detectAndDecode(img)
    if not datos:
        gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        datos, _, _ = detector.detectAndDecode(gris)

    return datos.strip() if datos else None


def obtener_vehiculos_activos_estudiante(documento: str) -> list[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT propietario, tipo_vehiculo, placa, detalles, foto_path
        FROM vehiculos
        WHERE codigo_estudiantil = ? AND estado = 'ACTIVO'
        """,
        (documento.strip(),),
    )
    filas = [
        {
            "propietario": r[0],
            "tipo": r[1],
            "placa": r[2],
            "detalles": r[3],
            "foto_path": r[4],
        }
        for r in cursor.fetchall()
    ]
    conn.close()
    return filas


def cargar_tabla(query: str) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def obtener_metricas_aforo() -> dict:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT tipo_vehiculo, COUNT(*)
        FROM accesos
        WHERE id IN (
            SELECT MAX(id) FROM accesos GROUP BY codigo_estudiantil, tipo_vehiculo
        )
        AND tipo_movimiento = 'ENTRADA'
        GROUP BY tipo_vehiculo
    """)
    conteo = {fila[0].lower(): fila[1] for fila in cursor.fetchall()}

    hoy = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT COUNT(*) FROM accesos WHERE timestamp LIKE ?", (f"{hoy}%",))
    movimientos_hoy = cursor.fetchone()[0]
    conn.close()

    carros = conteo.get("carro", 0)
    motos = conteo.get("moto", 0)
    micromovilidad = conteo.get("bicicleta", 0) + conteo.get("monopatín", 0) + conteo.get("monopatin", 0)

    return {
        "total_dentro": carros + motos + micromovilidad,
        "motorizados": carros + motos,
        "detalle_motorizados": f"{carros} carros · {motos} motos",
        "micromovilidad": micromovilidad,
        "movimientos_hoy": movimientos_hoy,
    }


st.title("🛡️ Terminal de Portería UIS — VigiBot-UIS")
st.caption("Control de Acceso Vehicular · Capa 1 Determinista (<50 ms) + Capa 2 Agente Supervisor IA")

metricas = obtener_metricas_aforo()
m1, m2, m3, m4 = st.columns(4)
m1.metric("Vehículos en Campus", metricas["total_dentro"])
m2.metric("Carros y Motos", metricas["motorizados"], metricas["detalle_motorizados"])
m3.metric("Bicicletas y Monopatines", metricas["micromovilidad"])
m4.metric("Movimientos Hoy", metricas["movimientos_hoy"])

st.divider()

col_izq, col_der = st.columns(2, gap="large")

with col_izq:
    st.subheader("1. Escaneo de Carné Digital UIS")
    tipo_movimiento = st.radio(
        "Dirección del flujo:",
        ["ENTRADA", "SALIDA"],
        horizontal=True,
    )

    tab_simulador, tab_camara = st.tabs(["⌨️ Simulación / Manual", "📷 Cámara en Vivo (OpenCV)"])

    with tab_simulador:
        st.markdown("**Simulación rápida de carné:**")
        b1, b2 = st.columns(2)

        if b1.button("⚡ Escanear 2232504 (1 vehículo)", use_container_width=True):
            qr = generar_qr_simulado("2232504")
            with st.spinner("Procesando lectura..."):
                st.session_state["resultado_escaneo"] = procesar_lectura_rapida(qr, tipo_movimiento)
                st.session_state["ultimo_doc_escaneado"] = "2232504"

        if b2.button("🤖 Escanear 2232503 (2 vehículos)", use_container_width=True):
            qr = generar_qr_simulado("2232503")
            with st.spinner("Ambigüedad detectada, consultando a VigiBot-UIS..."):
                st.session_state["resultado_escaneo"] = procesar_lectura_rapida(qr, tipo_movimiento)
                st.session_state["ultimo_doc_escaneado"] = "2232503"

        with st.form("form_qr_manual"):
            codigo_manual = st.text_input(
                "O ingresa un código estudiantil / cadena QR Base64:",
                placeholder="Ej. 2232522 o eyJJRCI6...",
            )
            enviar_qr = st.form_submit_button("Registrar acceso", use_container_width=True)

            if enviar_qr and codigo_manual.strip():
                entrada = codigo_manual.strip()
                qr_final = entrada if entrada.startswith("eyJ") else generar_qr_simulado(entrada)
                with st.spinner("Validando en portería..."):
                    st.session_state["resultado_escaneo"] = procesar_lectura_rapida(qr_final, tipo_movimiento)
                    st.session_state["ultimo_doc_escaneado"] = extraer_documento_qr(qr_final)

    with tab_camara:
        activar_cam = st.toggle("Encender cámara de portería")
        if activar_cam:
            foto_qr = st.camera_input("Enfoca el código QR del carné digital UIS")
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
                            st.session_state["ultimo_doc_escaneado"] = extraer_documento_qr(contenido_qr)
                    else:
                        st.session_state["resultado_escaneo"] = (
                            "⚠️ No se detectó ningún código QR en la imagen."
                        )
                        st.session_state["ultimo_doc_escaneado"] = None

    if "resultado_escaneo" in st.session_state:
        res = st.session_state["resultado_escaneo"]
        if res.startswith("⚡"):
            st.success(res)
        elif res.startswith("⚠️"):
            st.warning(res)
        else:
            st.info(res)

        doc_escaneado = st.session_state.get("ultimo_doc_escaneado")
        if doc_escaneado:
            vehiculos_usuario = obtener_vehiculos_activos_estudiante(doc_escaneado)
            if vehiculos_usuario:
                st.markdown("**Verificación visual de vehículos autorizados:**")
                cols_v = st.columns(len(vehiculos_usuario))
                for idx, v in enumerate(vehiculos_usuario):
                    with cols_v[idx]:
                        with st.container(border=True):
                            if v["foto_path"] and os.path.exists(v["foto_path"]):
                                st.image(v["foto_path"], use_container_width=True)
                            else:
                                st.caption("Sin fotografía registrada")
                            placa_txt = f" · Placa `{v['placa']}`" if v["placa"] else ""
                            st.markdown(f"**{v['tipo']}**{placa_txt}")
                            st.caption(f"{v['detalles']} ({v['propietario']})")

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

st.subheader("📊 Monitor en Vivo de Portería")
tab_accesos, tab_vehiculos = st.tabs(["Historial de Accesos", "Directorio de Vehículos Autorizados"])

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
        "SELECT codigo_estudiantil, propietario, tipo_vehiculo, placa, detalles, estado "
        "FROM vehiculos ORDER BY id DESC"
    )
    st.dataframe(df_vehiculos, use_container_width=True, hide_index=True)