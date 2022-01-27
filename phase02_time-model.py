from gurobipy import *
import math
import sys
import time

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
            hourlyDist = float(line.split()[3])

            if not origin in distances:
                distances[origin] = {dest: dist}
                hourlyDistances[origin] = {dest: hourlyDist}
            else:
                distances[origin][dest] = dist
                hourlyDistances[origin][dest] = hourlyDist

        elif line.startswith('t'):
            origin = int(line.split()[2])
            dest = int(line.split()[3])
            deadline = int(line.split()[5])

            if origin == dest:
              pass
            elif not origin in demand:
                demand[origin] = {dest: {deadline: 1}}
            elif not dest in demand[origin]:
                demand[origin][dest] = {deadline: 1}
            elif not deadline in demand[origin][dest]:
                demand[origin][dest][deadline] = 1
            else:
                demand[origin][dest][deadline] = demand[origin][dest][deadline] + 1                

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

##################################
# METHODS FOR BUILDING THE MODEL
##################################

def create_truck_variables(model, distances, hourlyDistances, arcs, times):
    '''
    returns dictionary of truck variables
    '''

    truck_vars = dict()
    
    for (i,j) in arcs:
        for t in times:
          if t + distances[i][j] <= max(times):
            truck_vars[i,j,t] = model.addVar(vtype=GRB.INTEGER, name="arc%d_%d_%d" % (i,j,t), obj=hourlyDistances[i][j])
          else:
            truck_vars[i,j,t] = 0

    return truck_vars

def create_shift_variables(model, distances, shifts, crossdocks, arcs, times, is_integer, allowed_transportation):
    '''
    returns dictionary of shift variables
    '''

    shift_vars = dict()
    vtype = GRB.INTEGER if is_integer else GRB.CONTINUOUS
    
    for (i,j) in arcs:
      for (s,st) in shifts:
        for t in times:
          if (s != j and not j in crossdocks) or not (i,j,s) in allowed_transportation:
            # if j is a depot but it is not the last trip.
            shift_vars[i,j,s,st,t] = 0
          elif s != j or t <= st - distances[i][j]:
            shift_vars[i,j,s,st,t] = model.addVar(vtype=vtype, name="shift%d_%d_%d_%d_%d" % (i,j,s,st,t), obj=0.0)
          else:
            # too late arrival for last trip.
            shift_vars[i,j,s,st,t] = 0
    return shift_vars

def create_inventory_variables(model, shifts, signed_locations, times):
    '''
    returns dictionary of inventory variables
    '''

    inventory_vars = dict()

    for (i,j) in signed_locations: # j=1 in-depot, j=0: out-depot, j=-1 cross
        for (s,st) in shifts:
            for t in times:
                inventory_vars[(i,j,s,st,t)] = model.addVar(vtype=GRB.CONTINUOUS, name="inventory(%d_%d)_%d_%d_%d" % (i,j,s,st,t), obj=0.0)

    return inventory_vars

def create_capacity_constraints(model, truck_vars, shift_vars, arcs, shifts, times, truck_capacity):
    '''
    creates and adds capacity constraints to model
    '''

    for (i,j) in arcs:
        for t in times:
            model.addConstr( quicksum(shift_vars[(i,j,s,st,t)] for (s,st) in shifts) <= truck_capacity * truck_vars[(i,j,t)])

def create_depot_truck_capacity_constraints(model, truck_vars, distances, arcs, locations, times, depot_truck_capacity, depots, loading_time, unloading_time):
    '''
    creates and adds depot truck capacity constraints to model
    '''

    for i in depots:
        for t in times:
            model.addConstr( quicksum(truck_vars[(i,j,t-eta)] for j in locations for eta in range(max(1,min(t+1,loading_time))) if (i,j) in arcs)
                             +
                             quicksum(truck_vars[(j,i,t-eta-distances[j][i]-loading_time)] for j in locations for eta in range(min(0,max(1,min(t+1+distances[j][i]+loading_time,unloading_time)))) if (j,i) in arcs)
                             <= depot_truck_capacity) # TODO: unloading_time=0 still implies that the truck blocks it for 1 tick! Is this desired?

def create_out_capacity_constraints(model, inventory_vars, times, shifts, depots, out_capacity):
    '''
    creates and adds out capacity constraints for depots
    '''

    for i in depots:
        for t in times:
            model.addConstr( quicksum(inventory_vars[(i,0,s,st,t)] for (s,st) in shifts) <= out_capacity) # TODO: incorporate that leaving trucks still load something.

def create_in_capacity_constraints(model, inventory_vars, times, shifts, depots, in_capacity):
    '''
    creates and adds in capacity constraints for depots
    '''

    for i in depots:
        for t in times:
            model.addConstr( quicksum(inventory_vars[(i,1,s,st,t)] for (s,st) in shifts) <= in_capacity) # TODO: incorporate that incoming trucks still unload something.

def create_inventory_constraints_outdepot(model, arcs, inventory_vars, shift_vars, loading_time, unloading_time, times, shifts, depots, locations, inflow):
    '''
    creates and adds inventory constraints for out depots
    '''

    for t in times:
        for i in depots:
            for (s,st) in shifts:
                if t >= 1:
                    model.addConstr( inventory_vars[(i,0,s,st,t)] == inventory_vars[(i,0,s,st,t-1)] + inflow[i][t][(s,st)]
                                     -
                                     quicksum(shift_vars[(i,j,s,st,t)] for j in locations if (i,j) in arcs))
                else:
                    model.addConstr( inventory_vars[(i,0,s,st,t)] == inflow[i][t][(s,st)]
                                     -
                                     quicksum(shift_vars[(i,j,s,st,t)] for j in locations if (i,j) in arcs))

def create_inventory_constraints_indepot(model, arcs, inventory_vars, shift_vars, loading_time, unloading_time, times, shifts, depots, locations, outflow, distances):
    '''
    creates and adds inventory constraints for in depots
    '''

    for t in times:
        for i in depots:
            for (s,st) in shifts:
                if t >= 1:
                    model.addConstr( inventory_vars[(i,1,s,st,t)] == inventory_vars[(i,1,s,st,t-1)] - outflow[i][t][(s,st)]
                                     +
                                     quicksum(shift_vars[(j,i,s,st,t-loading_time-unloading_time-distances[j][i])] for j in locations if (j,i) in arcs and t-loading_time-unloading_time-distances[j][i] >= 0))
                else:
                    model.addConstr( inventory_vars[(i,1,s,st,t)] == 0 )

def create_inventory_constraints_crossdock(model, arcs, inventory_vars, shift_vars, loading_time, unloading_time, times, shifts, crossdocks, locations, distances):
    '''
    creates and adds inventory constraints for crossdocks
    '''

    for t in times:
        for i in crossdocks:
            for (s,st) in shifts:
                if t >= 1:
                    model.addConstr( inventory_vars[(i,-1,s,st,t)] == inventory_vars[(i,-1,s,st,t-1)] - quicksum(shift_vars[(i,j,s,st,t)] for j in locations if (i,j) in arcs)
                                     +
                                     quicksum(shift_vars[(j,i,s,st,t-loading_time-unloading_time-distances[j][i])] for j in locations if (j,i) in arcs and t-loading_time-unloading_time-distances[j][i] >= 0))
                else:
                    model.addConstr( inventory_vars[(i,-1,s,st,t)] == 0 )

def create_capacity_constraints_outdepot(model, arcs, shift_vars, inventory_vars, depots, times, shifts, locations, loading_time, unloading_time, out_capacity):
    '''
    creates and adds capacity constraints for out depots
    '''

    for i in depots:
        for t in times:
            model.addConstr( quicksum(inventory_vars[(i,0,s,st,t)] for (s,st) in shifts)
                             +
                             quicksum(shift_vars[(i,j,s,st,t-eta)] for j in locations for (s,st) in shifts for eta in range(min(t+1, loading_time)) if (i,j) in arcs)
                             <= out_capacity)

def create_capacity_constraints_indepot(model, arcs, shift_vars, inventory_vars, depots, times, shifts, distances, locations, loading_time, unloading_time, in_capacity):
    '''
    creates and adds capacity constraints for in depots
    '''

    for i in depots:
        for t in times:
            model.addConstr( quicksum(inventory_vars[(i,1,s,st,t)] for (s,st) in shifts)
                             +
                             quicksum(shift_vars[(j,i,s,st,t-distances[j][i]-loading_time-eta)] for j in locations for (s,st) in shifts for eta in range(min(0,max(1,min(t-distances[j][i]-loading_time+1, unloading_time)))) if (j,i) in arcs)
                             <= in_capacity)



def create_mip(distances, hourlyDistances, demand, depots, crossdocks, truck_capacity, loading_time, unloading_time, shift_vars_integer, depot_truck_capacity, in_capacity, out_capacity, loading_periods, allowed_arcs, allowed_transportation):
    '''
    returns the network design model of phase 2
    '''

    indepots = [(d,1) for d in depots]
    outdepots = [(d,0) for d in depots]
    locations = depots + crossdocks
    signed_locations = indepots + outdepots + [(d,-1) for d in crossdocks] # used to distinguish in- and out-depots for inventory
    # arcs = [(i,j) for i in locations for j in locations if i != j]
    arcs = allowed_arcs
    shifts = [(j,t) for i in demand.keys() for j in demand[i].keys() for t in demand[i][j].keys()]
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
                outflow[j][t][(j,t)] += demand[i][j][t]

    # compute inflow of out-depots
    inflow = dict()
    for i in depots:
        inflow[i] = dict()
        for t in times:
            inflow[i][t] = dict()
            for (s,st) in shifts:
                inflow[i][t][(s,st)] = 0
    for i in demand.keys():
        for j in demand[i].keys():
            for t in demand[i][j].keys():
                dem = demand[i][j][t]

                # distribute demand dem equally in the time loading periods
                for cnt in range(loading_periods):
                    inflow[i][cnt][(j,t)] = dem/loading_periods
        

    mip = Model()

    start = time.time()

    truck_vars = create_truck_variables(mip, distances, hourlyDistances, arcs, times)
    shift_vars = create_shift_variables(mip, distances, shifts, crossdocks, arcs, times, shift_vars_integer, allowed_transportation)
    inventory_vars = create_inventory_variables(mip, shifts, signed_locations, times)

    print("create capacity constraints")
    create_capacity_constraints(mip, truck_vars, shift_vars, arcs, shifts, times, truck_capacity)
    print("create truck capacity constraints")
    create_depot_truck_capacity_constraints(mip, truck_vars, distances, arcs, locations, times, depot_truck_capacity, depots, loading_time, unloading_time)

    # ALREADY COVERED BY LAST TWO FAMILIES OF CONSTRAINTS
    # print("create out capacity constraints")
    # create_out_capacity_constraints(mip, inventory_vars, times, shifts, depots, out_capacity)
    # print("create in capacity constraints")
    # create_in_capacity_constraints(mip, inventory_vars, times, shifts, depots, in_capacity)

    print("create inventory outdepot constraints")
    create_inventory_constraints_outdepot(mip, arcs, inventory_vars, shift_vars, loading_time, unloading_time, times, shifts, depots, locations, inflow)
    print("create inventory indepot constraints")
    create_inventory_constraints_indepot(mip, arcs, inventory_vars, shift_vars, loading_time, unloading_time, times, shifts, depots, locations, outflow, distances)
    print("create inventory crossdocks constraints")
    create_inventory_constraints_crossdock(mip, arcs, inventory_vars, shift_vars, loading_time, unloading_time, times, shifts, crossdocks, locations, distances)
    print("create capacity out constraints")
    create_capacity_constraints_outdepot(mip, arcs, shift_vars, inventory_vars, depots, times, shifts, locations, loading_time, unloading_time, out_capacity)
    print("create capacity in constraints")
    create_capacity_constraints_indepot(mip, arcs, shift_vars, inventory_vars, depots, times, shifts, distances, locations, loading_time, unloading_time, in_capacity)

    end = time.time()
    print("time for building the model:", end - start)

    mip.optimize()



def main():
    
    truck_capacity = 48
    in_capacity = 400
    out_capacity = 1200
    depot_truck_capacity = 1000 # TODO: should scale with time discretization!
    loading_time = 0            # loading time in ticks
    unloading_time = 1 # unloading time in ticks
    shift_vars_integer = False  # whether shift variables are integral
    loading_periods = 5

    distances, hourlyDistances, demand, depots, crossdocks, ticksize = read_data(sys.argv[1])
    allowed_arcs, allowed_transportation = read_solution_stage_01(sys.argv[2])

    depot_truck_capacity = 12 * ticksize / 0.25
    loading_time = 0 if ticksize > 0.25 else 1
    loading_periods = math.ceil(10/ticksize)

    create_mip(distances, hourlyDistances, demand, depots, crossdocks, truck_capacity, loading_time, unloading_time, shift_vars_integer, depot_truck_capacity, in_capacity, out_capacity, loading_periods, allowed_arcs, allowed_transportation)
    
if __name__ == "__main__":
    main()
