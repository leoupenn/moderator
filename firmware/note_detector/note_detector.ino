/*********************************************************
  Dual MPR121 + NeoPixel controller for Moderator (rhythm game).

  Input:  prints state each loop as "[0, 1, 0, ...]" (16 values, commas+spaces).
  Output: PC → device
            • Frame (recommended):  C  then  P phys r g b  (×8)  then  S
            • M-batch (optional):   M r0 g0 b0 ... r7 g7 b7
            • Legacy (one LED):     idx r g b   (see setLED; clears strip)

  Place Adafruit_MPR121.cpp and Adafruit_MPR121.h in this folder (or use Library Manager).
  Based on note_detector XIAO ESP32-C3 + MPR121 ×2 + NeoPixel strip.
**********************************************************/

#include <Wire.h>
#include <ctype.h>
#include <stdlib.h>
#include "Adafruit_MPR121.h"
#include <Adafruit_NeoPixel.h>

#define LED_PIN    3   // D1 on XIAO ESP32-C3 = GPIO3
// 8 feedback LEDs in one linear strip (data in at index 0). For a 19-LED layout with
// sparse mapping, use LED_COUNT 19 and LED_MAP {1,3,6,8,10,13,15,18}.
#define LED_COUNT  8

/*
 * Pixel color order on the wire (must match the strip IC):
 *   NEO_GRB + NEO_KHZ800 — Adafruit / many WS2812B (default below).
 *   NEO_RGB + NEO_KHZ800 — many generic “WS2812” strips; try this if red/green look
 *     wrong or you mostly see blue when the app sends red/green.
 * If LEDs flicker randomly, try NEO_KHZ400 instead of NEO_KHZ800.
 */
#ifndef MODERATOR_NEOPIXEL_TYPE
#define MODERATOR_NEOPIXEL_TYPE (NEO_GRB + NEO_KHZ800)
#endif

Adafruit_NeoPixel strip(LED_COUNT, LED_PIN, MODERATOR_NEOPIXEL_TYPE);

Adafruit_MPR121 cap1 = Adafruit_MPR121();
Adafruit_MPR121 cap2 = Adafruit_MPR121();

#define TOUCH_THRESHOLD 600
#define TOUCH_FRAMES    3
#define COOLDOWN_MS     500
#define SMOOTH_ALPHA    0.15

const uint8_t PAD_MAP[16] = {11,10,9,8,7,6,5,4,3,2,1,0,12,13,14,15};
// Feedback slot k (0..7) -> physical NeoPixel index (linear strip: 0..7 in order).
const uint8_t LED_MAP[8] = {0, 1, 2, 3, 4, 5, 6, 7};

unsigned long lastTouch[16]  = {0};
uint8_t       frameCount[16] = {0};
bool          state[16]      = {0};
float         smoothed[16]   = {0};

static String s_hostLine;

void setLED(int idx, uint8_t r, uint8_t g, uint8_t b);

static long parseLongAdv(const char*& p) {
  while (*p && isspace((unsigned char)*p)) p++;
  char* end = NULL;
  long v = strtol(p, &end, 10);
  if (end == p) return 0;
  p = end;
  return v;
}

/*
 * M line must contain exactly 24 integers after M (8 × RGB). If a newline arrives
 * early (split USB/UART packet), strtol would leave the pointer stuck and the old
 * loop still ran 8 iterations — LED 0 correct, LEDs 1–7 often all black. Reject
 * incomplete lines and do not update the strip.
 */
static bool parseMLine24(const String& line, long rgb[24]) {
  const char* p = line.c_str();
  if (tolower((unsigned char)*p) == 'm') {
    p++;
    while (*p && isspace((unsigned char)*p)) p++;
  }
  for (int i = 0; i < 24; i++) {
    if (!*p) return false;
    char* end = NULL;
    long v = strtol(p, &end, 10);
    if (end == p) return false;
    p = end;
    rgb[i] = v;
  }
  while (*p && isspace((unsigned char)*p)) p++;
  return *p == '\0';
}

/* Same code path for feedback indices 0..7 as for index 0 (LED_MAP[k]). */
static void setMappedFeedbackPixel(int feedbackIndex, long r, long g, long b) {
  if (feedbackIndex < 0 || feedbackIndex >= 8) return;
  r = constrain(r, 0, 255);
  g = constrain(g, 0, 255);
  b = constrain(b, 0, 255);
  strip.setPixelColor(LED_MAP[feedbackIndex], strip.Color((uint8_t)r, (uint8_t)g, (uint8_t)b));
}

static void applyMLine(const String& line) {
  long rgb[24];
  if (!parseMLine24(line, rgb)) {
    return;
  }
  strip.clear();
  for (int k = 0; k < 8; k++) {
    setMappedFeedbackPixel(k, rgb[k * 3 + 0], rgb[k * 3 + 1], rgb[k * 3 + 2]);
  }
  strip.show();
}

/* Set one physical pixel without clear/show — use C … P … S frame from host. */
static void applyPixelLine(const String& line) {
  const char* p = line.c_str();
  if (tolower((unsigned char)*p) == 'p') p++;
  while (*p && isspace((unsigned char)*p)) p++;
  long phys = parseLongAdv(p);
  long r = parseLongAdv(p);
  long g = parseLongAdv(p);
  long b = parseLongAdv(p);
  if (phys >= 0 && phys < LED_COUNT) {
    r = constrain(r, 0, 255);
    g = constrain(g, 0, 255);
    b = constrain(b, 0, 255);
    strip.setPixelColor((uint16_t)phys, strip.Color((uint8_t)r, (uint8_t)g, (uint8_t)b));
  }
}

static void applyLegacyLine(const String& line) {
  const char* p = line.c_str();
  long idxPix = parseLongAdv(p);
  long r = parseLongAdv(p);
  long g = parseLongAdv(p);
  long b = parseLongAdv(p);
  if (idxPix >= -1 && idxPix < 8) {
    setLED((int)idxPix, (uint8_t)constrain(r, 0, 255), (uint8_t)constrain(g, 0, 255),
           (uint8_t)constrain(b, 0, 255));
  }
}

void setup() {
  Serial.begin(115200);
#if defined(ARDUINO_ARCH_ESP32)
  Serial.setRxBufferSize(1024);
#endif
  while (!Serial) { delay(10); }

  pinMode(0, OUTPUT);
  digitalWrite(0, HIGH);

  Wire.begin(6, 7);

  Serial.println("Adafruit MPR121 Dual Sensor Test");

  if (!cap1.begin(0x5A)) {
    Serial.println("MPR121 #1 (0x5A) not found, check wiring?");
    while (1);
  }
  Serial.println("MPR121 #1 found!");
  cap1.setAutoconfig(true);

  if (!cap2.begin(0x5B)) {
    Serial.println("MPR121 #2 (0x5B) not found, check wiring?");
    while (1);
  }
  Serial.println("MPR121 #2 found!");
  cap2.setAutoconfig(true);

  Serial.println("Initialization complete.");

  strip.begin();
  strip.setBrightness(50);
  strip.show();
}

void setLED(int idx, uint8_t r, uint8_t g, uint8_t b) {
  strip.clear();
  if (idx >= 0 && idx < 8) {
    strip.setPixelColor(LED_MAP[idx], strip.Color(r, g, b));
  }
  strip.show();
}

void printState() {
  Serial.print("[");
  for (uint8_t i = 0; i < 16; i++) {
    Serial.print(state[i] ? 1 : 0);
    if (i < 15) Serial.print(", ");
  }
  Serial.println("]");
}

void readLEDCommand() {
  while (Serial.available()) {
    int c = Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      s_hostLine.trim();
      if (s_hostLine.length() > 0) {
        char h = s_hostLine.charAt(0);
        if (h == 'M' || h == 'm') {
          applyMLine(s_hostLine);
        } else if (s_hostLine == "C") {
          strip.clear();
        } else if (s_hostLine == "S") {
          strip.show();
        } else if (h == 'P' || h == 'p') {
          applyPixelLine(s_hostLine);
        } else {
          applyLegacyLine(s_hostLine);
        }
      }
      s_hostLine = "";
    } else {
      s_hostLine += (char)c;
      if (s_hostLine.length() > 192) s_hostLine = "";
    }
  }
}

void loop() {
  readLEDCommand();

  unsigned long now = millis();

  for (uint8_t i = 0; i < 16; i++) {
    uint8_t phys = PAD_MAP[i];
    int raw;
    if (phys < 12) raw = (int)cap1.filteredData(phys);
    else           raw = (int)cap2.filteredData(phys - 12);

    if (smoothed[i] == 0) smoothed[i] = raw;
    smoothed[i] = SMOOTH_ALPHA * raw + (1.0 - SMOOTH_ALPHA) * smoothed[i];
    int value = (int)smoothed[i];

    if (value < TOUCH_THRESHOLD) {
      if (!state[i] && (now - lastTouch[i] >= COOLDOWN_MS)) {
        frameCount[i]++;
        if (frameCount[i] >= TOUCH_FRAMES) {
          frameCount[i] = 0;
          state[i] = true;
          lastTouch[i] = now;
        }
      }
    } else {
      frameCount[i] = 0;
      if (state[i]) {
        state[i] = false;
      }
    }
  }

  printState();
  delay(10);
}
