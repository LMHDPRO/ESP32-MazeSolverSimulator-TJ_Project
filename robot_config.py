# ============================================================
#  TJ Simulator — Configuracion fisica del robot
#  Edita aqui o usa el boton "Config Robot" en la UI
# ============================================================
import math as _math

# Motor GA12-N20 100RPM @ 6V, alimentado a ~4V
MOTOR_RPM_RATED    = 100.0
MOTOR_VOLT_RATED   = 6.0
MOTOR_VOLT_SUPPLY  = 4.0
MOTOR_GEAR_RATIO   = 30.0
MOTOR_PPR          = 7        # pulsos por rev del eje del motor (Hall)

# Rueda y robot
WHEEL_DIAMETER_MM  = 35.0
ROBOT_TRACK_MM     = 72.0     # distancia entre centros de ruedas
ROBOT_WIDTH_MM     = 90.0
ROBOT_LENGTH_MM    = 90.0
WHEEL_OFFSET_Y_MM  = 0.0      # offset longitudinal de las ruedas (+ = adelante del CG)
                               # Si Y>0: giros se hacen SOBRE un punto adelantado del centro
                               # Efecto: el robot se desplaza hacia atras al girar

# Casilla del laberinto
CELL_SIZE_MM       = 180.0

# Posicion de sensores (mm, relativo al centro del robot)
# Frontal: cuanto adelante del centro esta (+ = hacia frente)
SENSOR_FRONT_X_MM  = 40.0    # distancia hacia frente desde centro
SENSOR_FRONT_Y_MM  = 0.0     # offset lateral (0 = centrado)
# Laterales: mas adelante que las llantas para ver el pasillo
SENSOR_SIDE_X_MM   = 20.0    # offset hacia frente de las ruedas
SENSOR_SIDE_Y_MM   = 38.0    # distancia lateral desde el centro (mitad del track)

# PWM de cada modo (sobre 255)
PWM_EXPLORE = 170
PWM_FAST    = 215
PWM_GIRO    = 155

# ── Valores derivados (se recalculan con recompute()) ──────────
MOTOR_RPM_EFFECTIVE = MOTOR_RPM_RATED * (MOTOR_VOLT_SUPPLY / MOTOR_VOLT_RATED)
CPR_M1              = int(MOTOR_PPR * MOTOR_GEAR_RATIO * 4)
CPR_M2              = int(MOTOR_PPR * MOTOR_GEAR_RATIO * 2)
WHEEL_CIRCUM_MM     = _math.pi * WHEEL_DIAMETER_MM
MM_PER_CNT_M1       = WHEEL_CIRCUM_MM / CPR_M1
MM_PER_CNT_M2       = WHEEL_CIRCUM_MM / CPR_M2
PULSOS_CASILLA_M1   = int(CELL_SIZE_MM / MM_PER_CNT_M1)
PULSOS_CASILLA_M2   = int(CELL_SIZE_MM / MM_PER_CNT_M2)
PULSOS_GIRO_90_M1   = 0
PULSOS_GIRO_90_M2   = 0
MS_PER_CELL         = 0
MS_PER_90           = 0

PHYSICS_SPEEDS = {}
STEP_MS        = {}

def recompute():
    global MOTOR_RPM_EFFECTIVE, CPR_M1, CPR_M2, WHEEL_CIRCUM_MM
    global MM_PER_CNT_M1, MM_PER_CNT_M2
    global PULSOS_CASILLA_M1, PULSOS_CASILLA_M2
    global PULSOS_GIRO_90_M1, PULSOS_GIRO_90_M2
    global MS_PER_CELL, MS_PER_90
    global PHYSICS_SPEEDS, STEP_MS

    MOTOR_RPM_EFFECTIVE = MOTOR_RPM_RATED * (MOTOR_VOLT_SUPPLY / MOTOR_VOLT_RATED)
    CPR_M1 = int(MOTOR_PPR * MOTOR_GEAR_RATIO * 4)
    CPR_M2 = int(MOTOR_PPR * MOTOR_GEAR_RATIO * 2)
    WHEEL_CIRCUM_MM = _math.pi * WHEEL_DIAMETER_MM

    MM_PER_CNT_M1 = WHEEL_CIRCUM_MM / CPR_M1
    MM_PER_CNT_M2 = WHEEL_CIRCUM_MM / CPR_M2
    PULSOS_CASILLA_M1 = int(CELL_SIZE_MM / MM_PER_CNT_M1)
    PULSOS_CASILLA_M2 = int(CELL_SIZE_MM / MM_PER_CNT_M2)

    arc = _math.pi * ROBOT_TRACK_MM / 2
    PULSOS_GIRO_90_M1 = int(arc / MM_PER_CNT_M1)
    PULSOS_GIRO_90_M2 = int(arc / MM_PER_CNT_M2)

    # Velocidad maxima del motor en mm/s
    max_mm_s = MOTOR_RPM_EFFECTIVE * WHEEL_CIRCUM_MM / 60.0

    def cells_s(pwm_frac, mult):
        return (max_mm_s * pwm_frac / CELL_SIZE_MM) * mult

    def rot_ds(pwm_frac, mult):
        arc_mm = _math.pi * ROBOT_TRACK_MM / 2
        t_s = arc_mm / (max_mm_s * pwm_frac)
        return (90.0 / t_s) * mult

    # Multiplicadores visuales:
    #   Lento  = 0.85x real  (mas lento que el robot, se ven bien los giros)
    #   Normal = 1.0x real   (velocidad 1:1 con motor fisico)
    #   Rapido = 3x real
    #   Turbo  = 40x
    pf_exp  = PWM_EXPLORE / 255.0
    pf_fast = PWM_FAST    / 255.0
    pf_slow = 0.50

    PHYSICS_SPEEDS = {
        "Lento":  {'move': round(cells_s(pf_slow, 0.85), 3),
                   'rot':  round(rot_ds(pf_slow, 0.85), 1)},
        "Normal": {'move': round(cells_s(pf_exp,  1.00), 3),
                   'rot':  round(rot_ds(pf_exp,  1.00), 1)},
        "Rapido": {'move': round(cells_s(pf_fast, 3.00), 3),
                   'rot':  round(rot_ds(pf_fast, 3.00), 1)},
        "Turbo":  {'move': round(cells_s(1.0,    40.00), 3),
                   'rot':  round(rot_ds(1.0,    40.00), 1)},
    }

    # Step timer: sincronizado con la animacion (anim debe terminar antes del siguiente paso)
    # step_ms = 1000 / (move_speed_cells_s) * 0.92  (8% de margen)
    STEP_MS = {}
    for name, spd in PHYSICS_SPEEDS.items():
        STEP_MS[name] = max(5, int(1000.0 / spd['move'] * 0.92))

    # Tiempo real del robot fisico (a PWM_EXPLORE)
    mm_s_exp  = max_mm_s * pf_exp
    mm_s_giro = max_mm_s * (PWM_GIRO / 255.0)
    MS_PER_CELL = int(CELL_SIZE_MM / mm_s_exp * 1000)
    MS_PER_90   = int((_math.pi * ROBOT_TRACK_MM / 2) / mm_s_giro * 1000)

# Inicializar al importar
recompute()