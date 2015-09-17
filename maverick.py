#!/usr/bin/env python3
# coding=utf-8

# maverick.py
# Receives Wireless BBQ Thermometer Telegrams via RF-Receiver
# (c) Björn Schrader, 2015
# Code based on
# https://github.com/martinr63/OregonPi
# https://forums.adafruit.com/viewtopic.php?f=8&t=25414
# http://www.grillsportverein.de/forum/threads/wlan-maverick-bbq-thermometer-raspberry-pi-edition.232283/
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the "Software"), to deal in the Software without restriction, including without
# limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so, subject to the following 
# conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial
# portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
# LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import time
import pigpio
import argparse
import copy
import queue
import threading

parser = argparse.ArgumentParser(description='Receives Wireless BBQ Thermometer Telegrams via RF-Receiver')
parser.add_argument('--html', nargs='?', const='maverick.html', help='Writes a HTML file')
parser.add_argument('--json', nargs='?', const='maverick.json', help='Writes a JSON file')
parser.add_argument('--sqlite', nargs='?', const='maverick.sqlite', help='Writes to an SQLite Database')
parser.add_argument('--thingspeak', nargs='?', const='maverick.thingspeak', help='Writes to ThingSpeak (enter Write-API key)')
parser.add_argument('--debug', action='store_true', help='Generates additional debugging Output')
parser.add_argument('--pin', default=4, type=int, help='Sets the Pin number')
parser.add_argument('--nosync', action='store_true', help='Always register new IDs')
parser.add_argument('--offset', default=-80, type=int, help='Sets the offset of the rising Edge (in µs)')
parser.add_argument('--fahrenheit', action='store_true', help='Sets the Output to Fahrenheit')
parser.add_argument('--verbose', action='store_true', help='Print more Information to stdout')

options = parser.parse_args()

if options.debug:
   print(options)

# Globals für die Pinchange-Routine
oldtick=0 
state = 'wait'
packet = []
bit = 0

# Queue für fertige Pakete
packet_queue = queue.Queue()

# Liste der Sender für die Synchronisierung
unit_list = {}

def get_state (bitlist):
   # Wertet das Statusbye aus
   state = quart(bitlist[6*4:6*4+4]) << 2
   state |= quart(bitlist[7*4:7*4+4])
   if options.debug:
      print('state', state)
   if state == 7:
      return 'init'
   elif state == 2:
      return 'default'
   else:
      return 'unknown ' + state

def bitlist_to_int (bitlist):
   out = 0
   for bit in bitlist:
      out = (out << 1) | bit
   return out

def bitlist_to_hexlist (bitlist):
   # Gibt eine Bitliste als Hex aus
   # nützlich zum debuggen
   out = []
   max = int(len(bitlist)/8)
   for i in range(max):
      out.append(hex(bitlist_to_int(bitlist[i*8:i*8+8])))
   return out 

def quart (raw):
   # 4 zu 2 Umwandlung
   if raw == [0,1,0,1]:
      return 0
   elif raw == [0,1,1,0]:
      return 1
   elif raw == [1,0,0,1]:
      return 2
   elif raw == [1,0,1,0]:
      return 3
   else:
      print('Error in Quart conversion', raw)
      return -1

def calc_chksum(bitlist):
   # Berechnet die Checksumme anhand der Daten
   chksum_data = 0
   for i in range(12):
      chksum_data |= quart(bitlist[(6+i)*4:(6+i)*4+4]) << 22-2*i

   mask = 0x3331;
   chksum = 0x0;
   for i in range(24):
      if (chksum_data >> i) & 0x01:
         chksum ^= mask;
      msb = (mask >> 15) & 0x01
      mask = (mask << 1) & 0xFFFF
      if msb == 1:
         mask ^= 0x1021

   return chksum

def chksum(bitlist):
   # prüft die errechnete Checksumme gegen die übertragene
   # gibt das Ergebniss zurück, da es gleichzeitig die
   # zufällige ID des Senders ist

   chksum_data = calc_chksum(bitlist) 
   
   chksum = 0
   for i in range(6):
      chksum |= quart(bitlist[(18+i)*4:((18+i)*4)+4]) << 14-i*2
   
   if bitlist[24*4:(24*4)+4] == [0,0,0,1] or  bitlist[24*4:(24*4)+4] == [0,0,1,0]:
      # to be verified, our ET-733 use the ET-732 code below
      type = 'et733'
      chksum  |= 0xFFFF & (quart(bitlist[25*4:(25*4)+4])&1) << 3
      chksum  |= 0xFFFF & (quart(bitlist[25*4:(25*4)+4])&2) << 1
      if  bitlist[24*4:(24*4)+4] == [0,0,1,0]:
         chksum |= 0x02
   else:
      type = 'et732'
      chksum  |= 0xFFFF & quart(bitlist[24*4:(24*4)+4]) << 2
      chksum  |= 0xFFFF & quart(bitlist[25*4:(25*4)+4])

   chksum = (chksum_data & 0xffff) ^ chksum
   return type, chksum

def get_data (bitlist):
   # Liest die Sensordaten aus dem Datenpaket aus
   sensor1 = 0
   sensor2 = 0
   
   for i in range(5):
      startbit = (4-i)*4
      sensor1 += quart(bitlist[startbit+32:startbit+32+4]) * ( 1 << (2*i))
      sensor2 += quart(bitlist[startbit+52:startbit+52+4]) * ( 1 << (2*i))
   
   if sensor1 == 0:
      sensor1 = ''
   else:
      sensor1 -= 532
      if options.fahrenheit:
         sensor1 = (((sensor1*9)/5) +32)

   if sensor2 == 0:
      sensor2 = ''
   else:
      sensor2 -= 532
      if options.fahrenheit:
         sensor2 = (((sensor2*9)/5) +32)

   return [sensor1, sensor2]

def pinchange(gpio, level, tick):
   # Interruptroutine
   # wertet das Funksignal aus
   global oldtick
   global state
   global packet
   global bit
   global packet_queue

   # steigende Flanke etwas vorverlagern
   # Je nach Empfänger evtl. anpassen
   if (level==1):
      tick = tick + options.offset 

   duration = tick - oldtick
   oldtick = tick

   if options.debug:
      print(duration, level)

   # wait ist der Wartestatus
   if state == 'wait' and level == 1:
      # lange Ruhe = vermutlich Preamble
      if duration > 4000:
         state = 'preamble'
   # preamble heißt es könnte losgehen, wird nicht großartig geprüft
   elif state == 'preamble':
      if (400 < duration < 600):
         state = 'data'
         bit = 1
         packet[:] = []
         packet.append(1)
         packet.append(0)
      elif (200 < duration < 300):
         state = 'preamble'
      else:
         state = 'wait'
   elif state == 'data':
      if level == 0:
      # level == 0 heisst, es wurde ein HIGH-Impuls ausgewertet
         if (200 < duration < 300):
            # kurzer LOW = 0 wiederholt
            if bit == 0:
               packet.append(0)
         elif (400 < duration < 600):
            # langes LOW = 0
            packet.append(0)
            bit = 0
         else:
            # ungueltige Zeit
            state = 'wait'
      else:
         if (200 < duration < 300):
            # kurzer HIGH = 1 wiederholt
            if bit == 1:
               packet.append(1)
         elif (400 < duration < 600):
            # langes HIGH = 1
            packet.append(1)
            bit = 1
         else:
            # ungueltige Zeit
            state = 'wait'
   if len(packet) == 104:
      # komplettes Paket empfangen
      state = 'wait'
      packet_queue.put((time.time(),list(packet)))
      packet[:] = []

def updated(id, state, timestamp):
   # Prüft ob in den letzten 5s ein Paket vom gleichen Sender empfangen wurde
   global unit_list
   if id in unit_list:
      if (unit_list[id] + 5) < timestamp:
         unit_list[id] = timestamp
         if options.debug:
            print('units:', unit_list)
         return True
      else:
         return False
   else:
      if state == 'init' or options.nosync:
      # trägt neue Sender nur ein, wenn diese im Sync-Status sind, oder --nosync aktiv ist
         unit_list[id] = timestamp
         if options.debug:
            print('units:', unit_list)
         return True
      else:
         return False

def worker():
   if options.verbose:
      print('Main task running')
   # Hauptthread, wertet empfangene Pakete aus und verteilt an die anderen Queues
   global unit_list
   if options.fahrenheit:
      unit = 'F'
   else:
      unit = '°C'
   while True:
      item_time, item = packet_queue.get()
      type, chksum_is = chksum(item)
      temp1, temp2 = get_data(item)
      state = get_state(item)
      if updated(chksum_is, state, item_time):
         if options.html != None:
            html_queue.put((item_time, chksum_is, type, temp1, temp2))
         if options.json != None:
            json_queue.put((item_time, chksum_is, type, temp1, temp2))
         if options.sqlite != None:
            sqlite_queue.put((item_time, chksum_is, type, temp1, temp2))
         if options.thingspeak != None:
            thingspeak_queue.put((item_time, chksum_is, type, temp1, temp2))
         if options.verbose:
            print(time.strftime('%c:',time.localtime(item_time)),type, '-', chksum_is, '- Temperatur 1:', temp1, unit, 'Temperatur 2:', temp2, unit)
         if options.debug:
            print('raw:', item)
            print('hex', bitlist_to_hexlist(item))
      packet_queue.task_done()

def json_writer():
   # schreibt ein JSON-Logfile
   if options.verbose:
       print('Starting JSON writer Task')
   json_file = open(options.json, 'a')
   if options.fahrenheit:
      unit = 'F'
   else:
      unit = '°C'
   while True:
      item_time, chksum_is, type, temp1, temp2 =  json_queue.get()
      set = {'time': item_time, 'checksum': chksum_is, 'type' : type, 'unit': unit, 'temperature_1' : temp1, 'temperature_2' : temp2}
      json_file.write(json.dumps(set) + ',')
      json_file.flush()
      json_queue.task_done()

def html_writer():
   # schreibt eine HTML-Datei (ohne Header und Footer)
   if options.verbose:
       print('Starting HTML writer Task')
   html_file = open(options.html, 'a')
   if options.fahrenheit:
      unit = 'F'
   else:
      unit = '°C'
   while True:
      item_time, chksum_is, type, temp1, temp2 =  html_queue.get()
      print(time.strftime('%c:',time.localtime(item_time)), type, '-', chksum_is, '- Temperatur 1:', temp1, unit, 'Temperatur 2:', temp2, unit, '<br>', file=html_file)
      html_file.flush()
      html_queue.task_done()

def sqlite_writer():
   # speichert die Empfangenen Daten in eine SQlite Datei
   if options.verbose:
       print('Starting SQLite writer Task')
   sqlite_conn = sqlite3.connect(options.sqlite)
   sqlite_c = sqlite_conn.cursor()
   sqlite_c.execute('''CREATE TABLE IF NOT EXISTS maverick
             (date integer, type text, id integer, temperature_1 real, temperature_2 real)''')
   while True:
      item_time, chksum_is, type, temp1, temp2 =  sqlite_queue.get()
      sqlite_c.execute("INSERT INTO maverick VALUES (?, ?, ?, ?, ?)", (int(item_time), type,  chksum_is, temp1, temp2))
      sqlite_conn.commit()
      sqlite_queue.task_done()

def thingspeak_writer():
    global options
    # postet die Daten auf Thingspeak
    unit_list = {}
    if options.verbose:
        print('Starting ThingSpeak writer Task')
    while True:
        queueempty = False
        # Bei neuen Daten sofort senden, ansonsten nach 15s (Mindestintervall, anonsten werden die gesendeten Daten ignoriert
        try:
            item_time, chksum_is, type, temp1, temp2 = thingspeak_queue.get(True, 15)
        except queue.Empty:
            queueempty = True
        # Neue Daten verarbeiten
        # Es werden maximal 4 Empfänger mit je 2 Kanälen unterstützt, da ThingSpeak 8 Kanäle (Felder) unterstützt
        if not queueempty:
            id = 4
            if chksum_is in unit_list:
                if options.verbose:
                    print('Unit in List')
                unit_list[chksum_is]['timestamp'] = int(item_time)
                unit_list[chksum_is]['temp1'] = temp1
                unit_list[chksum_is]['temp2'] = temp2
                id = unit_list[chksum_is]['id']
            else:
                if len(unit_list) >= 4:
                    if options.verbose:
                        print('Maximum Number of Unit reached')
                    maxage = int(time.time() - 20)
                    oldestage = time.time()
                    oldestchksum = 0
                    for chksum, unit in unit_list.items():
                        if unit['timestamp'] <= maxage and unit['timestamp'] < oldestage:
                            oldestchksum = chksum
                            oldestage = unit['timestamp']
                            id = unit['id']
                    if oldestchksum != 0:
                        del unit_list[oldestchksum]
                    else:
                        print('All Slots in use, ignoring Device ', chksum_is)
                        continue 
                else:
                    if options.verbose:
                        print('Adding Unit to List')
                    slots = list(range(4))
                    for chksum, unit in unit_list.items():
                        slots.remove(unit['id'])
                    id = slots[0]
                unit_list[chksum_is] = {'timestamp': int(item_time), 'id': id, 'temp1': temp1, 'temp2': temp2}
        # Keine neuen Daten empfangen, damit nichts verloren geht trotzdem in den letzten 30s empfangene Daten senden
        else:
            if options.verbose:
                print('Nothing new received')
        status = ''
        fields = {}
        tosend = False
        # Welche Sender wurden in den letzten 30s empfangen
        for chksum, unit in unit_list.items():
            if unit['timestamp'] >= time.time() - 30:
                tosend = True
                fields.update({'field' + str(unit['id']*2+1): unit['temp1'], 'field' + str(unit['id']*2+2): unit['temp2']})
            # Im Statusfeld wird ein Zuordnung der Kanäle zu den Sendern übermittelt
            status += str(unit['id']*2+1) + '/' + str(unit['id']*2+2) + ':' + str(chksum) + ' '
        if options.verbose:
            print('Statusstring: ', status)
        data = {'api_key':options.thingspeak, 'status': status}
        data.update(fields)
        params = urllib.parse.urlencode(data)
        params = params.encode('utf-8')
        headers = {"Content-type": "application/x-www-form-urlencoded","Accept": "text/plain"}
        request = urllib.request.Request('http://api.thingspeak.com/update', params, headers)
        # Wenn Daten vorliegen, senden
        if tosend:
            if options.verbose:
                print('Sending to ThingSpeak')
            with urllib.request.urlopen(request) as response:
                pass
                #TODO Fehlerhandling

pi = pigpio.pi() # connect to local Pi
oldtick = pi.get_current_tick()
pi.set_mode(options.pin, pigpio.INPUT)
callback1 = pi.callback(4, pigpio.EITHER_EDGE, pinchange)
start = time.time()

if options.html != None:
   html_queue = queue.Queue()
   html_writer_worker = threading.Thread(target=html_writer)
   html_writer_worker.daemon = True
   html_writer_worker.start()

if options.json != None:
   import json
   json_queue = queue.Queue()
   json_writer_worker = threading.Thread(target=json_writer)
   json_writer_worker.daemon = True
   json_writer_worker.start()

if options.sqlite != None:
   import sqlite3
   sqlite_queue = queue.Queue()
   sqlite_writer_worker = threading.Thread(target=sqlite_writer)
   sqlite_writer_worker.daemon = True
   sqlite_writer_worker.start()

if options.thingspeak != None:
    import urllib.request
    import urllib.parse
    thingspeak_queue = queue.Queue()
    thingspeak_writer_worker = threading.Thread(target=thingspeak_writer)
    thingspeak_writer_worker.daemon = True
    thingspeak_writer_worker.start()

worker1 = threading.Thread(target=worker)
worker1.daemon = True
worker1.start()

while (1):
   time.sleep(0.2)
pi.stop()
