flowchart TD
    A([Inicio: Llegada de vehículo a portería UIS]) --> B[Vigilante detiene el vehículo y solicita carné UIS o documento]
    B --> C{¿Usuario pertenece a la comunidad UIS?}
    
    C -- No (Visitante) --> D[Verificar motivo de visita y solicitar documento de identidad]
    D --> E{¿Ingreso autorizado?}
    E -- No --> Z([Denegar acceso y finalizar])
    E -- Sí --> F[Anotar datos del visitante en planilla manual]
    
    C -- Sí (Estudiante / Empleado) --> G[Verificar vigencia del carné institucional]
    G --> H{¿Tipo de vehículo?}
    
    H -- Carro / Moto --> I[Inspección visual de placa y verificación de documentos]
    I --> J[Anotar manualmente: Fecha, Hora, Código/ID, Tipo y Placa]
    
    H -- Bicicleta / Monopatín --> K[Identificar tipo de vehículo y características físicas]
    K --> L[Anotar manualmente: Fecha, Hora, Código/ID y Tipo de vehículo]
    
    F --> M[Autorizar paso verbalmente / sin talanquera automatizada]
    J --> M
    L --> M
    
    M --> N([Vehículo ingresa al campus])
    
    N -.-> O([Salida del campus: Vehículo llega a portería])
    O --> P[Vigilante solicita carné y busca el registro de entrada en planilla]
    P --> Q[Validar coincidencia usuario-vehículo y anotar hora de salida]
    Q --> R([Fin del proceso])
