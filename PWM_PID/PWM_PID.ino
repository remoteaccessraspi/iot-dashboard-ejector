/*
  OPTA – Modbus RTU Slave
  READ HOLDING REGISTERS + FRAME COUNTER
  + External PWM Engine
*/

#include <Arduino.h>
#include <ArduinoRS485.h>
#include <ArduinoModbus.h>
#include "PWM_engine.h"

#define SLAVE_ID 1

constexpr auto baudrate = 9600;
constexpr auto bitduration = 1.0f / baudrate;
constexpr auto wordlen = 10.0f;

// RS485 delay podľa Modbus RTU špecifikácie
constexpr auto preDelayBR  = bitduration * 9.6f * wordlen * 4.0f * 1e6;
constexpr auto postDelayBR = bitduration * 9.6f * wordlen * 3.0f * 1e6;

// =========================
// HOLDING REGISTERS
// =========================
#define REG_PWM_PERIOD   0
#define REG_PWM_DUTY     1
#define REG_T_SET        2
#define REG_T_FULL       3
#define REG_T_MOVE       4

// =========================
// INPUT REGISTERS
// =========================
#define REG_FEEDBACK       0
#define REG_CURRENT_DUTY   1
#define REG_ERROR          2
#define REG_OUTPUT_STATE   3
#define REG_STATUS_FLAGS   4

// =========================
// COILS
// =========================
#define COIL_ENABLE_PWM   0
#define COIL_ENABLE_PID   1

// =========================
// Holding variables
// =========================
uint16_t pwm_period = 5000;
uint16_t pwm_duty   = 0;
uint16_t t_set      = 0;
uint16_t t_full     = 0;
uint16_t t_move     = 0;

// =========================
// Input variables
// =========================
int16_t  feedback_value = 250;
uint16_t current_duty   = 0;
int16_t  error_value    = 0;
uint16_t output_state   = 0;
uint16_t status_flags   = 0;

uint32_t frame_counter = 0;

// =========================
// Last values
// =========================
uint16_t last_pwm_period = 0;
uint16_t last_pwm_duty   = 0;
uint16_t last_t_move     = 0;
bool     last_enable_pwm = false;

// =========================
// PWM ENGINE
// =========================
PWMEngine pwm(D0);

// =========================
// DEBUG
// =========================
void printHoldingFrame() {

  Serial.println("\n==============================");
  Serial.print("Frame #: "); Serial.println(frame_counter);
  Serial.print("PWM Period (ms): "); Serial.println(pwm_period);
  Serial.print("PWM Duty (%): "); Serial.println(pwm_duty);
  Serial.print("T_set (x10): "); Serial.println(t_set);
  Serial.print("T_full: "); Serial.println(t_full);
  Serial.print("T_move: "); Serial.println(t_move);
  Serial.println("==============================");
}

// =========================
// SETUP
// =========================
void setup() {

  Serial.begin(115200);
  delay(300);

  RS485.setDelays(preDelayBR, postDelayBR);

  if (!ModbusRTUServer.begin(SLAVE_ID, baudrate, SERIAL_8N1)) {
    while (1);
  }

  ModbusRTUServer.configureHoldingRegisters(0x00, 8);
  ModbusRTUServer.configureInputRegisters(0x00, 8);
  ModbusRTUServer.configureCoils(0x00, 4);

  pwm.begin();

  Serial.println("OPTA Modbus Slave READY");
}

// =========================
// LOOP
// =========================
void loop() {

  // PWM vždy prvé → stabilný rytmus
  pwm.update();

  int requests = ModbusRTUServer.poll();

  if (requests > 0) {

    bool pwm_update = false;
    bool changed = false;

    uint16_t new_period = ModbusRTUServer.holdingRegisterRead(REG_PWM_PERIOD);
    if (new_period < 1000) new_period = 1000;

    uint16_t new_duty = ModbusRTUServer.holdingRegisterRead(REG_PWM_DUTY);
    if (new_duty > 100) new_duty = 100;

    uint16_t new_t_move = ModbusRTUServer.holdingRegisterRead(REG_T_MOVE);

    t_set  = ModbusRTUServer.holdingRegisterRead(REG_T_SET);
    t_full = ModbusRTUServer.holdingRegisterRead(REG_T_FULL);

    bool enable_pwm = ModbusRTUServer.coilRead(COIL_ENABLE_PWM);

    // PERIOD
    if (new_period != last_pwm_period) {

      pwm_period = new_period;
      pwm.setPeriod(pwm_period);

      last_pwm_period = new_period;

      pwm_update = true;
      changed = true;
    }

    // DUTY
    if (new_duty != last_pwm_duty) {

      pwm_duty = new_duty;
      last_pwm_duty = new_duty;

      pwm_update = true;
      changed = true;
    }

    // T_MOVE
    if (new_t_move != last_t_move) {

      t_move = new_t_move;
      pwm.setMinMove(t_move);

      last_t_move = new_t_move;

      pwm_update = true;
      changed = true;
    }

    // ENABLE
    if (enable_pwm != last_enable_pwm) {

      last_enable_pwm = enable_pwm;

      pwm_update = true;
      changed = true;
    }

    // APPLY PWM
    if (pwm_update) {

      uint16_t duty = enable_pwm ? pwm_duty : 0;
      pwm.setDuty(duty);
    }

    if (changed) {

      frame_counter++;
      printHoldingFrame();
    }
  }

  current_duty = pwm.getCurrentDuty();
  output_state = pwm.getOutputState();

  ModbusRTUServer.inputRegisterWrite(REG_FEEDBACK, feedback_value);
  ModbusRTUServer.inputRegisterWrite(REG_CURRENT_DUTY, current_duty);
  ModbusRTUServer.inputRegisterWrite(REG_ERROR, error_value);
  ModbusRTUServer.inputRegisterWrite(REG_OUTPUT_STATE, output_state);
  ModbusRTUServer.inputRegisterWrite(REG_STATUS_FLAGS, status_flags);
}