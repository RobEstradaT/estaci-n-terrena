/*
 * Generador de telemetría de PRUEBA para la estación terrena.
 *
 * NO es el firmware real del CanSat ni del receptor LoRa. Solo sirve para
 * comprobar el enlace ESP32 -> USB -> backend sin depender del resto del
 * hardware. Emite, con Serial.println, una trama por segundo en el formato
 * confirmado en docs/PROTOCOL.md:
 *
 *   pass,temperatura,co2,presion,altura,aceleracion,velocidad,rssi,snr
 *
 * - `pass`: en el receptor real es la cadena fija "571617"; aquí se usa el
 *   mismo valor para que el backend, que lo valida, acepte las tramas.
 * - Unidad de temperatura: PENDIENTE DE CONFIRMAR (aquí se envían valores
 *   que equivalen a grados Celsius).
 * - Los valores siguen un vuelo simulado (ascenso ~35 s hasta 1000 m,
 *   descenso a 6.5 m/s) y se repite al aterrizar.
 *
 * Uso: Arduino IDE -> placa "ESP32 Dev Module" -> subir -> cerrar el
 * Monitor Serie (si no, ocupa el puerto) -> ver docs/PRUEBA_SERIAL.md.
 */

// Debe coincidir con SERIAL_BAUDRATE del backend.
const unsigned long BAUDRATE = 115200;
const unsigned long INTERVAL_MS = 1000;

// Mismo valor que `String pass` del receptor real (y que FRAME_PASS del backend).
const char *PASS_VALUE = "571617";

// true: cada 10 tramas envía una corrupta, y cada 25 una con "nan" en la
// temperatura. Sirve para comprobar que el backend las descarta sin caerse.
const bool INJECT_BAD_FRAMES = false;

const unsigned long FLIGHT_LENGTH_S = 190;  // tras aterrizar, reinicia el vuelo

unsigned long lastSendMs = 0;
unsigned long t = 0;  // segundos simulados

float altitudeAt(float s) {
  if (s <= 35.0f) {
    float p = s / 35.0f;
    return 1000.0f * (3.0f * p * p - 2.0f * p * p * p);
  }
  float a = 1000.0f - 6.5f * (s - 35.0f);
  return a > 0.0f ? a : 0.0f;
}

void setup() {
  Serial.begin(BAUDRATE);
  delay(1000);
}

void loop() {
  unsigned long now = millis();
  if (now - lastSendMs < INTERVAL_MS) return;
  lastSendMs = now;

  t++;
  if (t > FLIGHT_LENGTH_S) t = 1;

  float alt = altitudeAt((float)t);
  float vel = alt - altitudeAt((float)(t - 1));      // m/s (dt = 1 s)
  float temp = 22.0f - 0.0065f * alt;
  float pres = 101.325f * expf(-alt / 8434.0f);      // kPa
  float co2 = 410.0f + (float)(t % 10);              // ppm
  float acc = 9.8f;                                  // m/s2
  float rssi = -40.0f - 55.0f * (alt / 1000.0f);     // dBm
  float snr = 12.0f - 15.0f * (alt / 1000.0f);       // dB

  if (INJECT_BAD_FRAMES && t % 25 == 0) temp = NAN;

  char msg2[128];
  snprintf(msg2, sizeof(msg2), "%s,%.2f,%.0f,%.2f,%.1f,%.1f,%.1f,%.0f,%.1f",
           PASS_VALUE, temp, co2, pres, alt, acc, vel, rssi, snr);

  if (INJECT_BAD_FRAMES && t % 10 == 0) {
    snprintf(msg2, sizeof(msg2), "%s,solo,tres,campos", PASS_VALUE);
  }

  Serial.println(msg2);
}
