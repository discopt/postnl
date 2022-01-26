import csv
import sys
import math

# Arguments:
#
#1: depot data
#2: shift onset
#3: distances
#4: trolleys_out
#5: time scale in minutes (#5 minutes are one step)
#6: time shift in hours
#
# Example: python data2instance.py depot_data.csv shift_onset.csv distances.csv trolleys_out.csv 7.5 15 > data-7.5-15.instance

# Parse scaling
timeScale = float(sys.argv[5]) / 60.0
if len(sys.argv) > 6:
  timeShift = float(sys.argv[6])
else:
  timeShift = 0.0
timeCross = math.ceil(15.0 / (timeScale * 60.0) )

print(f'T {timeScale} {timeShift} {timeCross}\n')

# Read depot data.

f = open(sys.argv[1], 'r')
reader = csv.reader(f)
header = next(reader, None)
depots = {}
depotIndex = 0
depotToPlace = {}
places = ''
for row in reader:
  name = row[0]
  lattitude = float(row[1])
  longitude = float(row[2])
  try:
    outCapacity = int(row[4])
  except:
    outCapacity = 99999
  try:
    inCapacity = int(row[5])
  except:
    inCapacity = 99999
  depotType = row[3]
  isCross = 1 if depotType in ['CROSS', 'DEPOTPLUS'] else 0
  isTarget = 1 if depotType in ['DEPOT', 'DEPOTPLUS'] else 0
  print(f'p {depotIndex} {name} {lattitude} {longitude} {isTarget} {isCross} {inCapacity} {outCapacity}')
  depotToPlace[name] = depotIndex
  depotIndex += 1
print()

# Read shift onset.

f = open(sys.argv[2], 'r')
reader = csv.reader(f)
header = next(reader, None)
shiftToTime = {}
for row in reader:
  for c in range(1, len(row)):
    shiftToTime[row[0],c] = float(row[c])

# Read distances.

f = open(sys.argv[3], 'r')
reader = csv.reader(f)
header = next(reader, None)
distances = {}
for row in reader:
  s = depotToPlace[row[0]]
  for c in range(1, len(row)):
    t = depotToPlace[header[c]]
    d = float(row[c])
    rd = math.ceil(d / timeScale)
    print(f'd {s} {t} {rd} {d:.3f}')
print()

# Read trolleys.

f = open(sys.argv[4], 'r')
reader = csv.reader(f)
header = next(reader, None)
numTrolleys = 0
for row in reader:
  s = depotToPlace[row[0]]
  t = depotToPlace[row[1]]
  release = math.ceil((float(row[4]) - timeShift) / timeScale)
  deadline = math.floor((shiftToTime[row[1], int(row[3])] - timeShift) / timeScale)
  print(f't {numTrolleys} {s} {t} {release} {deadline}')
  numTrolleys += 1
print()


