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
from lib.SCR import *
from lib.display import *
from datetime import datetime
from database import db

# scr = SCR.SCR(dev = "/dev/ttySC0",data_mode = 1)
debug = False
logging.basicConfig(format='%(asctime)s %(message)s')
# Create the I2C bus
i2c = busio.I2C(board.SCL, board.SDA)
#print(i2c.scan(), board.SDA, board.SCL)

# Create the ADC object using the I2C bus
ads = ADS.ADS1115(i2c)

def convert(value):
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

ResistanceValue = convert("10k")


def write_lcd(**kwargs):
    # lcd start
    lcd_device = lcd()
    # this command clears the display (captain obvious)
    lcd_device.lcd_clear()
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



def calcResistance(voltage):
    return ((ResistanceValue * voltage) / (3.3 - voltage))

def calcTemp(resistance):
    return 1 / ( (math.log(resistance / ResistanceValue) / 3435) + (1 / (273.15+25)) ) - 273.15;

def GetSonde1():
    etalonne = 1.5
    chan0 = AnalogIn(ads, ADS.P0)
    R0 = calcResistance(chan0.voltage)
    Temp0 = round(calcTemp(R0), 1) + etalonne

    chan1 = AnalogIn(ads, ADS.P1)
    R1 = calcResistance(chan1.voltage)
    Temp1 = round(calcTemp(R1), 1) + etalonne
    AvgTemp = (Temp0 + Temp1) / 2

    return {"haut": {"temp": Temp0, "resistance": round(R0)}, "bas": {"temp": Temp1, "resistance": round(R1)}, "moyenne": AvgTemp}

def GetSonde2():
    etalonne = 1.5
    chan2 = AnalogIn(ads, ADS.P3)
    R2 = calcResistance(chan2.voltage)
    Temp2 = round(calcTemp(R2), 1) + etalonne

    chan3 = AnalogIn(ads, ADS.P2)
    R3 = calcResistance(chan3.voltage)
    Temp3 = round(calcTemp(R3), 1) + etalonne
    AvgTemp = (Temp2 + Temp3) / 2

    return {"bas": {"temp": Temp2, "resistance": round(R2)}, "haut": {"temp": Temp3, "resistance": round(R3)}, "moyenne": AvgTemp}


def AjustPercent(temperature, temperatureMax, maxstep, temp=""):
    scr = SCR(data_mode = 0) #0:I2C  1: UART
    step = round(temperatureMax - temperature, 2)

    AjustTemp = 0

    #print(step, maxstep, temp, scr.angle2, scr.angle1)

    if (step > maxstep) or (step > 0 and scr.angle1 > 0 and temp == "temp1") or (step > 0 and scr.angle2 > 0 and temp == "temp2"):
        temperatureMax = temperatureMax # + (5 * step)
        if step > round(maxstep/3 ,1):
            print("Boost : {} > {} {}".format(step, round(maxstep/3,1), temp))
            AjustTemp = round((100-round(((temperatureMax/100)*temperature), 2)))-45.5
        else:
            AjustTemp = round(100-(100-round(((temperatureMax/100)*temperature), 2)))

            if AjustTemp <= 27 and AjustTemp > 10:
                AjustTemp = AjustTemp + (3*(step/1.2))

            if AjustTemp <= 10 and step > maxstep:
                AjustTemp = AjustTemp+12

            if AjustTemp <= 10 and step > maxstep:
                AjustTemp = AjustTemp

        #print(AjustTemp)
        if AjustTemp >= 100:
            AjustTemp = 99

    return round(AjustTemp, 1)

def channelVoltage(channel, percent, disable=False):
    scr = SCR(data_mode = 0) #0:I2C  1: UART
    scr.SetMode(1)
    #scr.GridFrequency(50)

    if disable == False and percent > 0:
        scr.ChannelEnable(channel)
        scr.channelVoltage(channel, percent)

    if percent == 0 and disable==True:
        scr.channelVoltage(channel, percent)
        scr.ChannelDisable(channel)

def SetResistance(sonde1, sonde2, temperature1, temperature2):

    Resistance1_P = 1500
    Resistance2_P = 1500
    Resistance1_Conso = 0
    Resistance2_Conso = 0
    Resistance2 = False
    Percent_R2 = 0
    Percent_R1 = 0
    delta = 0

    # ENTRER
    if temperature2 < 45:
        Percent_R2 = AjustPercent(temperature2, 45, 25, "temp1")

        if Percent_R2 != 0:
            Resistance2 = True
            if Percent_R2 >= 35:
                delta = round((1*Percent_R2)*6)
            else:
                delta = round((1*Percent_R2)*Percent_R2/10)
            db_save = db.Ballon1.create(Sonde_haut=sonde2['haut']['temp'], Sonde_bas=sonde2['bas']['temp'], moyenne_temperature=temperature2, resistance=Percent_R2, watt=round(Percent_R2/100*Resistance2_P)+delta)
            db_save.save()
            print("Resistance 1 Entrer - Turn On {} - conso: {}+{} ({}) - {}%".format(temperature2, round(Percent_R2/100*Resistance2_P), delta, round(Percent_R2/100*Resistance2_P)+delta, Percent_R2))
            channelVoltage(1, Percent_R2)

    # SORTIE
    if temperature1 < 50:

        # ENTRER MARCHE
        if Resistance2 == True:
            Percent_R1 = AjustPercent(temperature1, 40, 5, "temp2")
            Resistance1 = True
            if Percent_R1 != 0:
                if Percent_R1 >= 35:
                    delta = round((1*Percent_R1)*6)
                else:
                    delta = 120
                    delta = round((1*Percent_R1)*Percent_R1/10)
                db_save = db.Ballon2.create(Sonde_haut=sonde1['haut']['temp'], Sonde_bas=sonde1['bas']['temp'], moyenne_temperature=temperature1, resistance=Percent_R1, watt=round(Percent_R1/100*Resistance1_P)+delta)
                db_save.save()
                print("Resistance 2 Sortie - Turn On {} - conso: {}+{} ({}) - {}%".format(temperature1, round((Percent_R1*Resistance1_P)/100), delta, round((Percent_R1*Resistance1_P)/100)+delta, Percent_R1))
                channelVoltage(2, Percent_R1)

        # ENTRER STOP
        else:
            Percent_R1 = AjustPercent(temperature1, 50, 5, "temp2")
            Resistance1 = True
            if Percent_R1 != 0:
                if Percent_R1 >= 35:
                    delta = round((1*Percent_R1)*6)
                else:
                    delta = round((1*Percent_R1)*Percent_R1/10)
                db_save = db.Ballon2.create(Sonde_haut=sonde1['haut']['temp'], Sonde_bas=sonde1['bas']['temp'], moyenne_temperature=temperature1, resistance=Percent_R1, watt=round(Percent_R1/100*Resistance1_P)+delta)
                db_save.save()
                print("Resistance 2 Sortie - Turn On {} - conso: {}+{} ({}) - {}%".format(temperature1, round((Percent_R1*Resistance1_P)/100), delta, round((Percent_R1*Resistance1_P)/100)+delta,  Percent_R1))
                channelVoltage(2, Percent_R1)

    return Percent_R2, Percent_R1

sonde1 = GetSonde1()
sonde2 = GetSonde2()

# print("--------------- SORTIE ------------")
# print("Sonde 1 - Haut", sonde1['haut']['temp'], sonde1['haut']['resistance'])
# print("Avg Temp Sonde 1: {}".format(round(sonde1['moyenne'], 1)))
# print("Sonde 1 - Bas", sonde1['bas']['temp'], sonde1['bas']['resistance'])
# print("--------------- ENTRER -------------")
# print("Sonde 2 - Haut", sonde2['haut']['temp'], sonde2['haut']['resistance'])
# print("Avg temp Sonde 2: {}".format(round(sonde2['moyenne'], 1)))
# print("Sonde 2 - Bas", sonde2['bas']['temp'], sonde2['bas']['resistance'])
# print()

if debug:
    debug_table_data = [
        ['          SORTIE', '         ENTRER'],
        ["Sonde 1 - Haut {}°C ({})".format(sonde1['haut']['temp'], sonde1['haut']['resistance']), "Sonde 2 - Haut {}°C ({})".format(sonde2['haut']['temp'], sonde2['haut']['resistance'])],
        ["Avg Temp Sonde 1: {}°C".format(round(sonde1['moyenne'], 1)), "Avg temp Sonde 2: {}°C".format(round(sonde2['moyenne'], 1))],
        ["Sonde 1 - Bas {}°C ({})".format(sonde1['bas']['temp'], sonde1['bas']['resistance']), "Sonde 2 - Bas {}°C ({})".format(sonde2['bas']['temp'], sonde2['bas']['resistance'])]
    ]
    debug_table = AsciiTable(debug_table_data)
    print(debug_table.table)

else:

    moyenne = round((round(sonde1['moyenne'],1) + round(sonde2['moyenne'],1)) / 2,1)
    nb_moyenne = round((round(sonde2['moyenne'],1) - round(sonde1['moyenne'],1)),1)

    table_data = [
        ['    SORTIE', ' <--------- ', '    ENTRER'],
        ["Sonde 1: {}°C".format(round(sonde1['moyenne'], 1)), "{}°C ({})".format(moyenne, nb_moyenne), "Sonde 2: {}°C".format(round(sonde2['moyenne'], 1))],
    ]
    now = datetime.now()
    dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
    table = SingleTable(table_data, '{}Chauf Eau 2.0---{}'.format("-"*15, dt_string))
    print(table.table)

    r = requests.get("http://192.168.1.14/getmeterdata").json()

    V = r["channels"][0]["V"]/1000
    I = r["channels"][0]["I"]/1000
    W = round(V*I)

    print("Watt Total:", W)


    R1, R2 = SetResistance(sonde1, sonde2, round(sonde1['moyenne'], 1), round(sonde2['moyenne'], 1))

    if R1 == 0:
        channelVoltage(1, R1, disable=True)
        db_save = db.Ballon1.create(Sonde_haut=sonde2['haut']['temp'], Sonde_bas=sonde2['bas']['temp'], moyenne_temperature=sonde2['moyenne'], resistance=0, watt=0)
        db_save.save()

    if R2 == 0:
        channelVoltage(2, R2, disable=True)
        db_save = db.Ballon2.create(Sonde_haut=sonde1['haut']['temp'], Sonde_bas=sonde1['bas']['temp'], moyenne_temperature=sonde1['moyenne'], resistance=0, watt=0)
        db_save.save()

        # total_watt_R1 = round((R1*1500)/100)
        # total_watt_R2 = round((R2*1500)/100)
        # watt1 = W-total_watt_R1
        # watt2 = watt1-total_watt_R2
        # print("dispath watt: ", watt2-400)
    write_lcd(temp1=sonde1['moyenne'], temp2=sonde2['moyenne'])

exit(0)
