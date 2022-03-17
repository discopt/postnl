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
  
  def computeBalance(self, trolleys):
    productions = {}
    demands = {}
    for t in trolleys:
      releaseTick = self.network.trolleyReleaseTick(t)
      productions[t.source, releaseTick, t.commodity[0], t.commodity[1]] = productions.get((t.source, releaseTick, t.commodity[0], t.commodity[1]), 0) + 1
      demands[t.commodity] = demands.get(t.commodity, 0) + 1
    return productions,demands

  @property
  def network(self):
    return self._network

  @property
  def ticks(self):
    return range(self._minTick, self._maxTick+1)




  def create_truck_variables(self, arcs):
    '''
    returns dictionary of truck variables
    '''

    self.truck_vars = {}
    for (i,j) in self.network.connections:
        for t in self.ticks:
          if t + self.network.distanceTicks(i,j) in self.ticks:
            self.truck_vars[i,j,t] = self.model.addVar(vtype=GRB.INTEGER, name="arc_%d_%d_%d" % (i,j,t), obj=self.network.distance(i,j))

  def create_shift_variables(self, shifts, crossdocks, arcs, is_integer, allowed_transportation):
    '''
    returns dictionary of shift variables
    '''

    vtype = GRB.INTEGER if is_integer else GRB.CONTINUOUS
    self.shift_vars = {}
    for (i,j) in self.network.connections:
      for (s,st) in shifts:
        for t in self.ticks:
          if (s == j and t + self.network.distanceTicks(i,j) <= st) or (s != j and self.network.isCross(j) and t + self.network.distanceTicks(i,j) + self.network.distanceTicks(j,s) <= st):
            self.shift_vars[i,j,s,st,t] = self.model.addVar(vtype=vtype, name="shift%d_%d_%d_%d_%d" % (i,j,s,st,t), obj=0.0)

  def create_inventory_variables(self, shifts, signed_locations):
    '''
    returns dictionary of inventory variables
    '''

    inventory_vars = dict()

    for (i,j) in signed_locations: # j=1 in-depot, j=0: out-depot, j=-1 cross
        for (s,st) in shifts:
            for t in self.ticks:
                inventory_vars[(i,j,s,st,t)] = self.model.addVar(vtype=GRB.CONTINUOUS, name="inventory(%d_%d)_%d_%d_%d" % (i,j,s,st,t), obj=0.0)

    self.inventory_vars = inventory_vars

  def create_not_delivered_vars(self, shifts, indepots):

    not_delivered_vars = dict()

    for (i,j) in indepots:
        for (s,st) in shifts:
            not_delivered_vars[(i,s,st)] = 0
            # not_delivered_vars[(i,s,st)] = model.addVar(vtype=GRB.CONTINUOUS, name="notdelivered_%d_(%d_%d)" % (i,s,st), obj=1.0)

    self.not_delivered_vars = not_delivered_vars

  def create_not_increasedcap_vars(self, outdepots):

    not_increasedcap_vars = dict()

    for (i,j) in outdepots:
        for t in self.ticks:
            not_increasedcap_vars[(i,t)] = self.model.addVar(vtype=GRB.CONTINUOUS, name="inc_%d_%d" % (i,t), obj=1.0)

    self.not_increasedcap_vars = not_increasedcap_vars

  def create_capacity_constraints(self, arcs, shifts):
    '''
    Creates and adds capacity constraints.
    '''
    for (i,j) in arcs:
      for t in self.ticks:
        self.model.addConstr( quicksum(self.shift_vars.get((i,j,s,st,t), 0.0) for (s,st) in shifts) <= self.network.truckCapacity * self.truck_vars.get((i,j,t), 0.0))

  def create_depot_truck_capacity_constraints(self, arcs, locations, depots):
    '''
    creates and adds depot truck capacity constraints to model
    '''

    for i in depots:
        for t in self.ticks:
            self.model.addConstr( quicksum(self.truck_vars[(i,j,t-eta)] for j in locations for eta in range(max(1,min(t+1,self.network.loadingTicks))) if (i,j) in arcs and (i,j,t-eta) in self.ticks)
                             +
                             quicksum(self.truck_vars[(j,i,t-eta-self.network.distanceTicks(j,i)-self.network.loadingTicks)] for j in locations for eta in range(min(0,max(1,min(t+1+self.network.distanceTicks(j,i)+self.network.loadingTicks,self.network.unloadingTicks)))) if (j,i) in arcs and (j,i,t-eta-self.network.distanceTicks(j,i)-self.network.loadingTicks) in self.truck_vars)
                             <= self.network.numDocksPerTick(i)) # TODO: unloading_time=0 still implies that the truck blocks it for 1 tick! Is this desired?

  def create_out_capacity_constraints(self, shifts, depots):
    '''
    creates and adds out capacity constraints for depots
    '''

    for i in depots:
        for t in self.ticks:
            self.smodel.addConstr( quicksum(self.inventory_vars[(i,0,s,st,t)] for (s,st) in shifts) <= self.network.originCapacity(i))

  def create_in_capacity_constraints(self, shifts, depots):
    '''
    creates and adds in capacity constraints for depots
    '''

    for i in depots:
        for t in self.ticks:
            self.model.addConstr( quicksum(self.inventory_vars[(i,1,s,st,t)] for (s,st) in shifts) <= self.network.destinationCapacity(i))

  def create_inventory_constraints_outdepot(self, arcs, shifts, depots, locations, inflow):
    '''
    creates and adds inventory constraints for out depots
    '''

    for t in self.ticks:
        for i in depots:
            for (s,st) in shifts:
                if t > min(self.ticks):
                    self.model.addConstr( self.inventory_vars[(i,0,s,st,t)] == self.inventory_vars[(i,0,s,st,t-1)] + inflow[i][t][(s,st)]
                                     -
                                     quicksum(self.shift_vars.get((i,j,s,st,t), 0.0) for j in locations if (i,j) in arcs))
                else:
                    self.model.addConstr( self.inventory_vars[(i,0,s,st,t)] == inflow[i][t][(s,st)]
                                     -
                                     quicksum(self.shift_vars.get((i,j,s,st,t), 0.0) for j in locations if (i,j) in arcs))

  def create_inventory_constraints_indepot(self, arcs, shifts, depots, locations, outflow):
    '''
    creates and adds inventory constraints for in depots
    '''

    for t in self.ticks:
        for i in depots:
            for (s,st) in shifts:
                if t >= st:
                    # we might not deliver everything
                    self.model.addConstr( self.inventory_vars[(i,1,s,st,t)] <= self.inventory_vars[(i,1,s,st,t-1)] - outflow[i][t][(s,st)] + self.not_delivered_vars[(i,s,st)]
                                     +
                                     quicksum(self.shift_vars.get((j,i,s,st,t-self.network.loadingTicks-self.network.unloadingTicks-self.network.distanceTicks(j,i)), 0.0) for j in locations if (j,i) in arcs and t-self.network.loadingTicks-self.network.unloadingTicks-self.network.distanceTicks(j,i) in self.ticks))
                elif t > min(self.ticks):
                # if t >= 1:
                    self.model.addConstr( self.inventory_vars[(i,1,s,st,t)] == self.inventory_vars[(i,1,s,st,t-1)] - outflow[i][t][(s,st)]
                                     +
                                     quicksum(self.shift_vars.get((j,i,s,st,t-self.network.loadingTicks-self.network.unloadingTicks-self.network.distanceTicks(j,i)), 0.0) for j in locations if (j,i) in arcs and t-self.network.loadingTicks-self.network.unloadingTicks-self.network.distanceTicks(j,i) in self.ticks))
                else:
                    self.model.addConstr( self.inventory_vars[(i,1,s,st,t)] == 0 )

  def create_inventory_constraints_crossdock(self, arcs, shifts, crossdocks, locations):
    '''
    creates and adds inventory constraints for crossdocks
    '''

    for t in self.ticks:
        for i in crossdocks:
            for (s,st) in shifts:
                if t > min(self.ticks):
                    self.model.addConstr( self.inventory_vars[(i,-1,s,st,t)] == self.inventory_vars[(i,-1,s,st,t-1)] - quicksum(self.shift_vars.get((i,j,s,st,t), 0.0) for j in locations if (i,j) in arcs)
                                     +
                                     quicksum(self.shift_vars.get((j,i,s,st,t-self.network.loadingTicks-self.network.unloadingTicks-self.network.distanceTicks(j,i)), 0.0) for j in locations if (j,i) in arcs and t-self.network.loadingTicks-self.network.unloadingTicks-self.network.distanceTicks(j,i) in self.ticks))
                else:
                    self.model.addConstr( self.inventory_vars[(i,-1,s,st,t)] == 0 )

  def create_capacity_constraints_outdepot(self, arcs, depots, shifts, locations):
    '''
    creates and adds capacity constraints for out depots
    '''

    for i in depots:
        for t in self.ticks:
            self.model.addConstr( quicksum(self.inventory_vars[(i,0,s,st,t)] for (s,st) in shifts)
                             +
                             quicksum(self.shift_vars.get((i,j,s,st,t-eta), 0.0) for j in locations for (s,st) in shifts for eta in range(min(t+1, self.network.loadingTicks)) if (i,j) in arcs and (t-eta in self.ticks))
                             <= self.network.originCapacity(i) + self.not_increasedcap_vars[(i,t)])

  def create_capacity_constraints_indepot(self, arcs, depots, shifts, locations):
    '''
    creates and adds capacity constraints for in depots
    '''

    for i in depots:
        for t in self.ticks:
            self.model.addConstr( quicksum(self.inventory_vars[(i,1,s,st,t)] for (s,st) in shifts)
                             +
                             quicksum(self.shift_vars.get((j,i,s,st,t-self.network.distanceTicks(j,i)-self.network.loadingTicks-eta), 0.0) for j in locations for (s,st) in shifts for eta in range(min(0,max(1,min(t-self.network.distanceTicks(j,i)-self.network.loadingTicks+1, self.network.unloadingTicks)))) if (j,i) in arcs)
                             <= self.network.destinationCapacity(i))


  def evaluate_solution(self, arcs, shifts, increasedcap_vars):
    '''
    evaluates the solution of the model and prints arcs present in designed network to screen
    '''

    truck_solution = []
    for (i,j) in arcs:
        for t in self.ticks:
            if (i,j,t) in self.truck_vars and self.truck_vars[(i,j,t)].x > 0.5 and self.truck_vars[(i,j,t)].obj > 0:
                truck_solution.append((i, j, t, self.truck_vars[i,j,t].x))

    for (i, j, t, n) in truck_solution:
        print("x %d %d %d %d" % (i,j,t,n))
    print()

    flow_solution = dict()
    for (i,j) in arcs:
        for (s,st) in shifts:
            for t in self.ticks:
                if (i,j,s,st,t) in self.shift_vars and self.shift_vars[i,j,s,st,t].X > 0.001:
                    if (i,j,s,st,t) in flow_solution:
                        flow_solution[i,j,s,st,t] += self.shift_vars[i,j,s,st,t].X
                    else:
                        flow_solution[i,j,s,st,t] = self.shift_vars[i,j,s,st,t].X

    print()
    for (i,j,s,st,t) in flow_solution.keys():
        print("y %d %d %d" % (i,j,s))

    print()
    for (i,j,s,st,t) in flow_solution.keys():
        print("z %d %d %d %d %d %f" % (i,j,s,st,t,flow_solution[i,j,s,st,t]))

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

  productions,demands = mip.computeBalance(deliverableTrolleys)
  
  loading_periods = 25

  unused1, unused2, demand, depots, crossdocks, unused6 = read_data(sys.argv[5])

  print(crossdocks)

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
  
  print(sorted(arcs) == [ (i,j) for i in network.locations for j in network.locations if i != j ])


  shifts = [(j,tt) for i in demand.keys() for j in demand[i].keys() for t in demand[i][j].keys() for tt in demand[i][j][t].keys()]
  shifts = set(shifts)

  # compute outflow of in-depots
  outflow = dict()
  for i in depots:
      outflow[i] = dict()
      for t in mip.ticks:
          outflow[i][t] = dict()
          for (s,st) in shifts:
              outflow[i][t][(s,st)] = 0
  for i in demand.keys():
      for j in demand[i].keys():
          for t in demand[i][j].keys():
              for tt in demand[i][j][t]:
                  outflow[j][tt][(j,tt)] += demand[i][j][t][tt]

  # compute inflow of out-depots
  inflow = dict()
  for i in depots:
      inflow[i] = dict()
      for t in mip.ticks:
          inflow[i][t] = dict()
          for (s,st) in shifts:
              inflow[i][t][(s,st)] = 0

  if False:
      scale_demand = dict()
      for i in demand.keys():
          for j in demand[i].keys():
              for t in demand[i][j].keys():
                  for tt in demand[i][j][t].keys():
                      scale_demand[i,j,tt] = scale_demand.get((i,j,tt), 0) + demand[i][j][t][tt]

      # distribute demand equally over loading periods
      for (i,j,tt) in scale_demand:
          avg = float(max(1,scale_demand[i,j,tt] - 1))/float(loading_periods)
          freq = max(1,math.floor(1/avg))
          for cnt in range(0,loading_periods,freq):
              inflow[i][cnt][(j,tt)] = math.ceil(avg)
          

                     # # distribute demand dem equally in the time loading periods
                      # for cnt in range(loading_periods):
                      #     inflow[i][cnt][(j,tt)] = math.ceil(float(dem)/float(loading_periods))
  else:
      lastt = 0
      for i in demand.keys():
          for j in demand[i].keys():
              for t in demand[i][j].keys():
                  for tt in demand[i][j][t].keys():
                      inflow[i][t][(j,tt)] += demand[i][j][t][tt]

                  if t > lastt:
                      lastt = t
  print("\n\n\nLAST T: %d\n\n\n\n" % lastt)


  total_inflow = sum(inflow[i][t][(j,tt)] for i in depots for t in mip.ticks for (j,tt) in shifts)
  total_outflow = sum(outflow[j][tt][(j,tt)] for (j,tt) in shifts)
  total_demand = sum(demand[i][j][t][tt] for i in demand.keys() for j in demand[i].keys() for t in demand[i][j].keys() for tt in demand[i][j][t].keys())
  print("sanity check:", total_inflow, total_outflow, total_demand)

  mip.model = Model()

  start = time.time()

  if allowed_arcs is None:
      mip.create_truck_variables(arcs)
  else:
      mip.create_truck_variables(allowed_arcs)
  mip.create_shift_variables(shifts, crossdocks, arcs, False, allowed_transportation)
  mip.create_inventory_variables(shifts, signed_locations)
  mip.create_not_delivered_vars(shifts, indepots)
  mip.create_not_increasedcap_vars(outdepots)

  print("create capacity constraints")
  mip.create_capacity_constraints(arcs, shifts)
  print("create truck capacity constraints")
  mip.create_depot_truck_capacity_constraints(arcs, locations, depots)
  print("create inventory outdepot constraints")
  mip.create_inventory_constraints_outdepot(arcs, shifts, depots, locations, inflow)
  print("create inventory indepot constraints")
  mip.create_inventory_constraints_indepot(arcs, shifts, depots, locations, outflow)
  print("create inventory crossdocks constraints")
  mip.create_inventory_constraints_crossdock(arcs, shifts, crossdocks, locations)
  print("create capacity out constraints")
  mip.create_capacity_constraints_outdepot(arcs, depots, shifts, locations)
  print("create capacity in constraints")
  mip.create_capacity_constraints_indepot(arcs, depots, shifts, locations)

  end = time.time()
  print("time for building the model:", end - start)

  mip.model.optimize()

  mip.evaluate_solution(arcs, shifts, mip.not_increasedcap_vars)

