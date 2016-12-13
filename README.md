# MaverickBBQ
Receives Wireless BBQ Thermometer Telegrams via RF-Receiver attached to Raspberry Pi

Needs pigpiod (http://abyz.co.uk/rpi/pigpio/pigpiod.html) running to work
start with: pigpiod -x -1


usage: maverick.py [-h] [--html [HTML]] [--json [JSON]] [--sqlite [SQLITE]]
                   [--debug] [--pin PIN] [--nosync] [--fahrenheit] [--verbose]

Receives Wireless BBQ Thermometer Telegrams via RF-Receiver

optional arguments:
  -h, --help         show this help message and exit
  --html [HTML]      Writes a HTML file
  --json [JSON]      Writes a JSON file
  --sqlite [SQLITE]  Writes to an SQLite Database
  --debug            Generates additional debugging Output
  --pin PIN          Sets the Pin number
  --nosync           Always register new IDs
  --fahrenheit       Sets the Output to Fahrenheit
  --verbose          Print more Information to stdout

  Attach an 433,92MHz (different Receiver needed in the US, I think) receiver to a free GPIO (default=18 (BCM Numbering) and you are ready to go.
