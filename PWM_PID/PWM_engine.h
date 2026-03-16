#ifndef PWM_ENGINE_H
#define PWM_ENGINE_H

#include <Arduino.h>

class PWMEngine
{
public:

    PWMEngine(uint8_t pin)
    {
        _pin = pin;

        _period = 1000;
        _duty = 0;
        _t_move = 0;

        _onTime = 0;
        _offTime = 1000;

        _outputState = false;
        _stateStart = 0;
    }

    void begin()
    {
        pinMode(_pin, OUTPUT);
        digitalWrite(_pin, LOW);

        _stateStart = millis();
    }

    void setPeriod(uint16_t period_ms)
    {
        _period = period_ms;
        computeTimes();
    }

    void setDuty(uint16_t duty_0_100)
    {
        if (duty_0_100 > 100)
            duty_0_100 = 100;

        _duty = duty_0_100;

        computeTimes();
    }

    void setMinMove(uint16_t move_ms)
    {
        _t_move = move_ms;
        computeTimes();
    }

    void update()
    {
        uint32_t now = millis();

        // 0 %
        if (_duty == 0)
        {
            digitalWrite(_pin, LOW);
            _outputState = false;
            return;
        }

        // 100 %
        if (_duty >= 100)
        {
            digitalWrite(_pin, HIGH);
            _outputState = true;
            return;
        }

        if (_outputState)
        {
            if (now - _stateStart >= _onTime)
            {
                digitalWrite(_pin, LOW);

                _outputState = false;
                _stateStart = now;
            }
        }
        else
        {
            if (now - _stateStart >= _offTime)
            {
                digitalWrite(_pin, HIGH);

                _outputState = true;
                _stateStart = now;
            }
        }
    }

    uint16_t getCurrentDuty()
    {
        return _duty;
    }

    uint8_t getOutputState()
    {
        return _outputState ? 1 : 0;
    }

private:

    uint8_t _pin;

    uint16_t _period;
    uint16_t _duty;
    uint16_t _t_move;

    uint32_t _onTime;
    uint32_t _offTime;

    uint32_t _stateStart;
    bool _outputState;

    void computeTimes()
    {
        if (_period == 0)
        {
            _onTime = 0;
            _offTime = 1000;
            return;
        }

        _onTime  = ((uint32_t)_period * _duty) / 100;
        _offTime = _period - _onTime;

        if (_onTime > 0 && _onTime < _t_move)
            _onTime = _t_move;

        if (_offTime > 0 && _offTime < _t_move)
            _offTime = _t_move;

        // reset cyklu
        _stateStart = millis();
    }
};

#endif