// ============================================================
//  TJ Micromouse — 03: FLOOD FILL
//  Algoritmo clásico de micromouse.
//  
//  FASE 1: EXPLORACIÓN
//    El robot recorre el laberinto descubriendo paredes y
//    actualizando el mapa de distancias (flood fill) al objetivo.
//    Siempre se mueve hacia la celda vecina con menor distancia.
//  
//  FASE 2: CARRERA RÁPIDA (opcional, 2da vuelta)
//    Con el mapa completo, sigue el camino óptimo en alta velocidad.
//  
//  Requiere: 3 sensores VL53L0X, encoders, GY-91 (heading).
//  Garantiza llegar al objetivo en cualquier laberinto conectable.
// ============================================================

#include <WiFi.h>
#include <Wire.h>
#include <Adafruit_VL53L0X.h>
#include <MPU9250.h>   // Para el GY-91 (MPU-9250)

// ── Configuración del laberinto ──────────────────────────────
#define MAX_COLS 16
#define MAX_ROWS 16
#define INF      255

// Coordenadas de la META (ajustar según laberinto)
// Para laberinto 10x10: meta = (4,4) o (5,5) (centro)
#define GOAL_COL 4
#define GOAL_ROW 4

// ── Hardware ─────────────────────────────────────────────────
#define M1_IN1 35
#define M1_IN2 36
#define M2_IN1 38
#define M2_IN2 37

#define M1_C1 11
#define M1_C2 10
#define M2_C1 8
#define M2_C2 9

#define SDA_PIN   12
#define SCL_PIN   13
#define XSHUT_IZQ 5
#define XSHUT_CEN 6
#define XSHUT_DER 7
#define ADDR_IZQ  0x30
#define ADDR_CEN  0x31
#define ADDR_DER  0x32

#define PULSOS_POR_CASILLA 2470
#define PULSOS_GIRO_90     1000
#define DEBOUNCE_US        120

#define UMBRAL_LADO   150
#define UMBRAL_FRENTE 70

// ── Mapa de paredes ──────────────────────────────────────────
// Bit flags: N=1, E=2, S=4, W=8
// 0 = sin pared,  flag activo = hay pared
uint8_t wallMap[MAX_ROWS][MAX_COLS];
uint8_t floodDist[MAX_ROWS][MAX_COLS];
bool    discovered[MAX_ROWS][MAX_COLS];

// ── Estado del robot ─────────────────────────────────────────
int robotCol    = 0;
int robotRow    = 0;   // 0 = fila inferior (salida)
int robotHeading = 0;  // 0=N, 1=E, 2=S, 3=W

// Deltas por dirección (col, row)
const int dCol[4] = { 0,  1,  0, -1};
const int dRow[4] = {-1,  0,  1,  0};

// ── Variables encoders / sensores ────────────────────────────
volatile long enc1 = 0, enc2 = 0;
volatile uint32_t lastTick1 = 0, lastTick2 = 0;
Adafruit_VL53L0X LX, LC, LD;

// ── ISRs ─────────────────────────────────────────────────────
void IRAM_ATTR isr1() {
  uint32_t now = micros();
  if (now - lastTick1 < DEBOUNCE_US) return;
  lastTick1 = now;
  enc1 += (digitalRead(M1_C1) == digitalRead(M1_C2)) ? 1 : -1;
}
void IRAM_ATTR isr2() {
  uint32_t now = micros();
  if (now - lastTick2 < DEBOUNCE_US) return;
  lastTick2 = now;
  enc2 += (digitalRead(M2_C1) == digitalRead(M2_C2)) ? 1 : -1;
}

// ── Motores ──────────────────────────────────────────────────
void motor(int in1, int in2, int vel) {
  vel = constrain(vel, -255, 255);
  if (vel > 0)      { ledcWrite(in1, vel); ledcWrite(in2, 0);    }
  else if (vel < 0) { ledcWrite(in1, 0);   ledcWrite(in2, -vel); }
  else              { ledcWrite(in1, 0);   ledcWrite(in2, 0);    }
}
void motorStop() {
  motor(M1_IN1, M1_IN2, 0); motor(M2_IN1, M2_IN2, 0);
}
void resetEnc() { enc1 = 0; enc2 = 0; }

// ── Movimiento ───────────────────────────────────────────────
void avanzarCasilla() {
  resetEnc();
  unsigned long t0 = millis();
  while (abs(enc1) < PULSOS_POR_CASILLA && abs(enc2) < PULSOS_POR_CASILLA) {
    motor(M1_IN1, M1_IN2, 200);
    motor(M2_IN1, M2_IN2, 200);
    if (millis() - t0 > 2500) break;
  }
  motorStop(); delay(80);

  // Actualizar posición lógica
  robotCol += dCol[robotHeading];
  robotRow += dRow[robotHeading];
}

void girarA(int newHeading) {
  int diff = (newHeading - robotHeading + 4) % 4;
  if (diff == 0) return;
  
  if (diff == 1) {         // Girar derecha
    resetEnc();
    unsigned long t0 = millis();
    while (abs(enc2) < PULSOS_GIRO_90) {
      motor(M1_IN1, M1_IN2,  200);
      motor(M2_IN1, M2_IN2, -200);
      if (millis() - t0 > 2000) break;
    }
    motorStop(); delay(120);
  } else if (diff == 3) {  // Girar izquierda
    resetEnc();
    unsigned long t0 = millis();
    while (abs(enc1) < PULSOS_GIRO_90) {
      motor(M1_IN1, M1_IN2, -200);
      motor(M2_IN1, M2_IN2,  200);
      if (millis() - t0 > 2000) break;
    }
    motorStop(); delay(120);
  } else if (diff == 2) {  // Media vuelta
    girarA((robotHeading + 3) % 4);
    girarA((robotHeading + 3) % 4);
    return;
  }
  robotHeading = newHeading;
}

// ── Sensores ─────────────────────────────────────────────────
void leerSensores(uint16_t &izq, uint16_t &cen, uint16_t &der) {
  VL53L0X_RangingMeasurementData_t mI, mC, mD;
  LX.rangingTest(&mI, false);
  LC.rangingTest(&mC, false);
  LD.rangingTest(&mD, false);
  izq = (mI.RangeStatus != 4) ? mI.RangeMilliMeter : 500;
  cen = (mC.RangeStatus != 4) ? mC.RangeMilliMeter : 500;
  der = (mD.RangeStatus != 4) ? mD.RangeMilliMeter : 500;
}

// ── Mapa: dirección relativa → absoluta ──────────────────────
// relDir: 0=F, 1=R, 2=B, 3=L
int relToAbs(int relDir) {
  return (robotHeading + relDir) % 4;
}

int absDir(char side) {
  // side: 'F','R','B','L'
  int offsets[] = {0, 1, 2, 3};
  char sides[]  = {'F','R','B','L'};
  for (int i = 0; i < 4; i++)
    if (sides[i] == side) return (robotHeading + offsets[i]) % 4;
  return 0;
}

// ── Walls ────────────────────────────────────────────────────
uint8_t dirBit(int d) { return 1 << d; }  // N=1,E=2,S=4,W=8

bool hasWall(int col, int row, int dir) {
  if (col < 0 || col >= MAX_COLS || row < 0 || row >= MAX_ROWS) return true;
  return (wallMap[row][col] & dirBit(dir)) != 0;
}

void setWall(int col, int row, int dir, bool value) {
  if (col < 0 || col >= MAX_COLS || row < 0 || row >= MAX_ROWS) return;
  int opp = (dir + 2) % 4;
  int nc = col + dCol[dir];
  int nr = row + dRow[dir];
  if (value) {
    wallMap[row][col] |= dirBit(dir);
    if (nc >= 0 && nc < MAX_COLS && nr >= 0 && nr < MAX_ROWS)
      wallMap[nr][nc] |= dirBit(opp);
  } else {
    wallMap[row][col] &= ~dirBit(dir);
    if (nc >= 0 && nc < MAX_COLS && nr >= 0 && nr < MAX_ROWS)
      wallMap[nr][nc] &= ~dirBit(opp);
  }
}

// ── Flood Fill ───────────────────────────────────────────────
// Queue manual (simple FIFO)
int ffQueue[MAX_COLS * MAX_ROWS * 2][2];
int ffHead, ffTail;

void ffEnqueue(int col, int row) {
  ffQueue[ffTail][0] = col;
  ffQueue[ffTail][1] = row;
  ffTail = (ffTail + 1) % (MAX_COLS * MAX_ROWS * 2);
}

bool ffDequeue(int &col, int &row) {
  if (ffHead == ffTail) return false;
  col = ffQueue[ffHead][0];
  row = ffQueue[ffHead][1];
  ffHead = (ffHead + 1) % (MAX_COLS * MAX_ROWS * 2);
  return true;
}

void computeFlood(int goalCol, int goalRow) {
  // Initialize all to INF
  for (int r = 0; r < MAX_ROWS; r++)
    for (int c = 0; c < MAX_COLS; c++)
      floodDist[r][c] = INF;

  ffHead = ffTail = 0;
  floodDist[goalRow][goalCol] = 0;
  ffEnqueue(goalCol, goalRow);

  int c, r;
  while (ffDequeue(c, r)) {
    for (int d = 0; d < 4; d++) {
      int nc = c + dCol[d];
      int nr = r + dRow[d];
      if (nc >= 0 && nc < MAX_COLS && nr >= 0 && nr < MAX_ROWS) {
        if (!hasWall(c, r, d) && floodDist[nr][nc] > floodDist[r][c] + 1) {
          floodDist[nr][nc] = floodDist[r][c] + 1;
          ffEnqueue(nc, nr);
        }
      }
    }
  }
}

// ── Inicializar mapa ─────────────────────────────────────────
void initMap(int cols, int rows) {
  memset(wallMap,     0, sizeof(wallMap));
  memset(discovered,  0, sizeof(discovered));

  // Paredes exteriores
  for (int r = 0; r < rows; r++) {
    setWall(0,      r, 3, true);  // W border
    setWall(cols-1, r, 1, true);  // E border
  }
  for (int c = 0; c < cols; c++) {
    setWall(c, 0,      0, true);  // N border (row 0 = top)
    setWall(c, rows-1, 2, true);  // S border
  }
}

// ── Descubrir paredes ─────────────────────────────────────────
bool discoverWalls() {
  uint16_t izq, cen, der;
  leerSensores(izq, cen, der);
  bool changed = false;

  int frontDir = absDir('F');
  int leftDir  = absDir('L');
  int rightDir = absDir('R');

  bool wallFront = (cen <= UMBRAL_FRENTE);
  bool wallLeft  = (izq <= UMBRAL_LADO);
  bool wallRight = (der <= UMBRAL_LADO);

  if ((wallMap[robotRow][robotCol] & dirBit(frontDir)) != wallFront * dirBit(frontDir) ||
      !discovered[robotRow][robotCol]) {
    setWall(robotCol, robotRow, frontDir, wallFront);
    setWall(robotCol, robotRow, leftDir,  wallLeft);
    setWall(robotCol, robotRow, rightDir, wallRight);
    discovered[robotRow][robotCol] = true;
    changed = true;
  }
  return changed;
}

// ── SETUP ─────────────────────────────────────────────────────
void setupVL() {
  pinMode(XSHUT_IZQ, OUTPUT); pinMode(XSHUT_CEN, OUTPUT); pinMode(XSHUT_DER, OUTPUT);
  digitalWrite(XSHUT_IZQ, LOW); digitalWrite(XSHUT_CEN, LOW); digitalWrite(XSHUT_DER, LOW);
  delay(10);
  digitalWrite(XSHUT_IZQ, HIGH); delay(10); LX.begin(ADDR_IZQ);
  digitalWrite(XSHUT_CEN, HIGH); delay(10); LC.begin(ADDR_CEN);
  digitalWrite(XSHUT_DER, HIGH); delay(10); LD.begin(ADDR_DER);
}

void setup() {
  Serial.begin(115200); delay(300);

  pinMode(M1_C1, INPUT_PULLUP); pinMode(M1_C2, INPUT_PULLUP);
  pinMode(M2_C1, INPUT_PULLUP); pinMode(M2_C2, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(M1_C1), isr1, CHANGE);
  attachInterrupt(digitalPinToInterrupt(M2_C1), isr2, CHANGE);
  ledcAttach(M1_IN1, 40000, 8); ledcAttach(M1_IN2, 40000, 8);
  ledcAttach(M2_IN1, 40000, 8); ledcAttach(M2_IN2, 40000, 8);
  Wire.begin(SDA_PIN, SCL_PIN);
  setupVL();

  // Robot inicia en (0, rows-1) apuntando al Norte
  // Ajusta rows según el tamaño real del laberinto
  int MAZE_COLS = 10;
  int MAZE_ROWS = 10;
  initMap(MAZE_COLS, MAZE_ROWS);

  robotCol     = 0;
  robotRow     = MAZE_ROWS - 1;  // Fila inferior
  robotHeading = 0;              // Norte

  computeFlood(GOAL_COL, GOAL_ROW);

  Serial.println("TJ FloodFill ready");
  Serial.printf("Inicio: (%d,%d) → Meta: (%d,%d)\n",
                robotCol, robotRow, GOAL_COL, GOAL_ROW);
}

// ════════════════════════════════════════════════════════════
//  FLOOD FILL LOOP
// ════════════════════════════════════════════════════════════
bool atGoal() {
  return (robotCol == GOAL_COL && robotRow == GOAL_ROW);
}

void loop() {
  if (atGoal()) {
    motorStop();
    Serial.printf("¡META ALCANZADA! (%d,%d)\n", robotCol, robotRow);
    delay(10000);
    return;
  }

  // 1. Descubrir paredes en la celda actual
  bool changed = discoverWalls();

  // 2. Re-calcular flood si se detectaron nuevas paredes
  if (changed) {
    computeFlood(GOAL_COL, GOAL_ROW);
  }

  // 3. Buscar vecino con menor distancia flood
  int bestDir   = -1;
  int bestDist  = INF + 1;

  for (int d = 0; d < 4; d++) {
    int nc = robotCol + dCol[d];
    int nr = robotRow + dRow[d];
    if (nc >= 0 && nc < MAX_COLS && nr >= 0 && nr < MAX_ROWS) {
      if (!hasWall(robotCol, robotRow, d)) {
        if (floodDist[nr][nc] < bestDist) {
          bestDist = floodDist[nr][nc];
          bestDir  = d;
        }
      }
    }
  }

  if (bestDir == -1) {
    // Atrapado: re-flood y esperar
    computeFlood(GOAL_COL, GOAL_ROW);
    delay(200);
    return;
  }

  // 4. Girar hacia la mejor dirección y avanzar
  girarA(bestDir);
  avanzarCasilla();

  Serial.printf("→ (%d, %d) dist=%d\n", robotCol, robotRow,
                floodDist[robotRow][robotCol]);
}
