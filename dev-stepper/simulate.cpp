//
// Main program to simulate various stuff.
//

#include <iostream>

#include "lib/test/mock.hpp"
#include "lib/stepper.hpp"

using namespace std;

// Make a move pattern with stepper and print data in csv format for graphing.
void stepper_move_csv()
{
   // stepper s(0, 0, 0, 0, 0, 0,
   //           1, 700);
   // s.acceleration(2e4);
   // s.target_speed(1e4);
   // s.on();
   // s.target_pos(1500);

   stepper s(0, 0, 0, 0, 0, 0,
             1, 300);
   s.acceleration(400);
   s.target_speed(4000);
   s.on();
   s.target_pos(10000);

   cout << "time,pos,step,delay,micro,speed" << endl;
   
   uint32_t time = 0;
   uint32_t steps = 0;
   while (true) {
      s.step();
      uint32_t delay = s.delay();
      
      if (!delay) break;

      uint32_t micro = s.micro();
      steps++;
      float pos = float(s.pos()) / (1 << micro);

      time += delay;

      float velocity = 1e6/(delay << micro);

      cout << time/1e6 << "," << pos << "," << steps << "," << delay << "," << micro << "," << velocity << endl;
   }
}

int main()
{
   stepper_move_csv();
}
