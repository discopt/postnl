class Place:
  pass

class Trolley:
  pass

class Instance:

  def __init__(self, fileName):
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
      else:
        sys.stderr.write(f'Ignoring token <{data[i]}>.\n')
        i += 1

