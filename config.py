# ============================================================
#  TJ Simulator v2.3 — Configuration
#  robot_config.py handles all motor/physics params.
#  config.py imports from it — robot_config must NOT import config.
# ============================================================

SCREEN_W = 1368
SCREEN_H = 768
FPS      = 60
TITLE    = "TJ Simulator v2.3 — Micromouse"

PANEL_W   = 320
CONSOLE_H = 140
HEADER_H  = 44

C_BG           = (10,  10,  12 )
C_PANEL        = (20,  20,  24 )
C_CARD         = (30,  30,  36 )
C_BORDER       = (48,  48,  56 )
C_DIVIDER      = (38,  38,  44 )
C_RED          = (200, 20,  20 )
C_RED_H        = (230, 55,  55 )
C_RED_D        = (130, 10,  10 )
C_TEXT_H       = (225, 225, 230)
C_TEXT_M       = (155, 155, 165)
C_TEXT_L       = (80,  80,  92 )
C_GREEN        = (40,  185, 70 )
C_BLUE         = (50,  110, 215)
C_YELLOW       = (205, 180, 40 )
C_ORANGE       = (210, 120, 0  )
C_TEAL         = (0,   175, 155)
C_MAZE_BG      = (14,  14,  18 )
C_WALL         = (235, 235, 240)
C_WALL_WARN    = (220, 80,  0  )
C_WALL_DANGER  = (220, 30,  30 )
C_FLOOR        = (20,  20,  25 )
C_VISITED      = (28,  28,  50 )
C_START_CELL   = (18,  30,  90 )
C_GOAL_CELL    = (20,  90,  35 )
C_ROBOT_BODY   = (55,  55,  65 )
C_ROBOT_ACCENT = (200, 20,  20 )
C_SENSOR_BEAM  = (255, 90,  0  )
C_FLOOD_LO     = (20,  40,  100)
C_FLOOD_HI     = (180, 20,  20 )

# Sensor thresholds
WALL_SIDE_THRESHOLD  = 120
WALL_FRONT_THRESHOLD = 120
SENSOR_MAX_RANGE     = 350
VL53_NOISE_BASE      = 8.0
VL53_NOISE_FACTOR    = 0.012
VL53_OUTLIER_PROB    = 0.03
IMU_GYRO_DRIFT_DEG_S = 0.08

# Anti-colision visual
COLLISION_WARN_DIST   = 0.32
COLLISION_DANGER_DIST = 0.18

# PID
KP_DIST = 1.8
KI_DIST = 0.04
KP_GYRO = 2.5
MAX_CORR = 35

# Cell
CELL_SIZE_MM = 180

# Defaults
DEFAULT_SPEED = "Normal"
DEFAULT_COLS  = 10
DEFAULT_ROWS  = 10

# Start positions
START_POSITIONS = {
    "Inferior Izq (default)": "bottom_left",
    "Inferior Der":           "bottom_right",
    "Superior Izq":           "top_left",
    "Superior Der":           "top_right",
}

# ── Import physics from robot_config (one-way, no circular) ──
# robot_config.py must NEVER import from config.py
import robot_config as _RC

def _sync():
    """Pull live values from robot_config into this module's namespace."""
    import sys
    m = sys.modules[__name__]
    m.PHYSICS_SPEEDS        = _RC.PHYSICS_SPEEDS
    m.PULSOS_POR_CASILLA    = _RC.PULSOS_CASILLA_M1
    m.PULSOS_POR_CASILLA_M1 = _RC.PULSOS_CASILLA_M1
    m.PULSOS_POR_CASILLA_M2 = _RC.PULSOS_CASILLA_M2
    m.PULSOS_GIRO_90        = _RC.PULSOS_GIRO_90_M1
    m.PULSOS_GIRO_90_M1     = _RC.PULSOS_GIRO_90_M1
    m.PULSOS_GIRO_90_M2     = _RC.PULSOS_GIRO_90_M2
    m.CPR_M1                = _RC.CPR_M1
    m.CPR_M2                = _RC.CPR_M2
    m.MM_PER_CNT_M1         = _RC.MM_PER_CNT_M1
    m.MM_PER_CNT_M2         = _RC.MM_PER_CNT_M2
    m.WHEEL_CIRCUM_MM       = _RC.WHEEL_CIRCUM_MM
    m.WHEEL_DIAMETER_MM     = _RC.WHEEL_DIAMETER_MM
    m.ROBOT_TRACK_MM        = _RC.ROBOT_TRACK_MM
    m.MS_PER_CELL           = _RC.MS_PER_CELL
    m.MS_PER_90             = _RC.MS_PER_90

_sync()