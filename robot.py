# ============================================================
#  TJ Simulator — Robot  (GA12-N20 + VL53L0X noise + GY-91)
# ============================================================
import math, random
from config import (PULSOS_POR_CASILLA, PULSOS_GIRO_90,
                    SENSOR_MAX_RANGE, CELL_SIZE_MM,
                    VL53_NOISE_BASE, VL53_NOISE_FACTOR,
                    VL53_OUTLIER_PROB, IMU_GYRO_DRIFT_DEG_S,
                    WALL_SIDE_THRESHOLD, WALL_FRONT_THRESHOLD,
                    COUNTS_PER_MM, WHEEL_CIRCUM_MM)

_DIR_IDX = {'N':0,'E':1,'S':2,'W':3}
_IDX_DIR = {0:'N',1:'E',2:'S',3:'W'}
_TURN_CW  = {'N':'E','E':'S','S':'W','W':'N'}
_TURN_CCW = {'N':'W','W':'S','S':'E','E':'N'}

def _rel_to_abs(heading, rel):
    return _IDX_DIR[(_DIR_IDX[heading]+{'F':0,'R':1,'B':2,'L':3}[rel])%4]


class Robot:
    GOAL_COLOR_VALUE = 255   # TCS34725 devuelve 255 en la meta (verde)
    FLOOR_COLOR_VALUE = 30   # suelo negro normal

    def __init__(self, maze):
        self.maze = maze
        self.col, self.row = maze.start
        self.heading = 'N'

        # Encoders (pulsos acumulados)
        self.enc1 = 0
        self.enc2 = 0
        self.enc1_delta = 0
        self.enc2_delta = 0

        # GY-91 — "Norte virtual": arranque = 0 grados
        # El magnetometro tiene offset aleatorio que simula
        # que el robot no esta alineado perfectamente al norte real
        self._mag_offset = random.uniform(-30, 30)  # offset magnetico
        self._gyro_accum = 0.0    # acumulado de giros
        self._gyro_drift = 0.0    # deriva acumulada del giroscopio
        self.imu_heading_deg = 0.0  # heading relativo al arranque
        self.imu_accel = (0.0, 0.0, 0.0)

        # Memoria del laberinto (simula EEPROM del ESP32)
        self.maze_memory = None   # None = sin memoria, o dict con walls
        self.memory_loaded = False

        # Visitados / ruta
        self.visited = {(self.col, self.row)}
        self.path    = [(self.col, self.row)]

        # Animacion
        self.anim_t      = 1.0
        self.anim_from_c = self.col
        self.anim_from_r = self.row
        self.anim_from_h = self.heading

        # Stats
        self.steps         = 0
        self.total_dist_mm = 0.0
        self.total_turns   = 0

        # Cache sensores (con ruido)
        self._last_L = 0
        self._last_C = 0
        self._last_R = 0

    # ── VL53L0X con ruido realista ────────────────────────────
    def _add_vl53_noise(self, true_dist_mm):
        """
        Modelo de ruido VL53L0X basado en datasheet:
        - Ruido Gaussiano: sigma = max(8, 0.012 * d)
        - Outliers: 3% de probabilidad, ±50-100mm
        - Minimo: 30mm (el sensor no mide menos)
        - Maximo: SENSOR_MAX_RANGE (saturacion)
        """
        sigma = max(VL53_NOISE_BASE, VL53_NOISE_FACTOR * true_dist_mm)
        noisy = true_dist_mm + random.gauss(0, sigma)
        # Outlier ocasional
        if random.random() < VL53_OUTLIER_PROB:
            noisy += random.choice([-1, 1]) * random.uniform(40, 90)
        return int(max(30, min(SENSOR_MAX_RANGE + 50, noisy)))

    def _ray(self, direction):
        """Ray casting para obtener distancia real, luego aplica ruido."""
        c, r = self.col, self.row
        dist_mm = 0.0
        for _ in range(12):
            if self.maze.has_wall(c, r, direction):
                dist_mm += CELL_SIZE_MM / 2
                return self._add_vl53_noise(min(dist_mm, SENSOR_MAX_RANGE))
            dist_mm += CELL_SIZE_MM
            nc, nr = self.maze.next_cell(c, r, direction)
            if not self.maze._valid(nc, nr): break
            c, r = nc, nr
        return self._add_vl53_noise(SENSOR_MAX_RANGE)

    def read_sensors(self):
        """
        Simula 3 lecturas VL53L0X con ruido y tiempo de procesamiento.
        En el ESP32 real esto tarda ~75ms (25ms por sensor en serie).
        """
        L = self._ray(_rel_to_abs(self.heading, 'L'))
        C = self._ray(_rel_to_abs(self.heading, 'F'))
        R = self._ray(_rel_to_abs(self.heading, 'R'))
        self._last_L, self._last_C, self._last_R = L, C, R
        return L, C, R

    def read_sensors_true(self):
        """Lectura sin ruido (para visualizacion de beams)."""
        def ray_true(direction):
            c, r = self.col, self.row
            dist_mm = 0.0
            for _ in range(12):
                if self.maze.has_wall(c, r, direction):
                    return min(int(dist_mm + CELL_SIZE_MM/2), SENSOR_MAX_RANGE)
                dist_mm += CELL_SIZE_MM
                nc, nr = self.maze.next_cell(c, r, direction)
                if not self.maze._valid(nc, nr): break
                c, r = nc, nr
            return SENSOR_MAX_RANGE
        return (ray_true(_rel_to_abs(self.heading,'L')),
                ray_true(_rel_to_abs(self.heading,'F')),
                ray_true(_rel_to_abs(self.heading,'R')))

    # ── TCS34725 color sensor ────────────────────────────────
    def read_color(self):
        """
        Simula el sensor TCS34725.
        Devuelve 255 en zona de meta (verde), 30 en suelo negro.
        Con un poco de ruido de lectura ADC.
        """
        if self.is_at_goal():
            return int(self.GOAL_COLOR_VALUE + random.gauss(0, 3))
        return int(self.FLOOR_COLOR_VALUE + random.gauss(0, 2))

    # ── GY-91 IMU ────────────────────────────────────────────
    def read_imu(self):
        """
        Simula MPU-9250 con:
        - Magnetometro: heading relativo al "norte virtual" + ruido
        - Giroscopio: heading acumulado con deriva
        - Norte virtual: el heading al arranque = 0 grados
        """
        # Actualizar deriva del giroscopio (simula tiempo transcurrido)
        self._gyro_drift += IMU_GYRO_DRIFT_DEG_S * 0.1  # ~0.1s por paso
        heading_with_drift = (self.imu_heading_deg +
                              self._gyro_drift +
                              random.gauss(0, 0.5))
        # Magnetometro (mas ruidoso pero sin drift)
        mag_heading = self.imu_heading_deg + random.gauss(0, 2.0)
        # Fusion simple: 95% giroscopio, 5% magnetometro
        fused = 0.95 * heading_with_drift + 0.05 * mag_heading
        fused = fused % 360
        return fused, self.imu_accel, (0.0, 0.0, 0.0)

    # ── Goal detection ────────────────────────────────────────
    def is_at_goal(self):
        return (self.col, self.row) in self.maze.goal_cells

    def wall_in_direction(self, rel):
        return self.maze.has_wall(self.col, self.row,
                                  _rel_to_abs(self.heading, rel))

    # ── Movement ─────────────────────────────────────────────
    def move_forward(self):
        fwd = _rel_to_abs(self.heading, 'F')
        if self.maze.has_wall(self.col, self.row, fwd):
            return False

        self.anim_from_c = self.col
        self.anim_from_r = self.row
        self.anim_from_h = self.heading
        self.anim_t = 0.0

        nc, nr = self.maze.next_cell(self.col, self.row, fwd)
        self.col, self.row = nc, nr

        delta = PULSOS_POR_CASILLA
        # Simula pequeña diferencia entre encoders (ruido mecanico)
        noise = int(random.gauss(0, delta * 0.005))
        self.enc1 += delta + noise
        self.enc2 += delta - noise
        self.enc1_delta = delta + noise
        self.enc2_delta = delta - noise

        self.imu_accel = (0.0, 0.0, 1.0)
        self.steps += 1
        self.total_dist_mm += CELL_SIZE_MM
        self.visited.add((self.col, self.row))
        self.path.append((self.col, self.row))
        return True

    def turn_left(self):
        self.anim_from_h = self.heading
        self.anim_from_c = self.col
        self.anim_from_r = self.row
        self.anim_t = 0.0
        self.heading = _TURN_CCW[self.heading]
        self.enc1 -= PULSOS_GIRO_90
        self.enc2 += PULSOS_GIRO_90
        self.imu_heading_deg = (self.imu_heading_deg - 90) % 360
        self.total_turns += 1

    def turn_right(self):
        self.anim_from_h = self.heading
        self.anim_from_c = self.col
        self.anim_from_r = self.row
        self.anim_t = 0.0
        self.heading = _TURN_CW[self.heading]
        self.enc1 += PULSOS_GIRO_90
        self.enc2 -= PULSOS_GIRO_90
        self.imu_heading_deg = (self.imu_heading_deg + 90) % 360
        self.total_turns += 1

    def turn_180(self):
        self.turn_left(); self.turn_left()

    def reset(self):
        self.col, self.row = self.maze.start
        self.heading = 'N'
        self.enc1 = self.enc2 = 0
        self.enc1_delta = self.enc2_delta = 0
        self.imu_heading_deg = 0.0
        self._gyro_drift = 0.0
        self._gyro_accum = 0.0
        self.imu_accel = (0.0, 0.0, 0.0)
        self.visited = {(self.col, self.row)}
        self.path = [(self.col, self.row)]
        self.anim_t = 1.0
        self.anim_from_c = self.col
        self.anim_from_r = self.row
        self.anim_from_h = self.heading
        self.steps = 0
        self.total_dist_mm = 0.0
        self.total_turns = 0
        self._last_L = self._last_C = self._last_R = 0

    def status_lines(self):
        L, C, R = self._last_L, self._last_C, self._last_R
        color = self.read_color()
        fused_hdg, _, _ = self.read_imu()
        dirs8 = ['N','NE','E','SE','S','SO','O','NO']
        dname = dirs8[int((fused_hdg+22.5)%360//45)]
        is_goal = self.is_at_goal()

        return [
            f"Pos:  ({self.col:2d}, {self.row:2d})",
            f"Rumbo: {self.heading}   IMU: {fused_hdg:6.1f}  ({dname})",
            f"Enc1: {self.enc1:+9d} p   d:{self.enc1_delta:+5d}",
            f"Enc2: {self.enc2:+9d} p   d:{self.enc2_delta:+5d}",
            f"TOF-IZQ {L:4d}mm  TOF-CEN {C:4d}mm",
            f"TOF-DER {R:4d}mm",
            f"Color: {color:3d}  {'** META **' if is_goal else 'suelo negro'}",
            f"Pasos: {self.steps}   Giros: {self.total_turns}",
            f"Dist:  {self.total_dist_mm/1000:.3f} m",
            f"Mem:   {'CARGADA' if self.memory_loaded else 'vacia'}",
        ]