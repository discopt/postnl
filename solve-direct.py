import sys
from instance import Instance

instance = Instance(sys.argv[1])
print(f'Read instance with time range [{instance.start},{instance.end}].')

trolleysByOrigin = { p : [] for p in instance.places.keys() }
for t,data in instance.trolleys.items():
  trolleysByOrigin[data.origin].append((data.release, t))
for place in instance.places.keys():
  trolleysByOrigin[place].sort()
  print(instance.places[place].name, trolleysByOrigin[place])
