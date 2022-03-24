import sys
from common import *
from mip import run_experiments

network = Network(sys.argv[1])
trolleys = network.readTrolleys(sys.argv[2])
forbid_trucks2h = True

# set parameters needed to evaluate runs
bestsolval = 1e8
cnt = 0
usedTruckRoutesFileName = None

# run experiments with 2h discretization
while True:
    tickHours = 2.0
    tickZero = 0.0

    usedTrucksOutputFileName = f"log_run_{cnt}"
    cnt += 1
    TIMELIMIT = 30

    solval = run_experiments(network, trolleys, tickHours, tickZero, usedTrucksOutputFileName, usedTruckRoutesFileName, forbid_trucks2h, True, TIMELIMIT)

    if solval < 0.99 * bestsolval:
        bestsolval = solval
        usedTruckRoutesFileName = usedTrucksOutputFileName
        print(f"run {cnt}: found improved solution with value {bestsolval} for discretization of 2h")
    else:
        print(f"run {cnt}: no better solution could be found within the time limit for discretization of 2h")
        break

# run experiments with 1h discretization
bestsolval = 1e8
first_run = True
forbid_trucks1h = False
while True:
    tickHours = 1.0
    tickZero = 0.0

    usedTrucksOutputFileName = f"log_run_{cnt}"
    cnt += 1
    TIMELIMIT = 1800

    solval = run_experiments(network, trolleys, tickHours, tickZero, usedTrucksOutputFileName, usedTruckRoutesFileName, forbid_trucks1h or first_run, not first_run, TIMELIMIT)
    first_run = False

    if solval < 0.99 * bestsolval:
        bestsolval = solval
        usedTruckRoutesFileName = usedTrucksOutputFileName
        print(f"run {cnt}: found improved solution with value {bestsolval} for discretization of 1h")
    else:
        print(f"run {cnt}: no better solution could be found within the time limit for discretization of 1h")
        break

# run experiments with 0.5h discretization
bestsolval = 1e8
first_run = True
forbid_trucks30min = False

# just do 2 runs with 0.5h discretization

# the first run has a time limit and constructs a solution from the 1h discretization for the 0.5h discretization
tickHours = 0.5
tickZero = 0.0

usedTrucksOutputFileName = f"log_run_{cnt}"
cnt += 1
TIMELIMIT = 600

solval = run_experiments(network, trolleys, tickHours, tickZero, usedTrucksOutputFileName, usedTruckRoutesFileName, forbid_trucks30min, False, TIMELIMIT)
bestsolval = solval
usedTruckRoutesFileName = usedTrucksOutputFileName
print(f"run {cnt}: found improved solution with value {bestsolval} for discretization of 0.5h")

# the second run has a very long time limit and tries to find a solution as good as possible
tickHours = 0.5
tickZero = 0.0

usedTrucksOutputFileName = f"log_run_{cnt}_final"
cnt += 1
TIMELIMIT = 86400               # run for one entire day

solval = run_experiments(network, trolleys, tickHours, tickZero, usedTrucksOutputFileName, usedTruckRoutesFileName, forbid_trucks30min, False, TIMELIMIT)

if solval < 0.99 * bestsolval:
    bestsolval = solval
    print(f"run {cnt}: found improved solution with value {bestsolval} for discretization of 0.5h")
else:
    print(f"run {cnt}: no better solution could be found within the time limit for discretization of 0.5h")
