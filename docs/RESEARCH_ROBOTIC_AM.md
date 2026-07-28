# Investigación: elementos clave de un sistema de impresión 3D con brazo robótico

> Informe de investigación profunda (junio 2026) aplicado a nuestro stack: UR7e (PolyScope 5)
> + ROS2 `ur_robot_driver` (external control) + slicer propio planar/multi-eje.
> Metodología: 25 fuentes técnicas leídas, 123 afirmaciones extraídas, 25 verificadas
> adversarialmente (3 votos por afirmación) → 22 confirmadas, 3 refutadas.
> Estado: **pendiente de desarrollo** — ver "Recomendaciones accionables" al final.

---

## 1. Calibración del sistema

**Confirmado (3-0):** El hardware del UR7e es suficiente — la literatura peer-reviewed
(sistema ARMS, *Rapid Prototyping Journal* 26(4), 2020, DOI 10.1108/RPJ-09-2019-0243)
demuestra que brazos industriales con repetibilidad ±0.02–0.03 mm producen calidad FFF
comparable a impresoras cartesianas, **con una condición**: montaje en base rígida
anti-vibración (ARMS usó una placa de acero de 1.5×1.5 m). La rigidez del montaje
robot+cama es tan importante como la calibración misma.

Procedimiento práctico validado (tesis UR5 [Trtnik, Theseus 2022] + corroborado contra el
manual de PolyScope 5 "Teaching TCP Position"):

- **TCP del nozzle**: usar el asistente de PolyScope (TCP Configuration) tocando un punto
  fijo de referencia desde varias orientaciones — sin metrología externa. Un tornillo
  sujetado por imán sirve como referencia.
- **Registro de cama**: definir la superficie a altura fija en el frame base del robot,
  montar la cama **rígidamente a la misma estructura que el robot** (elimina movimiento
  relativo), nivelar esquinas con el método del papel contra el TCP ya calibrado.
- Referencia numérica: ARMS ajustó su solver IK hasta error de nozzle < 0.05 mm en el peor
  caso (ojo: tolerancia de convergencia del solver, no exactitud física medida end-to-end).

**Estado en nuestro repo:** `docker/ros2-printer/extract_calibration.sh` +
`KINEMATICS_PARAMS_FILE` ya cubren la calibración cinemática de fábrica. Falta
documentar/implementar el flujo de calibración TCP del extrusor y registro de cama como
rutina guiada.

## 2. Sincronización flujo ↔ velocidad TCP — el parámetro crítico nº 1

**Confirmado (3-0) con tres fuentes independientes convergentes.** El hallazgo más fuerte
de la investigación:

- Tesis con UR5 que extruía a **velocidad media constante** (steps/s = longitud de
  filamento ÷ tiempo estimado): produjo huecos en el infill y top layer que no cerró. El
  autor lo identifica como "la mejora más importante" pendiente.
  (theseus.fi/bitstream/handle/10024/750395/Trtnik_Ales.pdf)
- Paper ASME IMECE2025 (arxiv.org/pdf/2510.24994): extrudate rate ajustado dinámicamente
  según velocidad del robot (ROS2 → serial → ESP32 → stepper NEMA17).
- SEAM robótico (*Virtual and Physical Prototyping* 2025, DOI
  10.1080/17452759.2025.2551084): la falta de controlador integrado robot–extrusor es "el
  reto central".

**Implicación directa para nuestro stack (verificada contra docs y código fuente del
driver):** el `scaled_joint_trajectory_controller` modula la velocidad real con el speed
slider del pendant / modo reducido / safety **sin desviar la trayectoria** (implementación:
`traj_time_ += period * scaling_factor_`). Por tanto **nuestro extruder_controller debe
suscribirse al estado `speed_scaling` del driver** — si el robot se ralentiza al 50% y
seguimos extruyendo al 100%, sobre-extruimos exactamente 2×. Hoy no lo hacemos: es
probablemente la mejora de mayor impacto en calidad de impresión.

## 3. Modos de control de trayectoria

**Confirmado (3-0):** El driver ofrece tres vías relevantes
(docs.universal-robots.com → ur_robot_driver/ur_controllers; docs.ros.org/en/jazzy →
hardware_interface):

- Comando por **posición** o **velocidad** de juntas (streaming tipo servoJ).
- **Passthrough Trajectory Controller**: envía la trayectoria completa al controlador del
  robot, que interpola y ejecuta on-robot. Ventajas: el lookahead/interpolación lo hace el
  robot y **no requiere kernel RT en el host ROS**. Caveats: solo funciona con URSim o
  robot real (no mock hardware/Gazebo), y por defecto imita interpolación spline de
  ros2_control, no blending por radio de esquina.

**Para nosotros:** usamos `scaled_joint_trajectory_controller`; el passthrough es candidato
a evaluar para trayectorias largas de impresión (relaja los requisitos de tiempo real del
container `ur-printer`).

## 4. Pruebas pre-impresión (confianza media, prácticas no controvertidas)

1. **Dry-run con pluma**: montar una pluma con resorte en lugar del extrusor y trazar el
   path del TCP sobre papel en la cama — valida corrección y repetibilidad de la
   trayectoria completa.
2. **Test run sin extrusión a velocidad reducida** antes de cada impresión real.
3. **Primera capa como punto crítico**: en brazo robótico la desalineación de primera capa
   propaga defectos a todas las capas, y la sincronización es especialmente difícil en
   curvas y pendientes (modo de fallo específico de brazo vs gantry — ASME 2025).

**Para nosotros:** el dry-run sin extrusión a velocidad reducida es directamente
implementable — ya tenemos el pipeline de toolpath y el speed scaling; sería un botón
"Dry run" en el panel de impresión web.

## 5. Tipos de extrusoras y límite de payload

**Confirmado (3-0):** Los surveys de referencia (Urhal et al. 2019, *RCIM*, DOI
10.1016/j.rcim.2019.05.005; Rescsanski et al. 2024/25, *RCIM*, DOI
10.1016/j.rcim.2024.102925) establecen que lo que se monta en brazos son procesos que caben
compactos en un end effector: **extrusión de material (filamento FFF, pellet) y DED tipo
WAAM**. Para un UR7e con su payload limitado, las clases realistas:

| Clase | Viabilidad en UR7e |
|---|---|
| Filamento FFF (E3D-style) | ✓ holgada |
| Pellet ligero (ej. Dyze Pulsar ~6 kg) | ✓ justa — verificar peso + hopper |
| Jeringa / pasta / progressive cavity (ViscoTec) | ✓ |
| Pellet industrial pesado, hormigón, WAAM | ✗ fuera por payload |

(La acotación al UR7e es síntesis nuestra; las fuentes hablan de <50 kg en brazos grandes.)

## 6. Capacidades únicas vs cartesianas/CNC 3 ejes — cuantificadas

Todo peer-reviewed, confirmado 3-0 (ARMS/RPJ 2020 + *Scientific Reports* 2026,
nature.com/articles/s41598-026-46136-2):

- **Overhangs hasta 90° sin soportes** reorientando la dirección de construcción durante la
  impresión; rugosidad constante en todos los ángulos (la impresora cartesiana de control —
  Ultimaker 2+ — falló a 80°).
- **La gravedad no afecta la calidad FFF** (p = 1.00, orientaciones 0°–180°) — extrusor y
  capa pueden reorientarse libremente. *Solo demostrado para FFF/PLA con Ra como métrica;
  no extrapolar a pastas, silicona u hormigón.*
- **Impresión conformal 57% más fuerte**: un arco impreso con capas curvas siguiendo la
  geometría resistió 184 N vs 117 N con capas planas.
- **43.7% menos tiempo** en superficies de doble curvatura support-free con 6 DOF.

Material útil para documentación/justificación del proyecto.

## 7. Validación de nuestro enfoque de software

**Confirmado (3-0):**

- El pipeline CAD→robot es fundamentalmente distinto al flujo slicer→G-code convencional —
  la salida de un slicer cartesiano nunca se reutiliza sin transformación (Urhal 2019).
- **ROS2 es la solución open-source más usada en robotic AM** y "particularmente adecuada
  para sistemas a medida" (Rescsanski 2024/25) — valida nuestra arquitectura.
- **El slicing multi-eje automático sigue siendo problema abierto**: ARMS generó su G-code
  conformal con scripts MATLAB ad hoc y seccionado manual en CAD; el sistema ASME 2025 se
  limita a superficies planares. Nuestro slicer multi-eje propio es una contribución
  legítima, no una reinvención de rueda.

---

## ⚠️ Afirmaciones refutadas (NO citar)

La verificación adversarial (0-3) mató 3 claims que sonaban plausibles:

1. "128 vs 65 mm/s de ventaja de velocidad del brazo" (atribuido a Sci Rep 2026) — no está
   en la fuente.
2. "La repetibilidad varía 0.87 mm según dirección de aproximación" (atribuido a
   arxiv 2408.04827) — no verificable en la fuente.
3. "Overhang de 32.5° con 2% de desviación demostrado en slicing no-planar" — mal atribuido.

## Huecos sin evidencia verificada

La investigación NO cubrió con claims confirmados:

- Cuánto error introduce **omitir la factory calibration** vs usar cinemática nominal
  (relevante: nuestro fallback actual cuando no existe el YAML de calibración).
- **Hand-eye calibration** formal, control térmico, tool changers y gestión de ofsets TCP
  multi-herramienta.
- Specs verificadas de fabricantes concretos (Dyze, Massive Dimension, ViscoTec) y casos
  comerciales (AI Build AiSync, Adaxis AdaOne) — fuentes leídas pero sus claims no pasaron
  el corte de verificación.

## Preguntas abiertas

1. ¿Cómo integrar la factory calibration del UR7e en el pipeline URDF/IK propio, y cuánto
   error introduce omitirla frente a la repetibilidad nominal de ±0.03 mm?
2. ¿Qué arquitectura debe tener la sincronización de flujo: publicar `speed_scaling` al
   controlador del extrusor vs comandar la extrusión como eje adicional de la misma
   trayectoria? ¿Latencia máxima tolerable?
3. ¿Qué requisitos impone soportar extrusoras intercambiables en un UR7e: ofsets TCP por
   herramienta en PolyScope/URDF, interfaces eléctricas comunes, límites de payload por
   clase?
4. ¿Cómo se comparan cuantitativamente los slicers multi-eje existentes (Adaxis AdaOne,
   AI Build, ROS-I AM framework, RoboDK+Cura, Open5x) con el nuestro en blending de
   esquinas, lookahead y manejo de singularidades?

## Recomendaciones accionables, por impacto

1. **Suscribir el extruder_controller a `speed_scaling`** del driver y modular el caudal —
   mayor impacto en calidad según la evidencia.
2. **Botón "Dry run"** (trayectoria sin extrusión a velocidad reducida) en el panel web —
   bajo costo, alto valor.
3. **Rutina guiada de calibración**: TCP del nozzle (asistente PolyScope) + registro de
   cama (método del papel), documentada en `docs/`.
4. **Evaluar el Passthrough Trajectory Controller** para trayectorias de impresión largas.
5. **Verificar peso real** de cualquier extrusora candidata contra el payload del UR7e
   antes de comprar.

## Fuentes principales

| Fuente | Tipo |
|---|---|
| Fry et al., ARMS, *Rapid Prototyping J.* 26(4) 2020, DOI 10.1108/RPJ-09-2019-0243 | peer-reviewed |
| Urhal et al., *Robotics and CIM* 2019, DOI 10.1016/j.rcim.2019.05.005 | peer-reviewed (review) |
| Rescsanski et al., *Robotics and CIM* 2025, DOI 10.1016/j.rcim.2024.102925 (arxiv 2408.04827) | peer-reviewed (survey) |
| ASME IMECE2025, arxiv.org/pdf/2510.24994 | peer-reviewed |
| SEAM robótico, *Virtual and Physical Prototyping* 2025, DOI 10.1080/17452759.2025.2551084 | peer-reviewed |
| *Scientific Reports* 2026, nature.com/articles/s41598-026-46136-2 | peer-reviewed |
| Trtnik, tesis UR5+E3D, theseus.fi (2022) | tesis de grado |
| UR ROS2 driver docs: ur_controllers + hardware_interface (Jazzy) | doc oficial |
| Manual PolyScope 5.21 "Teaching TCP Position" | doc oficial |
