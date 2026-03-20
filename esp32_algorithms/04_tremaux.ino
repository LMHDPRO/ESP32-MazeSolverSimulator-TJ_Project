// ============================================================
//  TJ Micromouse — 04: ALGORITMO DE TRÉMAUX
//  (Inventado por Charles Pierre Trémaux, ~1882)
//
//  CÓMO FUNCIONA:
//    Marca cada pasillo que recorre con 1 o 2 marcas.
//    Reglas:
//      - Nunca cruza un pasillo con 2 marcas.
//      - Entra a pasillos con 0 marcas si existen.
//      - Si todos los pasillos tienen marca, retrocede
//        (sigue el pasillo por el que entró).
//  
//  VENTAJAS:
//    - No necesita mapa previo del laberinto.
//    - Garantizado para encontrar la salida.
//    - Funciona con solo 3 sensores de distancia.
//
//  LIMITACIONES:
//    - No encuentra el camino óptimo (solo garantiza llegar).
//    - Más lento que flood fill con mapa completo.
// ============================================================

#include <WiFi.h>
#include <Wire.h>
#include <Adafruit_VL53L0X.h>

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

#define MAX_COLS 16
#define MAX_ROWS 16

// ── Variables globales ───────────────────────────────────────
volatile long enc1 = 0, enc2 = 0;
volatile uint32_t lastTick1 = 0, lastTick2 = 0;
Adafruit_VL53L0X LX, LC, LD;

// Marcas de Trémaux: marks[row][col][dir] = 0, 1, o 2
uint8_t marks[MAX_ROWS][MAX_COLS][4];

int robotCol     = 0;
int robotRow     = 9;  // Ajustar según laberinto
int robotHeading = 0;  // 0=N, 1=E, 2=S, 3=W
int prevDir      = -1; // Dirección de la que venimos

// Coordenadas meta
#define GOAL_COL 4
#define GOAL_ROW 4

const int dCol[4] = { 0,  1,  0, -1};
const int dRow[4] = {-1,  0,  1,  0};

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
  robotCol += dCol[robotHeading];
  robotRow += dRow[robotHeading];
}

void girarA(int newHeading) {
  int diff = (newHeading - robotHeading + 4) % 4;
  if (diff == 0) return;
  resetEnc();
  unsigned long t0 = millis();
  if (diff == 1) {
    while (abs(enc2) < PULSOS_GIRO_90) {
      motor(M1_IN1, M1_IN2, 200); motor(M2_IN1, M2_IN2, -200);
      if (millis() - t0 > 2000) break;
    }
  } else if (diff == 3) {
    while (abs(enc1) < PULSOS_GIRO_90) {
      motor(M1_IN1, M1_IN2, -200); motor(M2_IN1, M2_IN2, 200);
      if (millis() - t0 > 2000) break;
    }
  } else {
    // 180°
    motorStop(); delay(60);
    girarA((robotHeading + 1) % 4);
    girarA((robotHeading + 1) % 4);
    return;
  }
  motorStop(); delay(120);
  robotHeading = newHeading;
}

// ── Sensores ─────────────────────────────────────────────────
void leerSensores(uint16_t &izq, uint16_t &cen, uint16_t &der) {
  VL53L0X_RangingMeasurementData_t mI, mC, mD;
  LX.rangingTest(&mI, false); LC.rangingTest(&mC, false); LD.rangingTest(&mD, false);
  izq = (mI.RangeStatus != 4) ? mI.RangeMilliMeter : 500;
  cen = (mC.RangeStatus != 4) ? mC.RangeMilliMeter : 500;
  der = (mD.RangeStatus != 4) ? mD.RangeMilliMeter : 500;
}

bool isWall(int sensor_val, bool isFront) {
  return sensor_val <= (isFront ? UMBRAL_FRENTE : UMBRAL_LADO);
}

// ── Helpers de dirección ─────────────────────────────────────
int relToAbs(int relOffset) { return (robotHeading + relOffset) % 4; }
int opposite(int d)         { return (d + 2) % 4; }
bool inBounds(int c, int r) {
  return c >= 0 && c < MAX_COLS && r >= 0 && r < MAX_ROWS;
}

// ── Marcas de Trémaux ────────────────────────────────────────
void addMark(int col, int row, int dir) {
  if (!inBounds(col, row)) return;
  if (marks[row][col][dir] < 2) marks[row][col][dir]++;
  int nc = col + dCol[dir];
  int nr = row + dRow[dir];
  int od = opposite(dir);
  if (inBounds(nc, nr) && marks[nr][nc][od] < 2) marks[nr][nc][od]++;
}

uint8_t getMark(int col, int row, int dir) {
  if (!inBounds(col, row)) return 2;
  return marks[row][col][dir];
}

// ── Setup ────────────────────────────────────────────────────
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
  memset(marks, 0, sizeof(marks));
  Serial.println("TJ Trémaux ready");
}

// ════════════════════════════════════════════════════════════
//  TRÉMAUX LOOP
// ════════════════════════════════════════════════════════════
void loop() {
  if (robotCol == GOAL_COL && robotRow == GOAL_ROW) {
    motorStop();
    Serial.println("¡META ALCANZADA con Trémaux!");
    delay(10000);
    return;
  }

  // Leer sensores
  uint16_t izq, cen, der;
  leerSensores(izq, cen, der);

  // Determinar qué pasillos están abiertos (no tienen pared)
  bool openDir[4];
  openDir[relToAbs(0)] = !isWall(cen, true);   // Frente
  openDir[relToAbs(3)] = !isWall(izq, false);  // Izquierda
  openDir[relToAbs(1)] = !isWall(der, false);  // Derecha
  // Atrás: asumimos abierto si venimos de ahí
  openDir[relToAbs(2)] = (prevDir != -1);

  // Buscar pasillos con 0 marcas (no visitados)
  int zeroMark[4];
  int zeroCount = 0;
  for (int d = 0; d < 4; d++) {
    if (openDir[d] && getMark(robotCol, robotRow, d) == 0) {
      zeroMark[zeroCount++] = d;
    }
  }

  int chosen = -1;

  if (zeroCount > 0) {
    // Preferir misma dirección si tiene 0 marcas
    bool sameDir = false;
    for (int i = 0; i < zeroCount; i++) {
      if (zeroMark[i] == prevDir) { chosen = prevDir; sameDir = true; break; }
    }
    if (!sameDir) chosen = zeroMark[0];
  } else {
    // Todos tienen marcas: retroceder (tomar pasillo con 1 marca)
    // Preferencia: el pasillo por el que venimos
    if (prevDir != -1 && openDir[opposite(prevDir)] &&
        getMark(robotCol, robotRow, opposite(prevDir)) < 2) {
      chosen = opposite(prevDir);
    } else {
      // Buscar cualquier pasillo con marca 1
      for (int d = 0; d < 4; d++) {
        if (openDir[d] && getMark(robotCol, robotRow, d) == 1) {
          chosen = d; break;
        }
      }
    }
    // Último recurso: pasillo con 2 marcas si no hay otro
    if (chosen == -1) {
      for (int d = 0; d < 4; d++) {
        if (openDir[d]) { chosen = d; break; }
      }
    }
  }

  if (chosen == -1) {
    // Sin salida (no debería pasar en laberinto bien formado)
    Serial.println("ERROR: Sin salida posible");
    delay(500);
    return;
  }

  // Añadir marca al pasillo elegido
  addMark(robotCol, robotRow, chosen);

  // Moverse
  girarA(chosen);
  prevDir = chosen;
  avanzarCasilla();

  Serial.printf("Trémaux → (%d,%d) dir=%d marca=%d\n",
                robotCol, robotRow, chosen,
                getMark(robotCol, robotRow, opposite(chosen)));
}
