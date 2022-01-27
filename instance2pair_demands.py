import sys
from common import Instance, Demandinstance

if len(sys.argv) == 1:
    sys.stderr.write(f'Usage: {sys.argv[0]} INSTANCE-FILE\nComputes from a full instance file '
                     f'the demands for the (origin, destination)-pairs.\n')
    sys.exit(1)

instance = Instance(sys.argv[1])
sys.stderr.write(f'Read instance with {len(instance.places)} places, {len(instance.trolleys)} trolleys and time range [{instance.start},{instance.end}].\n')

demandinstance = Demandinstance(instance)

print(demandinstance)
