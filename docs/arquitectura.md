# Arquitectura Técnica - Reforma Hub

## 1. Visión General de Arquitectura

El sistema adopta una arquitectura desacoplada basada en microservicios/módulos limpios, optimizada para rendimiento SEO en el cliente y mantenibilidad/testabilidad en el servidor.

---

## 2. Frontend: Next.js (App Router + TypeScript)

### Principios de Diseño

- **Server-First (SEO):** Páginas y rutas optimizadas para renderizado en servidor (SSR/SSG).
- **Componentes UI Limpios:** Presentación pura (Dumb Components) aislada de la lógica de negocio.
- **Custom Hooks:** Toda la lógica de interfaz, llamadas al API y manejo de estados se encapsula en hooks.
- **Helpers Puros:** Validaciones, transformaciones de moneda, formateo de fechas y utilidades de negocio sin dependencias de React.

### Estructura de Directorios (Frontend)

```text
src/
├── app/                  # Rutas, layouts y Server Components (SEO / SSG)
│   ├── [lang]/           # Soporte i18n (es / en)
│   │   ├── (auth)/       # Rutas de autenticación
│   │   ├── proyectos/    # Explorador y detalle de solicitudes
│   │   └── admin/        # Panel administrativo
├── components/           # Componentes visuales
│   ├── ui/               # Sistema de diseño atómico (Botones, Modales, Inputs)
│   └── features/         # Componentes de dominio (LeadCard, ProjectForm, WalletStatus)
├── hooks/                # Lógica de interfaz y estado
│   ├── useLeadPurchase.ts
│   ├── useProjectFilter.ts
│   └── useCurrencyConverter.ts
├── helpers/              # Funciones puras y utilidades
│   ├── currency.ts       # Formateo de USD/EUR y conversiones
│   ├── date.ts           # Formateo de fechas relativas
│   └── validators.ts     # Esquemas Zod / validaciones de formularios
├── services/             # Clientes HTTP y SDKs (Conexión al Backend)
│   ├── api.ts            # Cliente Axios/Fetch base con interceptores
│   ├── leads.service.ts  # Endpoints de solicitudes
│   └── payment.service.ts# Endpoints de transacciones Stripe
└── types/                # Definiciones de TypeScript (Interfaces y DTOs)
```

---

## 3. Backend: FastAPI + Arquitectura Hexagonal

### Principios de Diseño

- **Dominio Aislado:** El núcleo de la aplicación no depende de ningún framework, ORM ni librería externa.
- **Puertos y Adaptadores:** Desacoplamiento total de la base de datos (Postgres/PostGIS), pasarelas de pago (Stripe) y almacenamiento (S3/Cloudflare R2).
- **Casos de Uso Explícitos:** Cada interacción de negocio es un servicio aislado e independiente.

### Estructura de Directorios (Backend)

```text
app/
├── domain/               # NÚCLEO (Sin dependencias externas)
│   ├── models/           # Entidades puras (Lead, Professional, Payment)
│   ├── exceptions/       # Excepciones de negocio (LeadCapReachedException)
│   └── value_objects/    # Objetos de valor (Money, Location, Email)
├── application/          # CASOS DE USO (Orquestación de Negocio)
│   ├── ports/            # Interfaces/Clases Abstractas
│   │   ├── lead_repository_port.py
│   │   ├── payment_port.py
│   │   └── storage_port.py
│   └── use_cases/        # Casos de uso
│       ├── buy_lead.py
│       ├── create_lead.py
│       └── process_payout.py
├── infrastructure/       # ADAPTADORES E IMPLEMENTACIONES
│   ├── adapters/
│   │   ├── db/           # SQLAlchemy Async + GeoAlchemy2 (PostGIS)
│   │   │   ├── models/   # Tablas ORM
│   │   │   └── repositories/ # Implementación de puertos DB
│   │   ├── payments/     # Adaptador de Stripe API
│   │   └── storage/      # Adaptador S3 / Cloudflare R2
│   └── api/              # CONTROLADORES Y ENTRYPOINTS
│       ├── v1/           # Rutas FastAPI / Endpoints REST
│       ├── schemas/      # DTOs Pydantic (Request/Response)
│       └── middlewares/  # Autenticación, CORS, Manejo de errores
└── main.py               # Punto de entrada e Inyección de Dependencias
```

---

## 4. Persistencia, ORM y Herramientas

- **ORM:** **SQLAlchemy 2.0 (Modo Asíncrono)** para máximo rendimiento y mapeo desacoplado del dominio.
- **Consultas Geoespaciales:** **GeoAlchemy2** integrado con **PostGIS** para filtrados por radio en kilómetros y código postal.
- **Migraciones de BD:** **Alembic** para el control de versiones del esquema de base de datos.
