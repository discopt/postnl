import sys
import random

class Place:
  pass

class Trolley:
  pass

class Route:
  pass

class Instance:

  def __init__(self, fileName=None):
    if fileName != None:
      f = open(fileName, 'r')
      data = f.read().split()
      i = 0
      self.places = {}
      self.dist = {}
      self.hourDistances = {}
      self.trolleys = {}
      self.start = 9999999
      self.end = -9999999
      while i < len(data):
        if data[i] == 'T':
          self.tickHours = float(data[i+1])
          self.timeShift = float(data[i+2])
          self.crossTicks = int(data[i+3])
          i += 4
        elif data[i] == 'p':
          place = Place()
          place.name = data[i+2]
          place.lattitude = float(data[i+3])
          place.longitude = float(data[i+4])
          place.isTarget = data[i+5] == '1'
          place.isCross = data[i+6] == '1'
          place.inCapacity = int(data[i+7])
          place.outCapacity = int(data[i+8])
          place.inAmount = 0
          place.outAmount = 0
          self.places[int(data[i+1])] = place
          i += 9
        elif data[i] == 'd':
          self.dist[int(data[i+1]),int(data[i+2])] = int(data[i+3])
          self.hourDistances[int(data[i+1]),int(data[i+2])] = float(data[i+4])
          i += 5
        elif data[i] == 't':
          trolley = Trolley()
          trolley.origin = int(data[i+2])
          trolley.destination = int(data[i+3])
          trolley.release = int(data[i+4])
          trolley.deadline = int(data[i+5])
          self.trolleys[int(data[i+1])] = trolley
          i += 6
          if trolley.release < self.start:
            self.start = trolley.release
          if trolley.deadline > self.end:
            self.end = trolley.deadline
          trolley.position = -1   # keeps track of the position of the trolley
        else:
          sys.stderr.write(f'Ignoring token <{data[i]}>.\n')
          i += 1

  def writeRoutes(self, routes, fileStream=sys.stdout):
    for key,routeSet in routes.items():
      for route in routeSet:
        assert key[0] == route[0] and key[1] == route[-1]
        fileStream.write(f'{key[0]} {key[1]} {len(route)-2}' + ' '.join(map(str, route[1:-1])) + '\n')
    fileStream.flush()

  def readRoutes(self, fileName):
    f = open(fileName, 'r')
    data = f.read().split()
    i = 0
    self.routes = {}
    while i < len(data):
      route = Route()
      route.origin = int(data[i])
      route.destination = int(data[i+1])
      route.numberOfIntermediates = int(data[i+2])
      intermediatePlaces = ''
      for j in range(route.numberOfIntermediates):
        intermediatePlaces += data[i+3+j]
      route.itermediatePlaces = intermediatePlaces
      self.routes[int(data[i]),int(data[i+1])] = route
      i += 3 + route.numberOfIntermediates

  def writeinstance(self, filename):
    f = open(filename, 'w')

    f.write(f'T {self.tickHours} {self.timeShift} {self.crossTicks}\n\n')

    for p in self.places:
      place = self.places[p]
      f.write(f'p {place.name} {place.lattitude} {place.longitude} {1 if place.isTarget else 0} '
              f'{1 if place.isCross else 0} {place.inCapacity} {place.outCapacity}\n')
    f.write('\n')

    for i, j in self.dist:
      f.write(f'd {i} {j} {self.dist[(i,j)]} {self.hourDistances[(i,j)]}\n')
    f.write('\n')

    for t in self.trolleys:
      trolley = self.trolleys[t]
      f.write(f't {t} {trolley.origin} {trolley.destination} {trolley.release} {trolley.deadline}\n')
    f.write('\n')
    f.close()

class Demandinstance:

  def __init__(self, instance=None):
    if not instance is None:
      self.demand = dict()
      self.places = instance.places
      self.dist = instance.dist
      self.hourDistances = instance.hourDistances
      self.depots = [k for k in self.places if self.places[k].isTarget]
      self.tickHours = instance.tickHours
      self.timeShift = instance.timeShift
      self.crossTicks = instance.crossTicks

      for d in self.depots:
        self.places[d].spawn_start = 9999999
        self.places[d].spawn_end = -9999999
        self.places[d].shifts = set()

      for o in self.depots:
        for d in self.depots:
          self.demand[(o, d)] = 0

      for trolley in instance.trolleys.values():
        self.demand[(trolley.origin, trolley.destination)] += 1
        if trolley.release < self.places[trolley.origin].spawn_start:
          self.places[trolley.origin].spawn_start = trolley.release
        if trolley.release > self.places[trolley.origin].spawn_end:
          self.places[trolley.origin].spawn_end = trolley.release
        self.places[trolley.destination].shifts.add(trolley.deadline)

      for k in self.depots:
        place = self.places[k]
        place.demand = {destination: self.demand[(k, destination)] for destination in self.depots}

  def totaldemand(self):
    return sum(self.demand.values())

  def depottotaldemand(self, depot):
    return sum(self.places[depot].demand.values())

  def __str__(self):
    # return str(self.demand)
    s: str = '     ' + 'spawn_int'
    for o in self.depots:
      s += f'{o:>5}'
    s += ' total\n'
    for o in self.depots:
      s += f'{o:>2}:  [{self.places[o].spawn_start:>3},{self.places[o].spawn_end:>3}]'
      for d in self.depots:
        s += f'{self.demand[(o, d)]:>5}'
      s += f'{self.depottotaldemand(o):>6}\n'
    s += f'Total demand: {self.totaldemand()}\n'
    s += f'Total \'self\' demand: {sum([self.demand[(d, d)] for d in self.depots])}'
    return s

def randompairdemand(demandmatrix, error=0.25):
  randompaireddemand = {}
  pair_sigma = {}

  for o, d in demandmatrix:
    pair_sigma[(o, d)] = demandmatrix[(o, d)] * error / 3
    randompaireddemand[(o, d)] = round(random.normalvariate(demandmatrix[(o, d)], pair_sigma[(o, d)]))

  return randompaireddemand

def createRandomInstance(demandinstance, shorteninterval=0):
  randinstance = Instance()
  randinstance.places = demandinstance.places
  randinstance.dist = demandinstance.dist
  randinstance.hourDistances = demandinstance.hourDistances
  randinstance.tickHours = demandinstance.tickHours
  randinstance.timeShift = demandinstance.timeShift
  randinstance.crossTicks = demandinstance.crossTicks
  randinstance.trolleys = {}

  temptrolleys = []

  randomdemand = randompairdemand(demandinstance.demand, 0.25)  # adds variation to the paired demand (default 25% error)

  for o, d in randomdemand:
    origin = demandinstance.places[o]
    destination = demandinstance.places[d]
    demand = randomdemand[(o, d)]
    for _ in range(demand):
      t = Trolley()
      shifts = list(destination.shifts)
      shiftnr = random.randint(0, len(shifts) - 1)
      t.origin = o
      t.destination = d
      t.release = random.randint(round(origin.spawn_start + shorteninterval/2*(origin.spawn_end -origin.spawn_start)),
                                 round(origin.spawn_end - shorteninterval/2*(origin.spawn_end -origin.spawn_start)))
      t.deadline = shifts[shiftnr]
      temptrolleys += [t]

  sortedtrolleys = sorted(temptrolleys, key=lambda x: x.release)
  randinstance.trolleys = {i: sortedtrolleys[i] for i in range(len(temptrolleys))}

  return randinstance
