from gurobipy import *
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

    distances = dict()
    demand = dict()
    depots = []
    crossdocks = []

    for line in f:

        if line.startswith('d'):
            origin = int(line.split()[1])
            dest = int(line.split()[2])
            dist = int(line.split()[3])

            if not origin in distances:
                distances[origin] = {dest: dist}
            else:
                distances[origin][dest] = dist

        elif line.startswith('t'):
            origin = int(line.split()[2])
            dest = int(line.split()[3])
            deadline = int(line.split()[5])

            if not origin in demand:
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

    f.close()

    return distances, demand, depots, crossdocks

##################################
# METHODS FOR BUILDING THE MODEL
##################################

def create_truck_variables(model, distances, arcs, times):
    '''
    returns dictionary of truck variables
    '''

    arc_vars = dict()
    
    for (i,j) in arcs:
        for t in times:
            arc_vars[(i,j,t)] = model.addVar(vtype=GRB.INTEGER, name="arc%d_%d_%d" % (i,j,t), obj=distances[i][j])

    return arc_vars

def create_shift_variables(model, shifts, arcs, times, is_integer):
    '''
    returns dictionary of shift variables
    '''

    shift_vars = dict()
    vtype = GRB.INTEGER if is_integer else GRB.CONTINUOUS
    
    for (i,j) in arcs:
        for (s,st) in shifts:
            for t in times:
                shift_vars[(i,j,s,st,t)] = model.addVar(vtype=vtype, name="shift%d_%d_%d_%d_%d" % (i,j,s,st,t), obj=0.0)

    return shift_vars

def create_inventory_variables(model, shifts, signed_locations, times):
    '''
    returns dictionary of inventory variables
    '''

    inventory_vars = dict()

    for (i,j) in signed_locations:
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

def create_depot_truck_capacity_constraints(model, truck_vars, arcs, locations, times, depot_truck_capacity, depots, loading_time):
    '''
    creates and adds depot truck capacity constraints to model
    '''

    for i in depots:
        for t in times:
            model.addConstr( quicksum(truck_vars[(i,j,t-eta)] for j in locations for eta in range(min(t+1,loading_time)) if (i,j) in arcs)
                             +
                             quicksum(truck_vars[(j,i,t-eta)] for j in locations for eta in range(min(t+1,loading_time)) if (j,i) in arcs)
                             <= depot_truck_capacity)

def create_out_capacity_constraints(model, inventory_vars, times, shifts, depots, out_capacity):
    '''
    creates and adds out capacity constraints for depots
    '''

    for i in depots:
        for t in times:
            model.addConstr( quicksum(inventory_vars[(i,0,s,st,t)] for (s,st) in shifts) <= out_capacity)

def create_in_capacity_constraints(model, inventory_vars, times, shifts, depots, in_capacity):
    '''
    creates and adds in capacity constraints for depots
    '''

    for i in depots:
        for t in times:
            model.addConstr( quicksum(inventory_vars[(i,1,s,st,t)] for (s,st) in shifts) <= in_capacity)

def create_inventory_constraints_outdepot(model, inventory_vars, shift_vars, loading_time, times, shifts, depots, locations, inflow):
    '''
    creates and adds inventory constraints for out depots
    '''

    for t in times:
        for i in depots:
            for (s,st) in shifts:
                if t >= eta:
                    model.addConstr( inventory_vars[(i,0,s,st,t)] == inventory_vars[(i,0,s,st,t-1)] + inflow[i][t][(s,st)]
                                     -
                                     quicksum(shift_vars[(i,j,s,st,t-eta)] for j in locations if (i,j) in arcs))
                elif t >= 1:
                    model.addConstr( inventory_vars[(i,0,s,st,t)] == inventory_vars[(i,0,s,st,t-1)] + inflow[i][t][(s,st)])
                else:
                    model.addConstr( inventory_vars[(i,0,s,st,t)] == inflow[i][t][(s,st)])



def create_mip(distances, demand, depots, crossdocks, truck_capacity, loading_time, shift_vars_integer, depot_truck_capacity,
               in_capacity, out_capacity):
    '''
    returns the network design model of phase 2
    '''

    indepots = [(d,1) for d in depots]
    outdepots = [(d,0) for d in depots]
    locations = depots + crossdocks
    signed_locations = indepots + outdepots + [(d,-1) for d in depots] # used to distinguish in- and out-depots for inventory
    arcs = [(i,j) for i in locations for j in locations if i != j]
    shifts = [(j,t) for i in demand.keys() for j in demand[i].keys() for t in demand[i][j].keys()]
    shifts = set(shifts)
    times = range(max(t for (s,t) in shifts) + 1)

    mip = Model()

    truck_vars = create_truck_variables(mip, distances, arcs, times)
    shift_vars = create_shift_variables(mip, shifts, arcs, times, shift_vars_integer)
    inventory_vars = create_inventory_variables(mip, shifts, signed_locations, times)

    create_capacity_constraints(mip, truck_vars, shift_vars, arcs, shifts, times, truck_capacity)
    create_depot_truck_capacity_constraints(mip, truck_vars, arcs, locations, times, depot_truck_capacity, depots, loading_time)
    create_out_capacity_constraints(mip, inventory_vars, times, shifts, depots, out_capacity)
    create_in_capacity_constraints(mip, inventory_vars, times, shifts, depots, in_capacity)
    # create_inventory_constraints_outdepot(mip, inventory_vars, shift_vars, loading_time, times, shifts, depots, locations, inflow)

    
    mip.optimize()


    
def main():

    truck_capacity = 48
    in_capacity = 400
    out_capacity = 1200
    depot_truck_capacity = 12
    loading_time = 2            # (un-) loading time in ticks
    shift_vars_integer = False  # whether shift variables are integral

    start = time.time()
    distances, demand, depots, crossdocks = read_data(sys.argv[1])
    create_mip(distances, demand, depots, crossdocks, truck_capacity, loading_time, shift_vars_integer, depot_truck_capacity,
               in_capacity, out_capacity)
    end = time.time()
    print("time for building the model:", end - start)
    
if __name__ == "__main__":
    main()
