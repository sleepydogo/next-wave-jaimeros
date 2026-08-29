<!-- @import "[TOC]" {cmd="toc" depthFrom=1 depthTo=6 orderedList=false} -->

# NextWave — Plan de diseño (web + mobile)

Minimalismo funcional, estilo Apple/enterprise. Cero ruido visual, máxima legibilidad en contexto de puerto/ruta.

---

## 1. Filosofía

NextWave no es un producto de consumo: es una herramienta de monitoreo operativo que dos tipos de usuario muy distintos van a mirar bajo presión:

- **Monitorista (web):** mira una pantalla fija, muchas horas, necesita detectar una anomalía en segundos.
- **Conductor (mobile):** mira el teléfono con el camión parado o el puerto esperando, necesita una sola acción clara, con luz de sol y guantes puestos.

Principio rector: **una pantalla, una decisión.** Si una vista requiere explicación, está mal diseñada. Nada de dashboards "de todo un poco" ni botones decorativos.

Referencias de tono: Apple Health / Apple Wallet (mobile, foco absoluto), Linear / Stripe Dashboard (web, densidad de datos sin desorden).

---

## 2. Paleta de color

Una paleta casi monocromática + un solo acento + 3 colores de estado. Nada más.

| Uso                                | Color            | Hex       |
| ---------------------------------- | ---------------- | --------- |
| Fondo principal                    | Blanco casi puro | `#FAFAFA` |
| Fondo secundario / tarjetas        | Blanco           | `#FFFFFF` |
| Texto primario                     | Negro suave      | `#111111` |
| Texto secundario                   | Gris             | `#6B6B6B` |
| Bordes / separadores               | Gris muy claro   | `#E5E5E5` |
| Acento (marca, acciones primarias) | Azul náutico     | `#0A5C8C` |
| Éxito / evento resuelto            | Verde            | `#1E8E5A` |
| Alerta / atención                  | Ámbar            | `#B87A0A` |
| Emergencia / crítico               | Rojo             | `#C22E2E` |

Reglas:

- Nunca más de dos colores de estado visibles al mismo tiempo en una misma vista.
- El acento (`#0A5C8C`) se usa solo para acciones o elementos de marca — no para decorar.
- Modo oscuro (opcional, fase 2): invertir superficies (`#111111`/`#1B1B1B`), mantener los tres colores de estado sin cambios (son los que importan a las 3am).

---

## 3. Tipografía

Una sola familia, sistema nativo (evita flash de carga y ya se ve "Apple-like" gratis):

- **Web:** `-apple-system, "SF Pro Display", "Inter", system-ui, sans-serif`
- **Mobile:** fuente del sistema (SF en iOS, Roboto/system en Android) — no traer fuente custom.

Escala tipográfica (web y mobile comparten la lógica, mobile ~10-15% más grande):

| Nivel     | Tamaño | Peso                               | Uso                                   |
| --------- | ------ | ---------------------------------- | ------------------------------------- |
| Display   | 32px   | 600                                | Métrica principal (ej. costo del día) |
| Título    | 20px   | 600                                | Encabezado de sección/pantalla        |
| Cuerpo    | 15px   | 400                                | Texto general                         |
| Subtítulo | 13px   | 400                                | Metadata, timestamps                  |
| Micro     | 11px   | 500 (mayúsculas, tracking +0.04em) | Etiquetas de estado                   |

Nada de más de 3 pesos de fuente en toda la app.

---

## 4. Web — Dashboard del monitorista

### 4.1 Estructura general

Layout fijo, sin scroll horizontal, sidebar minimalista (solo íconos + label corto):

```
┌───────────┬──────────────────────────────────────────┐
│  Sidebar  │  Header (fecha, estado del sistema, costo │
│           │  acumulado del día)                        │
│  · Viajes │──────────────────────────────────────────│
│  · Alertas│                                            │
│  · Llamada│   Contenido de la sección activa           │
│  · Costos │                                            │
└───────────┴──────────────────────────────────────────┘
```

Sin menús desplegables anidados. Sin modales para tareas frecuentes (usar paneles laterales deslizables en su lugar).

### 4.2 Pantallas

**1. Viajes (home)**
Lista de camiones activos como tarjetas horizontales, no tabla densa:

- Nombre/patente del camión, estado del viaje (en ruta / en puerto / carga habilitada), última posición (relativa: "hace 2 min"), badge de color según estado.
- Un solo dato numérico por tarjeta si hace falta (ej. velocidad). Todo lo demás al hacer clic → panel lateral con el detalle (eventos, llamadas, línea de tiempo del viaje).

**2. Alertas**
Feed cronológico simple, tipo "activity log": ícono de estado + una línea de texto + hora. Sin tabla de columnas. Click → contexto completo en panel lateral (transcripción de la llamada, evento que la disparó).

- Alertas críticas (emergencia) se distinguen solo por el punto de color rojo a la izquierda, nunca por fondo rojo de fila completa (eso cansa la vista en turnos largos).

**3. Llamadas**
Similar al feed de alertas: quién, cuándo, resultado (contestó / no contestó / resuelto), duración. Reproductor de audio simple si aplica, sin diseño de "player" recargado — solo play/pausa y una barra de progreso fina.

**4. Costos**
Una sola cifra grande arriba: costo del día (agente) vs. lo que hubiera costado con monitorista humano, con la diferencia en verde. Debajo, un gráfico de línea simple (sin grid pesado, sin leyenda si no hace falta) evento vs. costo acumulado. Nada de gráficos 3D, donuts ni gauges — un dashboard de costos no necesita "impresionar", necesita responder "¿estamos ahorrando o no?" en 2 segundos.

### 4.3 Componentes compartidos

- Tarjeta base: fondo blanco, borde `#E5E5E5` 1px, radio 12px, sin sombra dura (si acaso, `box-shadow: 0 1px 2px rgba(0,0,0,0.04)`).
- Badges de estado: pastilla pequeña, texto en mayúsculas, color de fondo muy suave (10% opacidad del color de estado) + texto en el color sólido.
- Botón primario: fondo acento, texto blanco, radio 8px, sin gradientes, sin iconos innecesarios.
- Botón secundario: solo borde + texto, fondo transparente.

---

## 5. Mobile — App del conductor

### 5.1 Principio

El conductor tiene **una pantalla**, no una app con tabs. Todo lo que necesita ver/hacer cabe en una sola vista que cambia de estado según el momento del viaje.

### 5.2 Los 4 estados de la pantalla única

1. **En ruta:** mapa de fondo tenue (o silueta simple), texto grande: "En camino al puerto" + distancia/tiempo estimado. Sin botones (no hay nada que el conductor deba hacer).
2. **Llegando / en puerto, esperando:** texto grande: "Esperando habilitación de carga". Un solo botón secundario, chico, abajo: _"Ya estoy listo"_ (dispara el ack y evita la llamada). Nada de countdown ansiógeno.
3. **Llamada entrante del agente:** pantalla de llamada estilo nativo (como una llamada telefónica normal, no una UI custom rara) — el conductor ya sabe cómo se ve una llamada, no le enseñamos una interfaz nueva.
4. **Carga habilitada / viaje resuelto:** confirmación simple con ícono de check verde, un texto corto, y vuelve solo al estado de reposo después de unos segundos.

### 5.3 Reglas mobile

- Texto grande siempre (mínimo 17pt para el mensaje principal) — se usa con el celular lejos, al sol, manejando.
- Un solo botón de acción visible por pantalla, nunca dos compitiendo.
- Sin bottom navigation, sin drawer, sin configuración visible salvo un ícono chico de ajustes en una esquina.
- Notificaciones push: mismo lenguaje visual que el estado 3 (llamada), no un banner distinto.
- Vibración/sonido solo en transiciones de estado importantes (llamada entrante, carga habilitada), nunca en actualizaciones de posición.

---

## 6. Movimiento / microinteracciones

- Transiciones entre estados: fade + slight scale (150–200ms), nunca deslizamientos largos ni bounce.
- Ningún spinner genérico: usar skeleton sutil (bloques grises pulsando) mientras carga data real.
- El color de estado (verde/ámbar/rojo) es lo único que "se mueve" con una animación (pulso suave) cuando algo pasa de un estado a otro — el resto de la interfaz permanece estática.

---

## 7. Qué NO hacer (para no perder el foco después)

- No agregar gráficos que no respondan una pregunta operativa concreta.
- No usar más de un acento de color por pantalla.
- No duplicar la lógica de estados entre web y mobile con nombres distintos — mismo vocabulario de estado en ambos (en_ruta / en_puerto / llamada_activa / resuelto / emergencia).
- No meter branding fuerte (logo grande, colores de marca por todos lados): esto es una herramienta operativa, no una app de consumo.

---

## 8. Próximo paso sugerido

1. Definir el vocabulario de estados compartido (paso 7) antes de tocar código de `web/` o `mobile/` — hoy no existe ese contrato y es la base de todo lo demás.
2. Wireframes en baja fidelidad de las 4 pantallas de `web/` y los 4 estados de `mobile/` (papel o Figma, sin color todavía).
3. Recién ahí aplicar esta paleta y tipografía sobre los wireframes aprobados por el equipo.
