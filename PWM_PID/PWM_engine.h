#ifndef PWM_ENGINE_H
#define PWM_ENGINE_H

#include <Arduino.h>
#include <mbed.h>
#include <chrono>

class PWMEngine {
public:

  PWMEngine(uint8_t pin) : _pin(pin) {}

  void begin()
  {
    pinMode(_pin, OUTPUT);
    digitalWrite(_pin, LOW);

    _enabled = false;
    _stateOn = false;
    _reconfigurePending = false;

    recomputeTimes();
    _timeout.detach();
  }

  void setPeriod(uint32_t p)
  {
    if (p == 0) p = 1;

    core_util_critical_section_enter();

    if (period != p)
    {
      period = p;
      recomputeTimes();
      _reconfigurePending = true;
    }

    core_util_critical_section_exit();
  }

  void setDuty(uint8_t d)
  {
    if (d > 100) d = 100;

    core_util_critical_section_enter();

    if (duty != d)
    {
      duty = d;
      recomputeTimes();
      _reconfigurePending = true;
    }

    core_util_critical_section_exit();
  }

  void enable(bool en)
  {
    bool doStart = false;
    bool doStop  = false;

    core_util_critical_section_enter();

    if (_enabled != en)
    {
      _enabled = en;

      if (_enabled)
      {
        _reconfigurePending = true;
        doStart = true;
      }
      else
      {
        doStop = true;
      }
    }

    core_util_critical_section_exit();

    if (doStop)
      stopOutput();

    if (doStart)
      restartCycle();
  }

  void update()
  {
    bool needRestart = false;
    bool en = false;

    core_util_critical_section_enter();
    needRestart = _reconfigurePending;
    en = _enabled;
    if (needRestart) _reconfigurePending = false;
    core_util_critical_section_exit();

    if (en && needRestart)
      restartCycle();
  }

  uint32_t getTimeOn() const { return pwm_time_on; }
  uint32_t getTimeOff() const { return pwm_time_off; }

private:

  uint8_t _pin;

  volatile uint32_t period = 5000;
  volatile uint8_t  duty   = 0;

  volatile uint32_t pwm_time_on  = 0;
  volatile uint32_t pwm_time_off = 5000;

  volatile bool _enabled = false;
  volatile bool _stateOn = false;
  volatile bool _reconfigurePending = false;

  mbed::Timeout _timeout;

  void recomputeTimes()
  {
    pwm_time_on  = (period * duty) / 100;
    pwm_time_off = period - pwm_time_on;
  }

  void stopOutput()
  {
    _timeout.detach();

    core_util_critical_section_enter();
    _stateOn = false;
    core_util_critical_section_exit();

    digitalWrite(_pin, LOW);
  }

  void restartCycle()
  {
    _timeout.detach();

    core_util_critical_section_enter();
    bool en = _enabled;
    uint8_t d = duty;
    uint32_t ton = pwm_time_on;
    core_util_critical_section_exit();

    if (!en)
    {
      digitalWrite(_pin, LOW);
      core_util_critical_section_enter();
      _stateOn = false;
      core_util_critical_section_exit();
      return;
    }

    if (d == 0)
    {
      digitalWrite(_pin, LOW);
      core_util_critical_section_enter();
      _stateOn = false;
      core_util_critical_section_exit();
      return;
    }

    if (d >= 100)
    {
      digitalWrite(_pin, HIGH);
      core_util_critical_section_enter();
      _stateOn = true;
      core_util_critical_section_exit();
      return;
    }

    // štart vždy ON
    digitalWrite(_pin, HIGH);

    core_util_critical_section_enter();
    _stateOn = true;
    core_util_critical_section_exit();

    scheduleNext(ton);
  }

  void scheduleNext(uint32_t delay_ms)
  {
    if (delay_ms == 0) delay_ms = 1;

    _timeout.attach(
      mbed::callback(this, &PWMEngine::onTimeout),
      std::chrono::milliseconds(delay_ms)
    );
  }

  void onTimeout()
  {
    core_util_critical_section_enter();

    bool en = _enabled;
    bool currentState = _stateOn;
    uint32_t ton  = pwm_time_on;
    uint32_t toff = pwm_time_off;

    core_util_critical_section_exit();

    if (!en)
    {
      digitalWrite(_pin, LOW);

      core_util_critical_section_enter();
      _stateOn = false;
      core_util_critical_section_exit();
      return;
    }

    if (currentState)
    {
      digitalWrite(_pin, LOW);

      core_util_critical_section_enter();
      _stateOn = false;
      core_util_critical_section_exit();

      scheduleNext(toff);
    }
    else
    {
      digitalWrite(_pin, HIGH);

      core_util_critical_section_enter();
      _stateOn = true;
      core_util_critical_section_exit();

      scheduleNext(ton);
    }
  }
};

#endif