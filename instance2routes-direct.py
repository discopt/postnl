import sys
from common import Instance

if len(sys.argv) == 1:
  sys.stderr.write(f'Usage: {sys.argv[0]} INSTANCE-FILE\nComputes all direct routes and outputs them in the routes file format.\n')
  sys.exit(1)

instance = Instance(sys.argv[1])
sys.stderr.write(f'Read instance with {len(instance.places)} places, {len(instance.trolleys)} trolleys and time range [{instance.start},{instance.end}].\n')

routes = {}

for origin in instance.places.keys():
  for destination in instance.places.keys():
    if origin != destination:
      routes[origin,destination] = [[origin, destination]]

instance.writeRoutes(routes)

