import sys
from common import *
from mip import run_experiments
import time

network = Network(sys.argv[1])
trolleys = network.readTrolleys(sys.argv[2])

# the first run has a time limit and constructs a solution from the 1h discretization for the 0.5h discretization
tickHours = 0.5
tickZero = 0.0

cnt = 10
totaltimelimit = 3600*24
usedTruckRoutesFileName = "log_run_9_final"
usedTrucksOutputFileName = f"newlog_run_{cnt}"

bestsolval = 1e9

starttime = time.time()
solval = run_experiments(network, trolleys, tickHours, tickZero, usedTrucksOutputFileName, usedTruckRoutesFileName, True, True, totaltimelimit, sollimit=2)
endtime = time.time()
if solval < 0.99 * bestsolval:
    bestsolval = solval
    print(f"run {cnt}: found improved solution with value {bestsolval} for discretization of 0.5h")
else:
    print(f"run {cnt}: no better solution could be found within the time limit for discretization of 0.5h")

totaltimelimit -= endtime - starttime
soltl = 60

while totaltimelimit > 0:
    usedTruckRoutesFileName = f"newlog_run_{cnt}"
    cnt += 1
    usedTrucksOutputFileName = f"newlog_run_{cnt}"

    starttime = time.time()
    solval = run_experiments(network, trolleys, tickHours, tickZero, usedTrucksOutputFileName, usedTruckRoutesFileName, False, True, totaltimelimit, sollimit=2, soltimelimit=soltl)
    endtime = time.time()

    totaltimelimit -= endtime - starttime

    if solval < bestsolval - 1:
        bestsolval = solval
        print(f"run {cnt}: found improved solution with value {bestsolval} for discretization of 0.5h")
        soltl = 60
    else:
        print(f"run {cnt}: no better solution could be found within the time limit for discretization of 0.5h; increase time limit after improved solution has been found")
        soltl = 2*soltl
