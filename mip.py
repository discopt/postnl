import sys
from gurobipy import *
from common import *
import matplotlib.pyplot as plt
import math
import time

def time2tick(time, timeshift, ticklen):
    return int((time - timeshift) / ticklen)

def printUsage(errorMessage=None):
  if errorMessage is not None:
    print(f'Error: {errorMessage}')
  print(f'Usage: {sys.argv[0]} <network file name> <tickhours> <tickzero> <trolleys file name> [OPTIONS...]')
  print('Solves the MIP for network and trolleys, discretizing tickhours hours with offset tickzero hours.')
  print('Options:')
  print('  -o FILE  Write used trucks to <FILE>.')  
  print('  -i FILE  Read used trucks from <FILE>.')
  print('  -t TIME  After a feasible solution was, the solve has TIME seconds for solving.')
  print('  -d DEV   Truck times may deviate up to DEV hours from the ones read from <FILE> to be considered allowed.')
  print('  -m       Modify trolleys to become deliverable instead of removing them.')
  print('  -c       Construct initial solution from that input file.')
  sys.exit(1)

class MIP:
  
  def __init__(self, network, readTrucksFileName, allowedTruckDeviation):
    self._vtypeFlow = GRB.CONTINUOUS
    self._vtypeInventory = GRB.CONTINUOUS

    self._model = Model('PostNL')
    self._model.params.threads = 4
    self._model.params.startNodeLimit = 1
    self._model.params.MIPFocus = 1
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
    self._undeliveredPenalty = 10
    self._extendedCapacityCost = 10
    self._extraDockPenalty = 10

    self._allowedTruckDeviation = allowedTruckDeviation
    self.readAllowedTrucks(readTrucksFileName)
  
  def readAllowedTrucks(self, readTrucksFileName):
    if readTrucksFileName is None:
      self._allowedTrucks = None
    else:
      self._allowedTrucks = {}

      f = open(readTrucksFileName, 'r')
      for line in f:
        if not line.startswith('T'):
          continue
        split = line.split()
        source, target, time = int(split[1]), int(split[2]), float(split[3])
        if (source,target) in self._allowedTrucks:
          self._allowedTrucks[source,target].add(time)
        else:
          self._allowedTrucks[source,target] = set([time])
      f.close()

  def setTimeHorizon(self, trolleys):
    for t in trolleys:
      tick = self.network.trolleyReleaseTick(t)
      if tick < self._minTick:
        self._minTick = tick
      if tick > self._maxTick:
        self._maxTick = tick

  def filterDeliverableTrolleys(self, trolleys):
    return [ t for t in trolleys if self.network.trolleyReleaseTick(t) + self.network.travelTicks(t.source, t.commodity[0]) <= self.network.deadlineTick(t.commodity) ]

  def makeTrolleysDeliverable(self, trolleys):
    modifiedTrolleys = []
    countModifications = 0
    for t in trolleys:
      if self.network.trolleyReleaseTick(t) + self.network.travelTicks(t.source, t.commodity[0]) > self.network.deadlineTick(t.commodity):
        newRelease = self.network.tickTime( self.network.deadlineTick(t.commodity) - self.network.travelTicks(t.source, t.commodity[0]) )
        t = Trolley(t.source, newRelease, t.commodity)
        countModifications += 1
      assert self.network.trolleyReleaseTick(t) + self.network.travelTicks(t.source, t.commodity[0]) <= self.network.deadlineTick(t.commodity)
      modifiedTrolleys.append(t)
    return modifiedTrolleys, countModifications

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

  def createTruckVars(self, forFree=False):
    print('Creating truck variables.')
    self._varTruck = {}
    for (i,j) in self.arcs:
      for t in self.ticks:
        if t + self.network.travelTicks(i,j) <= max(self.ticks):
          obj = self.network.distance(i,j)
          ub = 9999.0
          if forFree:
            obj = 0.0
          if not self._allowedTrucks is None:
            if not (i,j) in self._allowedTrucks:
#              print(f'Disallowing truck route from {i} to {j} completely.')
              ub = 0.0
            else:
              dist = min( math.fabs(self.network.tickTime(t) - at) for at in self._allowedTrucks[i,j])
              if dist > self._allowedTruckDeviation:
#                print(f'Disallowing truck route from {i} to {j} at tick {t} = time {self._network.tickTime(t)} because of distance {dist}.')
                ub = 0.0
          if ub > 0.0:
            self._varTruck[i,j,t] = self._model.addVar(name=f'x#{i}#{j}#{t}', vtype=GRB.INTEGER, obj=obj, ub=ub)
          else:
            self._varTruck[i,j,t] = 0.0 # We still add the dict entry since some loops go through its keys.
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
        self._varTruck[i,j,t] = 1000.0
    self._model.update()

  def createFlowVars(self):
    print('Creating flow variables.')
    self._varFlow = {}
    for (i,j) in self.arcs:
      for t in self.ticks:
        if t + self.network.travelTicks(i,j) <= max(self.ticks):
          for target,shift in self.network.commodities:
            if (target == j and t + self.network.travelTicks(i,j) <= self.network.deadlineTick((target,shift))) or (self.network.isCross(j) and t + self.network.travelTicks(i,j) + self.network.travelTicks(j,target) <= self.network.deadlineTick((target,shift))):
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
          if ub > 0:
            self._varInventory[i,t,target,shift] = self._model.addVar(name=f'z#{i}#{t}#{target}#{shift}', vtype=self._vtypeInventory, obj=obj, ub=ub)
    self._model.update()

  def createNotDeliveredVars(self):
    print('Creating non-delivery variables.')
    self._varNotDelivered = {}
    for target,shift in self.network.commodities:
      self._varNotDelivered[target,shift] = self._model.addVar(name=f'notdeliver#{target}#{shift}', obj=self._undeliveredPenalty)
    self._model.update()

  def createNotProducedVars(self, trolleys):
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
            self._varNotProduced[i,t,target,shift] = self._model.addVar(name=f'notproduced#{i}#{t}#{target}#{shift}', ub=production[i,t,target,shift], obj=self._undeliveredPenalty)
    self._model.update()

  def createExtendedCapacityVars(self):
    print('Creating extended-capacity variables.')
    self._varExtendedCapacity = {}
    for i in self.nodes:
      self._varExtendedCapacity[i] = self._model.addVar(name=f'extcap#{i}', obj=self._extendedCapacityCost)

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
          newInventory = self._varInventory.get((i,t,target,shift), 0.0)
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
        # for non-crossdocks: total inventory of commodities with difference destination <= 400
        # for crossdocks: total inventory of commodities with difference destination <= 400 + big number
        self._model.addConstr( quicksum( self._varInventory.get((i,t,target,shift), 0.0) for target,shift in self.network.commodities if target != i) <= self.network.sourceCapacity(i) + self.network.crossCapacity(i))
    
  def createTargetCapacityConstraints(self):
    print('Creating target capacity constraints.')
    for i in self.nodes:
      for t in self.ticks:
        # inventory of all commodities with this location as destination <= 1200
        self._model.addConstr( quicksum( self._varInventory.get((i,t,target,shift), 0.0) for target,shift in self.network.commodities if target == i) <= self.network.targetCapacity(i) )

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

    # do nothing if no file has been provided
    if logfile is None:
      return

    f = open(logfile, 'r')

    network = self.network
    truck_vars = self.truckvars
    mintick = self.mintick
    maxtick = self.maxtick
    truck_capacity = network.truckCapacity

    # read the capacities used by the trucks in the previous solution
    for line in f:
      split = line.split()
      if split and split[0] == 'C':
        source, target, time, num = int(split[1]), int(split[2]), float(split[3]), int(split[4])
        tick = network.timeTick(time)
        if (source,target,tick) in truck_vars and not isinstance(truck_vars[source,target,tick], float):
          truck_vars[source,target,tick].start = num
    f.close()


  def optimize(self):
    self._model.optimize()
    return self._model.status

  def setSollimit(self, limit):
    self._model.Params.SolutionLimit = limit

  def setTimelimit(self, limit):
    self._model.Params.TimeLimit = limit

  def getRuntime(self):
    return self._model.Runtime

  def getSolutionValue(self):
    if self._model.status in [GRB.INFEASIBLE, GRB.INF_OR_UNBD, GRB.UNBOUNDED]:
      return None

    totalDistance = 0.0
    totalPenalty = 0.0
    countNotProduced = 0.0
    countNotDelivered = 0.0
    for var in self._varTruck.values():
      if not isinstance(var, float):
        if var.x > 0.5:
          totalDistance += round(var.x,0) * var.obj
    for var in self._varNotProduced.values():
      if not isinstance(var, float):
        if var.x > 0.01:
          countNotProduced += var.x
          print(f'not produced: {var.x}')
    for var in self._varNotDelivered.values():
      if not isinstance(var, float):
        if var.x > 0.01:
          countNotDelivered += var.x
          print(f'not delivered: {var.x}')
    totalPenalty = self._model.objVal - totalDistance
    return self._model.objVal, totalDistance, totalPenalty, countNotProduced, countNotDelivered

  def write(self, fileName):
    self._model.write(fileName)

  def writeUsedTrucks(self, fileName):
    if fileName is None or self._model.status in [GRB.INFEASIBLE, GRB.INF_OR_UNBD, GRB.UNBOUNDED]:
      return False

    f = open(fileName, 'w')
    vals = self.getSolutionValue()
    assert vals
    f.write(f'OBJ {vals[0]}\n')
    f.write(f'DIST {vals[1]}\n')
    f.write(f'PEN {vals[2]}\n')
    f.write(f'NPRO {vals[3]}\n')
    f.write(f'NDEL {vals[4]}\n')
    f.write('\n')

    for k in self._varInventory.keys():
      f.write(f'I {k} {self._varInventory[k].X}\n')

    for (i,j) in self.arcs:
      for t in self.ticks:
        if t + self.network.travelTicks(i,j) <= max(self.ticks):
          if (i,j,t) in self._varTruck and not isinstance(self._varTruck[i,j,t], float) and self._varTruck[i,j,t].x > 0.5:
            f.write(f'T {i} {j} {self.network.tickTime(t)}\n')

    f.write('\n')

    for (i,j) in self.arcs:
      for t in self.ticks:
        if t + self.network.travelTicks(i,j) <= max(self.ticks):
          if (i,j,t) in self._varTruck and not isinstance(self._varTruck[i,j,t], float) and self._varTruck[i,j,t].x > 0.5:
            usage = 0.0
            for target,shift in self.network.commodities:
              if (i,j,t,target,shift) in self._varFlow and self._varFlow[i,j,t,target,shift].x > 1.0e-4:
                usage += self._varFlow[i,j,t,target,shift].x
                f.write(f'S {i} {j} {target} {shift} {self.network.tickTime(t)} {math.ceil(round(self._varFlow[i,j,t,target,shift].x,2))}\n')
            f.write(f'C {i} {j} {self.network.tickTime(t)} {math.ceil(round(usage,2) / self._network.truckCapacity)}\n')
    f.close()
    return True

  def printSolution(self):
    loadingTicks = self.network.loadingTicks
    unloadingTicks = self.network.unloadingTicks
    totalDrivingDistance = 0.0
    totalUndelivered = 0
    totalNotproduced = 0

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

            for target,shift in self.network.commodities:
              if (i,j,t,target,shift) in self._varFlow and self._varFlow[i,j,t,target,shift].x > 1.0e-4:
                print(f'  It carries {round(self._varFlow[i,j,t,target,shift].x,2)} trolleys of commodity {target}<{self.network.name(target)}>,{shift} from {i}<{self.network.name(i)}> to {j}<{self.network.name(j)}> at tick {t} -> {t + self.network.travelTicks(i,j)}.')
    for target,shift in self.network.commodities:
      if (target,shift) in self._varNotDelivered and self._varNotDelivered[target,shift].x > 0.5:
        print(f'Commodity {target}<{self.network.name(target)}>,{shift} has {round(self._varNotDelivered[target,shift].x,0)} undelivered trolleys.')
        totalUndelivered += round(self._varNotDelivered[target,shift].x,0)
      for i in self.nodes:
        for t in self.ticks:
          if (i,t,target,shift) in self._varNotProduced and self._varNotProduced[i,t,target,shift].x > 0.5:
            print(f'Commodity {target}<{self.network.name(target)}>,{shift} has {round(self._varNotProduced[i,t,target,shift].x,0)} trolleys not produced in {i}<{self.network.name(i)}> at tick {t} (deadline {self.network.deadlineTick((target,shift))}).')
            totalNotproduced += round(self._varNotProduced[i,t,target,shift].x,0)
    print(f'Total driving distance is {totalDrivingDistance}.')
    print(f'Total number of undelivered trolleys is {totalUndelivered}.')
    print(f'Total number of not produced trolleys is {totalNotproduced}.')




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

def run_experiments(network, trolleys, tickHours, tickZero, modifyTrolleysDeliverable, writeTrucksFileName, readTrucksFileName, allowedTruckDeviation, constructInitial, timeLimit, solutionLimit, solutionTimeLimit):

  print(f'Read instance with {len(network.locations)} locations and {len(trolleys)} trolleys.')

  network.setDiscretization(tickHours, tickZero)

  requiredTrolleys = [ t for t in trolleys if t.source != t.commodity[0] ]
  print(f'Removed {len(trolleys) - len(requiredTrolleys)} trolleys having equal origin and destination.')

  mip = MIP(network, readTrucksFileName, allowedTruckDeviation)

  if modifyTrolleysDeliverable:
    trolleys,numModifications = mip.makeTrolleysDeliverable(requiredTrolleys)
    print(f'Modified {numModifications} trolley release times to make them deliverable.')
  else:
    trolleys = mip.filterDeliverableTrolleys(requiredTrolleys)
    print(f'Kept {len(trolleys)} of {len(requiredTrolleys)} deliverable trolleys.')

  mip.setTimeHorizon(trolleys)
  print(f'Ticks are in range [{min(mip.ticks)},{max(mip.ticks)}].')

  mip.createTruckVars(forFree=False)
  mip.createFlowVars()
  mip.createInventoryVars()
  mip.createExtraDocksVars()
  mip.createNotDeliveredVars()
  mip.createNotProducedVars(trolleys)
  mip.createExtendedCapacityVars()
  mip.createCapacityConstraints()
  mip.createSourceCapacityConstraints()
  mip.createTargetCapacityConstraints()
  mip.createFlowBalanceConstraints(trolleys)
  mip.createDockingConstraints()

  if constructInitial:
     mip.constructInitialSolutionLog(readTrucksFileName)

  status = None
  currentTime = 0.0

  # if we use a solution limit together with a time limit
  if not solutionLimit is None:
    mip.setSollimit(solutionLimit)
    mip.setTimelimit(timeLimit)
    status = mip.optimize()
    mip.setSollimit(1000)
    mip.setTimelimit(min(solutionTimeLimit, max(0, timeLimit - mip.getRuntime())))
    status = mip.optimize()

    vals = mip.getSolutionValue()
    mip.writeUsedTrucks(writeTrucksFileName)
    return vals

  # Run the code to produce one solution in case we do not read an initial solution
  if readTrucksFileName is None:
    mip.setSollimit(1)
    mip.optimize()
    currentTime = mip.getRuntime()

  # Continue running the code until it hits a time limit (or finds an optimal solution)
  mip.setSollimit(1000)
  mip.setTimelimit(currentTime + timeLimit)
  mip.optimize()

  vals = mip.getSolutionValue()
  mip.writeUsedTrucks(writeTrucksFileName)
  return vals

if __name__ == "__main__":

  if len(sys.argv) < 5:
    printUsage('Requires 4 arguments.')

  network = Network(sys.argv[1])
  tickHours = float(sys.argv[2])
  tickZero = float(sys.argv[3])
  trolleys = network.readTrolleys(sys.argv[4])

  writeTrucksFileName = None
  readTrucksFileName = None
  allowedTruckDeviation = 1e4
  modifyTrolleysDeliverable = False
  timeLimit = 86400
  constructInitial = False
  a = 5
  while a < len(sys.argv):
    arg = sys.argv[a]
    if arg == '-o' and a+1 < len(sys.argv):
      writeTrucksFileName = sys.argv[a+1]
      a += 1
    elif arg == '-i' and a+1 < len(sys.argv):
      readTrucksFileName = sys.argv[a+1]
      a += 1
    elif arg == '-t' and a+1 < len(sys.argv):
      timeLimit = float(sys.argv[a+1])
      a += 1
    elif arg == '-d' and a+1 < len(sys.argv):
      allowedTruckDeviation = float(sys.argv[a+1])
      a += 1
    elif arg == '-m':
      modifyTrolleysDeliverable = True
    elif arg == '-c':
      constructInitial = True
    else:
      printUsage(f'Unprocessed argument <{arg}>.')
    a += 1

  vals = run_experiments(network=network, trolleys=trolleys, tickHours=tickHours, tickZero=tickZero,
    modifyTrolleysDeliverable=modifyTrolleysDeliverable, writeTrucksFileName=writeTrucksFileName,
    readTrucksFileName=readTrucksFileName, allowedTruckDeviation=allowedTruckDeviation, constructInitial=constructInitial,
    timeLimit=timeLimit, solutionLimit=None, solutionTimeLimit=60)

  if vals is None:
    print(f'No solution found.')
  else:
      print(f'The best incumbent solution has value {vals[0]} with total distance {vals[1]:.2f} and penalties {vals[2]:.1f} ({vals[3]:.1f} not produced and {vals[4]:.1f} not delivered.')

