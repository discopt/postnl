import sys
from gurobipy import *
from common import *
import matplotlib.pyplot as plt
import math
import time

def printUsage(errorMessage=None):
  if errorMessage is not None:
    print(f'Error: {errorMessage}')
  print(f'Usage: {sys.argv[0]} <network file name> <tickhours> <tickzero> <trolleys file name> [OPTIONS...]')
  print('Solves the MIP for network and trolleys, discretizing tickhours hours with offset tickzero hours.')
  print('Options:')
  print('  -oT FILE  Write used trucks to <FILE>.')
  print('  -rT FILE  Read used trucks from <FILE> and use routes.')
  sys.exit(1)

if len(sys.argv) < 5:
  printUsage('Requires 4 arguments.')

network = Network(sys.argv[1])
trolleys = network.readTrolleys(sys.argv[4])
tickHours = float(sys.argv[2])
tickZero = float(sys.argv[3])
usedTrucksOutputFileName = None
usedTruckRoutesFileName = None
a = 5
while a < len(sys.argv):
  arg = sys.argv[a]
  if arg == '-oT' and a+1 < len(sys.argv):
    usedTrucksOutputFileName = sys.argv[a+1]
    a += 1
  elif arg == '-rT' and a+1 < len(sys.argv):
    usedTruckRoutesFileName = sys.argv[a+1]
    a += 1
  else:
    printUsage(f'Unprocessed argument <{arg}>.')
  a += 1


print(f'Read instance with {len(network.locations)} locations and {len(trolleys)} trolleys.')

network.setDiscretization(tickHours, tickZero)

class MIP:
  
  def __init__(self, network, usedTruckRoutesFileName):
    self._vtypeFlow = GRB.CONTINUOUS
    self._vtypeInventory = GRB.CONTINUOUS

    self._model = Model('PostNL')
    self._network = network
    self._minTick = 99999
    self._maxTick = -99999
    for k in network.commodities:
      tick = network.deadlineTick(k)
      if tick < self._minTick:
        self._minTick = tick
      if tick > self._maxTick:
        self._maxTick = tick
    self._nodes = list(self._network.locations)
    self._arcs = [ (i,j) for i in self._nodes for j in self._nodes ]
    self._varTruck = {}
    self._varFlow = {}
    self._varInventory = {}
    self._varNotDelivered = {}
    self._varNotProduced = {}
    self._varExtendedCapacity = {}
    self._varExtraDocks = {}
    self._undeliveredPenalty = 1e4
    self._extenedCapacityCost = 1e4
    self._extraDockPenalty = 1e4
    self._allowedTrucks = self.read_allowed_trucks(usedTruckRoutesFileName)

  def read_allowed_trucks(self, usedTruckRoutesFileName):

    if usedTruckRoutesFileName is None:
      return None

    allowedTrucks = set()

    f = open(usedTruckRoutesFileName, 'r')

    for line in f:
      split = line.split()
      source, target, time = int(split[1]), int(split[2]), float(split[3])
      allowedTrucks.add((source, target, (time - self.network._tickZero) / self.network._tickHours))
      # allowedTrucks.add((source, target, 1 + (time - self.network._tickZero) / self.network._tickHours))

    f.close()

    return allowedTrucks

  def scanTrolleys(self, trolleys):
    deliverableTrolleys = []
    first = True
    for t in trolleys:
      tick = network.trolleyReleaseTick(t)
      if self.network.trolleyReleaseTick(t) + self.network.travelTicks(t.source, t.commodity[0]) > self.network.deadlineTick(t.commodity):
        if first:
          print(f'Example for a trolley that cannot be delivered for time reasons: {t.source}<{self.network.name(t.source)}> -> {t.commodity[0]}<{self.network.name(t.commodity[0])}> within [{t.release},{self.network.deadline(t.commodity)}], but distance is {self.network.distance(t.source, t.commodity[0])}')
          print(f'Ticks are {self.network.trolleyReleaseTick(t)} + {self.network.travelTicks(t.source, t.commodity[0])} > {self.network.deadlineTick(t.commodity)}')
          first = False
        continue

      deliverableTrolleys.append(t)
      if tick < self._minTick:
        self._minTick = tick
      if tick > self._maxTick:
        self._maxTick = tick
    return deliverableTrolleys

  @property
  def network(self):
    return self._network

  @property
  def ticks(self):
    return range(self._minTick, self._maxTick+1)

  @property
  def nodes(self):
    return self._nodes

  @property
  def arcs(self):
    return self._arcs

  @property
  def truckvars(self):
    return self._varTruck

  @property
  def mintick(self):
    return self._minTick

  @property
  def maxtick(self):
    return self._maxTick

  def createTruckVars(self, free=False):
    print('Creating truck variables.')
    self._varTruck = {}
    allowedTrucks = self._allowedTrucks
    for (i,j) in self.arcs:
      for t in self.ticks:
        if t + self.network.travelTicks(i,j) <= max(self.ticks):
          obj = self.network.distance(i,j)
          ub = 9999.0
          if free:
            obj = 0.0
          if allowedTrucks != None and not (i,j,t) in allowedTrucks:
            ub = 0.0
          self._varTruck[i,j,t] = self._model.addVar(name=f'x#{i}#{j}#{t}', vtype=GRB.INTEGER, obj=obj, ub=ub)
    self._model.update()

  def createExtraDocksVars(self):
    print('Creating extra docks variables.')
    self._varExtraDocks = {}
    for i in self.nodes:
      self._varExtraDocks[i] = self._model.addVar(name=f'extradocks#{i}', obj=self._extraDockPenalty)
    self._model.update()

  def createTruckInfinite(self):
    self._varTruck = {}
    for (i,j) in self.arcs:
      for t in self.ticks:
        self._varTruck[i,j,t] = 1000
    self._model.update()

  def createFlowVars(self):
    print('Creating flow variables.')
    self._varFlow = {}
    for (i,j) in self.arcs:
      for t in self.ticks:
        if t + self.network.travelTicks(i,j) <= max(self.ticks):
          for target,shift in self.network.commodities:
            if self.network.isCross(j) or target == j:
              self._varFlow[i,j,t,target,shift] = self._model.addVar(name=f'y#{i}#{j}#{t}#{target}#{shift}', vtype=self._vtypeFlow)
    self._model.update()

  def createInventoryVars(self):
    print('Creating inventory variables.')
    self._varInventory = {}
    for i in self.nodes:
      for t in self.ticks:
        for target,shift in self.network.commodities:
          obj = 1.0e5 if t == max(self.ticks) else 0.0
          ub = 0 if t == max(self.ticks) else GRB.INFINITY
          self._varInventory[i,t,target,shift] = self._model.addVar(name=f'z#{i}#{t}#{target}#{shift}', vtype=self._vtypeInventory, obj=obj, ub=ub)
    self._model.update()

  def createNotDeliveredVars(self):
    print('Creating non-delivery variables.')
    self._varNotDelivered = {}
    for target,shift in self.network.commodities:
      self._varNotDelivered[target,shift] = self._model.addVar(name=f'notdeliver#{target}#{shift}', obj=self._undeliveredPenalty)
    self._model.update()

  def createNotProducedVars(self):
    print('Creating non-production variables.')
    production = {}
    demand = {}
    for t in trolleys:
      releaseTick = self.network.trolleyReleaseTick(t)
      production[t.source, releaseTick, t.commodity[0], t.commodity[1]] = production.get((t.source, releaseTick, t.commodity[0], t.commodity[1]), 0) + 1
      demand[t.commodity] = demand.get(t.commodity, 0) + 1

    self._varNotProduced = {}
    for i in self.nodes:
      for t in self.ticks:
        for target,shift in self.network.commodities:
          if (i,t,target,shift) in production:
            self._varNotProduced[i,t,target,shift] = self._model.addVar(name=f'notproduced#{i}#{t}#{target}#{shift}', obj=self._undeliveredPenalty)
    self._model.update()

  def createExtendedCapacityVars(self):
    print('Creating extended-capacity variables.')
    self._varExtendedCapacity = {}
    for i in self.nodes:
      self._varExtendedCapacity[i] = self._model.addVar(name=f'extcap#{i}', obj=self._extenedCapacityCost)

  def createCapacityConstraints(self):
    print('Creating truck capacity constraints.')
    for (i,j) in self.arcs:
      for t in self.ticks:
        if (i,j,t) in self._varTruck:
          self._model.addConstr( quicksum( self._varFlow[i,j,t,target,shift] for (target,shift) in self.network.commodities if (i,j,t,target,shift) in self._varFlow ) <= self.network.truckCapacity * self._varTruck[i,j,t], f'capacity#{i}#{j}#{t}')

  def createDockingConstraints(self):
    print('Creating docking capacity constraints.')
    loadingTicks = self.network.loadingTicks
    unloadingTicks = self.network.unloadingTicks
    for i in self.nodes:
      for t in self.ticks:
        departing = quicksum( self._varTruck[i,j,t-eta] for j in self.nodes for eta in range(loadingTicks) if (i,j,t) in self._varTruck )
        arriving = quicksum( self._varTruck[j,i,t-self.network.travelTicks(j,i)+unloadingTicks-eta] for j in self.nodes for eta in range(unloadingTicks) if (j,i,t-self.network.travelTicks(j,i)+unloadingTicks-eta) in self._varTruck )
        extraDocks = 0
        if i in self._varExtraDocks:
          extraDocks = self._varExtraDocks[i]
        self._model.addConstr( departing + arriving <= self.network.numDocksPerTick(i) + extraDocks, f'docking#{i}#{t}')

  def createFlowBalanceConstraints(self, trolleys):
    print('Creating flow balance constraints.')
    production = {}
    demand = {}
    for t in trolleys:
      releaseTick = self.network.trolleyReleaseTick(t)
      production[t.source, releaseTick, t.commodity[0], t.commodity[1]] = production.get((t.source, releaseTick, t.commodity[0], t.commodity[1]), 0) + 1
      demand[t.commodity] = demand.get(t.commodity, 0) + 1

    loadingTicks = self.network.loadingTicks
    unloadingTicks = self.network.unloadingTicks
    sumRhs = 0
    for i in self.nodes:
      for t in self.ticks:
        for target,shift in self.network.commodities:
          oldInventory = self._varInventory.get((i,t-1,target,shift), 0.0)
          newInventory = self._varInventory[i,t,target,shift]
          outFlow = quicksum( self._varFlow.get((i,j,t,target,shift), 0.0) for j in self.nodes if t+self.network.travelTicks(i,j) in self.ticks)
          inFlow = quicksum( self._varFlow.get((j,i,t-self.network.travelTicks(j,i),target,shift), 0.0) for j in self.nodes )
          produced = production.get((i,t,target,shift), 0)
          sumRhs += produced
          if i == target and t == self.network.deadlineTick((target,shift)):
            consumed = demand.get((target,shift), 0) - self._varNotDelivered.get((target,shift), 0.0)
            sumRhs -= demand.get((target,shift), 0)
          else:
            consumed = 0
          if produced > 0 and (i,t,target,shift) in self._varNotProduced:
            self._varNotProduced[i,t,target,shift].ub = produced
            produced = produced - self._varNotProduced[i,t,target,shift]
          self._model.addConstr( newInventory - oldInventory + outFlow - inFlow == produced - consumed, f'flow_balance#{i}#{t}#{target}#{shift}')
    if sumRhs != 0:
      assert 'Total flow balance of network is nonzero!' == None

  def createSourceCapacityConstraints(self):
    print('Creating source capacity constraints.')
    for i in self.nodes:
      for t in self.ticks:
        self._model.addConstr( quicksum( self._varInventory.get((i,t,target,shift), 0.0) for target,shift in self.network.commodities if target != i) <= self.network.sourceCapacity(i) + self.network.crossCapacity(i))
    
  def createTargetCapacityConstraints(self):
    print('Creating target capacity constraints.')
    for i in self.nodes:
      for t in self.ticks:
        lhs = quicksum( self._varFlow.get((j,i,t-self.network.travelTicks(j,i),target,shift), 0.0) for j in self.nodes for target,shift in self.network.commodities )
        for target,shift in self.network.commodities:
          if target == i and t < self.network.deadlineTick((target,shift)):
            lhs += self._varInventory.get((i,t,target,shift), 0.0)
        self._model.addConstr( lhs <= self.network.targetCapacity(i) )

  def constructInitialSolution(self, trolleys):

    network = self.network
    truck_vars = self.truckvars
    mintick = self.mintick
    maxtick = self.maxtick
    truck_capacity = network.truckCapacity

    # collect information about releasing the trolleys over time
    depot_inventories = {}
    sources = set()
    targets = set()
    duetimes = set()
    for t in trolleys:
      releaseTick = network.trolleyReleaseTick(t)
      source = t.source
      target = t.commodity[0]
      depot_inventories[source, releaseTick, target] = depot_inventories.get((source, releaseTick, target), 0) + 1
      sources.add(source)
      targets.add(target)

    # derive truck departures from depot_inventories
    departures = {}
    corrections = {}
    for rt in range(mintick, maxtick+1):
      for s in sources:
        for t in targets:
          if depot_inventories.get((s,rt,t),0) >= truck_capacity:
            truck_vars[s,t,rt].Start = math.ceil(depot_inventories[s,rt,t] / truck_capacity)
            corrections[s,rt,t] = corrections.get((s,rt,t), 0) + depot_inventories[s,rt,t]
            depot_inventories[s,rt,t] = depot_inventories[s,rt,t] - corrections[s,rt,t]

          # elif depot_inventories.get((s,rt,t),0) > 0 and depot_inventories.get((s,rt,t),0) == depot_inventories.get((s,rt-2,t),0):
          elif depot_inventories.get((s,rt,t),0) > 0 and not (s,t,rt+1) in truck_vars:
            truck_vars[s,t,rt].Start = math.ceil(depot_inventories[s,rt,t] / truck_capacity)
            corrections[s,rt,t] = corrections.get((s,rt,t), 0) + depot_inventories[s,rt,t]
            depot_inventories[s,rt,t] = depot_inventories[s,rt,t] - corrections[s,rt,t]

          elif rt < maxtick and depot_inventories.get((s,rt,t),0) > 0:
            depot_inventories[s,rt+1,t] = depot_inventories.get((s,rt+1,t),0) + depot_inventories[s,rt,t]
            if (s,t,rt) in truck_vars:
              truck_vars[s,t,rt].Start = 0.0

    # for s in sources:
    #   for t in targets:
    #     print(s,t)
    #     yvals = [depot_inventories.get((s,j,t),0) for j in range(mintick, maxtick+1)]
    #     fig, ax1 = plt.subplots()

    #     lns1 = ax1.plot(range(mintick, maxtick+1), yvals)
    #     plt.show()

  def constructInitialSolutionLog(self, logfile):

    f = open(logfile, 'r')

    network = self.network
    truck_vars = self.truckvars
    mintick = self.mintick
    maxtick = self.maxtick
    truck_capacity = network.truckCapacity

    for line in f:
      split = line.split()
      source, target, tick, num = int(split[1]), int(split[2]), int(split[3]), int(split[4])
      truck_vars[source,target,tick].Start = num

    f.close()


  def optimize(self):
    self._model.optimize()
    return self._model.status

  def write(self, fileName):
    self._model.write(fileName)

  def writeUsedTrucks(self, fileName):
    f = open(fileName, 'w')
    for (i,j) in self.arcs:
      for t in self.ticks:
        if t + self.network.travelTicks(i,j) <= max(self.ticks):
          if self._varTruck[i,j,t].x > 0.5:
            f.write(f'T {i} {j} {self.network.tickTime(t)}\n')
    f.close()

  def printSolution(self):
    loadingTicks = self.network.loadingTicks
    unloadingTicks = self.network.unloadingTicks
    totalDrivingDistance = 0.0

    f = open("log%f.txt" % time.time(), 'w')

    for (i,j) in self.arcs:
      for t in self.ticks:
        if t + self.network.travelTicks(i,j) <= max(self.ticks):
          if self._varTruck[i,j,t].x > 0.5:
            totalDrivingDistance += self._varTruck[i,j,t].x * self._varTruck[i,j,t].obj
            usage = 0.0
            for target,shift in self.network.commodities:
              if (i,j,t,target,shift) in self._varFlow and self._varFlow[i,j,t,target,shift].x > 1.0e-4:
                usage += self._varFlow[i,j,t,target,shift].x
            print(f'Truck from {i}<{self.network.name(i)}> to {j}<{self.network.name(j)}> at tick {t} -> {t + self.network.travelTicks(i,j)}, carrying {round(usage,2)} trolleys.')
            f.write(f'TT {i} {j} {t} {math.ceil(round(usage,2) / self._network.truckCapacity)}\n')

            for target,shift in self.network.commodities:
              if (i,j,t,target,shift) in self._varFlow and self._varFlow[i,j,t,target,shift].x > 1.0e-4:
                print(f'  It carries {round(self._varFlow[i,j,t,target,shift].x,2)} trolleys of commodity {target}<{self.network.name(target)}>,{shift} from {i}<{self.network.name(i)}> to {j}<{self.network.name(j)}> at tick {t} -> {t + self.network.travelTicks(i,j)}.')
    for target,shift in self.network.commodities:
      if (target,shift) in self._varNotDelivered and self._varNotDelivered[target,shift].x > 0.5:
        print(f'Commodity {target}<{self.network.name(target)}>,{shift} has {round(self._varNotDelivered[target,shift].x,0)} undelivered trolleys.')
      for i in self.nodes:
        for t in self.ticks:
          if (i,t,target,shift) in self._varNotProduced and self._varNotProduced[i,t,target,shift].x > 0.5:
            print(f'Commodity {target}<{self.network.name(target)}>,{shift} has {round(self._varNotProduced[i,t,target,shift].x,0)} trolleys not produced in {i}<{self.network.name(i)}> at tick {t}.')
    print(f'Total driving distance is {totalDrivingDistance}.')

    f.close()

requiredTrolleys = [ t for t in trolleys if t.source != t.commodity[0] ]
print(f'{len(trolleys) - len(requiredTrolleys)} trolleys have origin = destination.')

mip = MIP(network, usedTruckRoutesFileName)
deliverableTrolleys = mip.scanTrolleys(requiredTrolleys)
print(f'Ticks are in range [{min(mip.ticks)},{max(mip.ticks)}].')
print(f'{len(requiredTrolleys) - len(deliverableTrolleys)} trolleys cannot be delivered for time reasons.')
mip.createTruckVars(False)
# mip.createTruckVars(True)
mip.createFlowVars()
mip.createInventoryVars()
# mip.createExtraDocksVars()
# mip.createNotDeliveredVars()
# mip.createNotProducedVars()
# mip.createExtendedCapacityVars()
mip.createCapacityConstraints()
mip.createSourceCapacityConstraints()
mip.createTargetCapacityConstraints()
mip.createFlowBalanceConstraints(deliverableTrolleys)
mip.createDockingConstraints()

# mip.constructInitialSolution(requiredTrolleys)
# mip.constructInitialSolutionLog("log.txt") # requires a log file from a previous run that contains the used trucks

status = mip.optimize()

if status != GRB.INFEASIBLE and status != GRB.INF_OR_UNBD and status != GRB.UNBOUNDED:
  mip.printSolution()
  if usedTrucksOutputFileName != None:
    mip.writeUsedTrucks(usedTrucksOutputFileName)


#mip.write('mip.lp')

#status = mip.optimize()
#removedTrolleys = {}
#for i in mip.nodes:
#  for t in mip.ticks:
#    for target,shift in mip.network.commodities:
#      removed = int(round(mip._varNotProduced[i,t,target,shift].x)) if (i,t,target,shift) in mip._varNotProduced else 0
#      if removed > 0:
#        removedTrolleys[(i,t,target,shift)] = removedTrolleys.get((i,t,target,shift), 0) + removed
#print(removedTrolleys)
#print(len(removedTrolleys))
#
#sys.exit(0)

#mip = MIP(network)
#mip.scanTrolleys(trolleys)
#
#print(f'Ticks are in range [{min(mip.ticks)},{max(mip.ticks)}].')

#mip.createTruckVars()
#mip.createFlowVars()
#mip.createInventoryVars()
#mip.createNotDeliveredVars()
#mip.createNotProducedVars()
#mip.createExtendedCapacityVars()
#mip.createCapacityConstraints()
#mip.createDockingConstraints()
#mip.createSourceCapacityConstraints()
#mip.createTargetCapacityConstraints()
#mip.createFlowBalanceConstraints(trolleys[:len(trolleys)])

#mip.write('mip.lp')
#status = mip.optimize()
#mip.printSolution()


