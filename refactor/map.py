import cartopy
import cartopy.crs as ccrs
import matplotlib.pyplot as plt
import matplotlib
import sys
import math
#from modelicares import util


from common import * 

network = Network(sys.argv[1])
outputFileName = sys.argv[2]

countConnections = {}
countShiftTrolleys = {}
drawAllPlaces = True
drawAllConnections = False
drawUsed = False
drawUsedDirect = False
drawUsedCross = False
drawOcean = False
drawTimeRange = None
drawShift = None

if len(sys.argv) > 4:
  if sys.argv[4] == 'used':
    drawUsed = True
  if sys.argv[4] == 'direct':
    drawUsedDirect = True
  elif sys.argv[4] == 'cross':
    drawUsedCross = True
  elif sys.argv[4] == 'times' and len(sys.argv) > 6:
    drawTimeRange = (float(sys.argv[5]), float(sys.argv[6]))
  elif sys.argv[4] == 'shift' and len(sys.argv) > 6:
    drawShift = (sys.argv[5], int(sys.argv[6]))

if drawShift:
  try:
    drawShift = (int(drawShift[0]), drawShift[1])
  except:
    for i in network.locations:
      if drawShift[0] == network.name(i):
        drawShift = (i, drawShift[1])
    if isinstance(drawShift[0], str):
      print(f'Could not find location <{drawShift[0]}>. These locations are available:\n' + ','.join(network.name(i) for i in network.locations))
      sys.exit(1)
  print(f'Considering shift {drawShift[1]} for destination <{network.name(drawShift[0])}> = {drawShift[0]}.')

minTime = float('inf')
maxTime = float('-inf')
lastS = 0
if len(sys.argv) > 3:
  trucksFile = open(sys.argv[3], 'r')
  for line in trucksFile.read().split('\n'):
    split = line.split()
    if split and split[0] == 'C':
      source, target, time, num = int(split[1]), int(split[2]), float(split[3]), int(split[4])
      if num > 0:
        minTime = min(minTime, time)
        maxTime = max(maxTime, time)
        if not drawTimeRange or (time >= drawTimeRange[0] and time <= drawTimeRange[1]):
          countConnections[source,target] = countConnections.get((source,target), 0) + num
      lastS = 0
    if split and split[0] == 'S':
      source, target, destination, shift, time, entry = int(split[1]), int(split[2]), int(split[3]), int(split[4]), float(split[5]), int(split[6])
      num = entry - lastS # TODO: Due to a (by now fixed) bug, trolley numbers were aggregated in the output file.
      if drawShift and drawShift[0] == destination and drawShift[1] == shift:
        countShiftTrolleys[source,target] = countShiftTrolleys.get((source,target), 0) + num
      lastS = entry
      
  trucksFile.close()
print(f'Times are in [{minTime},{maxTime}].')

#plt.figure(figsize=(19.2, 10.8), dpi=500)
plt.figure()
ax = plt.axes(projection=cartopy.crs.Mercator(5.2))
ax.add_feature(cartopy.feature.BORDERS, linestyle='-', alpha=1)
ax.add_feature(cartopy.feature.COASTLINE)
if drawOcean:
  ax.add_feature(cartopy.feature.OCEAN, facecolor=(0.0,0.0,1.0))
ax.set_extent ((3.6, 7.1, 50.9, 53.4), cartopy.crs.PlateCarree())

if drawAllConnections:
  for i,j in network.connections:
    plt.plot([network.x(i),network.x(j)], [network.y(i),network.y(j)], color='darkgrey', linewidth=1, marker='o', transform=ccrs.Geodetic())

if drawTimeRange or drawUsed or drawUsedDirect or drawUsedCross:
  arrows = []
  for i,j in countConnections.keys():
    isCross = network.isCross(i) or network.isCross(j)
    if isCross and not (drawTimeRange or drawUsed or drawUsedCross):
      continue
    elif not isCross and not (drawTimeRange or drawUsed or drawUsedDirect):
      continue

    if countConnections[i,j] <= 0:
      continue
    if countConnections[i,j] == 1:
      color = 'green'
      linestyle = 'solid'
      linewidth = 0.5
    elif countConnections[i,j] == 2:
      color = 'blue'
      linestyle = 'solid'
      linewidth = 1
    elif countConnections[i,j] == 3:
      color = 'orange'
      linestyle = 'solid'
      linewidth = 1.5
    elif countConnections[i,j] == 4:
      color = 'red'
      linestyle = 'solid'
      linewidth = 2
    else:
      color = 'purple'
      linestyle = 'solid'
      linewidth = 4
    arrows.append((linewidth, network.x(i), network.y(i), 0.95*(network.x(j) - network.x(i)), 0.95*(network.y(j) - network.y(i)), 0.0005*linewidth, color, linestyle))

  # We now sort the arrow tuples and draw them, lowest priority first.
  arrows.sort()
  for priority,x,y,dx,dy,w,c,ls in arrows:
    ax.arrow(x, y, dx, dy, width=w, head_width=0.04, head_length=0.05, fc=c, ec=c, ls=ls, length_includes_head=True, transform=ccrs.PlateCarree())

if drawShift:
  arrows = []
  for i,j in countShiftTrolleys.keys():
    if countShiftTrolleys[i,j] == 0:
      continue
    if countShiftTrolleys[i,j] < 10:
      color = 'green'
      linestyle = 'solid'
      linewidth = 0.5
    elif countShiftTrolleys[i,j] < 20:
      color = 'blue'
      linestyle = 'solid'
      linewidth = 1
    elif countShiftTrolleys[i,j] < 30:
      color = 'orange'
      linestyle = 'solid'
      linewidth = 1.5
    elif countShiftTrolleys[i,j] < 40:
      color = 'red'
      linestyle = 'solid'
      linewidth = 2
    else:
      assert countShiftTrolleys[i,j] >= 40
      color = 'purple'
      linestyle = 'solid'
      linewidth = 3
    arrows.append((linewidth, network.x(i), network.y(i), 0.95*(network.x(j) - network.x(i)), 0.95*(network.y(j) - network.y(i)), 0.0005*linewidth, color, linestyle))

  # We now sort the arrow tuples and draw them, lowest priority first.
  arrows.sort()
  for priority,x,y,dx,dy,w,c,ls in arrows:
    ax.arrow(x, y, dx, dy, width=w, head_width=0.04, head_length=0.05, fc=c, ec=c, ls=ls, length_includes_head=True, transform=ccrs.PlateCarree())

if drawAllPlaces:
  for i in network.locations:
    marker = 'D' if network.isCross(i) else 'o'
    plt.plot([network.x(i)], [network.y(i)], marker=marker, markersize=6, color='black', transform=ccrs.PlateCarree())

plt.savefig(outputFileName, dpi=300)
#plt.show()
