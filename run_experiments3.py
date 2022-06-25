import sys
from common import *
from mip import run_experiments
from os.path import exists
import time

network = Network(sys.argv[1])
trolleys = network.readTrolleys(sys.argv[2])
prefix = sys.argv[3]

# 120min discretization

count120 = 0
lastFileName = None
bestVals = None
bestValsFileName = None
while True:
  count120 += 1
  outputFileName = f'{prefix}.120-{count120}.sol'
  if exists(outputFileName):
    print(f'Output file <{outputFileName}> exists!')
    sys.exit(1)

  vals = run_experiments(network=network, trolleys=trolleys, tickHours=2.0, tickZero=0.0,
    modifyTrolleysDeliverable=False, writeTrucksFileName=outputFileName,
    readTrucksFileName=lastFileName, allowedTruckDeviation=1, constructInitial=True,
    timeLimit=300, solutionLimit=None, solutionTimeLimit=60)
  lastFileName = outputFileName

  if vals is None:
    print(f'No solution found.')
    break
  else:
    print(f'Found 120min solution with value {vals[0]} with total distance {vals[1]:.2f} and penalties {vals[2]:.1f}.')
    if bestVals is None or vals[0] < bestVals[0] * 0.99:
      bestVals = vals
      bestValsFileName = lastFileName
      print(f'Current best solution is stored in <{lastFileName}>.')
    else:
      break

# 60min discretization

count60 = 0
while True:
  count60 += 1
  outputFileName = f'{prefix}.60-{count60}.sol'
  if exists(outputFileName):
    print(f'Output file <{outputFileName}> exists!')
    sys.exit(1)

  vals = run_experiments(network=network, trolleys=trolleys, tickHours=1.0, tickZero=0.0,
    modifyTrolleysDeliverable=False, writeTrucksFileName=outputFileName,
    readTrucksFileName=lastFileName, allowedTruckDeviation=1.1, constructInitial=True,
    timeLimit=1800, solutionLimit=None, solutionTimeLimit=60)
  lastFileName = outputFileName

  if vals is None:
    print(f'No solution found.')
    break
  else:
    print(f'Found 60min solution with value {vals[0]} with total distance {vals[1]:.2f} and penalties {vals[2]:.1f}.')
    if bestVals is None or vals[0] < bestVals[0] * 0.99:
      bestVals = vals
      bestValsFileName = lastFileName
      print(f'Current best solution is stored in <{lastFileName}>.')
    else:
      break

# 30min discretization

count30 = 0
solTimeLimit = 300
remainingTime = 86400
while remainingTime > 60:
  count30 += 1
  outputFileName = f'{prefix}.30-{count30}.sol'
  if exists(outputFileName):
    print(f'Output file <{outputFileName}> exists!')
    sys.exit(1)

  start = time.time()
  vals = run_experiments(network=network, trolleys=trolleys, tickHours=0.5, tickZero=0.0,
    modifyTrolleysDeliverable=False, writeTrucksFileName=outputFileName,
    readTrucksFileName=lastFileName, allowedTruckDeviation=0.6, constructInitial=True,
    timeLimit=remainingTime, solutionLimit=2, solutionTimeLimit=solTimeLimit)
  end = time.time()
  remainingTime -= (end - start)
  lastFileName = outputFileName

  if vals:
    print(f'Found 30min solution with value {vals[0]} with total distance {vals[1]:.2f} and penalties {vals[2]:.1f}.')
    if bestVals is None or vals[0] < bestVals[0] * 0.99:
      bestVals = vals
      bestValsFileName = lastFileName
      print(f'Current best solution is stored in <{lastFileName}>.')
      continue
  else:
    print(f'No solution found.')
  solTimeLimit *= 2
  print(f'New solution time limit is {solTimeLimit}.')

