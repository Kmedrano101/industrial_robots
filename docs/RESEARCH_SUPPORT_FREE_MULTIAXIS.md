# Investigación + plan: impresión sin soportes vía reorientación multi-eje

> Profundización de [`RESEARCH_ROBOTIC_AM.md`](RESEARCH_ROBOTIC_AM.md) enfocada específicamente en
> eliminar soportes en piezas complejas aprovechando los ejes del robot. Metodología: búsquedas
> web dirigidas + lectura de fuentes primarias (papers SIGGRAPH/ACM TOG/CAD, arXiv, patentes) —
> **sin el harness de verificación adversarial multi-agente** usado en el informe anterior (no
> estaba disponible esta sesión). Varios PDFs académicos no permitieron extracción de texto —
> las afirmaciones marcadas [resumen-buscador] provienen del resumen que generó la búsqueda, no
> de mi lectura directa del paper; trátalas con un escalón menos de confianza que las marcadas
> [leído directamente].
> Estado: **pendiente de desarrollo**, este documento es el plan de referencia.

---

## 0. El hallazgo que reencuadra todo el plan

**[leído directamente]** El paper *"Trajectory Optimization for Collision-Aware Redundant Robotic
Multi-Axis Additive Manufacturing by Constrained Gradient Projection"* (arXiv 2606.29766, 2026) es
explícito: para que un sistema pueda simultáneamente (a) trazar una trayectoria de herramienta
exacta, (b) mantener una orientación de boquilla prescrita, y (c) tener *DOF de sobra* para
optimizar reorientación/evitar colisiones, necesita **redundancia cinemática real**. Su sistema
usa **6-DOF (brazo ABB) + 2-DOF (posicionador) = 8 DOF total**.

Un UR de 6 ejes cargando el extrusor sobre una cama fija —que es exactamente nuestra arquitectura
mecánica actual— **no tiene ese sobrante**: los 6 grados de libertad se consumen enteros en
(x, y, z) + 2 ángulos de inclinación de boquilla necesarios para seguir cualquier trayectoria con
cualquier orientación; solo queda **1 DOF libre** (la rotación de la boquilla sobre su propio eje,
irrelevante si la boquilla es simétrica de revolución). Ese único DOF libre es exactamente lo que
ya usamos hoy en `multiaxis_planner.py` como margen de búsqueda para el `SelfCollisionChecker`.

**Consecuencia directa:** con el hardware actual (UR7e + boquilla en `tool0` + cama fija en
`world`, ver `public/robots/*.urdf`), **no existe margen cinemático para hacer segmentación de
dirección de construcción de forma continua** (el enfoque "de verdad" de la literatura). Esto no
es un límite de software — es un límite físico de grados de libertad. El plan de abajo está
organizado en tiers precisamente para separar "lo que el hardware actual permite hoy" de "lo que
requeriría añadir un eje".

## 1. Descomposición de volumen / segmentación por dirección de construcción

**[resumen-buscador, corroborado en 2 búsquedas independientes]** La técnica seminal es Dai,
Wang et al., *"Support-free volume printing by multi-axis motion"* (ACM Transactions on Graphics,
SIGGRAPH 2018, TU Delft — Charlie C. L. Wang). Estrategia de dos descomposiciones sucesivas:

1. **Volumen → superficies**: optimiza un **campo escalar** dentro del volumen que representa la
   secuencia de fabricación; las isosuperficies de ese campo son las "capas curvas", restringidas
   a que cada una quede soportada desde abajo por una superficie convexa (navegable sin colisión
   por el cabezal).
2. **Superficies → curvas**: cada capa curva se convierte en trayectoria de herramienta.

**Arreglo mecánico clave (dato duro, corrobora el hallazgo §0):** en su sistema, **el brazo de 6
ejes mueve la PLATAFORMA de impresión, y el extrusor está FIJO al marco** — lo inverso de nuestra
arquitectura. Así, los 6 DOF del brazo se dedican enteros a reorientar+posicionar la pieza bajo
una boquilla fija, sin gastar DOF en "trazar" el path (eso lo hace el propio movimiento de la
pieza). Es la razón mecánica por la que su sistema sí tiene libertad de reorientación total y el
nuestro, tal como está, no.

**Trabajos relacionados confirmados (mismo patrón: descomposición + reorientación intermitente):**
- *"General Support-Effective Decomposition for Multi-Directional 3D Printing"* (arXiv 1812.00606)
- *"Volume Decomposition for Multi-axis Support-free and Gouging-free Printing based on Ellipsoidal
  Slicing"* (Computer-Aided Design, 2021, DOI 10.1016/j.cad.2021.103135)
- *"Geodesic Distance Field-based Curved Layer Volume Decomposition for Multi-Axis Support-free
  Printing"* (arXiv 2003.05938)
- *"Near support-free multi-directional 3D printing via global-optimal decomposition"*
  (ScienceDirect, DOI 10.1016/j.cagd — heurística para minimizar área de voladizo y número de
  pasos de descomposición)
- *"Support-Free 3D Printing Based on Model Decomposition"* (MDPI *Micromachines* 2025/26, DOI
  10.3390/mi16121316 — trabajo reciente, confirma que el problema sigue activo en 2025-2026, no
  resuelto de forma general)

**Patrón práctico común a todos (más barato que el campo escalar continuo):** dividir el modelo en
un puñado de **subregiones**, cada una imprimible sin soporte en su propia dirección de
construcción, impresas **secuencialmente vía rotación intermitente** de la plataforma — es decir,
reorientación **discreta entre segmentos**, no continua durante la impresión. Esto es alcanzable
sin campo escalar ni curvas continuas.

## 2. Slicing de capas curvas / no-planas — qué NO es lo mismo que nuestro tilting actual

**[resumen-buscador]** *CurviSlicer* (ACM TOG 2019, DOI 10.1145/3306346.3323022) resuelve un
problema **distinto y más simple**: no elimina soportes, solo reduce el efecto escalón en
superficies inclinadas. Su método no calcula capas curvas directamente — **deforma el modelo**
(optimización convexa vía QP) y luego lo corta con un slicer plano estándar convencional. Es
"3-eje ligeramente curvo", pensado para impresoras cartesianas, **no** para eliminar overhangs
severos ni voladizos de 90°.

**Diferencia clave con nuestro `multiaxis_planner.py` actual:** lo que ya tenemos (inclinar la
boquilla siguiendo la normal local sobre cortes planos a Z fija) es una técnica más cercana a
"5-axis surface following" que a slicing de capas curvas real. Ninguno de los slicers no-planos
open-source que encontré (S4-Slicer, `non-planar-post-processor`, `RotBotSlicer`,
`NonPlanarIroning`, forks de Slic3r) hace descomposición volumétrica tipo Dai et al. — todos son
post-procesadores de mejora de acabado superficial en 3 ejes, un problema mucho más acotado que el
que se pidió investigar. **No hay una implementación open-source lista para usar** del algoritmo
de eliminación de soportes por reorientación; se tendría que construir con primitivas de
geometría existentes (§4).

## 3. Planificación de secuencia, reorientación y colisión en 6+ DOF

**[leído directamente, arXiv 2606.29766]** Método: *manifold-guided gradient projection*. Cada
waypoint se proyecta sobre su "self-motion manifold" (el conjunto de configuraciones articulares
que alcanzan ese punto), y las actualizaciones de gradiente se restringen al espacio tangente de
esa variedad — así la optimización de la redundancia (suavizar movimiento, evitar colisión) nunca
viola la posición de depósito (mantienen ~10 μm de precisión). Su caso de uso concreto: brazo ABB
6-DOF + posicionador 2-DOF = 8 DOF.

**Colisión contra la PIEZA EN CRECIMIENTO (no solo autocolisión del brazo):** usan un modelo de
**SDF diferenciable** — SDF precalculado por eslabón del robot (geometría fija) + la pieza
impresa representada como nube de puntos muestreados del material ya depositado; solo evalúan
distancia/gradiente contra el "conjunto activo" (los K puntos más cercanos), evitando reconstruir
un SDF global en cada iteración. **Esto es exactamente lo que a nuestro `collision_checker.py`
le falta hoy**: `SelfCollisionChecker` solo comprueba autocolisión del brazo (cápsulas vía FK
DH-based); no hay chequeo contra el volumen ya impreso.

**No hay release de código.** Confirmado explícitamente: el paper no menciona repositorio.

**Conclusión práctica ya citada en su propio texto:** para un UR estándar (6 DOF, sin eje extra),
"conseguir libertad de reorientación tipo segmentación requiere actuadores adicionales" — refuerza
§0.

## 4. Requisitos de hardware derivados

**[resumen-buscador, corroborado en búsqueda separada + 3 patentes US]** El patrón dominante en
literatura y patentes (`US11198252`, `US11498281`, `US11642851` — "Multiple axis robotic additive
manufacturing system and methods") es: **brazo 6-DOF que porta el extrusor + plataforma de
impresión con 2 DOF de posicionamiento** (o, alternativamente, un segundo brazo robótico sujetando
la pieza, dando "DOF efectivos" más altos para llegar a puntos difíciles — arreglo dual-robot).
Ninguna fuente describe un sistema de eliminación de soportes real usando **solo** 6 DOF sobre
cama fija — consistente con §0.

**Fixturing:** ninguna fuente entra en detalle de sujeción de pieza específica para impresión
aditiva (a diferencia de mecanizado, donde el fixturing es tema mucho más maduro); es un hueco de
la literatura, no una respuesta encontrada — señalarlo como riesgo/incógnita abierta, no una
solución lista.

**Monitoreo in-situ (complementario, no core al problema de soportes):** **[resumen-buscador]**
un sistema de closed-loop con inspección 3D por nube de puntos + re-planificación redujo defectos
de 10.7% a 1.3% en volumen (fuente no identificada de forma unívoca en el resumen — tratar como
dato indicativo, no verificado a nivel de paper concreto). Otro sistema con cámara monocular a
720×1280, comparando contra capas de referencia simuladas del G-code, logró 100% detección de
defectos catastróficos con cero falsos positivos, <2s/capa en CPU estándar — mismo nivel de
confianza (resumen de búsqueda, no lectura directa).

## 5. Librerías / software reusable

| Necesidad | Librería confirmada | Nota |
|---|---|---|
| Segmentación de malla en componentes | `libigl` (`facet_components`) | Solo componentes conexas — no hace el corte "support-aware"; sería el punto de partida, no la solución |
| Segmentación de superficie más sofisticada | CGAL `Surface_mesh_segmentation` | Segmentación general (SDF shape-diameter-based), no diseñada para overhangs — otro punto de partida |
| Booleanas de malla (para cortar en subvolúmenes) | `libigl` `copyleft::cgal::mesh_boolean` | Confirmado disponible desde Python vía bindings |
| Planificación cartesiana en ROS2 | MoveIt2 Cartesian planner, Descartes, Pilz | Resuelven "sigue esta línea exacta" — no resuelven decomposición ni generan la secuencia; son la capa de EJECUCIÓN, no de SLICING |
| Algoritmo de descomposición support-free en sí | **Ninguno open-source encontrado** | Habría que implementarlo a partir de los papers, usando las librerías de arriba como primitivas |

## Caveats de esta investigación

1. Varios PDFs académicos (Dai et al. SIGGRAPH, arXiv 1812.00606) no permitieron extracción de
   texto (streams de imagen); los detalles citados de esos dos vienen del resumen de búsqueda, no
   de mi lectura directa — marcado explícitamente arriba.
2. No hubo verificación adversarial de 3 votos como en el informe anterior — esta sesión no tenía
   el harness de investigación disponible. Los datos numéricos "10.7%→1.3%" y "720×1280 / <2s" no
   están atados de forma inequívoca a una fuente concreta verificada; tratarlos como indicativos.
3. La hoja de ruta abajo asume que nuestra arquitectura mecánica actual es "brazo carga el
   extrusor, cama fija" — confirmado leyendo `public/robots/ur5e.urdf` (extrusor en `tool0`, `print_bed_surface`
   fijo a `world`). Si eso cambia, el análisis de §0 hay que rehacerlo.

---

## Plan de implementación por tiers

### Tier 1 — solo software, funciona con el UR7e tal cual está hoy

Sin nuevo hardware. Reorientación **discreta** entre segmentos (pausa, el operador reposiciona la
pieza en una fixture indexada, se reanuda) — el patrón "rotación intermitente de plataforma" que
usan varios papers como paso previo al continuo.

1. ✅ **`overhang_analyzer.py`** (implementado — `ur_3d_printer/ur_3d_printer/overhang_analyzer.py`,
   13 tests en `test/test_overhang_analyzer.py`, todos pasando)
   Recorre las caras de la malla STL cargada por `load_stl_mesh()` (reusado de
   `multiaxis_planner.py`) y calcula el ángulo de voladizo de cada cara respecto a la dirección de
   construcción configurable (default +Z), con la convención 0°=pared vertical (bien) / 90°=techo
   recto hacia abajo (peor caso) — documentada explícitamente en el módulo porque distintos
   slicers miden este ángulo al revés. Marca caras por encima de un umbral configurable (default
   45°, la regla clásica de FDM) como "necesita soporte". Salida: `OverhangReport` con
   `overhang_faces` (cara + ángulo + área + centroide), `overhang_area_pct`, `worst_angle_deg`,
   `needs_support`. Validado contra `chair.stl`/`wave_vase.stl`/`triangle_prism.stl` reales del
   repo — `wave_vase.stl` reporta 30.2% de área con voladizo (peor ángulo 90°), consistente con su
   geometría de paredes onduladas re-entrantes ya discutida antes en este proyecto.

2. ✅ **`build_segmentation.py`** (implementado — `ur_3d_printer/ur_3d_printer/build_segmentation.py`,
   14 tests en `test/test_build_segmentation.py`, todos pasando)
   Agrupa las caras en un número pequeño (configurable, default máx. 4) de subregiones, cada una
   con la dirección de build que minimiza su propio voladizo, usando `overhang_analyzer` como
   función de puntuación. Algoritmo: greedy set-cover sobre un pool de candidatos — por defecto
   los **6 ejes cartesianos** (simplificación deliberada, no atajo: sin un posicionador (Tier 2)
   la reorientación física real de Tier 1 es "pausar + fijación indexada", que en la práctica solo
   alcanza orientaciones a incrementos de 90°, así que optimizar sobre direcciones continuas
   arbitrarias resolvería un problema más difícil del que el hardware puede ejecutar). Cada
   iteración elige el candidato que cubre más área aún-sin-asignar; las caras que ningún candidato
   arregla se asignan al segmento que les da el mejor ángulo posible (invariante: todas las caras
   terminan en algún segmento, ninguna se descarta silenciosamente). Orden de impresión sugerido:
   la dirección default primero (si fue elegida), luego por área descendente — **heurística
   documentada explícitamente como tal**, no un problema de dependencia/orden resuelto (eso es
   Tier 2/3). Validado en las 3 mallas reales del repo — resultado más fuerte:
   **`wave_vase.stl` pasa de 30.2% de área con voladizo (1 sola dirección) a 0% residual con
   2 segmentos** (+Z para una porción pequeña, -X para el resto), demostrando que el enfoque
   Tier 1 realmente resuelve el problema del vaso re-entrante discutido antes en este proyecto,
   sin hardware nuevo.

3. **Extender `MultiAxisConfig` / `MultiAxisToolpathGenerator`** para aceptar un `print_frame` por
   segmento (ya existe el parámetro `print_frame` en `generate_from_stl()` — hoy se usa una sola
   vez para toda la pieza; extenderlo a "una lista de (subvolumen, print_frame, layers)").

4. **Flujo del operador en el backend/web**: nuevo endpoint `POST /api/slice/segmented` que
   devuelve N sub-toolpaths + instrucción legible ("reorienta la pieza a X° antes del segmento 2").
   El frontend ya tiene toda la infraestructura de preview por capas (`Toolpath.tsx`,
   `LayerSlider.tsx`) — extenderla a mostrar "segmento actual" es incremental, no un rediseño.

5. **Zona de transición/costura entre segmentos**: geometría de interfaz simple (pequeño solape o
   dentado) en el borde de cada subvolumen para que la unión no sea un plano de fractura limpio.
   Bajo esfuerzo, alto impacto en resistencia mecánica de la costura.

Esto es alcanzable con el hardware actual y no requiere ninguna compra. Es también lo más
alineado con lo que la literatura llama la variante "barata" del problema.

### Tier 2 — añade un eje de posicionador (la arquitectura real de la literatura)

Requiere hardware nuevo: una mesa/fixture rotativa (idealmente rotary+tilt, 2 DOF) bajo la cama de
impresión, controlada como un joint ROS2 adicional.

1. **Nuevo controlador ROS2** para el posicionador (patrón estándar `ros2_control` de un joint
   extra, análogo a como ya integramos `scaled_joint_trajectory_controller` del UR).
2. **`workpiece_collision.py`** (extiende `collision_checker.py`): añadir chequeo de colisión
   brazo↔pieza-ya-impresa, no solo autocolisión. Empezar simple (cápsulas contra un swept-volume
   aproximado de las capas ya depositadas) antes de intentar el SDF diferenciable del paper 2606.29766
   — ese nivel de sofisticación es Tier 3.
3. **Redundancy resolution real**: con 6+2=8 DOF ya hay margen para implementar una versión
   simplificada de la proyección de gradiente restringida a la variedad (sin necesitar GPU ni
   SDF completo — una aproximación discreta con `ur_screw_kinematics` ya evaluando IK debería
   bastar para el volumen de piezas que imprimimos).
4. Esto habilita **reorientación continua durante la impresión** (no solo entre segmentos) —
   el salto real de calidad frente a Tier 1.

### Tier 3 — investigación abierta, alto esfuerzo, solo si Tier 1/2 no bastan

- Slicing volumétrico continuo tipo Dai et al. (campo escalar / geodesic distance field) — sigue
  siendo tema de papers en 2025-2026, ningún grupo lo ha dejado como librería reusable.
- SDF diferenciable completo para colisión pieza-en-crecimiento con gradientes (arXiv 2606.29766).
- Monitoreo in-situ por visión/nube de puntos con corrección de proceso en closed-loop.

## Próximo paso recomendado

Tier 1 pasos 1 y 2 (`overhang_analyzer.py`, `build_segmentation.py`) ya están implementados y
validados. **Siguiente paso: Tier 1, pasos 3-5** — conectar `SegmentationResult` al
`MultiAxisToolpathGenerator` existente (extender `print_frame` para aceptar uno por segmento,
hoy solo acepta uno para toda la pieza), exponer un endpoint web
`POST /api/slice/segmented` que devuelva los N sub-toolpaths + la instrucción de reorientación
legible para el operador, y diseñar la geometría de costura/transición entre segmentos. Este es
ahora el eslabón que falta entre "sabemos cómo segmentar" (hecho) y "el operador puede imprimir
la pieza segmentada de verdad" (pendiente).
