# TJ Simulator v1.0 — Micromouse Competition Simulator

Simulador de micromouse para la competencia ROBGAM 2026 con laberinto 3m×3m,
pasillos de 18cm de ancho, superficie negra y paredes blancas.

---

## Instalación

```bash
pip install pygame numpy
python main.py
```

---

## Estructura del proyecto

```
tj_simulator/
├── main.py              ← Punto de entrada
├── simulator.py         ← Aplicación pygame principal
├── config.py            ← Colores y constantes
├── maze.py              ← Clase Maze, parseo y exportación
├── maze_gen.py          ← Generador de laberintos
├── robot.py             ← Simulación del robot y sensores
├── algorithms.py        ← Todos los algoritmos de navegación
├── examples/            ← Laberintos de ejemplo
│   ├── maze_10x10_ejemplo.txt
│   └── maze_3x2_test.txt
└── esp32_algorithms/    ← Código ESP32 para tu robot
    ├── 01_left_wall_follower.ino
    ├── 03_flood_fill.ino        ← RECOMENDADO
    └── 04_tremaux.ino
```

---

## Controles

| Tecla / Botón | Acción |
|---|---|
| **Space** | Run / Stop |
| **R** | Reset robot a inicio |
| **E** | Activar modo edición de paredes |
| **S** | Ejecutar un paso |
| **Ctrl+O** | Cargar laberinto |
| **Ctrl+S** | Guardar laberinto |
| **Clic derecho** | (en edición) Mover inicio |
| **Shift+Clic der** | (en edición) Mover meta |

---

## Formato de laberintos

### Map format (ASCII)
```
+---+---+---+
|       |   |
+   +   +   +
|   |       |
+---+---+---+
```
- Cada celda: 4 caracteres de ancho, 2 líneas de alto
- `---` = pared horizontal, `|` = pared vertical

### Num format
```
X Y N E S W
0 0 0 1 1 1
0 1 1 0 0 1
```
- X, Y = coordenadas (Y=0 es abajo)
- N/E/S/W = 1 si hay pared, 0 si no

---

## Sensores simulados

| Sensor | Descripción |
|---|---|
| **VL53L0X Izquierda** | Distancia en mm a la pared izquierda |
| **VL53L0X Centro** | Distancia en mm a la pared frontal |
| **VL53L0X Derecha** | Distancia en mm a la pared derecha |
| **GY-91 Heading** | Ángulo de orientación (grados) |
| **Encoders** | Pulsos acumulados (PULSOS_POR_CASILLA = 2470) |
| **Color** | 255 en META, 30 en suelo normal |

Umbrales (iguales que tu ESP32):
- Pared lateral: < 150mm → pared detectada
- Pared frontal: < 70mm → pared detectada

---

## Algoritmos disponibles

1. **Right Wall Follower** — Tu código actual (frente→izq→der→180)
2. **Left Wall Follower** — Espejo del anterior
3. **Flood Fill** ⭐ — Mejor para micromouse, descubre paredes en tiempo real
4. **BFS** — Camino mínimo garantizado (requiere mapa completo)
5. **A\*** — A-Star con heurística Manhattan
6. **Trémaux** — Sin mapa, garantiza llegar, marca pasillos
7. **Right Wall + Memoria** — Wall follower con memoria de visitas

### Comparación

| Algoritmo | Conocimiento mapa | Óptimo | Velocidad |
|---|---|---|---|
| Wall Follower | No | No | Medio |
| Flood Fill | Parcial | Casi | Rápido |
| BFS | Completo | Sí | Muy rápido (2ª vuelta) |
| A* | Completo | Sí | Muy rápido |
| Trémaux | No | No | Lento |

**Recomendación para la competencia:**
1. Primera vuelta: **Flood Fill** (explora y llega)
2. Segunda vuelta: **BFS** o **A*** (camino mínimo con mapa conocido)

---

## Código ESP32 recomendado

Para la competencia, usa `esp32_algorithms/03_flood_fill.ino`.

Ajusta antes de compilar:
```cpp
#define GOAL_COL 4   // Columna de la meta
#define GOAL_ROW 4   // Fila de la meta
int robotRow = 9;    // Fila inicial (rows-1 para laberinto 10x10)
```

---

## Especificaciones de la competencia ROBGAM 2026

- Laberinto: 3m × 3m
- Pasillos: ~18cm de ancho
- Barreras: madera, 5cm de alto
- Suelo: fórmica negro mate
- Paredes: blancas, alta reflectancia
- Robot: máx. 10cm × 10cm
- Intentos: 3 rounds, mejor tiempo cuenta

---

## Autor
TJ Team — JOSÉ PARDIÑAZ, CESAR FRANCO & ANGELICA BONILLA
