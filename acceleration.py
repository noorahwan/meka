#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import math
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

# Algorithm 0, velocity stopping distance formula:
#
# v = sqrt(2 * a * s)
#
# Algorithm 1, delay:
#
# d0 = sqrt(1/a) ???
# dn = d0(sqrt(n + 1) - sqrt(n))
#
# Algorithm 2, taylor approx delay:
#
# d0 = constant based on a
# dn = dn-1 * ( 1 - 2 / (4n + 1)) = dn-1 * (4n - 1) / (4n + 1)
# inverse is:
# dn-1 = dn * (4n + 1) / (4n - 1)


def plot(x, y, *dfs):
    """ Plot x and y axis of dfs in common graph. """
    ax = None
    for df in dfs:
        ax = df[[x, y]].set_index(x).plot(kind='line', ylim=(0, None), xlim=(0, None), ax=ax)

    
def accel_0(steps, a):
    
    df = pd.DataFrame(index=np.arange(0, steps), columns=('v', 's', 'd', 't'))

    v = 0.0
    t = 0.0
    
    df.loc[0] = [0, 0, 0, 0];
    for s in np.arange(1, steps):
        v = math.sqrt(2 * a * s)
        t = t + 1/v
        df.loc[s] = [v, s, 1/v, t]
    return df.dropna()

    
def accel_1(steps, a):
    # Har nån knasknäcki början

    df = pd.DataFrame(index=np.arange(0, steps), columns=('v', 's', 'd', 't'))
    
    t = 0.0
    d0 = d = math.sqrt(1/a)

    df.loc[0] = [0, 0, 0, 0];
    for s in np.arange(1, steps):
        t = t + d
        df.loc[s] = [1/d, s, d, t]
        d = d0 * (math.sqrt(s + 1) - math.sqrt(s))
    return df.dropna()


def accel_2(steps, a):

    df = pd.DataFrame(index=np.arange(0, steps), columns=('v', 's', 'd', 't'))
    
    t = 0.0
    d0 = d = math.sqrt(1/a)
    
    df.loc[0] = [0, 0, 0, 0];
    for s in np.arange(1, steps):
        t = t + d
        df.loc[s] = [1/d, s, d, t]
        if True or s < 500:
            d = d * (4 * s - 1) / (4 * s + 1)
        else:
            u = 1000 - s
            d = d * (4 * u + 1) / (4 * u -1 )
            if d < 0:
                break

    return df.dropna()


def accel_2_micro(steps, a):
    df = pd.DataFrame(index=np.arange(0, steps * 16), columns=('v', 's', 'd', 't'))

    t = 0.0
    d0 = d = math.sqrt(1/a)

    p = 0.0
    delta = 1.0
    s = 1
    for i in range(steps * 8):
        s += 1
        p += delta
        d -= d * 2 / (4 * s + 1)
        t += d
        df.loc[s] = [delta/d, p, d, t]
        if s == 10:
            delta /= 16
            s *= 16
            d /= 16

    return df.dropna()


class Stepper(object):
    """
    Stepper class to later convert to c++.
    
    * Can change target_pos at any time.
    
    * Will micro step below certain speed.
    
    * Updates to acceleration/dir will be done at full steps only.
    
    * All times are in us.

    * Target pos outisde max and min will be changed to a pos within max and min.

    * Max speed can be changed at any time (but decelration will take it's time).

    * Acceleration can only be changed when speed is 0.
    
    """

    def __init__(self, accel, max_speed, micro_delay):
        """
        All parameters are dependent on the motor, system etc.
        
        :param accel: acceleration in steps/s²
        :param max_speed: max speed in steps/s
        :param micro_delay: when going above this delay we will start micro stepping
        """
        
        # Absolute position (full steps)
        self.pos = 0

        # The position we want to move to.
        self.target_pos = 0
        
        # Steps used for acceleration, to know when we need to decelerate.
        self.accel_steps = 0

        # 1 or -1
        self.dir = 1

        # Delay 0 will only be used at 0 speed when changing
        # direction. Delay is calculated before actual delay.
        self.delay0 = self.delay = int(math.sqrt(1/accel) * 1e6)

        # This is essentialy max speed. Delay will be moved to nearest
        # point above this. We want delay to be predictable when decelerating.
        self.min_delay = int(1/max_speed * 1e6)

        # Delay can be shifted 16 bits for increased precision when top 16 bits no longer are needed. The number of
        # shifted bits will be stored here.
        self.shift = 0

        # Micro step count.
        self.micro_step = 0

        # Level of micro stepping right now.
        self.micro_level = 0

        # Above this delay, we will 2 micro step (if we reach it again we will 4 micro step etc..)
        self.micro_delay = micro_delay

    def step(self):
        """ Returns next delay based on speed and target pos. Algorithm now, delays later. """

        aligned = self.pos & (-1 << self.micro_level) == self.pos

        # Change micro stepping level, only changed micro step mode when aligned. TODO Verify that this does not
        # destroy precision shifted delay. But do that when algorithm is done.
        if aligned:
            while self.delay > self.micro_delay and self.micro_level < 5:
                self.micro_level += 1
                self.delay >>= 1
                self.min_delay >>= 1
                self.accel_steps <<=1
                self.pos <<= 1
                self.target_pos <<=1

            while self.delay < self.micro_delay >> 1 and  self.micro_level > 0:
                self.micro_level -= 1
                self.delay <<= 1
                self.min_delay <<= 1
                self.accel_steps >>= 1
                self.pos >>= 1
                self.target_pos >>= 1

            # Set mode here.

        # Shift/unshift delay for precision? Biggest delay change factor up is 1-2/(4+1) = 0.6 or down is 1+2/(4-1) =
        #  1.7 so a 1 bit margin on 16 bit shift should be safe, but then we have micro stepping changing delay too,
        # so we need 2 bit margin. Shift when delay < 1¹15 (because it is possible), unshift when delay > 1^31.

        # Disable shift while doing micro stepping.
        # if self.shift == 16 and (self.delay > 1<<30 or self.min_delay > 1<<30):
        #     # Shift to less precision.
        #     self.delay >>= self.shift
        #     self.min_delay >>= self.shift
        #     self.shift = 0
        #
        # if self.shift == 0 and (self.delay < 1<<14 and self.min_delay < 1<<14):
        #     # Shift to more precision.
        #     self.shift = 16
        #     self.delay <<= self.shift
        #     self.min_delay <<= self.shift

        distance = self.target_pos - self.pos

        # Handle stopped state.

        if aligned and self.accel_steps <= 1:
            # It is possible to stop now if we want to, no need to decelerate.

            if self.pos == self.target_pos:
                # We have arrived and can stop.
                self.accel_steps = 0
                self.delay = self.delay0 << self.shift  # This should work, it should not be possbile to get to
                                                        # accel_steps == 1 still shifted if delay0 does
                                                        # not fit in shifted.
                return 0

            if (self.dir > 0) == (distance < 0):
                # Change dir, allow some time for it.
                self.accel_steps = 0
                self.dir = -self.dir
                return self.min_delay >> self.shift

        # TODO Step here and calculate delay later to be able to include time consuming calculation in next delay.

        # Should we accelerate?

        # What if distance = 2 and we accel to a place where decel is
        # impossible? But we also need to be able move 1 step.
        if self.dir * distance > 0 and self.dir * distance > self.accel_steps and self.delay >= self.min_delay:
            if self.accel_steps == 0:
                delta = 0  # Set to delay0 here instead, but then we need to handle shifted state.
            else:
                delta = self.delay * 2 // (4 * self.accel_steps + 1)
            self.accel_steps += 1
            self.delay -= delta

        # Should we decelerate?

        # What if min_delay changed? How do we know that we need to
        # delerate no new max speed? last delay would do it.
        elif self.dir * distance <= self.accel_steps:
            if self.accel_steps == 0: raise Exception("bug")
            self.accel_steps -= 1
            self.delay += self.delay * 2 // (4 * self.accel_steps - 1)

        # Handle ongoing micro stepping (implement later).
        self.pos += self.dir

        # Return delay
        return max(self.delay, self.min_delay) >> self.shift

    # Accelerate
    #
    # dn+1 = dn ( 1 + 4 * s - 2) / (4 * s + 1)
    # dn+1 = dn ( 1 - 2 / (4 * s + 1))
    # dn+1 = dn - dn * 2 / (4 * s + 1))

    # Decelerate
    #
    # dn-1 = dn * (4n + 1) / (4n - 1)
    # dn-1 = dn * (4n - 1 + 2) / (4n - 1)
    # dn-1 = dn * 2 // (4n - 1)


def accel_2_integer(steps, a):

    stepper = Stepper(a, 1e4, 1000)
    stepper.target_pos = steps

    df = pd.DataFrame(index=np.arange(0, steps * 16), columns=('v', 's', 'd', 't', 'adj_d', 'micro'))

    t = 0
    s = 0
    while True:
        d = stepper.step()
        if d == 0:
            break

        m = 1 << stepper.micro_level
        df.loc[s] = [1e6/d/m, stepper.pos / m, d, t/1e6, d // m, m]
        t += d
        s += 1
    return df.dropna()

def move_a_bit(a):
    stepper = Stepper(a, 1e4, 1000)

    df = pd.DataFrame(index=np.arange(0, 1e4), columns=('v', 's', 'd', 't', 'p'))

    t = 0
    s = 0
    try:
        stepper.target_pos = 1500
        for i in range(200):
            d = stepper.step()
            # print(stepper.pos, stepper.target_pos, d)
            if d == 0:
                break
            df.loc[s] = [1e6/d, s, d/1e6, t/1e6, stepper.pos]
            t += d
            s += 1
        stepper.target_pos = 150
        for i in range(1500):
            d = stepper.step()
            # print(stepper.pos, stepper.target_pos, d)
            if d == 0:
                break
            df.loc[s] = [1e6/d, s, d/1e6, t/1e6, stepper.pos]
            t += d
            s += 1
    except:
        print("FAIL")
    return df.dropna()

a = 20000.0 # steps / s2
s = 1500
# df0 = accel_0(s, a)
# df1 = accel_1(s, a)
# df2 = accel_2(s, a)
dfi = accel_2_integer(s, a)
# dfu = accel_2_micro(s, a)
# dfm = move_a_bit(a)

# print("df0\n", df0.head())
print("dfi\n", dfi)
# print("dfu\n", dfu)
# print("dfm\n", dfm)

plot('t', 's', dfi)
plot('t', 'd', dfi)
plot('t', 'v', dfi)
plot('s', 'v', dfi)
plt.show()

# ax = df0[['t', 'd']].set_index('t').plot(kind='line', ylim=(0, None))
# df1[['t', 'd']].set_index('t').plot(kind='line', ylim=(0, None), ax=ax)
# df2[['t', 'd']].set_index('t').plot(kind='line', ylim=(0, None), ax=ax)
# df3[['t', 'd']].set_index('t').plot(kind='line', ylim=(0, None), ax=ax)
# plt.show()


# dft = df.set_index('t')
# dft.plot(kind='line', subplots=True, layout=(2, 3), figsize=(18, 4), ylim=(0, None))
# plt.show()
# 
# dfs = df.set_index('s')
# dfs.plot(kind='line', subplots=True, layout=(2, 3), figsize=(18, 4), ylim=(0, None))
# plt.show()

# Algo maste kunna prognostisera inbromsningar (target kan andras nar
# som helst), men jag tror man kan rakna fran speed faktiskt.
# Utfora decelaration pa samma satt som acceleration (alltid ligga pa samma kurva, ingen forandring vid max).
# Berakning vara tillrackligt snabb.
# Mikrostega.
# Bra kurva i start och slut.
    
