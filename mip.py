from gurobipy import *
import math
import sys
import time
from network import *

##################################
# AUXILIARY METHODS
##################################

def is_crossdock_capacity(capacity):
    '''
    returns whether `capacity` is the capacity of a cross dock
    '''

    return capacity == 99999


def pathname(p):
    '''
    returns name of path as string
    '''

    name = str(p[0])
    for i in range(1, len(p)):
        name += "_" + str(p[i])
    return name

def is_arc_in_path(a, p):
    '''
    returns whether an arc is contained in a path
    '''

    for i in range(len(p) - 1):
        if p[i] == a[0] and p[i+1] == a[1]:
            return True

    return False


def read_data(datafile):
    '''
    reads data from file and returns
    
    distances: dictionary mapping [origin][destination] to distance
    demand: dictionary mapping [origin][destination] to number of trolleys
    '''

    f = open(datafile, 'r')

    distances = {}
    hourlyDistances = {}
    demand = dict()
    depots = []
    crossdocks = []
    ticksize = 0

    for line in f:

        if line.startswith('d'):
            origin = int(line.split()[1])
            dest = int(line.split()[2])
            dist = int(line.split()[3])
            hourlyDist = float(line.split()[4])

            if not origin in distances:
                distances[origin] = {dest: dist}
                hourlyDistances[origin] = {dest: hourlyDist}
            else:
                distances[origin][dest] = dist
                hourlyDistances[origin][dest] = hourlyDist

        elif line.startswith('t'):
            origin = int(line.split()[2])
            dest = int(line.split()[3])
            release = int(line.split()[4])
            deadline = int(line.split()[5])

            if deadline == 0:
                print(origin, dest, release, deadline)

            if origin == dest:
              pass
            elif not origin in demand:
                demand[origin] = {dest: {release: {deadline: 1}}}
            elif not dest in demand[origin]:
                demand[origin][dest] = {release: {deadline: 1}}
            elif not release in demand[origin][dest]:
                demand[origin][dest][release] = {deadline: 1}
            elif not deadline in demand[origin][dest][release]:
                demand[origin][dest][release][deadline] = 1
            else:
                demand[origin][dest][release][deadline] = demand[origin][dest][release][deadline] + 1

        elif line.startswith('p'):
            idx = int(line.split()[1])
            outcapacity = int(line.split()[8])

            if is_crossdock_capacity(outcapacity):
                crossdocks.append(idx)
            else:
                depots.append(idx)

        elif line.startswith('T'):
            ticksize = float(line.split()[1])

    f.close()

    return distances, hourlyDistances, demand, depots, crossdocks, ticksize

def read_solution_stage_01(solufile):
    '''
    reads and returns solution from stage 1
    '''

    f = open(solufile, 'r')

    allowed_arcs = []
    allowed_transportation = []

    for line in f:
        if line.startswith("x "):
            (u,v) = (int(line.split()[1]), int(line.split()[2]))
            allowed_arcs.append((u,v))
        elif line.startswith("y "):
            (u,v,w) = (int(line.split()[1]), int(line.split()[2]), int(line.split()[3]))
            allowed_transportation.append((u,v,w))

    f.close()

    allowed_transportation = set(allowed_transportation)

    return allowed_arcs, allowed_transportation

def read_solution_stage_02(solufile):
    '''
    reads and returns solution from stage 2
    '''

    f = open(solufile, 'r')

    allowed_arcs = []

    for line in f:
        if line.startswith("x "):
            (u,v,t) = (int(line.split()[1]), int(line.split()[2]), int(line.split()[3]))
            allowed_arcs.append((u,v,t))
    f.close()

    return (allowed_arcs, None)

##################################
# METHODS FOR BUILDING THE MODEL
##################################

class MIP:

  def __init__(self, network):
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

  def scanTrolleys(self, trolleys):
    deliverableTrolleys = []
    first = True
    for t in trolleys:
      tick = network.trolleyReleaseTick(t)
#      if self.network.trolleyReleaseTick(t) + self.network.travelTicks(t.source, t.commodity[0]) > self.network.deadlineTick(t.commodity):
#        if first:
#          print(f'Example for a trolley that cannot be delivered for time reasons: {t.source}<{self.network.name(t.source)}> -> {t.commodity[0]}<{self.network.name(t.commodity[0])}> within [{t.release},{self.network.deadline(t.commodity)}], but distance is {self.network.distance(t.source, t.commodity[0])}')
#          print(f'Ticks are {self.network.trolleyReleaseTick(t)} + {self.network.travelTicks(t.source, t.commodity[0])} > {self.network.deadlineTick(t.commodity)}')
#          first = False
#        continue

      deliverableTrolleys.append(t)
      if tick < self._minTick:
        self._minTick = tick
      if tick > self._maxTick:
        self._maxTick = tick

    return deliverableTrolleys
  
  def computeBalance(self, trolleys):
    productions = {}
    demands = {}
    for t in trolleys:
      if t.source == t.commodity[0]:
        continue
      releaseTick = self.network.trolleyReleaseTick(t)
      deadlineTick = self.network.deadlineTick(t.commodity)
      productions[t.source, releaseTick, t.commodity[0], deadlineTick] = productions.get((t.source, releaseTick, t.commodity[0], deadlineTick), 0) + 1
      demands[t.commodity[0], deadlineTick, t.commodity[0], deadlineTick] = demands.get((t.commodity[0], deadlineTick, t.commodity[0], deadlineTick), 0) + 1
    return productions,demands

  @property
  def network(self):
    return self._network

  @property
  def ticks(self):
    return range(self._minTick, self._maxTick+1)




  def create_truck_variables(self):
    '''
    returns dictionary of truck variables
    '''

    self.truck_vars = {}
    for (i,j) in self.network.connections:
        for t in self.ticks:
          if t + self.network.distanceTicks(i,j) in self.ticks:
            self.truck_vars[i,j,t] = self.model.addVar(vtype=GRB.INTEGER, name="arc_%d_%d_%d" % (i,j,t), obj=self.network.distance(i,j))

  def create_shift_variables(self, mergedCommodities, is_integer):
    '''
    returns dictionary of shift variables
    '''

    vtype = GRB.INTEGER if is_integer else GRB.CONTINUOUS
    self.shift_vars = {}
    for (i,j) in self.network.connections:
      for ci,ct in mergedCommodities:
        for t in self.ticks:
          if (ci == j and t + self.network.distanceTicks(i,j) <= ct) or (ci != j and self.network.isCross(j) and t + self.network.distanceTicks(i,j) + self.network.distanceTicks(j,ci) <= ct):
            self.shift_vars[i,j,ci,ct,t] = self.model.addVar(vtype=vtype, name="shift%d_%d_%d_%d_%d" % (i,j,ci,ct,t), obj=0.0)

  def create_inventory_variables(self, mergedCommodities, signed_locations):
    '''
    returns dictionary of inventory variables
    '''

    inventory_vars = dict()

    for (i,j) in signed_locations: # j=1 in-depot, j=0: out-depot, j=-1 cross
        for ci,ct in mergedCommodities:
            for t in self.ticks:
                inventory_vars[(i,j,ci,ct,t)] = self.model.addVar(vtype=GRB.CONTINUOUS, name="inventory(%d_%d)_%d_%d_%d" % (i,j,ci,ct,t), obj=0.0)

    self.inventory_vars = inventory_vars

#  def create_not_delivered_vars(self, mergedCommodities, indepots):
#
#    not_delivered_vars = dict()
#
#    for (i,j) in indepots:
#        for (s,st) in mergedCommodities:
#            not_delivered_vars[(i,s,st)] = 0
#            # not_delivered_vars[(i,s,st)] = model.addVar(vtype=GRB.CONTINUOUS, name="notdelivered_%d_(%d_%d)" % (i,s,st), obj=1.0)
#
#    self.not_delivered_vars = not_delivered_vars

  def create_not_increasedcap_vars(self, outdepots):

    not_increasedcap_vars = dict()

    for i in self.network.locations:
      for t in self.ticks:
        not_increasedcap_vars[(i,t)] = self.model.addVar(vtype=GRB.CONTINUOUS, name="notinccap_%d_%d" % (i,t), obj=1.0)

    self.not_increasedcap_vars = not_increasedcap_vars

  def create_capacity_constraints(self, mergedCommodities):
    '''
    Creates and adds capacity constraints.
    '''
    for (i,j) in self.network.connections:
      for t in self.ticks:
        self.model.addConstr( quicksum(self.shift_vars.get((i,j,ci,ct,t), 0.0) for ci,ct in mergedCommodities) <= self.network.truckCapacity * self.truck_vars.get((i,j,t), 0.0))

  def create_depot_truck_capacity_constraints(self, locations, depots):
    '''
    Creates and adds depot truck capacity constraints.
    '''

    for i in self.network.locations:
      for t in self.ticks:
        self.model.addConstr( quicksum(self.truck_vars.get((i,j,t-eta), 0.0) for j in self.network.locations for eta in range(max(1,min(t+1,self.network.loadingTicks))) if j != i and (i,j,t-eta) in self.ticks)
                             +
                             quicksum(self.truck_vars.get((j,i,t-eta-self.network.distanceTicks(j,i)-self.network.loadingTicks), 0.0) for j in locations for eta in range(min(0,max(1,min(t+1+self.network.distanceTicks(j,i)+self.network.loadingTicks,self.network.unloadingTicks)))) if j != i)
                             <= self.network.numDocksPerTick(i)) # TODO: unloading_time=0 still implies that the truck blocks it for 1 tick! Is this desired?

  def create_out_capacity_constraints(self, mergedCommodities, depots):
    '''
    Creates and adds out capacity constraints.
    '''
    for i in self.network.locations:
      for t in self.ticks:
        self.model.addConstr( quicksum(self.inventory_vars[(i,0,ci,ct,t)] for ci,ct in mergedCommodities) <= self.network.originCapacity(i))

  def create_in_capacity_constraints(self, mergedCommodities, depots):
    '''
    Creates and adds in capacity constraints.
    '''
    for i in self.network.locations:
      for t in self.ticks:
        self.model.addConstr( quicksum(self.inventory_vars[(i,1,ci,ct,t)] for ci,ct in mergedCommodities) <= self.network.destinationCapacity(i))

  def create_inventory_constraints_outdepot(self, mergedCommodities, depots, locations, productions):
    '''
    Creates and adds inventory constraints for out depots
    '''
    for t in self.ticks:
      for i in depots:
        for ci,ct in mergedCommodities:
          self.model.addConstr( self.inventory_vars[(i,0,ci,ct,t)] == self.inventory_vars.get((i,0,ci,ct,t-1), 0.0) + productions.get((i,t,ci,ct), 0.0)
            - quicksum(self.shift_vars.get((i,j,ci,ct,t), 0.0) for j in self.network.locations if j != i))

  def create_inventory_constraints_indepot(self, mergedCommodities, depots, locations, demands):
    '''
    creates and adds inventory constraints for in depots
    '''

    for t in self.ticks:
        for i in depots:
            for ci,ct in mergedCommodities:
                if t >= ct:
                    # we might not deliver everything
                    self.model.addConstr( self.inventory_vars[(i,1,ci,ct,t)] <= self.inventory_vars[(i,1,ci,ct,t-1)] - demands.get((i,t,ci,ct), 0.0) #+ self.not_delivered_vars[(i,s,st)]
                                     +
                                     quicksum(self.shift_vars.get((j,i,ci,ct,t-self.network.loadingTicks-self.network.unloadingTicks-self.network.distanceTicks(j,i)), 0.0) for j in locations if (j,i) in self.network.connections and t-self.network.loadingTicks-self.network.unloadingTicks-self.network.distanceTicks(j,i) in self.ticks))
                elif t > min(self.ticks):
                # if t >= 1:
                    self.model.addConstr( self.inventory_vars[(i,1,ci,ct,t)] == self.inventory_vars[(i,1,ci,ct,t-1)] - demands.get((i,t,ci,ct), 0.0)
                                     +
                                     quicksum(self.shift_vars.get( (j,i,ci,ct,t-self.network.loadingTicks-self.network.unloadingTicks-self.network.distanceTicks(j,i)), 0.0) for j in locations if (j,i) in self.network.connections and t-self.network.loadingTicks-self.network.unloadingTicks-self.network.distanceTicks(j,i) in self.ticks))
                else:
                    self.model.addConstr( self.inventory_vars[(i,1,ci,ct,t)] == 0 )

  def create_inventory_constraints_crossdock(self, mergedCommodities, crossdocks, locations):
    '''
    creates and adds inventory constraints for crossdocks
    '''

    for t in self.ticks:
        for i in crossdocks:
            for ci,ct in mergedCommodities:
                if t > min(self.ticks):
                    self.model.addConstr( self.inventory_vars[(i,-1,ci,ct,t)] == self.inventory_vars[(i,-1,ci,ct,t-1)] - quicksum(self.shift_vars.get((i,j,ci,ct,t), 0.0) for j in locations if (i,j) in self.network.connections)
                                     +
                                     quicksum(self.shift_vars.get((j,i,ci,ct,t-self.network.loadingTicks-self.network.unloadingTicks-self.network.distanceTicks(j,i)), 0.0) for j in locations if (j,i) in self.network.connections and t-self.network.loadingTicks-self.network.unloadingTicks-self.network.distanceTicks(j,i) in self.ticks))
                else:
                    self.model.addConstr( self.inventory_vars[(i,-1,ci,ct,t)] == 0 )

  def create_capacity_constraints_outdepot(self, depots, mergedCommodities, locations):
    '''
    creates and adds capacity constraints for out depots
    '''

    for i in depots:
        for t in self.ticks:
            self.model.addConstr( quicksum(self.inventory_vars[(i,0,ci,ct,t)] for ci,ct in mergedCommodities)
                             +
                             quicksum(self.shift_vars.get((i,j,ci,ct,t-eta), 0.0) for j in locations for ci,ct in mergedCommodities for eta in range(min(t+1, self.network.loadingTicks)) if (i,j) in self.network.connections and (t-eta in self.ticks))
                             <= self.network.originCapacity(i) + self.not_increasedcap_vars[(i,t)])

  def create_capacity_constraints_indepot(self, depots, mergedCommodities, locations):
    '''
    creates and adds capacity constraints for in depots
    '''

    for i in depots:
        for t in self.ticks:
            self.model.addConstr( quicksum(self.inventory_vars[(i,1,ci,ct,t)] for ci,ct in mergedCommodities)
                             +
                             quicksum(self.shift_vars.get((j,i,ci,ct,t-self.network.distanceTicks(j,i)-self.network.loadingTicks-eta), 0.0) for j in locations for ci,ct in mergedCommodities for eta in range(min(0,max(1,min(t-self.network.distanceTicks(j,i)-self.network.loadingTicks+1, self.network.unloadingTicks)))) if (j,i) in self.network.connections)
                             <= self.network.destinationCapacity(i))


  def evaluate_solution(self, mergedCommodities, increasedcap_vars):
    '''
    evaluates the solution of the model and prints arcs present in designed network to screen
    '''

    truck_solution = []
    for (i,j) in self.network.connections:
        for t in self.ticks:
            if (i,j,t) in self.truck_vars and self.truck_vars[(i,j,t)].x > 0.5 and self.truck_vars[(i,j,t)].obj > 0:
                truck_solution.append((i, j, t, self.truck_vars[i,j,t].x))

    for (i, j, t, n) in truck_solution:
        print("x %d %d %d %d" % (i,j,t,n))
    print()

    flow_solution = dict()
    for i,j in self.network.connections:
      for ci,ct in mergedCommodities:
        for t in self.ticks:
          if (i,j,ci,ct,t) in self.shift_vars and self.shift_vars[i,j,ci,ct,t].X > 0.001:
            flow_solution[i,j,ci,ct,t] = flow_solution.get( (i,j,ci,ct,t), 0.0) + self.shift_vars[i,j,ci,ct,t].x

    print()
    for (i,j,ci,ct,t) in flow_solution.keys():
        print("y %d %d %d" % (i,j,s))

    print()
    for (i,j,ci,ct,t) in flow_solution.keys():
        print("z %d %d %d %d %d %f" % (i,j,ci,ct,t,flow_solution[i,j,ci,ct,t]))

    print()
    for (i,t) in increasedcap_vars.keys():
        if increasedcap_vars[i,t].X > 1.0e-5:
            print("i %d %d %f" % (i, t, increasedcap_vars[i,t].X))

if __name__ == "__main__":

  network = Network(sys.argv[1])
  tickHours = float(sys.argv[2])
  tickZero = float(sys.argv[3])
  trolleys = network.readTrolleys(sys.argv[4])

  network.setDiscretization(tickHours, tickZero)
  
  mip = MIP(network)

  deliverableTrolleys = mip.scanTrolleys(trolleys)

  productions,demands = mip.computeBalance(trolleys)
  
  loading_periods = 25

  unused1, unused2, unused3, depots, crossdocks, unused6 = read_data(sys.argv[5])

  if len(sys.argv) > 6:
    # allowed_arcs, allowed_transportation = read_solution_stage_01(sys.argv[2])
    allowed_arcs, allowed_transportation = read_solution_stage_02(sys.argv[6])
  else:
    allowed_arcs, allowed_transportation = (None, None)

  indepots = [(d,1) for d in depots]
  outdepots = [(d,0) for d in depots]
  locations = depots + crossdocks
  signed_locations = indepots + outdepots + [(d,-1) for d in crossdocks] # used to distinguish in- and out-depots for inventory
  if not allowed_arcs is None:
      arcs = allowed_arcs
      if len(allowed_arcs[0]) == 3:
          arcs = [(u,v) for (u,v,t) in allowed_arcs]
          arcs = set(arcs)
  else:
      arcs = [(i,j) for i in locations for j in locations if i != j]
  
  mergedCommodities = list(set([ (k,network.deadlineTick((k,l))) for k,l in network.commodities ]))

  assert sum(productions.get((i,t,j,tt), 0.0) for i in depots for t in mip.ticks for (j,tt) in mergedCommodities) == sum(demands.get((j,tt,j,tt), 0.0) for (j,tt) in mergedCommodities)

  mip.model = Model()

  start = time.time()

  if allowed_arcs is None:
      mip.create_truck_variables()
  else:
      mip.create_truck_variables(allowed_arcs)
  mip.create_shift_variables(mergedCommodities, False)
  mip.create_inventory_variables(mergedCommodities, signed_locations)
#mip.create_not_delivered_vars(mergedCommodities, indepots)
  mip.create_not_increasedcap_vars(outdepots)

  print("create capacity constraints")
  mip.create_capacity_constraints(mergedCommodities)
  print("create truck capacity constraints")
  mip.create_depot_truck_capacity_constraints(locations, depots)
  print("create inventory outdepot constraints")
  mip.create_inventory_constraints_outdepot(mergedCommodities, depots, locations, productions)
  print("create inventory indepot constraints")
  mip.create_inventory_constraints_indepot(mergedCommodities, depots, locations, demands)
  print("create inventory crossdocks constraints")
  mip.create_inventory_constraints_crossdock(mergedCommodities, crossdocks, locations)
  print("create capacity out constraints")
  mip.create_capacity_constraints_outdepot(depots, mergedCommodities, locations)
  print("create capacity in constraints")
  mip.create_capacity_constraints_indepot(depots, mergedCommodities, locations)

  end = time.time()
  print("time for building the model:", end - start)

  mip.model.optimize()

#  mip.evaluate_solution(mergedCommodities, mip.not_increasedcap_vars)

