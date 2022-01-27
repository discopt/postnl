import sys
from common import Instance
from gurobipy import *

if len(sys.argv) == 1:
  sys.stderr.write(f'Usage: {sys.argv[0]} INSTANCE-FILE\nComputes all direct routes and outputs them in the routes file format.\n')
  sys.exit(1)

instance = Instance(sys.argv[1])
sys.stderr.write(f'Read instance with {len(instance.places)} places, {len(instance.trolleys)} trolleys and time range [{instance.start},{instance.end}].\n')

arcs = []
for source in instance.places.keys():
  for target in instance.places.keys():
    if target != source:
      arcs.append((source,target))

items = set()
for trolley in instance.trolleys.values():
  items.add((trolley.destination, trolley.deadline))
items = list(items)

model = Model("")
x = {}
for arc in arcs:
  latest = instance.end - instance.dist[arc[0],arc[1]]
  for t in range(instance.start, latest+1):
    x[t,arc] = model.addVar(vtype=GRB.INTEGER, name=f'x_{t}_{arc[0]}#_{arc[1]}', obj=instance.hourDistances[arc[0],arc[1]])

y = {}
for arc in arcs:
  for item in items:
    if item[0] == arc[1] or instance.places[arc[1]].isCross:
      if item[0] == arc[1]:
        latest = item[1] - instance.dist[arc[0],arc[1]]
      else:
        latest = item[1] - instance.dist[arc[0],arc[1]] - instance.dist[arc[1],item[0]]
      for t in range(instance.start, latest+1):
        y[t,arc,item] = model.addVar(vtype=GRB.INTEGER, name=f'y_{t}_{arc[0]}_{arc[1]}_{item[0]}_{item[1]}')
      for t in range(latest, instance.end+1):
        y[t,arc,item] = 0

zOut = {}
zIn = {}
for place in instance.places.keys():
  for item in items:
    for t in range(instance.start, instance.end+1):
      zOut[t,place,item] = model.addVar(vtype=GRB.INTEGER, name=f'z#out_{t}_{place}_{item[0]}_{item[1]}')
      zIn[t,place,item] = model.addVar(vtype=GRB.INTEGER, name=f'z#in_{t}_{place}_{item[0]}_{item[1]}')

model.update()

# Linking
for arc in arcs:
  latest = instance.end - instance.dist[arc[0],arc[1]]
  for t in range(instance.start, latest+1):
    model.addConstr( quicksum( y[t,arc,item] for item in items if (t,arc,item) in y.keys() ) <= 48 * x[t,arc] )

# Balance
for place in instance.places.keys():
  for item in items:
    for t in range(instance.start+1, instance.end+1):
      model.addConstr( z )

# Capacities
for place in instance.places.keys():
  for t in range(instance.start, instance.end+1):
    model.addConstr( quicksum( zOut[t,place,item] for item in items ) <= instance.places[place].outCapacity )
    model.addConstr( quicksum( zIn[t,place,item] for item in items ) <= instance.places[place].inCapacity )

model.optimize()
