#pragma once
#include <Arduino.h>

class PIDEngine
{
public:

  void begin(uint8_t pin_open, uint8_t pin_close)
  {
    _pin_open  = pin_open;
    _pin_close = pin_close;

    pinMode(_pin_open, OUTPUT);
    pinMode(_pin_close, OUTPUT);

    digitalWrite(_pin_open, LOW);
    digitalWrite(_pin_close, LOW);

    reset();

    Serial.println("PIDEngine v5 ready");
  }

  void begin() {}

  void reset()
  {
    _state = IDLE;
    _last_enable = false;
    _position = 0.0f;
    _moving = false;
    _direction = 0;
  }

  // ---------------- CONFIG ----------------

  void setTiming(uint16_t t_full_sec)
  {
    _t_full = max((uint16_t)1, t_full_sec);
  }

  void setMoveTime(uint16_t t_move_sec)
  {
    _t_move = max((uint16_t)1, t_move_sec);
  }

  void setDeadband(float db)
  {
    _deadband = db;
  }

  // ---------------- MAIN ----------------

  void process(float t_set, float t_mix, bool enable_pid)
  {
    uint32_t now = millis();

    updatePosition(now);

    // enable edge
    if (enable_pid && !_last_enable)
    {
      Serial.println("INIT_OPEN");

      _state = INIT_OPEN;
      openValve(now);

      _timer = now;
      _interval = _t_full * 1000UL;
    }

    _last_enable = enable_pid;

    if (!enable_pid)
    {
      stopValve(now);
      _state = IDLE;
      return;
    }

    if (now - _timer < _interval)
      return;

    _timer = now;

    float error = t_set - t_mix;

    switch (_state)
    {
      case INIT_OPEN:
      {
        stopValve(now);

        _position = 100.0f;

        _state = FAST;
        closeValve(now);

        _interval = max(1UL, (_t_move * 1000UL) / 10);
        break;
      }

      case FAST:
      {
        if (fabs(error) <= _deadband)
        {
          stopValve(now);
          _state = REGULATE;
          _interval = _t_move * 1000UL;
        }
        else
        {
          moveByError(error, now);
          _interval = max(1UL, (_t_move * 1000UL) / 10);
        }
        break;
      }

      case REGULATE:
      {
        if (fabs(error) <= _deadband)
        {
          stopValve(now);
          _interval = _t_move * 1000UL;
        }
        else
        {
          _state = FAST;
          moveByError(error, now);
          _interval = max(1UL, (_t_move * 1000UL) / 10);
        }
        break;
      }

      default:
        break;
    }

    // DEBUG
    if (now - _dbg_timer > 1000)
    {
      _dbg_timer = now;

    //  Serial.print("POS=");
    //  Serial.print(_position);
    //  Serial.print(" ERR=");
    //  Serial.println(error);
    }
  }

  uint16_t getPosition() const
  {
    return (uint16_t)_position;
  }

private:

  enum State
  {
    IDLE,
    INIT_OPEN,
    FAST,
    REGULATE
  };

  State _state = IDLE;

  uint8_t _pin_open;
  uint8_t _pin_close;

  uint32_t _timer = 0;
  uint32_t _interval = 0;

  uint16_t _t_full = 120;
  uint16_t _t_move = 10;

  float _deadband = 1.0f;
  bool _last_enable = false;

  float _position = 0.0f;

  uint32_t _move_start = 0;
  int _direction = 0;
  bool _moving = false;

  uint32_t _dbg_timer = 0;

  // ---------------- CORE ----------------

  void updatePosition(uint32_t now)
  {
    if (!_moving) return;

    uint32_t dt = now - _move_start;

    float delta = (dt / (float)(_t_full * 1000.0f)) * 100.0f;

    _position += delta * _direction;

    _position = constrain(_position, 0.0f, 100.0f);

    _move_start = now;
  }

  void moveByError(float error, uint32_t now)
  {
    if (error > 0)
      openValve(now);
    else
      closeValve(now);
  }

  // ---------------- VALVE ----------------

  void openValve(uint32_t now)
  {
    if (_moving && _direction == +1)
      return;

    stopValve(now);

    digitalWrite(_pin_open, HIGH);
    digitalWrite(_pin_close, LOW);

    startMove(+1, now);
  }

  void closeValve(uint32_t now)
  {
    if (_moving && _direction == -1)
      return;

    stopValve(now);

    digitalWrite(_pin_open, LOW);
    digitalWrite(_pin_close, HIGH);

    startMove(-1, now);
  }

  void stopValve(uint32_t now)
  {
    updatePosition(now);

    digitalWrite(_pin_open, LOW);
    digitalWrite(_pin_close, LOW);

    _moving = false;
  }

  void startMove(int dir, uint32_t now)
  {
    _move_start = now;
    _moving = true;
    _direction = dir;
  }
};