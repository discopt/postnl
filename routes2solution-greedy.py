import sys
from common import Instance

if len(sys.argv) <= 2:
  sys.stderr.write(f'Usage: {sys.argv[0]} INSTANCE-FILE ROUTES-FILE\nComputes a solution greedily using only the given routes.\n')
  sys.exit(1)

instance = Instance(sys.argv[1])
sys.stderr.write(f'Read instance with {len(instance.places)} places, {len(instance.trolleys)} trolleys and time range [{instance.start},{instance.end}].\n')
routes = instance.readRoutes(sys.argv[2])

trolleysByOrigin = { p : [] for p in instance.places.keys() }
for t,data in instance.trolleys.items():
  trolleysByOrigin[data.origin].append((data.release, t))
for place in instance.places.keys():
  trolleysByOrigin[place].sort()
  print(instance.places[place].name, trolleysByOrigin[place])
