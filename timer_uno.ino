// #include <Arduino.h>

const byte sensorPin = 2; // E18-D80NK ต่อเข้า Pin 2 (INT0)

// ตัวแปรเก็บจำนวนรอบการรีเซ็ต (Overflow) ของ Timer 1
volatile unsigned long timer1Overflows = 0;
volatile unsigned long startOverflows = 0;
volatile unsigned long endOverflows = 0;
volatile unsigned int startTicks = 0;
volatile unsigned int endTicks = 0;

enum SystemState { READY, RUNNING, FINISHED };
volatile SystemState currentState = READY;

// Debounce ป้องกันท้ายหุ่นยนต์ตัดเซนเซอร์ซ้ำซ้อน (ประมาณ 500ms)
const unsigned long DEBOUNCE_OVERFLOWS = 122; 

// ตัวแปรสำหรับคุมรอบการส่งข้อมูลทุกๆ 50ms (ใช้เก็บค่า Overflow ล่าสุดที่ส่ง)
unsigned long lastSendOverflows = 0;
const unsigned long SEND_INTERVAL_OVERFLOWS = 12; // ~50ms (16MHz / 65536 * 0.05s)

// ISR เมื่อ Timer 1 มีการล้น (Overflow ทุกๆ 65,536 Ticks)
ISR(TIMER1_OVF_vect) {
  timer1Overflows++;
}

// ISR เมื่อเซนเซอร์โดนบัง (FALLING Edge บน Pin 2)
void sensorInterrupt() {
  unsigned int currentTicks = TCNT1;      // อ่านค่าจาก Timer 1 ทันที
  unsigned long currentOverflows = timer1Overflows;

  // ตรวจสอบสถานะการทริกเกอร์ล้นในขณะนั้น (Handling TCNT1 Overflow Buffering)
  if ((TIFR1 & _BV(TOV1)) && (currentTicks < 1024)) {
    currentOverflows++;
  }

  if (currentState == READY) {
    // หุ่นยนต์เริ่มวิ่งออกตัว
    startTicks = currentTicks;
    startOverflows = currentOverflows;
    currentState = RUNNING;
  } 
  else if (currentState == RUNNING) {
    // ตรวจสอบ Debounce ป้องกันท้ายหุ่นยนต์บังเซนเซอร์ซ้ำซ้อน
    if ((currentOverflows - startOverflows) > DEBOUNCE_OVERFLOWS) {
      endTicks = currentTicks;
      endOverflows = currentOverflows;
      currentState = FINISHED;
    }
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(sensorPin, INPUT_PULLUP);

  // ตั้งค่า Hardware Timer 1 (16-bit)
  noInterrupts();
  TCCR1A = 0;             // โหมด Normal
  TCCR1B = 0;             // เคลียร์ค่าเดิม
  TCNT1 = 0;              // รีเซ็ตตัวนับเริ่มต้น
  TIMSK1 |= _BV(TOIE1);   // เปิดใช้งาน Timer 1 Overflow Interrupt
  TCCR1B |= _BV(CS10);    // เริ่มให้ Timer ทำงานด้วย Prescaler = 1 (16 MHz)
  interrupts();

  // เปิดใช้งาน External Interrupt ที่ Pin 2 (จับสัญญาณช่วงขาลง FALLING)
  attachInterrupt(digitalPinToInterrupt(sensorPin), sensorInterrupt, FALLING);
  
  Serial.println("STATUS:READY");
}

void loop() {
  // สถานะ RUNNING: ส่งค่าเวลาระหว่างทางออกไปทุกๆ 50ms
  if (currentState == RUNNING) {
    unsigned long currentOverflows = timer1Overflows;
    if (currentOverflows - lastSendOverflows >= SEND_INTERVAL_OVERFLOWS) {
      lastSendOverflows = currentOverflows;
      
      // คำนวณเวลา ณ ปัจจุบันเทียบกับจุดสตาร์ท
      unsigned long currentTicks = TCNT1;
      unsigned long totalStartTicks = (startOverflows * 65536UL) + startTicks;
      unsigned long totalCurrentTicks = (currentOverflows * 65536UL) + currentTicks;
      
      if (totalCurrentTicks >= totalStartTicks) {
        unsigned long elapsedTicks = totalCurrentTicks - totalStartTicks;
        double elapsedTimeSeconds = (double)elapsedTicks / 16000000.0;
        Serial.print("RUN:");
        Serial.println(elapsedTimeSeconds, 4); // ส่งทศนิยม 4 ตำแหน่งสำหรับเรียลไทม์
      }
    }
  }

  // สถานะ FINISHED: หุ่นเข้าเส้นชัย คำนวณเวลาที่แท้จริงระดับไมโครวินาที
  if (currentState == FINISHED) {
    detachInterrupt(digitalPinToInterrupt(sensorPin)); // ปิดอินเทอร์รัปต์ชั่วคราว

    unsigned long totalStartTicks = (startOverflows * 65536UL) + startTicks;
    unsigned long totalEndTicks = (endOverflows * 65536UL) + endTicks;
    unsigned long elapsedTicks = totalEndTicks - totalStartTicks;

    double elapsedTimeSeconds = (double)elapsedTicks / 16000000.0;

    // ส่งผลลัพธ์สุดท้ายที่แม่นยำที่สุด
    Serial.print("TIME:");
    Serial.println(elapsedTimeSeconds, 6); // ทศนิยม 6 ตำแหน่ง (ระดับไมโครวินาที)

    currentState = READY;
    delay(1000); // หน่วงเวลาให้หุ่นยนต์พ้นระยะเซนเซอร์ชัวร์ๆ
    
    // เคลียร์ระบบเพื่อรับหุ่นตัวถัดไป
    noInterrupts();
    timer1Overflows = 0;
    TCNT1 = 0;
    lastSendOverflows = 0;
    interrupts();
    attachInterrupt(digitalPinToInterrupt(sensorPin), sensorInterrupt, FALLING);
    
    Serial.println("STATUS:READY");
  }

  // รองรับคำสั่งคำสั่งเขียน RESET จากหน้าจอ PC
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    if (command == "RESET") {
      noInterrupts();
      currentState = READY;
      timer1Overflows = 0;
      TCNT1 = 0;
      lastSendOverflows = 0;
      interrupts();
      Serial.println("STATUS:READY");
    }
  }
}
