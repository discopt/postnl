import sys
from common import *

if len(sys.argv) <= 2:
  sys.stderr.write(f'Usage: {sys.argv[0]} INSTANCE-FILE ROUTES-FILE\nComputes a solution greedily using only the given routes.\n')
  sys.exit(1)

instance = Instance(sys.argv[1])
sys.stderr.write(f'Read instance with {len(instance.places)} places, {len(instance.trolleys)} trolleys and time range [{instance.start},{instance.end}].\n')
routes = instance.readRoutes(sys.argv[2])

trolleysByOrigin = { p : [] for p in instance.places.keys() }
""" 
for t,data in instance.trolleys.items():
  trolleysByOrigin[data.origin].append((data.release, t))

for place in instance.places.keys():
  trolleysByOrigin[place].sort()
  print(instance.places[place].name, trolleysByOrigin[place])
"""
actions = { t : [] for t in range(instance.start, instance.end+1) }
for t,data in instance.trolleys.items():
  actions[data.release].append((data.release, 'r', t))
  actions[data.deadline].append((data.deadline, 's', t))

for t in range(instance.start, instance.end):
    # first do all actions
    for action in actions[t]:
        if action[1] == 'r': # release of the trolley
            instance.trolleys[action[2]].position = instance.trolleys[action[2]].origin
            instance.places[instance.trolleys[action[2]].origin].outAmount =+ 1 
        if action[1] == 's': # shift for trolley
            if instance.trolleys[action[2]].position == instance.trolleys[action[2]].destination:
                instance.trolleys[action[2]].position = 999999  
                instance.places[instance.trolleys[action[2]].origin].inAmount = -1 
        if action[1] == 'a': # arrival of a transport
            pass 
    # for every depot: check if a transport should leave
    for t, data in instance.places.items():
        if data.inAmount >= 400:
            pass 
            # transport
        