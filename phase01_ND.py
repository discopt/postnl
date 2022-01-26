from gurobipy import *
import sys

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

            if not origin in demand:
                demand[origin] = {dest: 1}
            elif not dest in demand[origin]:
                demand[origin][dest] = 1
            else:
                demand[origin][dest] = demand[origin][dest] + 1

        elif line.startswith('p'):
            idx = int(line.split()[1])
            outcapacity = int(line.split()[8])

            if is_crossdock_capacity(outcapacity):
                crossdocks.append(idx)
            else:
                depots.append(idx)

    f.close()

    return distances, demand, depots, crossdocks


def compute_paths(depots, crossdocks):
    '''
    computes all paths of length at most 3 from all depots to all other depots
    '''

    paths = []

    # length 1 paths
    paths1 = [(i,j) for i in depots for j in depots if i != j]

    # length 2 paths
    paths2 = [(i,k,j) for i in depots for j in depots for k in crossdocks if i != j]

    # length 3 paths
    paths3 = [(i,k,l,j) for i in depots for j in depots for k in crossdocks for l in crossdocks if i != j and k != l]

    return paths1 + paths2 + paths3


##################################
# METHODS FOR BUILDING THE MODEL
##################################

def create_arc_variables(model, distances, arcs):
    '''
    returns dictionary of arc variables
    '''

    arc_vars = dict()
    
    for (i,j) in arcs:
        arc_vars[(i,j)] = model.addVar(vtype=GRB.INTEGER, name="arc%d_%d" % (i,j), obj=distances[i][j])

    return arc_vars

def create_path_variables(model, paths):
    '''
    returns dictionary of path variables
    '''

    path_vars = dict()
    
    for p in paths:
        path_vars[p] = model.addVar(vtype=GRB.CONTINUOUS, name="path%s" % pathname(p), obj=0.0)

    return path_vars

def create_demand_constraints(model, demand, depots, path_vars, paths):
    '''
    creates and adds demand constraints to model
    '''

    for i in depots:
        for j in depots:
            if i == j:
                continue

            if i in demand.keys() and j in demand[i].keys():
                model.addConstr( quicksum(path_vars[p] for p in paths if p[0] == i and p[-1] == j) == demand[i][j])
            else:
                model.addConstr( quicksum(path_vars[p] for p in paths if p[0] == i and p[-1] == j) == 0)

def create_capacity_constraints(model, arc_vars, path_vars, arcs, paths, truck_capacity):
    '''
    creates and adds capacity constraints to model
    '''

    for a in arcs:
        model.addConstr( quicksum(path_vars[p] for p in paths if is_arc_in_path(a, p)) <= truck_capacity * arc_vars[a])

def evaluate_solution(arc_vars, arcs):
    '''
    evaluates the solution of the model and prints arcs present in designed network to screen
    '''

    solution = []
    for a in arcs:
        if arc_vars[a].X > 0.5:
            solution.append(a)

    print("optimized network has %d arcs (out of %d)" % (len(solution), len(arcs)))
    print(solution)

def create_mip(distances, demand, depots, crossdocks, truck_capacity):
    '''
    returns the network design model of phase 1
    '''

    locations = depots + crossdocks
    arcs = [(i,j) for i in locations for j in locations if i != j]
    paths = compute_paths(depots, crossdocks)

    mip = Model()

    arc_vars = create_arc_variables(mip, distances, arcs)
    path_vars = create_path_variables(mip, paths)

    create_demand_constraints(mip, demand, depots, path_vars, paths)
    create_capacity_constraints(mip, arc_vars, path_vars, arcs, paths, truck_capacity)
    
    mip.optimize()

    evaluate_solution(arc_vars, arcs)


def main():

    truck_capacity = 48

    distances, demand, depots, crossdocks = read_data(sys.argv[1])
    create_mip(distances, demand, depots, crossdocks, truck_capacity)
    
if __name__ == "__main__":
    main()
