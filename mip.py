from gurobipy import *
import math
import sys
import time
from network import *

##################################
# AUXILIARY METHODS
##################################

def evaluate_solution(arcs, times, shifts, truck_vars, shift_vars, increasedcap_vars):
    '''
    evaluates the solution of the model and prints arcs present in designed network to screen
    '''

    # maxtime = max(times)
    truck_solution = []
    for (i,j) in arcs:
        for t in times:
            if (not truck_vars[(i,j,t)] is 0) and truck_vars[(i,j,t)].X > 0.5 and truck_vars[(i,j,t)].obj > 0:
                truck_solution.append((i, j, t, truck_vars[i,j,t].X))

    for (i, j, t, n) in truck_solution:
        print("x %d %d %d %d" % (i,j,t,n))
    print()

    flow_solution = dict()
    for (i,j) in arcs:
        for (s,st) in shifts:
            for t in times:
                if (not shift_vars[(i,j,s,st,t)] is 0) and shift_vars[i,j,s,st,t].X > 0.001:
                    if (i,j,s,st,t) in flow_solution:
                        flow_solution[i,j,s,st,t] += shift_vars[i,j,s,st,t].X
                    else:
                        flow_solution[i,j,s,st,t] = shift_vars[i,j,s,st,t].X

    print()
    for (i,j,s,st,t) in flow_solution.keys():
        print("y %d %d %d" % (i,j,s))

    print()
    for (i,j,s,st,t) in flow_solution.keys():
        print("z %d %d %d %d %d %f" % (i,j,s,st,t,flow_solution[i,j,s,st,t]))

    print()
    for (i,t) in increasedcap_vars.keys():
        if increasedcap_vars[i,t].X > 0:
            print("i %d %d %f" % (i, t, increasedcap_vars[i,t].X))


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

  @property
  def network(self):
    return self._network

  @property
  def ticks(self):
    return range(self._minTick, self._maxTick+1)




  def create_truck_variables(self, arcs, times):
    '''
    returns dictionary of truck variables
    '''

    truck_vars = dict()
    cur_arcs = arcs
    if len(arcs[0]) == 3:
        cur_arcs = [(u,v) for (u,v,t) in arcs]
        cur_arcs = set(cur_arcs)

    for (i,j) in cur_arcs:
        for t in times:
          if t + self.network.distanceTicks(i,j) <= max(times):
            # truck_vars[i,j,t] = model.addVar(vtype=GRB.INTEGER, name="arc%d_%d_%d" % (i,j,t), obj=0)
            truck_vars[i,j,t] = self.model.addVar(vtype=GRB.INTEGER, name="arc%d_%d_%d" % (i,j,t), obj=self.network.distance(i,j))
            if len(arcs[0]) == 3 and not (i,j,t) in arcs:
                truck_vars[i,j,t] = 0
            # if len(arcs[0]) == 3 and not (i,j,t) in arcs:
            #     truck_vars[i,j,t].obj = 1.0
          else:
            truck_vars[i,j,t] = 0

    self.truck_vars = truck_vars

  def create_shift_variables(self, shifts, crossdocks, arcs, times, is_integer, allowed_transportation):
    '''
    returns dictionary of shift variables
    '''

    shift_vars = dict()
    vtype = GRB.INTEGER if is_integer else GRB.CONTINUOUS
    
    for (i,j) in arcs:
      for (s,st) in shifts:
        for t in times:
          if (s != j and not j in crossdocks) or (allowed_transportation and not (i,j,s) in allowed_transportation):
            # if j is a depot but it is not the last trip.
            shift_vars[i,j,s,st,t] = 0
          elif s != j or t <= st - self.network.distanceTicks(i,j):
            shift_vars[i,j,s,st,t] = self.model.addVar(vtype=vtype, name="shift%d_%d_%d_%d_%d" % (i,j,s,st,t), obj=0.0)
          else:
            # too late arrival for last trip.
            shift_vars[i,j,s,st,t] = 0

    self.shift_vars = shift_vars

  def create_inventory_variables(self, shifts, signed_locations, times):
    '''
    returns dictionary of inventory variables
    '''

    inventory_vars = dict()

    for (i,j) in signed_locations: # j=1 in-depot, j=0: out-depot, j=-1 cross
        for (s,st) in shifts:
            for t in times:
                inventory_vars[(i,j,s,st,t)] = self.model.addVar(vtype=GRB.CONTINUOUS, name="inventory(%d_%d)_%d_%d_%d" % (i,j,s,st,t), obj=0.0)

    self.inventory_vars = inventory_vars

  def create_not_delivered_vars(self, shifts, indepots):

    not_delivered_vars = dict()

    for (i,j) in indepots:
        for (s,st) in shifts:
            not_delivered_vars[(i,s,st)] = 0
            # not_delivered_vars[(i,s,st)] = model.addVar(vtype=GRB.CONTINUOUS, name="notdelivered_%d_(%d_%d)" % (i,s,st), obj=1.0)

    self.not_delivered_vars = not_delivered_vars

  def create_not_increasedcap_vars(self, outdepots, times):

    not_increasedcap_vars = dict()

    for (i,j) in outdepots:
        for t in times:
            not_increasedcap_vars[(i,t)] = self.model.addVar(vtype=GRB.CONTINUOUS, name="inc_%d_%d" % (i,t), obj=1.0)

    self.not_increasedcap_vars = not_increasedcap_vars

  def create_capacity_constraints(self, arcs, shifts, times):
    '''
    creates and adds capacity constraints to model
    '''

    for (i,j) in arcs:
        for t in times:
            self.model.addConstr( quicksum(self.shift_vars[(i,j,s,st,t)] for (s,st) in shifts) <= self.network.truckCapacity * self.truck_vars[(i,j,t)])

  def create_depot_truck_capacity_constraints(self, arcs, locations, times, depot_truck_capacity, depots, loading_time, unloading_time):
    '''
    creates and adds depot truck capacity constraints to model
    '''

    for i in depots:
        for t in times:
            self.model.addConstr( quicksum(self.truck_vars[(i,j,t-eta)] for j in locations for eta in range(max(1,min(t+1,loading_time))) if (i,j) in arcs)
                             +
                             quicksum(self.truck_vars[(j,i,t-eta-self.network.distanceTicks(j,i)-loading_time)] for j in locations for eta in range(min(0,max(1,min(t+1+self.network.distanceTicks(j,i)+loading_time,unloading_time)))) if (j,i) in arcs)
                             <= depot_truck_capacity) # TODO: unloading_time=0 still implies that the truck blocks it for 1 tick! Is this desired?

  def create_out_capacity_constraints(self, times, shifts, depots, out_capacity):
    '''
    creates and adds out capacity constraints for depots
    '''

    for i in depots:
        for t in times:
            self.smodel.addConstr( quicksum(self.inventory_vars[(i,0,s,st,t)] for (s,st) in shifts) <= out_capacity) # TODO: incorporate that leaving trucks still load something.

  def create_in_capacity_constraints(self, times, shifts, depots, in_capacity):
    '''
    creates and adds in capacity constraints for depots
    '''

    for i in depots:
        for t in times:
            self.model.addConstr( quicksum(self.inventory_vars[(i,1,s,st,t)] for (s,st) in shifts) <= in_capacity) # TODO: incorporate that incoming trucks still unload something.

  def create_inventory_constraints_outdepot(self, arcs, loading_time, unloading_time, times, shifts, depots, locations, inflow):
    '''
    creates and adds inventory constraints for out depots
    '''

    for t in times:
        for i in depots:
            for (s,st) in shifts:
                if t >= 1:
                    self.model.addConstr( self.inventory_vars[(i,0,s,st,t)] == self.inventory_vars[(i,0,s,st,t-1)] + inflow[i][t][(s,st)]
                                     -
                                     quicksum(self.shift_vars[(i,j,s,st,t)] for j in locations if (i,j) in arcs))
                else:
                    self.model.addConstr( self.inventory_vars[(i,0,s,st,t)] == inflow[i][t][(s,st)]
                                     -
                                     quicksum(self.shift_vars[(i,j,s,st,t)] for j in locations if (i,j) in arcs))

  def create_inventory_constraints_indepot(self, arcs, loading_time, unloading_time, times, shifts, depots, locations, outflow):
    '''
    creates and adds inventory constraints for in depots
    '''

    for t in times:
        for i in depots:
            for (s,st) in shifts:
                if t >= st:
                    # we might not deliver everything
                    self.model.addConstr( self.inventory_vars[(i,1,s,st,t)] <= self.inventory_vars[(i,1,s,st,t-1)] - outflow[i][t][(s,st)] + self.not_delivered_vars[(i,s,st)]
                                     +
                                     quicksum(self.shift_vars[(j,i,s,st,t-loading_time-unloading_time-self.network.distanceTicks(j,i))] for j in locations if (j,i) in arcs and t-loading_time-unloading_time-self.network.distanceTicks(j,i) >= 0))
                elif t >= 1:
                # if t >= 1:
                    self.model.addConstr( self.inventory_vars[(i,1,s,st,t)] == self.inventory_vars[(i,1,s,st,t-1)] - outflow[i][t][(s,st)]
                                     +
                                     quicksum(self.shift_vars[(j,i,s,st,t-loading_time-unloading_time-self.network.distanceTicks(j,i))] for j in locations if (j,i) in arcs and t-loading_time-unloading_time-self.network.distanceTicks(j,i) >= 0))
                else:
                    self.model.addConstr( self.inventory_vars[(i,1,s,st,t)] == 0 )

  def create_inventory_constraints_crossdock(self, arcs, loading_time, unloading_time, times, shifts, crossdocks, locations):
    '''
    creates and adds inventory constraints for crossdocks
    '''

    for t in times:
        for i in crossdocks:
            for (s,st) in shifts:
                if t >= 1:
                    self.model.addConstr( self.inventory_vars[(i,-1,s,st,t)] == self.inventory_vars[(i,-1,s,st,t-1)] - quicksum(self.shift_vars[(i,j,s,st,t)] for j in locations if (i,j) in arcs)
                                     +
                                     quicksum(self.shift_vars[(j,i,s,st,t-loading_time-unloading_time-self.network.distanceTicks(j,i))] for j in locations if (j,i) in arcs and t-loading_time-unloading_time-self.network.distanceTicks(j,i) >= 0))
                else:
                    self.model.addConstr( self.inventory_vars[(i,-1,s,st,t)] == 0 )

  def create_capacity_constraints_outdepot(self, arcs, depots, times, shifts, locations, loading_time, unloading_time, out_capacity):
    '''
    creates and adds capacity constraints for out depots
    '''

    for i in depots:
        for t in times:
            self.model.addConstr( quicksum(self.inventory_vars[(i,0,s,st,t)] for (s,st) in shifts)
                             +
                             quicksum(self.shift_vars[(i,j,s,st,t-eta)] for j in locations for (s,st) in shifts for eta in range(min(t+1, loading_time)) if (i,j) in arcs)
                             <= out_capacity + self.not_increasedcap_vars[(i,t)])

  def create_capacity_constraints_indepot(self, arcs, depots, times, shifts, locations, loading_time, unloading_time, in_capacity):
    '''
    creates and adds capacity constraints for in depots
    '''

    for i in depots:
        for t in times:
            self.model.addConstr( quicksum(self.inventory_vars[(i,1,s,st,t)] for (s,st) in shifts)
                             +
                             quicksum(self.shift_vars[(j,i,s,st,t-self.network.distanceTicks(j,i)-loading_time-eta)] for j in locations for (s,st) in shifts for eta in range(min(0,max(1,min(t-self.network.distanceTicks(j,i)-loading_time+1, unloading_time)))) if (j,i) in arcs)
                             <= in_capacity)


if __name__ == "__main__":

  network = Network(sys.argv[1])
  tickHours = float(sys.argv[2])
  tickZero = float(sys.argv[3])
  trolleys = network.readTrolleys(sys.argv[4])

  network.setDiscretization(tickHours, tickZero)
  
  mip = MIP(network)
  
  in_capacity = 800
  out_capacity = 400
  depot_truck_capacity = 1000 # TODO: should scale with time discretization!
  loading_time = 0            # loading time in ticks
  unloading_time = 1 # unloading time in ticks
  shift_vars_integer = False  # whether shift variables are integral
  loading_periods = 25

  unused1, unused2, demand, depots, crossdocks, ticksize = read_data(sys.argv[5])

  if len(sys.argv) > 6:
    # allowed_arcs, allowed_transportation = read_solution_stage_01(sys.argv[2])
    allowed_arcs, allowed_transportation = read_solution_stage_02(sys.argv[6])
  else:
    allowed_arcs, allowed_transportation = (None, None)

  depot_truck_capacity = 12 * ticksize / 0.25
  loading_time = 0 if ticksize > 0.25 else 1
  # loading_periods = math.ceil(10/ticksize)


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
  shifts = [(j,tt) for i in demand.keys() for j in demand[i].keys() for t in demand[i][j].keys() for tt in demand[i][j][t].keys()]
  shifts = set(shifts)
  times = range(max(t for (s,t) in shifts) + 1)

  # compute outflow of in-depots
  outflow = dict()
  for i in depots:
      outflow[i] = dict()
      for t in times:
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
      for t in times:
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


  total_inflow = sum(inflow[i][t][(j,tt)] for i in depots for t in times for (j,tt) in shifts)
  total_outflow = sum(outflow[j][tt][(j,tt)] for (j,tt) in shifts)
  total_demand = sum(demand[i][j][t][tt] for i in demand.keys() for j in demand[i].keys() for t in demand[i][j].keys() for tt in demand[i][j][t].keys())
  print("sanity check:", total_inflow, total_outflow, total_demand)

  mip.model = Model()

  start = time.time()

  if allowed_arcs is None:
      mip.create_truck_variables(arcs, times)
  else:
      mip.create_truck_variables(allowed_arcs, times)
  mip.create_shift_variables(shifts, crossdocks, arcs, times, shift_vars_integer, allowed_transportation)
  mip.create_inventory_variables(shifts, signed_locations, times)
  mip.create_not_delivered_vars(shifts, indepots)
  mip.create_not_increasedcap_vars(outdepots, times)

  print("create capacity constraints")
  mip.create_capacity_constraints(arcs, shifts, times)
  print("create truck capacity constraints")
  mip.create_depot_truck_capacity_constraints(arcs, locations, times, depot_truck_capacity, depots, loading_time, unloading_time)
  print("create inventory outdepot constraints")
  mip.create_inventory_constraints_outdepot(arcs, loading_time, unloading_time, times, shifts, depots, locations, inflow)
  print("create inventory indepot constraints")
  mip.create_inventory_constraints_indepot(arcs, loading_time, unloading_time, times, shifts, depots, locations, outflow)
  print("create inventory crossdocks constraints")
  mip.create_inventory_constraints_crossdock(arcs, loading_time, unloading_time, times, shifts, crossdocks, locations)
  print("create capacity out constraints")
  mip.create_capacity_constraints_outdepot(arcs, depots, times, shifts, locations, loading_time, unloading_time, out_capacity)
  print("create capacity in constraints")
  mip.create_capacity_constraints_indepot(arcs, depots, times, shifts, locations, loading_time, unloading_time, in_capacity)

  end = time.time()
  print("time for building the model:", end - start)

  mip.model.optimize()

  evaluate_solution(arcs, times, shifts, mip.truck_vars, mip.shift_vars, mip.not_increasedcap_vars)
