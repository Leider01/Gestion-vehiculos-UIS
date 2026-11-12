# Gestión Vehicular UIS — VigiBot-UIS (PRO-RF-02)

|Leider Yesid Gomez Giraldo - 2232503|
|David Alejandro Galvis Duarte- 2232522|

Sistema híbrido para la modernización y automatización del control de acceso vehicular (carros, motos, bicicletas y monopatines) en la Universidad Industrial de Santander, utilizando el código QR dinámico del carné digital institucional.

## Arquitectura Híbrida

El sistema divide la operación de portería en dos capas para garantizar velocidad en el flujo cotidiano y razonamiento inteligente en casos complejos:

1. **Capa 1 — Programa Base Determinista (`scanner.py`):** Decodifica la cadena Base64 del carné digital UIS (`DOCUMENT`) y consulta SQLite. Si el usuario tiene un único vehículo registrado y su historial de entradas/salidas es coherente, registra el movimiento en **< 50 ms** sin consumir llamadas a la API.
2. **Capa 2 — Agente Supervisor de IA (`agent.py`):** Se activa únicamente ante ambigüedades (estudiantes con múltiples vehículos registrados), conflictos de estado (entradas duplicadas por salidas olvidadas), excepciones reportadas en lenguaje natural por el vigilante (visitantes o celulares sin batería) y consultas administrativas sobre el aforo del campus.

## Diagrama de Flujo del Proceso Propuesto

```mermaid
flowchart TD
    A(["Inicio: Llegada a portería UIS"]) --> B["Captura: Escaneo de QR dinámico del carné UIS o reporte del vigilante"]
    B --> C["Capa 1: Programa Base Determinista (scanner.py)<br/>Decodifica Base64 (DOCUMENT) y consulta SQLite"]
    C --> D{"¿Caso limpio?<br/>(1 vehículo y estado coherente)"}
    
    D -- "Sí (Flujo rápido)" --> E["INSERT directo en SQLite sin usar IA (< 50 ms)"]
    E --> F["Confirmación instantánea en pantalla"]
    F --> G(["Vehículo ingresa o sale del campus"])
    
    D -- "No (Excepción o anomalía)" --> H["Capa 2: Agente de IA VigiBot-UIS (agent.py)<br/>• Múltiples vehículos o conflicto de estado<br/>• Visitantes o celular sin batería (lenguaje natural)<br/>• Ejecuta Tools SQL y razona reglas"]
    H --> I{"¿Acceso autorizado?"}
    
    I -- "Sí" --> J["Registra en SQLite y notifica al vigilante"]
    J --> G
    
    I -- "No" --> K["Alerta de seguridad / Acceso denegado"]
    K --> L["Vehículo no ingresa y se retira"]
    L --> M(["Fin del proceso"])
    G --> M
```

## Estructura del Proyecto

* `database.py`: Inicialización de SQLite (`vehiculos` y `accesos`) y datos de prueba.
* `scanner.py`: Capa 1 determinista para validación ultrarrápida del código QR.
* `agent.py`: Capa 2 con **VigiBot-UIS** (Gemini 2.5 Flash) para resolución de excepciones y lenguaje natural.
* `tools.py`: Herramientas SQL (`Function Calling`) para consultar historiales, registrar movimientos y ejecutar consultas de lectura.
* `main.py`: Simulador interactivo de portería para pruebas locales.

## Instalación y Uso Local

1. Crear y activar el entorno virtual:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```
3. Configurar la clave de API copiando `.env.example` a `.env` y añadiendo tu `GEMINI_API_KEY`.
4. Ejecutar el simulador:
   ```bash
   python main.py
   ```
