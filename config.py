# ============================================================
#  TJ Simulator — Configuration
#  Motor: GA12-N20 100RPM 6V | Wheel ≈ 35mm
# ============================================================

SCREEN_W = 1368
SCREEN_H = 768
FPS = 60
TITLE = "TJ Simulator v2.0 — Micromouse"

PANEL_W   = 320
CONSOLE_H = 140
HEADER_H  = 44

C_BG         = (10,  10,  12 )
C_PANEL      = (20,  20,  24 )
C_CARD       = (30,  30,  36 )
C_BORDER     = (48,  48,  56 )
C_DIVIDER    = (38,  38,  44 )
C_RED        = (200, 20,  20 )
C_RED_H      = (230, 55,  55 )
C_RED_D      = (130, 10,  10 )
C_TEXT_H     = (225, 225, 230)
C_TEXT_M     = (155, 155, 165)
C_TEXT_L     = (80,  80,  92 )
C_GREEN      = (40,  185, 70 )
C_BLUE       = (50,  110, 215)
C_YELLOW     = (205, 180, 40 )
C_ORANGE     = (210, 120, 0  )
C_TEAL       = (0,   175, 155)
C_MAZE_BG    = (14,  14,  18 )
C_WALL       = (235, 235, 240)
C_FLOOR      = (20,  20,  25 )
C_VISITED    = (28,  28,  50 )
C_SOLUTION   = (18,  60,  32 )
C_START_CELL = (18,  30,  90 )
C_GOAL_CELL  = (20,  90,  35 )
C_ROBOT_BODY   = (55,  55,  65 )
C_ROBOT_ACCENT = (200, 20,  20 )
C_SENSOR_BEAM  = (255, 90,  0  )
C_FLOOD_LO   = (20,  40,  100)
C_FLOOD_HI   = (180, 20,  20 )

# ── Motor GA12-N20 100RPM @ 6V ───────────────────────────────
# Gear ratio ≈ 150:1  |  Hall sensor: 7 PPR (motor shaft)
# ISR CHANGE en canal A → 14 transiciones por rev motor
# Counts/wheel_rev = 14 × 150 = 2100
# Wheel diameter = 35mm → circumference = 109.96mm
# Counts/mm = 2100 / 109.96 ≈ 19.1
MOTOR_GEAR_RATIO    = 150       # relacion de engranaje
MOTOR_PPR           = 7         # pulsos por rev del motor
MOTOR_COUNTS_PER_REV = MOTOR_PPR * 2 * MOTOR_GEAR_RATIO  # 2100
WHEEL_DIAMETER_MM   = 35.0
WHEEL_CIRCUM_MM     = 3.14159 * WHEEL_DIAMETER_MM         # 109.96 mm
COUNTS_PER_MM       = MOTOR_COUNTS_PER_REV / WHEEL_CIRCUM_MM  # 19.1

# Laberinto: pasillo de 180mm
CELL_SIZE_MM        = 180
PULSOS_POR_CASILLA  = int(COUNTS_PER_MM * CELL_SIZE_MM)   # ≈ 3438
# Giro 90°: rueda recorre π*D_robot/4 (D_robot ≈ 80mm → 62.8mm de arco)
ROBOT_TRACK_MM      = 80        # distancia entre ruedas
PULSOS_GIRO_90      = int(COUNTS_PER_MM * 3.14159 * ROBOT_TRACK_MM / 4)  # ≈ 1199

# ── Sensores ─────────────────────────────────────────────────
WALL_SIDE_THRESHOLD  = 120    # mm
WALL_FRONT_THRESHOLD = 120    # mm
SENSOR_MAX_RANGE     = 350    # mm — rango maximo simulado

# VL53L0X noise model (basado en datasheet):
# sigma = max(8, 0.012 * distance_mm)
# Lectura caduca cada ~25ms (tiempo de medicion del sensor)
VL53_NOISE_BASE     = 8.0     # mm — ruido minimo 1-sigma
VL53_NOISE_FACTOR   = 0.012   # ruido relativo (1.2% de la distancia)
VL53_READ_TIME_MS   = 25      # ms por lectura (3 sensores en serie = 75ms)
VL53_OUTLIER_PROB   = 0.03    # probabilidad de lectura erronea

# GY-91 (MPU-9250):
# Gyro drift: ~0.1 deg/s en condiciones normales
# Mag noise: ~2 uT RMS
IMU_GYRO_DRIFT_DEG_S = 0.08   # deriva del giroscopio
IMU_MAG_NOISE_UT     = 2.0    # ruido del magnetometro

# ESP32 processing time simulation
ESP32_SENSOR_CYCLE_MS = 80    # tiempo total de ciclo sensor (ms)

# ── Speeds ───────────────────────────────────────────────────
SPEEDS = {
    "Lento":   900,
    "Normal":  300,
    "Rapido":  80,
    "Turbo":   8,
}

DEFAULT_SPEED = "Normal"
DEFAULT_COLS  = 10
DEFAULT_ROWS  = 10

# Start positions disponibles
START_POSITIONS = {
    "Inferior Izq (default)": "bottom_left",
    "Inferior Der":           "bottom_right",
    "Superior Izq":           "top_left",
    "Superior Der":           "top_right",
}