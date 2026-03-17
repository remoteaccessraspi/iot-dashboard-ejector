#ifndef PWM_ENGINE_H
#define PWM_ENGINE_H

class PWMEngine {

public:

  PWMEngine(uint8_t pin) : _pin(pin) {}

  void begin()
  {
    pinMode(_pin,OUTPUT);
    digitalWrite(_pin,LOW);
    cycle = millis();
  }

  void setPeriod(uint32_t p)
  {
    period = p;
  }

  void setDuty(uint8_t d)
  {
    if(d>100)d=100;
    duty = d;
  }

  void update()
  {
    uint32_t now = millis();

    if(now-cycle>=period)
      cycle = now;

    uint32_t ontime = period*duty/100;

    if(now-cycle < ontime)
      digitalWrite(_pin,HIGH);
    else
      digitalWrite(_pin,LOW);
  }

private:

  uint8_t _pin;
  uint32_t period=5000;
  uint8_t duty=0;
  uint32_t cycle=0;
};

#endif