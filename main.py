import time
import board
import busio
import time, signal, sys, os, math
import numpy as np
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import requests

# Create the I2C bus
i2c = busio.I2C(board.SCL, board.SDA)
#print(i2c.scan(), board.SDA, board.SCL)

# Create the ADC object using the I2C bus
ads = ADS.ADS1115(i2c)

def calcResistance(voltage):
    return ((10000 * voltage) / (3.3 - voltage))

def calcTemp(resistance):
    return 1 / ( (math.log(resistance / 10000) / 3435) + (1 / (273.15+25)) ) - 273.15;

def GetSonde1():
    chan0 = AnalogIn(ads, ADS.P0)
    R0 = calcResistance(chan0.voltage)
    Temp0 = round(calcTemp(R0), 1)

    chan1 = AnalogIn(ads, ADS.P1)
    R1 = calcResistance(chan1.voltage)
    Temp1 = round(calcTemp(R1), 1)
    AvgTemp = (Temp0 + Temp1) / 2

    return {"haut": {"temp": Temp0, "resistance": round(R0)}, "bas": {"temp": Temp1, "resistance": round(R1)}, "moyenne": AvgTemp}

def GetSonde2():
    chan2 = AnalogIn(ads, ADS.P2)
    R2 = calcResistance(chan2.voltage)
    Temp2 = round(calcTemp(R2), 1)

    chan3 = AnalogIn(ads, ADS.P3)
    R3 = calcResistance(chan3.voltage)
    Temp3 = round(calcTemp(R3), 1)
    AvgTemp = (Temp2 + Temp3) / 2

    return {"haut": {"temp": Temp2, "resistance": round(R2)}, "bas": {"temp": Temp3, "resistance": round(R3)}, "moyenne": AvgTemp}


while True:
    sonde1 = GetSonde1()
    print("Sonde 1 - Haut", sonde1['haut']['temp'], sonde1['haut']['resistance'])
    print("Avg Temp Sonde 1: {}".format(round(sonde1['moyenne'],1)))
    print("Sonde 1 - Bas", sonde1['bas']['temp'], sonde1['bas']['resistance'])
    print("------------------------------------")
    time.sleep(1)

