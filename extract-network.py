import csv
import sys
import math
from common import *

def printUsage(errorMessage=None):
  if errorMessage is not None:
    print(f'Error: {errorMessage}')
  print(f'Usage: {sys.argv[0]} DEPOTDATA DRIVETIMES SHIFTONSET')
  print('Creates the network file from the three csv files.')
  sys.exit(1)

if len(sys.argv) < 4:
  printUsage('Requires 3 arguments.')

network = Network()

# Read depot data.

try:
  f = open(sys.argv[1], 'r')
except:
  printUsage(f'Failed to open depot data csv file <{sys.argv[1]}>.')
reader = csv.reader(f)
header = next(reader, None)
columns = {}
for column,label in enumerate(header):
  if label == 'Name':
    columns['name'] = column
  elif label in ['lon', 'x-coord']:
    columns['x'] = column
  elif label in ['lat', 'y-coord']:
    columns['y'] = column
  elif label in ['Max Stock Output', 'buffer_out']:
    columns['source-capacity'] = column
  elif label in ['Max Stock Input', 'buffer_in']:
    columns['target-capacity'] = column
  elif label in ['DepotType', 'type']:
    columns['type'] = column
  elif label in ['Cross dock buffer', 'buffer_cross'] :
    columns['cross-capacity'] = column
  elif label in ['Aantal docks', 'num_docks']:
    columns['num-docks'] = column
  elif label == 'Aantal docks  cross docking':
    columns['num-docks-cross'] = column
  else:
    sys.stderr.write(f'Ignoring column <{label}>.')
for row in reader:
  name = row[columns['name']] if 'name' in columns else None
  x = float(row[columns['x']]) if 'x' in columns else 0.0
  y = float(row[columns['y']]) if 'y' in columns else 0.0
  sourceCapacityStr = row[columns['source-capacity']] if 'source-capacity' in columns else 0
  sourceCapacity = int(sourceCapacityStr) if sourceCapacityStr != '' else 999999
  targetCapacityStr = row[columns['target-capacity']] if 'target-capacity' in columns else 0
  targetCapacity = int(targetCapacityStr) if targetCapacityStr != '' else 999999
  crossCapacityStr = row[columns['cross-capacity']] if 'cross-capacity' in columns else 0
  crossCapacity = int(crossCapacityStr) if crossCapacityStr != '' else 0
  numDocksStr = row[columns['num-docks']] if 'num-docks' in columns else ''
  numDocks = int(numDocksStr) if numDocksStr.strip() != '' else 0
  numDocksCrossStr = row[columns['num-docks-cross']] if 'num-docks-cross' in columns else None
  numDocks += int(numDocksCrossStr) if numDocksCrossStr else 0
  network.addLocation(LocationData(name, x, y, sourceCapacity, targetCapacity, crossCapacity, numDocks))

# Read distances.

try:
  f = open(sys.argv[2], 'r')
except:
  printUsage(f'Failed to open depot drivetimes csv file <{sys.argv[2]}>.')
reader = csv.reader(f)
header = next(reader, None)
nameToLocation = {}
for i,p in enumerate(network.locations):
  assert header[i+1] == network.name(p)
  nameToLocation[network.name(p)] = i
for row in reader:
  for target,distance in enumerate(row[1:]):
    network.addArc(network.find(row[0]), network.find(header[target+1]), float(distance))

# Read commodities.

try:
  f = open(sys.argv[3], 'r')
except:
  printUsage(f'Failed to open depot shiftonset csv file <{sys.argv[3]}>.')
reader = csv.reader(f)
header = next(reader, None)
for row in reader:
  for c in range(1, len(row)):
    network.addCommodity(network.find(row[0]), c, float(row[c]))

network.setTruckCapacity(48)
network.setUnloadingTime(0.15)
network.setLoadingTime(0.10)

network.write(sys.stdout)

