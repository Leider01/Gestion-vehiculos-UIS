import base64
import json
from database import init_db
from scanner import procesar_lectura_rapida
from agent import invocar_agente_excepcion


def generar_qr_simulado(codigo_estudiantil: str) -> str:
    """Genera una cadena Base64 idéntica a la del carné digital oficial de la UIS."""
    payload = {
        "ID": 34520,
        "VERIFICATION": 105295998,
        "ID_DEVICE": "V74n7egxW5sMs7UC9fo6AtP17J8u0L",
        "DOCUMENT": codigo_estudiantil,
    }
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")


def main():
    init_db()
    print("✅ Sistema Híbrido VigiBot-UIS inicializado correctamente.")

    while True:
        print("\n--- SIMULADOR DE PORTERÍA UIS ---")
        print("1. Escaneo rápido (Estudiante 2232504 - 1 vehículo -> Flujo determinista)")
        print("2. Escaneo con ambigüedad (Estudiante 2232503 - 2 vehículos -> Agente IA)")
        print("3. Reporte o consulta en lenguaje natural del vigilante (Agente IA)")
        print("4. Salir")

        opcion = input("Selecciona una opción: ").strip()

        if opcion == "1":
            mov = input("Tipo de movimiento (ENTRADA/SALIDA): ").strip() or "ENTRADA"
            qr = generar_qr_simulado("2232504")
            print("\n" + procesar_lectura_rapida(qr, mov))

        elif opcion == "2":
            mov = input("Tipo de movimiento (ENTRADA/SALIDA): ").strip() or "ENTRADA"
            qr = generar_qr_simulado("2232503")
            print("\n" + procesar_lectura_rapida(qr, mov))

        elif opcion == "3":
            mensaje = input("Escribe el reporte o consulta para VigiBot-UIS: ").strip()
            if mensaje:
                print("\n" + invocar_agente_excepcion(mensaje))

        elif opcion == "4":
            print("Cerrando sistema.")
            break
        else:
            print("Opción no válida.")


if __name__ == "__main__":
    main()