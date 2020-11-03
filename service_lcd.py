import time
import board
import busio
import time, signal, sys, os, math
import numpy as np
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from terminaltables import SingleTable
import requests
import logging
from lib import SCR
from lib.display import *
from datetime import datetime
from lib.daemon import *
import smbus

# scr = SCR.SCR(dev = "/dev/ttySC0",data_mode = 1)
debug = False
logging.basicConfig(format='%(asctime)s %(message)s')
# Create the I2C bus

class LCD_DISPLAY(Daemon):
        def __init__(self):

            self.pidfile = "/tmp/daemon-lcd_python.pid"
            self.sysargv = sys.argv

            self.i2c = busio.I2C(board.SCL, board.SDA)
            self.ads = ADS.ADS1115(self.i2c)
            self.ResistanceValue = self.convert("10k")

            super().__init__(pidfile=self.pidfile, sysargv=self.sysargv)

        def run(self):
            while True:
                sonde1 = self.GetSonde1()
                sonde2 = self.GetSonde2()
                self.write_lcd(temp1=sonde1['moyenne'], temp2=sonde2['moyenne'])
                time.sleep(0.5)

                if datetime.now().hour > 22 or datetime.now().hour < 6:
                    self.set_lcd_light("lcd", 15)

                elif datetime.now().hour >= 6 or datetime.now().hour < 12:
                    self.set_lcd_light("lcd", 25)

                elif datetime.now().hour >= 12:
                    self.set_lcd_light("lcd", 35)

        def set_lcd_light(self, channel, value):
            bus = smbus.SMBus(1)

            data_now_channel1 = bus.read_byte_data(0x2C, 0x01)
            data_now_channel2 = bus.read_byte_data(0x2C, 0x03)

            if channel == "lcd" and data_now_channel1 != value:
                # bus1
                bus.write_i2c_block_data(0x2C, 0x01, [value])
                time.sleep(0.5)

            if channel == "fan" and data_now_channel2 != value:
                # bus2
                bus.write_i2c_block_data(0x2C, 0x03, [value])
                time.sleep(0.5)

        def convert(self, value):
            if value:
                # determine multiplier
                multiplier = 1
                if value.endswith('K') or value.endswith('k'):
                    multiplier = 1000
                    value = value[0:len(value)-1] # strip multiplier character
                elif value.endswith('M') or value.endswith('m'):
                    multiplier = 1000000
                    value = value[0:len(value)-1] # strip multiplier character

                # convert value to float, multiply, then convert the result to int
                return int(float(value) * multiplier)

            else:
                return 0

        def write_lcd(self, **kwargs):
            # lcd start
            lcd_device = lcd()
            # this command clears the display (captain obvious)
            #lcd_device.lcd_clear()
            lineTemperature = ""
            medium = (kwargs['temp2'] + kwargs['temp1']) / 2
            date = datetime.now().strftime('%d, %b %Y %H:%M')
            for key, value in kwargs.items():

                if key == "temp1":
                    lineTemperature += "{}C".format(round(value,1))

                if key == "temp2":
                    lineTemperature += "  <----   {}C".format(round(value,1))

            # now we can display some characters (text, line)
            lcd_device.lcd_display_string(" {}".format(date), 1)
            lcd_device.lcd_display_string(lineTemperature, 3)
            lcd_device.lcd_display_string("       {}C".format(round(medium,1)), 4)

        def calcResistance(self, voltage):
            return ((self.ResistanceValue * voltage) / (3.3 - voltage))

        def calcTemp(self, resistance):
            return 1 / ( (math.log(resistance / self.ResistanceValue) / 3435) + (1 / (273.15+25)) ) - 273.15;

        def GetSonde1(self):
            etalonne = 1.5
            chan0 = AnalogIn(self.ads, ADS.P0)
            R0 = self.calcResistance(chan0.voltage)
            Temp0 = round(self.calcTemp(R0), 1) + etalonne

            chan1 = AnalogIn(self.ads, ADS.P1)
            R1 = self.calcResistance(chan1.voltage)
            Temp1 = round(self.calcTemp(R1), 1) + etalonne
            AvgTemp = (Temp0 + Temp1) / 2

            return {"haut": {"temp": Temp0, "resistance": round(R0)}, "bas": {"temp": Temp1, "resistance": round(R1)}, "moyenne": AvgTemp}

        def GetSonde2(self):
            etalonne = 1.5
            chan2 = AnalogIn(self.ads, ADS.P3)
            R2 = self.calcResistance(chan2.voltage)
            Temp2 = round(self.calcTemp(R2), 1) + etalonne

            chan3 = AnalogIn(self.ads, ADS.P2)
            R3 = self.calcResistance(chan3.voltage)
            Temp3 = round(self.calcTemp(R3), 1) + etalonne
            AvgTemp = (Temp2 + Temp3) / 2

            return {"bas": {"temp": Temp2, "resistance": round(R2)}, "haut": {"temp": Temp3, "resistance": round(R3)}, "moyenne": AvgTemp}

if __name__ == "__main__":
    daemon = LCD_DISPLAY()
    #print(daemon.GetSonde1())
