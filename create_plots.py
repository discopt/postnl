from mip import *
from common import *
import matplotlib.pyplot as plt
import math

network = Network(sys.argv[1])
trolleys = network.readTrolleys(sys.argv[4])
tickHours = float(sys.argv[2])
tickZero = float(sys.argv[3])
solfile = sys.argv[5]

network.setDiscretization(tickHours, tickZero)

def time2tick(time, timeshift, ticklen):
    return int((time - timeshift) / ticklen)

def createPlots(network, trolleys, logfile):

    # collect information about releasing the trolleys over time
    inflow = {}
    sources = set()
    targets = set()
    deadlines = set()
    mintick = 9999
    maxtick = -9999
    for t in trolleys:
        releaseTick = network.trolleyReleaseTick(t)
        source = t.source
        target = t.commodity[0]
        deadline = network.deadlineTick(t.get_commodity())
        inflow[source,releaseTick,target,deadline] = inflow.get((source,releaseTick,target,deadline), 0) + 1
        sources.add(source)
        targets.add(target)
        deadlines.add(deadline)

        if releaseTick < mintick:
            mintick = releaseTick
        if deadline > maxtick:
            maxtick = deadline        

    f = open(logfile, 'r')

    # read the capacities used by the trucks in the previous solution
    truck_outflow = {}
    truck_inflow = {}
    for line in f:
        if not line.startswith('S '):
            continue
        split = line.split()
        i, j, target, shift, ticktime, num = int(split[1]), int(split[2]), int(split[3]), int(split[4]), float(split[5]), float(split[6])
        
        tick = time2tick(ticktime, tickZero, tickHours)
        deadline = int(math.floor((network.deadline((target,shift)) - tickZero) / tickHours))

        if i == 0 and target == 1 and deadline == 65:
            print(tick, shift, deadline, num, i, j)
        # if i == 0 and j == 1 and deadline == 65:
        #     print(num)

        truck_outflow[i,target,deadline,tick] = truck_outflow.get((i,target,deadline,tick), 0) + num
        arrival = tick + network.travelTicks(i,j)
        truck_inflow[j,target,deadline,arrival] = truck_inflow.get((j,target,deadline,arrival), 0) + num

    f.close()

    print("inflow")
    for k in inflow.keys():
        if k[0] == 0 and k[2] == 1 and k[3] == 65:
            print(k[1], inflow[k])
    print()
    print("truck outflows")
    for k in truck_outflow.keys():
        if k[0] == 0 and k[1] == 1 and k[2] == 65:
            print(k[3], truck_outflow[k])
    print()
    print("truck inflows")
    for k in truck_inflow.keys():
        if k[0] == 0 and k[1] == 1 and k[2] == 65:
            print(truck_intflow[k])
    print()

    inventories = {}
    locations = network.locations
    for tick in range(mintick, maxtick+1):
        for source in locations:
            for target in locations:
                for deadline in deadlines:
                    if tick > mintick:
                        if source == 0 and target == 1 and deadline == 65:
                            print(tick, inventories[source,tick-1,target,deadline], inflow.get((source,tick,target,deadline), 0), truck_inflow.get((source,target,deadline, tick),0), truck_outflow.get((source,target,deadline,tick), 0))
                        inventories[source,tick,target,deadline] = inventories[source,tick-1,target,deadline] + inflow.get((source,tick,target,deadline), 0) + truck_inflow.get((source,target,deadline, tick),0) - truck_outflow.get((source,target,deadline,tick), 0)
                    else:
                        inventories[source,tick,target,deadline] = inflow.get((source,tick,target,deadline), 0)
            

    
    for s in sources:
        for t in targets:
            if s == t:
                continue
            # if not (s == 1 and t == 1):
            #     continue
            for d in deadlines:
          
                print(s,t,d)
                yvals = [inventories.get((s,j,t,d),0) for j in range(mintick, maxtick+1)]
                fig, ax1 = plt.subplots()

                lns1 = ax1.plot(range(mintick, maxtick+1), yvals)
                plt.show()


createPlots(network, trolleys, solfile)
