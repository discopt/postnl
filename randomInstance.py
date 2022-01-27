import random
from common import *

instance = Instance(sys.argv[1])
demandinstance = Demandinstance(instance)

randinstance = Instance()
randinstance.places = instance.places
randinstance.tickHours = instance.tickHours
randinstance.timeShift = instance.timeShift
randinstance.crossTicks = instance.crossTicks
randinstance.trolleys = {}

temptrolleys = []

for o,d in demandinstance.demand:
    origin = demandinstance.places[o]
    destination = demandinstance.places[d]
    demand = demandinstance.demand[(o, d)]
    for _ in range(demand):
        t = Trolley()
        shifts = list(destination.shifts)
        shiftnr = random.randint(0, len(shifts)-1)
        t.origin = o
        t.destination = d
        t.release = random.randint(origin.spawn_start, origin.spawn_end)
        t.deadline = shifts[shiftnr]
        temptrolleys += [t]

sortedtrolleys = sorted(temptrolleys, key=lambda x: x.release)
randinstance.trolleys = {i: sortedtrolleys[i] for i in range(len(temptrolleys))}

for i in randinstance.trolleys:
    print(f'{randinstance.trolleys[i].release} {randinstance.trolleys[i].deadline}')
