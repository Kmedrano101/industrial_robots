# Revisión de diseño UI y plan de mejora

> Auditoría de la interfaz web actual (julio 2026) frente al objetivo del proyecto:
> **una celda de impresión aditiva con brazo robótico, operada desde el navegador, en
> entorno de laboratorio/puesta en marcha**. Ese contexto manda: no es una app de
> consumo, es un HMI que controla una máquina que puede hacer daño.
>
> Método: capturas de todas las pantallas y estados (no de memoria), auditoría del
> código, y referencias externas — HMI industrial (ISO 9241-110 / ISO 10218), slicers
> de escritorio (PrusaSlicer, Bambu Studio, Orca) e interfaces web de impresión
> (Mainsail, Fluidd, OctoPrint).

---

## 1. Diagnóstico

### 1.1 Problemas de corrección de la información (prioridad máxima)

Son los más graves porque **la interfaz afirma cosas falsas**.

**a) Estado contradictorio y simultáneo.** En la vista Live conviven, a 10 cm de
distancia: cabecera `● Ready` en verde, y panel `Connection: ● Disconnected` en rojo.
Ambos son "el estado", ninguno dice de qué. El de la cabecera es el estado de
*impresión* (IDLE→"Ready"), no el de conexión — pero nadie puede deducir eso mirando.
Un operador que ve verde asume que puede imprimir.

**b) Acciones destructivas disponibles sin precondiciones.** `Start Print` aparece
activo y en color primario sin ningún STL cargado y sin robot conectado. La guía HMI
lo llama explícitamente *inadequate error prevention*: el sistema debe impedir la
acción imposible, no dejar que falle.

**c) Colores sin semántica fija.** 57 utilidades de color distintas en el árbol de
componentes. El amarillo señala tanto "UNKNOWN" (dato ausente, benigno) como
"movimiento bloqueado" (condición operativa). La regla HMI es la contraria: paleta
corta y **los colores saturados reservados a condiciones anómalas**. Hoy el azul
primario compite con el rojo del E-STOP por la atención.

### 1.2 Problemas de flujo de trabajo

**d) El flujo no se comunica.** Un slicer profesional (Bambu, Prusa, Orca) hace
explícito el pipeline *importar → colocar → laminar → previsualizar → imprimir*. Aquí
los pasos existen pero están implícitos y desordenados: el panel de impresión aparece
antes que el de laminado, y nada indica en qué punto estás ni qué falta.

**e) Vacío sin instrucción.** En Prepare, dos tercios de la pantalla son rejilla vacía
sin una sola pista de qué hacer. El *empty state* es la mejor oportunidad de enseñar
el flujo y se está desperdiciando.

**f) Falta la información que define una impresora.** Ninguna interfaz de impresión
seria omite: gráfico de temperatura en el tiempo, progreso con ETA, tiempo estimado y
material del laminado. Mainsail y Fluidd los ponen en la vista principal. Aquí la
temperatura es un número plano (`0°C / 0°C`) y el progreso sólo existe mientras
imprime.

### 1.3 Problemas de sistema y calidad

**g) Móvil/tablet roto.** Sólo 11 usos de breakpoints responsive en todo el árbol. A
420 px: la cabecera se solapa (la pestaña "Printer" queda bajo el engranaje), los
botones de modelo se truncan a `UR3(`, `UR5(`, los badges desbordan y los ángulos se
pisan (`Shoulder0.0°Shoulder0`). **Relevante de verdad**: en un laboratorio se opera
desde tablet junto a la máquina.

**h) Accesibilidad prácticamente ausente.** 2 atributos ARIA en todo el árbol de
componentes. Sin foco visible consistente, sin `aria-live` para el estado que cambia
solo, sin etiquetas en los controles de sólo icono. La guía HMI insiste en no depender
del color (daltonismo) — hoy el estado se codifica sólo por color.

**i) Sin estados de carga/vacío/error.** Sólo `FileUpload` los contempla. Laminar una
pieza grande tarda; no hay feedback de progreso ni forma de cancelar.

**j) Tema claro sin validar.** Existe la opción pero nunca se ha comprobado; varias
superficies usan colores fijos oscuros (`#1a1a2e` en los tres visores 3D).

**k) Sin atajos de teclado** salvo en el slider de capas.

---

## 2. Principios para este proyecto

Antes de la lista de tareas, los criterios con los que decidir. Derivados del objetivo
(máquina real, operador técnico, sesiones largas de puesta en marcha):

1. **Un solo lugar para el estado.** Nunca dos indicadores que puedan contradecirse.
2. **El color es información, no decoración.** Verde/ámbar/rojo sólo para condición
   operativa. La marca y la jerarquía se expresan con tipografía y espacio.
3. **Impedir, no reprochar.** Si falta una precondición, el control se deshabilita y
   *dice cuál falta* — el patrón que ya aplicamos al selector Simulación/Robot real y
   que conviene generalizar.
4. **El vacío enseña.** Cada estado vacío explica el siguiente paso.
5. **Denso pero jerarquizado.** El operador quiere ver mucho a la vez; la respuesta no
   es ocultar, es agrupar y jerarquizar.
6. **Nada crítico a más de un clic.** E-STOP y estado siempre visibles (ya se cumple).

---

## 3. Plan por fases

### Fase 1 — Veracidad y prevención de errores

*Sin esto, lo demás es maquillaje.*

1. **Unificar el estado en la cabecera.** Un único componente con jerarquía explícita:
   conexión → modo robot → seguridad → estado de impresión. Si no hay robot, el estado
   de impresión no puede mostrarse en verde.
2. **Deshabilitar acciones sin precondiciones**, con el motivo visible: `Start Print`
   requiere STL laminado + robot conectado + control de movimiento; `Calibrate Origin`
   requiere conexión. Reutilizar el patrón "razón del bloqueo" ya implementado.
3. **Fijar semántica de color** en tokens: `--state-ok / --state-warn / --state-danger
   / --state-idle`. Sustituir los 57 usos ad hoc.
4. **Distinguir "sin dato" de "estado malo".** `UNKNOWN` es gris neutro, no ámbar.

### Fase 2 — Flujo de trabajo explícito

5. **Barra de progreso de flujo** en Prepare: `1 Importar → 2 Ajustes → 3 Laminar →
   4 Previsualizar → 5 Imprimir`, con el paso actual resaltado y los no alcanzables
   atenuados. Es el patrón de Bambu/Prusa y resuelve (d) y (e) a la vez.
6. **Reordenar el panel** a ese orden real. Hoy Print aparece antes que Slice.
7. **Estado vacío con instrucción** en el visor: silueta de la cama y el texto del
   paso 1, en lugar de rejilla desnuda.
8. **Resumen de laminado**: tiempo estimado, material, nº de capas, altura — tras
   laminar y antes de imprimir. Hoy no existe y es la información con la que se decide
   si la pieza está bien preparada.
9. **Progreso de laminado** con posibilidad de cancelar.

### Fase 3 — Instrumentación propia de una impresora

10. **Gráfico de temperatura en el tiempo** (extrusor real vs objetivo). Estándar en
    Mainsail/Fluidd; imprescindible para diagnosticar una primera capa.
11. **Panel de progreso persistente durante impresión**: capa actual/total, % , tiempo
    transcurrido y ETA, altura Z. Con `aria-live` para lectores de pantalla.
12. **Registro de eventos** (consola) con timestamps: comandos enviados, respuestas,
    errores. Hoy los mensajes aparecen y desaparecen en una línea.
13. **Historial de trabajos**: qué se imprimió, con qué ajustes, resultado. Es lo que
    convierte la herramienta en instrumento de investigación — encaja con los informes
    de `RESEARCH_*.md`.

### Fase 4 — Sistema de diseño y calidad

14. **Tokens y escala**: espaciado, radios, tipografía y color en un único sitio;
    componentes `Button/Card/Badge/Field` consistentes.
15. **Responsive real**: cabecera colapsable, paneles apilados, objetivos táctiles
    ≥44 px (la guía HMI pide ~1,5 cm en pantalla táctil), y desactivar `Split view`
    por debajo de `lg`.
16. **Accesibilidad**: etiquetas ARIA, foco visible, `aria-live` en estado, contraste
    AA verificado, y estado codificado además del color (icono/texto).
17. **Validar el tema claro** de punta a punta, incluidos los visores 3D.
18. **Atajos**: `Espacio` pausa/reanuda, `Esc` cancela diálogo, `1..5` vistas de
    cámara, `?` ayuda.

### Fase 5 — Extras de valor

19. **Vista de cámara** de la celda junto al 3D (la investigación señala el monitoreo
    in-situ como línea abierta).
20. **Comparador simulación vs real**: superponer pose comandada y pose real para ver
    desviación — encaja con el objetivo de precisión del proyecto.
21. **Perfiles de material/proceso** guardables, como en los slicers.
22. **Notificaciones** de fin/fallo de impresión.

---

## 4. Recomendación de orden

Fase 1 completa antes que nada: son defectos de veracidad, baratos de corregir y hoy
la interfaz puede inducir a error a un operador. Fase 2 es la que más cambia la
percepción de "producto profesional" por esfuerzo invertido. Fase 3 es lo que la hace
comparable a Mainsail/Fluidd. Fase 4 conviene hacerla *antes* de añadir más pantallas,
para no multiplicar la deuda. Fase 5 es opcional y dirigida por la investigación.

## 5. Fuentes

- ISO 9241-110 (principios de diálogo) e ISO 10218-1/2:2025 (seguridad robótica)
- Guía de buenas prácticas HMI industrial (aufaitux.com/blog/hmi-design-best-practices)
- Comparativas y documentación de PrusaSlicer / Bambu Studio / OrcaSlicer
- Mainsail (docs.mainsail.xyz), Fluidd, OctoPrint como referencia de UI web de impresión
