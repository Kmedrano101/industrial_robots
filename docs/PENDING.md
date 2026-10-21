# Pendiente

Trabajo abierto en `feature/ur3d-printer-docker`. Actualizado 2026-10-21.
Orden sugerido: panel del extrusor → caudal con `speed_scaling`.

## Verificación con robot (UR7e real o URSim)

- [ ] Ajustes → Robot: "Capturar pose" para el home y los puntos de cama
      (`p1`–`p4`, `center`). Sin robot no se pudo probar.
- [ ] Confirmar que `print_node` usa el home guardado al imprimir
      (aplicado en caliente, ver [SETTINGS.md](SETTINGS.md)).
- [ ] Subir los commits locales de la rama (`git push`).

## Extrusor ([EXTRUDERS.md](EXTRUDERS.md))

- [ ] **Panel web del extrusor** guiado por `extruder_info`: temperatura por
      zona, consignas, ventilador, purga, estado de fallo y `reset_fault`.
      El backend ya reenvía `extruder_state` (multi-zona) y `extruder_info`;
      faltan endpoints para los servicios `SetExtruderTemperature`,
      `SetExtruderFan`, `PurgeExtruder`, `~/reset_fault`, `~/heaters_off`.
- [ ] **Caudal por segmento con adelanto**: `print_node` /
      `trajectory_planner` deben ordenar el caudal `flow.lag_s` antes de cada
      cambio de velocidad (el tornillo de pellets responde con retraso).
- [ ] **Longitud de herramienta del Mahor V5 PRO** (0.179 m, `nozzle_tcp` en
      `pellet_extruder.urdf.xacro`) como valor por defecto de la celda al
      elegir ese perfil; hoy se pone a mano en Ajustes → Robot.
- [ ] **Medir en la unidad real** los valores marcados `VERIFY` en
      `config/extruders/mahor_v5_m12_pro.yaml`: `flow.lag_s`, mm³ por vuelta,
      `e_mm_per_mm3` de la placa y potencia de los calentadores.

## Roadmap de investigación ([RESEARCH_ROBOTIC_AM.md](RESEARCH_ROBOTIC_AM.md))

- [ ] Suscribir `extruder_controller` a `speed_scaling` del
      `ur_robot_driver` para escalar el caudal cuando el robot frena
      (hallazgo nº 1).
- [ ] Botón **Dry run** en la web: trayectoria sin extrusión a velocidad
      reducida.
- [ ] Calibración guiada del TCP de la boquilla y registro de la cama.
- [ ] Evaluar el Passthrough Trajectory Controller.

## Multi-eje sin soportes ([RESEARCH_SUPPORT_FREE_MULTIAXIS.md](RESEARCH_SUPPORT_FREE_MULTIAXIS.md))

- [ ] Conectar `SegmentationResult` a `MultiAxisToolpathGenerator`
      (un `print_frame` por segmento).
- [ ] Endpoint `POST /api/slice/segmented` y su vista en la web (Tier 1,
      pasos 3–5).
