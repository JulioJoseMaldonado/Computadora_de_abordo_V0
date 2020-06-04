import serial 
import os
import sys
import sqlite3
import string
import pynmea2
import RPi.GPIO as gpio
from datetime import datetime
from oled.device import sh1106 
from oled.render import canvas
from PIL import ImageDraw, ImageFont
from geopy.distance import distance


#DB section.

#Conect with database (dbgps.db).
#Create the table Odometers if it's necessary. The table Odometers contains (id integer, kms long, unity text, typeOdometer text).
#If the entry for Odometer total (id = 1) exists initialize odometerTotal variable with the value stored. If it's not exists create the entry.
#If the entry for Odometer partial (id = 2) exists initialize odometerPartial variable with the value stored. If it's not exists create the entry.
#Return True when don't have problem, false in the other case.
def InitDBforOdometers():
    global odometerPartial
    global odometerTotal
    global dbconnect
    global cursor
    try:
        dbconnect = sqlite3.connect("dbgps.db")
        cursor = dbconnect.cursor()
        
        #Create table for Odometers,if it does not exist.
        cursor.execute('''CREATE TABLE IF NOT EXISTS Odometers (id integer, kms long, unity text, typeOdometer text);''')

        #Check if exist entry for Odometer Total (id = 1). 
        #If it doesn't exist, create the entry. 
        #If it exists, Initialize the odometerTotal variable with the stored value.
        cursor.execute('SELECT * FROM Odometers WHERE id = 1;')
        rows = cursor.fetchall()
        if (len(rows) == 0):
            cursor.execute('''INSERT INTO Odometers values(1, 0.0, 'km', 'Odometer Total')''')
        else:
            odometerTotal = rows[0][1]
            print(odometerTotal)
            
        #Check if exist entry for Odometer Partial (id = 2). 
        #If it doesn't exist, create the entry. 
        #If it exists, Initialize the odometerPartial variable with the stored value.
        cursor.execute('SELECT * FROM Odometers WHERE id = 2;')
        rows = cursor.fetchall()
        if (len(rows) == 0):
            cursor.execute('''INSERT INTO Odometers values(2, 0.0, 'km', 'Odometer Partial')''')
        else:
            odometerPartial = rows[0][1]
            print(odometerPartial)
            
        dbconnect.commit()
        gpio.output(GPIOLedDBOk,True)
        return True
        
    except:
        return False
    
    
    
#Update value the Odometer Total and Partial
#Return True when don't have problem, false in the other case.        
def UpdateOdometers():
    global odometerTotal
    global odometerPartial
    global dbconnect
    global cursor
    try:
        strQuery = "UPDATE Odometers SET kms = " + str(odometerTotal) + " WHERE id = 1";
        cursor.execute(strQuery);
        strQuery = "UPDATE Odometers SET kms = " + str(odometerPartial) + " WHERE id = 2";
        cursor.execute(strQuery)
        dbconnect.commit()
        gpio.output(GPIOLedDBOk,True)
        return True
    except:
        return False
    



        


#Oled sh1106 section.

#Shows data on the oled display.
#a is data for the first line.
#b is data for the second line.
#c is data for the third line.
def DisplayOled(a, b, c):
    try:
        with canvas(oled) as draw:
            draw.text((0, 0), a, font=font, fill=255)
            draw.text((0, 25), b, font=font1, fill=255)
            draw.text((0, 40), c, font=font1, fill=255)
    except:
        print ("Error in DisplayOlded.")
        
        

#Setup the necesarry for the correct funtion of Oled sh1106.
#Setup the font used (C&C Red Alert[INET].ttf).
#Return True when don't have problem, false in the other case.
def InitOledSH1106():
    global oled
    global font
    global font1
    try:
        oled = sh1106(port=1, address=0x3C)
        font = ImageFont.truetype('C&C Red Alert[INET].ttf', 30)
        font1 = ImageFont.truetype('C&C Red Alert[INET].ttf', 18) 
        DisplayOled("Inicializando", " ", " ")
        return True
    except:
        return False
    


        
#GPIO section.

def ResetOdometerPartial(channel):
    global odometerPartial
    print("Reset")
    odometerPartial = 0.0
    
def CallbackShutdown(channel):
    global shutDownOk
    shutDownOk = True
    
def InitGPIO():
    global gpio
    global GPIOButtonResetOdometer
    global GPIOButtonShutDown
    
    global GPIOLedOledError
    global GPIOLedGPSOk
    global GPIOLedDBOk
    GPIOButtonResetOdometer = 23
    GPIOButtonShutDown = 26
    
    GPIOLedOledError = 16
    GPIOLedGPSOk = 20
    GPIOLedDBOk = 21
    
    gpio.setwarnings(False)   
    gpio.setmode(gpio.BCM)
    gpio.setup(GPIOButtonResetOdometer, gpio.IN)
    gpio.setup(GPIOButtonShutDown, gpio.IN)
    gpio.setup(GPIOLedOledError, gpio.OUT)
    gpio.setup(GPIOLedGPSOk, gpio.OUT)
    gpio.setup(GPIOLedDBOk, gpio.OUT)
    gpio.output(GPIOLedGPSOk, False)
    gpio.output(GPIOLedDBOk, False)
    

    
#GPS section.

def InitGPS():
    global ser
    try:
        port = "/dev/ttyS0"
        ser = serial.Serial(port, baudrate=9600, timeout=0.5)
        return True
    except:
        return False

def ReadGPS():
    global coord
    global coordPas
    global timeStamp
    global timeStampPas
    global firstRead
    datagps = False 
    dataOut = pynmea2.NMEAStreamReader()
    newData = ser.readline() 
    gpio.output(GPIOLedGPSOk, False)
    if newData[0:6] == "$GPGGA":
        newMsg = pynmea2.parse(newData)
        if (newMsg.gps_qual == 1 or newMsg.gps_qual == 2 or newMsg.gps_qual == 3)  and newMsg.num_sats>=4:
            gpio.output(GPIOLedGPSOk,True)
            lat = newMsg.latitude
            lng = newMsg.longitude
            timeStamp = newMsg.timestamp.isoformat()
            if firstRead:
                timeStampPas = timeStamp
                coordPas = (lat, lng)
            else:
                coord = (lat, lng)
            datagps = True
    return datagps

def ProcessDataGPS():
    global coord
    global coordPas
    global timeStamp
    global timeStampPas
    global speed
    global odometerPartial
    global odometerTotal
    FMT = '%H:%M:%S'
    msgOled = False 
    d = distance(coord, coordPas).km
    if (d>0.001):
        odometerTotal =  odometerTotal + d
        odometerPartial = odometerPartial + d
        diffTime = ((datetime.strptime(timeStamp, FMT) - datetime.strptime(timeStampPas, FMT)).total_seconds())/3600
        speed = d / diffTime
        coordPas = coord
        timeStampPas = timeStamp
        strdistance = str(round(d,1)) + "km" 
        gps = "Latitud = " + str(coord[0]) + ", longitud= " + str(coord[1]) + ", distance = " + str(d) + " km, odometro: " + strdistance 
        msgOled =  True
    else:
        gps = "Latitud = " + str(coord[0]) + ", longitud= " + str(coord[1]) + ", distance = " + str(0.0)
    print(gps)
    return msgOled
                
                
#Main

shutDownOk= False
odometerTotal = 0.0
odometerPartial = 0.0
InitGPIO()
while not InitOledSH1106():
    gpio.output(GPIOLedOledError, True)
gpio.output(GPIOLedOledError, False)
    
while not InitGPS():
    DisplayOled("Error GPS.", "", "")
firstRead = True
while firstRead:
    if ReadGPS():
        if firstRead:
            firstRead = False
if not InitDBforOdometers():
    print("Data Base Error")
gpio.add_event_detect(GPIOButtonResetOdometer, gpio.RISING, callback=ResetOdometerPartial, bouncetime=1000)
gpio.add_event_detect(GPIOButtonShutDown, gpio.RISING, callback=CallbackShutdown, bouncetime=1000)

while not shutDownOk:
        if ReadGPS():
            if ProcessDataGPS():
                strodometerPartial = str(round(odometerPartial,2)) + " km"
                strodometerTotal = str(round(odometerTotal,2)) + " km"
                strspeed = str(round(speed,1)) + "km/h" 
                DisplayOled(strspeed, strodometerTotal, strodometerPartial)
                if not UpdateOdometers():
                    gpio.output(GPIOLedDBOk, False)
 
os.system('sudo shutdown -h 1')
gpio.output(GPIOLedDBOk, False)
gpio.output(GPIOLedGPSOk, False)
dbconnect.close()
DisplayOled("", "","")
sys.exit()
        
        
        
            

        
    
    


    




