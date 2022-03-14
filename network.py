import math
import csv

class LocationData:

  def __init__(self, name, x, y, sourceCapacity, targetCapacity, crossCapacity, numDocks):
    self.name = name
    self.x = x
    self.y = y
    self.sourceCapacity = sourceCapacity
    self.targetCapacity = targetCapacity
    self.crossCapacity = crossCapacity
    self.numDocks = numDocks
    self.distances = {}

class Trolley:

  def __init__(self, source, release, commodity):
    self.source = source
    self.release = release
    self.commodity = commodity

class Network:

  def __init__(self, fileName=None):
    self._locationData = []
    self._nameToLocation = {}
    self._commodities = {}
    self._connections = []
    self._truckCapacity = None
    self._loadingTime = None
    self._unloadingTime = None
    if fileName:
      f = open(fileName, 'r')
      for line in f.read().split('\n'):
        line = line.strip().split()
        if not line:
          continue
        elif line[0] == 'l':
          self.addLocation(LocationData(line[1], float(line[2]), float(line[3]), int(line[4]), int(line[5]), int(line[6]), int(line[7])))
        elif line[0] == 'd':
          self.addArc(int(line[1]), int(line[2]), float(line[3]))
        elif line[0] == 'c':
          self.addCommodity(int(line[1]), int(line[2]), float(line[3]))
        elif line[0] == 'U':
          self._truckCapacity = int(line[1])
        elif line[0] == 'i':
          self._unloadingTime = float(line[1])
        elif line[0] == 'o':
          self._loadingTime = float(line[1])
        else:
          assert False

  def addLocation(self, locationData):
    v = len(self._locationData)
    self._nameToLocation[locationData.name] = v
    self._locationData.append(locationData)
    self._connections += [ (s,v) for s in range(v) ] + [ (v,s) for s in range(v) ]
    return v

  def addArc(self, source, target, distance):
    self._locationData[source].distances[target] = distance

  def addCommodity(self, target, shift, deadline):
    self._commodities[(target,shift)] = deadline

  def setDiscretization(self, tickHours, tickZero=0.0):
    self._tickHours = tickHours
    self._tickZero = tickZero

  def setTruckCapacity(self, truckCapacity):
    self._truckCapacity = truckCapacity

  def setLoadingTime(self, loadingTime):
    self._loadingTime = loadingTime

  def setUnloadingTime(self, unloadingTime):
    self._unloadingTime = unloadingTime

  @property
  def locations(self):
    return list(range(len(self._locationData)))

  @property
  def connections(self):
    return self._connections

  @property
  def commodities(self):
    return self._commodities.keys()

  @property
  def truckCapacity(self):
    return self._truckCapacity

  @property
  def unloadingTicks(self):
    return math.ceil(self._unloadingTime / self._tickHours)

  @property
  def loadingTicks(self):
    return math.ceil((self._unloadingTime + self._loadingTime) / self._tickHours) - self.unloadingTicks

  def name(self, location):
    return self._locationData[location].name

  def x(self, location):
    return self._locationData[location].x

  def y(self, location):
    return self._locationData[location].y

  def sourceCapacity(self, location):
    return self._locationData[location].sourceCapacity

  def targetCapacity(self, location):
    return self._locationData[location].targetCapacity

  def crossCapacity(self, location):
    return self._locationData[location].crossCapacity

  def numDocks(self, location):
    return self._locationData[location].numDocks

  def numDocksPerTick(self, location):
    scaling = self._tickHours / (self._loadingTime + self._unloadingTime)
    return self.numDocks(location) * math.ceil(scaling)

  def deadline(self, commodity):
    return self._commodities[commodity]

  def deadlineTick(self, commodity):
    return int(math.floor((self.deadline(commodity) - self._tickZero) / self._tickHours))

  def tickTime(self, tick):
    return self._tickHours * tick + self._tickZero

  def distance(self, source, target):
    return self._locationData[source].distances[target]

  def distanceTicks(self, source, target):
    return int(math.ceil(self.distance(source, target) / self._tickHours))

  def travelTicks(self, source, target):
    return int(math.ceil((self.distance(source, target) + self._loadingTime + self._unloadingTime) / self._tickHours))

  def isCross(self, location):
    return self._locationData[location].crossCapacity > 0

  def find(self, name):
    return self._nameToLocation.get(name, -1)

  def write(self, f):
    f.write(f'U {self._truckCapacity}\n')
    f.write(f'i {self._unloadingTime}\n')
    f.write(f'o {self._loadingTime}\n')
    f.write('\n')
    for p in self.locations:
      f.write(f'l {self.name(p)} {self.x(p):.4f} {self.y(p):.4f} {self.sourceCapacity(p)} {self.targetCapacity(p)} {self.crossCapacity(p)} {self.numDocks(p)}\n')
    f.write('\n')
    for s in self.locations:
      for t in self.locations:
        f.write(f'd {s} {t} {self.distance(s,t):.3f}\n')
    f.write('\n')
    for target,shift in self.commodities:
      f.write(f'c {target} {shift} {self.deadline((target,shift))}\n')
    f.write('\n')

  def readTrolleys(self, fileName):
    trolleys = []
    f = open(fileName, 'r')
    reader = csv.reader(f)
    header = next(reader, None)
    for row in reader:
      if len(row) == 1:
        row = row[0].split(';')
      trolleys.append(Trolley(self.find(row[0]), float(row[-1]), (self.find(row[1]), int(row[-2]))))
    return trolleys

  def trolleyReleaseTick(self, trolley):
    return int(math.ceil((trolley.release - self._tickZero) / self._tickHours))

