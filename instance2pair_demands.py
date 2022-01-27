import random
import sys
import math
from common import Instance, Demandinstance

if len(sys.argv) == 1:
    sys.stderr.write(f'Usage: {sys.argv[0]} INSTANCE-FILE\nComputes from a full instance file '
                     f'the demands for the (origin, destination)-pairs.\n')
    sys.exit(1)

instance = Instance(sys.argv[1])
sys.stderr.write(f'Read instance with {len(instance.places)} places, {len(instance.trolleys)} trolleys and time range [{instance.start},{instance.end}].\n')

demandinstance = Demandinstance(instance)

print(demandinstance)

pair_error = 0.25 #0.33 to approximate 0.07
depot_error = 0.07 #0.098 to approximate 0.02
total_error = 0.02

# pair sigma = pair_error/3
# depot sigma = depot_error/3
# total sigma = total_error/3

pair_sigma = {}
depot_sigma = {}
total_sigma = demandinstance.totaldemand()*total_error/3

for o, d in demandinstance.demand:
    pair_sigma[(o, d)] = demandinstance.demand[(o, d)]*pair_error/3

for d in demandinstance.depots:
    depot_sigma[d] = demandinstance.depottotaldemand(d)*depot_error/3

print(f'Total sigma is {total_sigma:.2f}. sqrt of sum of squares of depotsigma\'s '
      f'is {math.sqrt(sum([sigma**2 for sigma in depot_sigma.values()])):.2f}')

for d in demandinstance.depots:
    print(f'Total sigma of depot {d} is {depot_sigma[d]:.2f}. sqrt of sum of squares of pairsigma\'s '
          f'is {math.sqrt(sum([pair_sigma[(i,j)] ** 2 for i,j in pair_sigma if i == d])):.2f}')

randompaireddemand = {}

for o, d in demandinstance.demand:
    randompaireddemand[(o, d)] = round(random.normalvariate(demandinstance.demand[(o, d)], pair_sigma[(o, d)]))

