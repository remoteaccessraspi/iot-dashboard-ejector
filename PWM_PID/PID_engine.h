#ifndef PID_ENGINE_H
#define PID_ENGINE_H

class PIDEngine {

public:

  void begin(uint8_t openPin,uint8_t closePin)
  {
    pinOpen=openPin;
    pinClose=closePin;

    pinMode(pinOpen,OUTPUT);
    pinMode(pinClose,OUTPUT);

    digitalWrite(pinOpen,LOW);
    digitalWrite(pinClose,LOW);

    state=INIT;
    timer=millis();
  }

  void setTiming(float full)
  {
    T_full=full;
    speed=100.0/T_full;
  }

  float computeFeedForward(float Tset,float Thot,float Tcold)
  {
    float denom=Thot-Tcold;

    if(denom<0.1) return 50;

    float r=(Tset-Tcold)/denom;

    if(r>1) r=1;
    if(r<0) r=0;

    return r*100;
  }

  void update(float target)
  {
    uint32_t now=millis();
    float dt=(now-last)/1000.0;
    last=now;

    if(state==INIT)
    {
      digitalWrite(pinOpen,LOW);
      digitalWrite(pinClose,HIGH);

      if(now-timer > T_full*1000)
      {
        digitalWrite(pinClose,LOW);
        position=0;
        state=RUN;
      }

      return;
    }

    float error=target-position;

    if(error>1)
    {
      digitalWrite(pinOpen,HIGH);
      digitalWrite(pinClose,LOW);
      position+=speed*dt;
    }
    else if(error<-1)
    {
      digitalWrite(pinOpen,LOW);
      digitalWrite(pinClose,HIGH);
      position-=speed*dt;
    }
    else
    {
      digitalWrite(pinOpen,LOW);
      digitalWrite(pinClose,LOW);
    }

    if(position>100) position=100;
    if(position<0) position=0;
  }

  uint16_t getPosition()
  {
    return position;
  }

private:

  enum State
  {
    INIT,
    RUN
  };

  State state;

  uint8_t pinOpen;
  uint8_t pinClose;

  float position=0;

  float T_full=120;
  float speed;

  uint32_t timer;
  uint32_t last=0;
};

#endif