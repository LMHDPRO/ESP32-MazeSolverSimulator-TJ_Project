# ============================================================
#  TJ Simulator v2.2 — Robot
#  · Sensor beams con raycast en angulo continuo (fangle)
#  · Action queue: movimientos encadenados sin parar
#  · PID doble lazo: dist_mm + gyro
# ============================================================

import math, random
from math import copysign
from collections import deque
from config import (
    CELL_SIZE_MM, SENSOR_MAX_RANGE,
    CPR_M1, CPR_M2, MM_PER_CNT_M1, MM_PER_CNT_M2,
    PULSOS_POR_CASILLA_M1, PULSOS_POR_CASILLA_M2,
    PULSOS_GIRO_90_M1, PULSOS_GIRO_90_M2,
    KP_DIST, KI_DIST, KP_GYRO, MAX_CORR,
    VL53_NOISE_BASE, VL53_NOISE_FACTOR, VL53_OUTLIER_PROB,
    IMU_GYRO_DRIFT_DEG_S, PHYSICS_SPEEDS,
    COLLISION_WARN_DIST, COLLISION_DANGER_DIST,
)

_DIR_IDX = {'N':0,'E':1,'S':2,'W':3}
_IDX_DIR = {0:'N',1:'E',2:'S',3:'W'}
_TURN_CW  = {'N':'E','E':'S','S':'W','W':'N'}
_TURN_CCW = {'N':'W','W':'S','S':'E','E':'N'}
_HEADING_ANGLE = {'N':0.0,'E':90.0,'S':180.0,'W':270.0}

def _rel_to_abs(heading, rel):
    return _IDX_DIR[(_DIR_IDX[heading]+{'F':0,'R':1,'B':2,'L':3}[rel])%4]

def _ease_out_cubic(t):
    return 1.0 - (1.0-t)**3

def _ease_smooth(t):
    return t*t*(3.0-2.0*t)

# Beams: separación angular de los 3 sensores (grados)
SENSOR_ANGLES = {'L': -90.0, 'F': 0.0, 'R': 90.0}


class Robot:
    GOAL_COLOR_VALUE  = 255
    FLOOR_COLOR_VALUE = 30

    def __init__(self, maze):
        self.maze = maze
        self.col, self.row = maze.start
        # Face the open direction at spawn so first move is forward
        self.heading = getattr(maze, 'start_heading', 'N')

        # ── Posicion y angulo continuos ──────────────────────
        self.fx     = float(self.col)
        self.fy     = float(self.row)
        self.fangle = _HEADING_ANGLE.get(self.heading, 0.0)

        # Estado de animacion
        self.state         = 'idle'
        self.move_from_fx  = self.fx
        self.move_from_fy  = self.fy
        self.move_to_fx    = self.fx
        self.move_to_fy    = self.fy
        self.move_progress = 0.0
        self.rot_from      = self.fangle
        self.rot_to        = self.fangle
        self.rot_progress  = 0.0

        # ── Action queue (movimientos encadenados) ───────────
        # Cada item: ('forward'|'rotate', delta)
        self._action_queue = deque()
        self._pending_discrete = deque()   # acciones discretas pendientes

        # ── Encoders (CPR diferente M1/M2) ──────────────────
        self.enc1 = 0
        self.enc2 = 0
        self.enc1_delta = 0
        self.enc2_delta = 0
        self._dist1_mm = 0.0
        self._dist2_mm = 0.0
        self._integral_dist = 0.0

        # ── IMU MPU6500 ──────────────────────────────────────
        self._gyro_drift     = 0.0
        self.imu_heading_deg = 0.0
        self._target_angle   = 0.0
        self.imu_accel       = (0.0, 0.0, 0.0)

        # ── Sensor cache ─────────────────────────────────────
        self._last_L = 350
        self._last_C = 350
        self._last_R = 350
        # Cache de raycast en angulo continuo (para beams)
        self._beam_L = 350.0
        self._beam_C = 350.0
        self._beam_R = 350.0

        # ── Memoria EEPROM simulada ──────────────────────────
        self.maze_memory   = None
        self.memory_loaded = False

        # ── Visitados / ruta ─────────────────────────────────
        self.visited = {(self.col, self.row)}
        self.path    = [(self.col, self.row)]

        # ── Stats ────────────────────────────────────────────
        self.steps         = 0
        self.total_dist_mm = 0.0
        self.total_turns   = 0

    # ══════════════════════════════════════════════════════════
    #  RAYCAST EN ANGULO CONTINUO
    #  Se usa para los beams visuales — refleja exactamente
    #  donde apunta el sensor segun el angulo visual actual.
    # ══════════════════════════════════════════════════════════
    def _ray_continuous(self, angle_deg: float) -> float:
        """
        Raycast DDA desde la posicion continua (fx, fy).
        angle_deg: 0=N, 90=E, 180=S, 270=W
        Retorna distancia en mm a la primera pared.
        """
        rad = math.radians(angle_deg)
        dx  =  math.sin(rad)
        dy  = -math.cos(rad)

        eps = 1e-9
        if abs(dx) < eps: dx = copysign(eps, dx) if dx != 0 else eps
        if abs(dy) < eps: dy = copysign(eps, dy) if dy != 0 else eps

        # Convertir angulo a direccion de pared para chequeo rapido
        dir_map = {
            (1, 0): 'E', (-1, 0): 'W',
            (0, 1): 'S', (0, -1): 'N',
        }

        cx = max(0, min(self.maze.cols-1, int(self.fx)))
        cy = max(0, min(self.maze.rows-1, int(self.fy)))

        # El robot se posiciona en el CENTRO de la celda (fx+0.5, fy+0.5)
        # sub = fraccion dentro de la celda [0..1], siempre desde el centro (0.5)
        abs_x = self.fx + 0.5   # posicion absoluta del centro del robot
        abs_y = self.fy + 0.5
        cx = max(0, min(self.maze.cols-1, int(abs_x)))
        cy = max(0, min(self.maze.rows-1, int(abs_y)))
        sub_x = abs_x - cx     # fraccion dentro de la celda
        sub_y = abs_y - cy

        step_x = 1 if dx > 0 else -1
        step_y = 1 if dy > 0 else -1

        # t hasta el proximo borde en x e y
        if dx > 0:
            t_max_x = (1.0 - sub_x) / dx
        else:
            t_max_x = sub_x / abs(dx)
        if dy > 0:
            t_max_y = (1.0 - sub_y) / dy
        else:
            t_max_y = sub_y / abs(dy)

        t_delta_x = 1.0 / abs(dx)
        t_delta_y = 1.0 / abs(dy)

        t = 0.0

        for _ in range(25):
            if not self.maze._valid(cx, cy):
                return min(t * CELL_SIZE_MM, float(SENSOR_MAX_RANGE))

            # Determinar cual borde cruzamos a continuacion
            if t_max_x < t_max_y:
                # Cruzamos borde E o W
                wall_dir = 'E' if step_x > 0 else 'W'
                if self.maze.has_wall(cx, cy, wall_dir):
                    dist_cells = t_max_x
                    return min(dist_cells * CELL_SIZE_MM, float(SENSOR_MAX_RANGE))
                t = t_max_x
                t_max_x += t_delta_x
                cx += step_x
            else:
                # Cruzamos borde S o N
                wall_dir = 'S' if step_y > 0 else 'N'
                if self.maze.has_wall(cx, cy, wall_dir):
                    dist_cells = t_max_y
                    return min(dist_cells * CELL_SIZE_MM, float(SENSOR_MAX_RANGE))
                t = t_max_y
                t_max_y += t_delta_y
                cy += step_y

        return float(SENSOR_MAX_RANGE)

    def update_beams(self):
        """Recalcula los beams con el angulo visual actual."""
        for rel, offset in SENSOR_ANGLES.items():
            ang = (self.fangle + offset) % 360.0
            dist = self._ray_continuous(ang)
            if rel == 'L': self._beam_L = dist
            elif rel == 'F': self._beam_C = dist
            elif rel == 'R': self._beam_R = dist

    # ══════════════════════════════════════════════════════════
    #  FISICA CONTINUA
    # ══════════════════════════════════════════════════════════
    def update_physics(self, dt_sec: float, speed_name: str):
        if speed_name not in PHYSICS_SPEEDS:
            speed_name = "Normal"
        spd = PHYSICS_SPEEDS[speed_name]

        if self.state == 'moving':
            # Avance proporcional al tiempo
            advance = dt_sec * spd['move']
            self.move_progress = min(1.0, self.move_progress + advance)
            t = _ease_out_cubic(self.move_progress)
            self.fx = self.move_from_fx + (self.move_to_fx - self.move_from_fx) * t
            self.fy = self.move_from_fy + (self.move_to_fy - self.move_from_fy) * t

            # Encadenar siguiente forward antes de terminar (progress > 0.80)
            # Esto elimina la pausa visual entre casillas consecutivas
            if self.move_progress >= 0.80 and self._action_queue:
                next_act = self._action_queue[0]
                if next_act[0] == 'forward':
                    self._action_queue.popleft()
                    # Aplicar discreto
                    disc = self._pending_discrete.popleft() if self._pending_discrete else None
                    if disc:
                        self._apply_discrete_forward(disc)
                    self._start_move_anim()
                    return

            if self.move_progress >= 1.0:
                self.fx    = self.move_to_fx
                self.fy    = self.move_to_fy
                self.state = 'idle'

        elif self.state == 'rotating':
            span = abs(self.rot_to - self.rot_from)
            if span < 0.01:
                self.fangle = self.rot_to % 360.0
                self.state  = 'idle'
                return
            advance = dt_sec * spd['rot'] / span
            self.rot_progress = min(1.0, self.rot_progress + advance)
            t = _ease_smooth(self.rot_progress)
            self.fangle = (self.rot_from +
                           (self.rot_to - self.rot_from) * t) % 360.0
            if self.rot_progress >= 1.0:
                self.fangle = self.rot_to % 360.0
                self.state  = 'idle'

        # Actualizar beams cada frame
        self.update_beams()

        # Deriva gyro
        self._gyro_drift += IMU_GYRO_DRIFT_DEG_S * dt_sec

    def is_busy(self):
        return self.state != 'idle'

    # ══════════════════════════════════════════════════════════
    #  SENSORES
    # ══════════════════════════════════════════════════════════
    def _add_noise(self, d):
        sigma = max(VL53_NOISE_BASE, VL53_NOISE_FACTOR * d)
        noisy = d + random.gauss(0, sigma)
        if random.random() < VL53_OUTLIER_PROB:
            noisy += random.choice([-1, 1]) * random.uniform(40, 90)
        return int(max(30, min(SENSOR_MAX_RANGE + 50, noisy)))

    def _ray_discrete(self, direction):
        """Raycast discreto para la logica del algoritmo."""
        c, r  = self.col, self.row
        dist  = 0.0
        for _ in range(12):
            if self.maze.has_wall(c, r, direction):
                return min(int(dist + CELL_SIZE_MM / 2), SENSOR_MAX_RANGE)
            dist += CELL_SIZE_MM
            nc, nr = self.maze.next_cell(c, r, direction)
            if not self.maze._valid(nc, nr): break
            c, r = nc, nr
        return SENSOR_MAX_RANGE

    def read_sensors(self):
        """Con ruido — para los algoritmos."""
        L = self._add_noise(self._ray_discrete(_rel_to_abs(self.heading,'L')))
        C = self._add_noise(self._ray_discrete(_rel_to_abs(self.heading,'F')))
        R = self._add_noise(self._ray_discrete(_rel_to_abs(self.heading,'R')))
        self._last_L, self._last_C, self._last_R = L, C, R
        return L, C, R

    def read_color(self):
        base = self.GOAL_COLOR_VALUE if self.is_at_goal() else self.FLOOR_COLOR_VALUE
        return int(base + random.gauss(0, 2))

    def read_imu(self):
        noisy = (self.imu_heading_deg + self._gyro_drift
                 + random.gauss(0, 0.4)) % 360.0
        return noisy, self.imu_accel, (0.0, 0.0, 0.0)

    # ══════════════════════════════════════════════════════════
    #  PID (para mostrar en panel)
    # ══════════════════════════════════════════════════════════
    def _pid_correction(self):
        ed = self._dist1_mm - self._dist2_mm
        self._integral_dist = max(-200.0, min(200.0,
                                              self._integral_dist + ed))
        corr_dist = KP_DIST * ed + KI_DIST * self._integral_dist
        hdg, _, _ = self.read_imu()
        eh = hdg - self._target_angle
        while eh >  180.0: eh -= 360.0
        while eh < -180.0: eh += 360.0
        return max(-float(MAX_CORR), min(float(MAX_CORR),
                                         corr_dist + KP_GYRO * eh))

    # ══════════════════════════════════════════════════════════
    #  GOAL / PROXIMIDAD
    # ══════════════════════════════════════════════════════════
    def is_at_goal(self):
        return (self.col, self.row) in self.maze.goal_cells

    def wall_in_direction(self, rel):
        return self.maze.has_wall(self.col, self.row,
                                  _rel_to_abs(self.heading, rel))

    def wall_proximity(self):
        col = max(0, min(self.maze.cols-1, int(self.fx)))
        row = max(0, min(self.maze.rows-1, int(self.fy)))
        cx  = self.fx - col
        cy  = self.fy - row
        return {
            'N': (cy,       self.maze.has_wall(col, row, 'N')),
            'S': (1.0-cy,   self.maze.has_wall(col, row, 'S')),
            'W': (cx,       self.maze.has_wall(col, row, 'W')),
            'E': (1.0-cx,   self.maze.has_wall(col, row, 'E')),
        }

    # ══════════════════════════════════════════════════════════
    #  MOVIMIENTO
    # ══════════════════════════════════════════════════════════
    def _apply_discrete_forward(self, fwd_dir):
        """Aplica el cambio discreto de posicion y encoders."""
        nc, nr = self.maze.next_cell(self.col, self.row, fwd_dir)
        self.col, self.row = nc, nr
        n1 = int(random.gauss(0, PULSOS_POR_CASILLA_M1 * 0.005))
        n2 = int(random.gauss(0, PULSOS_POR_CASILLA_M2 * 0.005))
        self.enc1 += PULSOS_POR_CASILLA_M1 + n1
        self.enc2 += PULSOS_POR_CASILLA_M2 + n2
        self.enc1_delta = PULSOS_POR_CASILLA_M1 + n1
        self.enc2_delta = PULSOS_POR_CASILLA_M2 + n2
        self._dist1_mm += (PULSOS_POR_CASILLA_M1 + n1) * MM_PER_CNT_M1
        self._dist2_mm += (PULSOS_POR_CASILLA_M2 + n2) * MM_PER_CNT_M2
        hdg, _, _ = self.read_imu()
        self._target_angle  = hdg
        self._integral_dist = 0.0
        self.imu_accel = (0.0, 0.0, 1.0)
        self.steps         += 1
        self.total_dist_mm += CELL_SIZE_MM
        self.visited.add((self.col, self.row))
        self.path.append((self.col, self.row))

    def _start_move_anim(self):
        """Inicia animacion de movimiento hacia la celda actual."""
        # Snap any ongoing move to avoid position drift
        if self.state == 'moving':
            self.fx = self.move_to_fx
            self.fy = self.move_to_fy
        self.move_from_fx  = self.fx
        self.move_from_fy  = self.fy
        self.move_to_fx    = float(self.col)
        self.move_to_fy    = float(self.row)
        self.move_progress = 0.0
        self.state         = 'moving'

    def move_forward(self) -> bool:
        fwd = _rel_to_abs(self.heading, 'F')
        if self.maze.has_wall(self.col, self.row, fwd):
            return False
        self._apply_discrete_forward(fwd)
        self._start_move_anim()
        return True

    def _start_rotate(self, delta_deg: float):
        # If already rotating, snap to final angle first
        if self.state == 'rotating':
            self.fangle = self.rot_to % 360.0
        self.rot_from     = self.fangle
        self.rot_to       = self.fangle + delta_deg
        self.rot_progress = 0.0
        self.state        = 'rotating'
        self.imu_heading_deg = (self.imu_heading_deg + delta_deg) % 360.0
        self._integral_dist  = 0.0
        self.total_turns    += 1

        # Wheel Y offset effect on turn: when wheels are offset longitudinally,
        # the pivot point shifts. Simulate as small position displacement.
        # At 90° turn with offset_y mm: robot CG moves offset_y * sqrt(2) - offset_y
        # in the direction perpendicular to travel. Very subtle at small offsets.
        try:
            import robot_config as _RC
            offset_y_mm = _RC.WHEEL_OFFSET_Y_MM
            if abs(offset_y_mm) > 0.5 and abs(delta_deg) >= 88:
                rad = math.radians(self.fangle)
                # Perpendicular to current heading
                perp_x =  math.cos(rad)
                perp_y =  math.sin(rad)
                sign = 1 if delta_deg > 0 else -1
                # Displacement in cells (very small — mm to cells)
                from config import CELL_SIZE_MM as _CS
                disp = sign * offset_y_mm * 0.05 / _CS   # very subtle
                self.fx += perp_x * disp
                self.fy += perp_y * disp
        except Exception:
            pass

    def turn_left(self):
        self.heading = _TURN_CCW[self.heading]
        self.enc1   -= PULSOS_GIRO_90_M1
        self.enc2   += PULSOS_GIRO_90_M2
        self._start_rotate(-90.0)

    def turn_right(self):
        self.heading = _TURN_CW[self.heading]
        self.enc1   += PULSOS_GIRO_90_M1
        self.enc2   -= PULSOS_GIRO_90_M2
        self._start_rotate(+90.0)

    def turn_180(self):
        opp = {'N':'S','S':'N','E':'W','W':'E'}
        self.heading = opp[self.heading]
        self.enc1   -= PULSOS_GIRO_90_M1 * 2
        self.enc2   += PULSOS_GIRO_90_M2 * 2
        self._start_rotate(-180.0)

    def reset(self):
        self.col, self.row   = self.maze.start
        self.heading          = getattr(self.maze,'start_heading','N')
        self.fx               = float(self.col)
        self.fy               = float(self.row)
        self.fangle           = _HEADING_ANGLE.get(
            getattr(self.maze,'start_heading','N'), 0.0)
        self.state            = 'idle'
        self.move_progress    = 0.0
        self.rot_progress     = 0.0
        self.move_from_fx = self.move_to_fx = self.fx
        self.move_from_fy = self.move_to_fy = self.fy
        self.rot_from = self.rot_to = self.fangle
        self._action_queue.clear()
        self._pending_discrete.clear()
        self.enc1 = self.enc2 = 0
        self.enc1_delta = self.enc2_delta = 0
        self._dist1_mm = self._dist2_mm = 0.0
        self._integral_dist = 0.0
        self._gyro_drift     = 0.0
        self.imu_heading_deg = 0.0
        self._target_angle   = 0.0
        self.imu_accel       = (0.0, 0.0, 0.0)
        self.visited = {(self.col, self.row)}
        self.path    = [(self.col, self.row)]
        self.steps   = 0
        self.total_dist_mm = 0.0
        self.total_turns   = 0
        self._last_L = self._last_C = self._last_R = 350
        self._beam_L = self._beam_C = self._beam_R = 350.0
        self.update_beams()

    # ── Panel ────────────────────────────────────────────────
    def status_lines(self):
        L, C, R  = self._last_L, self._last_C, self._last_R
        color    = self.read_color()
        fused, _, _ = self.read_imu()
        dirs8    = ['N','NE','E','SE','S','SO','O','NO']
        dname    = dirs8[int((fused+22.5)%360//45)]
        pid_corr = self._pid_correction()
        return [
            f"Pos ({self.col:2d},{self.row:2d})  "
            f"phy({self.fx:.2f},{self.fy:.2f})",
            f"Rumbo: {self.heading}  IMU: {fused:6.1f} ({dname})",
            f"Ang: {self.fangle:.1f}  Drift: {self._gyro_drift:.2f}",
            f"Enc1(840cpr) {self.enc1:+8d} p",
            f"Enc2(420cpr) {self.enc2:+8d} p",
            f"Dist M1: {self._dist1_mm:7.1f}mm",
            f"Dist M2: {self._dist2_mm:7.1f}mm",
            f"PID corr: {pid_corr:+.1f}  Int: {self._integral_dist:.1f}",
            f"TOF-IZQ {L:4d}  CEN {C:4d}  DER {R:4d} mm",
            f"Color: {color:3d}  "
            f"{'** META **' if self.is_at_goal() else 'suelo'}",
            f"Pasos: {self.steps}  Giros: {self.total_turns}",
            f"Dist: {self.total_dist_mm/1000:.3f} m",
        ]