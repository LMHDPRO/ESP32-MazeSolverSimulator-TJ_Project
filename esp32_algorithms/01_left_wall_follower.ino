// ============================================================
//  TJ Micromouse — 01: LEFT WALL FOLLOWER
//  Prioridad: izquierda → frente → derecha → 180°
//  Ideal cuando el objetivo está al fondo del laberinto
//  usando la convención de mano izquierda.
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

// Umbrales (mm)
#define UMBRAL_LADO   150
#define UMBRAL_FRENTE 70

// ── Variables globales ───────────────────────────────────────
volatile long enc1 = 0, enc2 = 0;
volatile uint32_t lastTick1 = 0, lastTick2 = 0;
Adafruit_VL53L0X LX, LC, LD;

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
void stop() { motor(M1_IN1, M1_IN2, 0); motor(M2_IN1, M2_IN2, 0); }
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
  stop(); delay(80);
}

void giroIzq90() {
  resetEnc();
  unsigned long t0 = millis();
  while (abs(enc1) < PULSOS_GIRO_90) {
    motor(M1_IN1, M1_IN2, -200);
    motor(M2_IN1, M2_IN2,  200);
    if (millis() - t0 > 2000) break;
  }
  stop(); delay(120);
}

void giroDer90() {
  resetEnc();
  unsigned long t0 = millis();
  while (abs(enc2) < PULSOS_GIRO_90) {
    motor(M1_IN1, M1_IN2,  200);
    motor(M2_IN1, M2_IN2, -200);
    if (millis() - t0 > 2000) break;
  }
  stop(); delay(120);
}

void giro180() { giroIzq90(); delay(60); giroIzq90(); }

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
}

// ════════════════════════════════════════════════════════════
//  LEFT WALL FOLLOWER LOOP
//  Prioridad: IZQ → FRENTE → DER → 180
// ════════════════════════════════════════════════════════════
void loop() {
  uint16_t L, C, R;
  leerSensores(L, C, R);

  bool izq_libre   = (L > UMBRAL_LADO);
  bool frente_libre = (C > UMBRAL_FRENTE);
  bool der_libre    = (R > UMBRAL_LADO);

  if (izq_libre) {
    // Pasillo a la izquierda: girar izq y avanzar
    giroIzq90();
    avanzarCasilla();
  } else if (frente_libre) {
    // Frente libre: avanzar
    avanzarCasilla();
  } else if (der_libre) {
    // Solo derecha: girar der y avanzar
    giroDer90();
    avanzarCasilla();
  } else {
    // Callejón sin salida: dar vuelta
    giro180();
    avanzarCasilla();
  }
}
