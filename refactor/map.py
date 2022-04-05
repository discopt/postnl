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

minTime = float('inf')
maxTime = float('-inf')
if len(sys.argv) > 3:
  trucksFile = open(sys.argv[3], 'r')
  for line in trucksFile.read().split('\n'):
    split = line.split()
    if split and split[0] == 'T':
      source, target, time = int(split[1]), int(split[2]), float(split[3])
      minTime = min(minTime, time)
      maxTime = max(maxTime, time)
      if not drawTimeRange or (time >= drawTimeRange[0] and time <= drawTimeRange[1]):
        countConnections[source,target] = countConnections.get((source,target), 0) + 1
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
#    line = util.ArrowLine([network.x(i),network.y(i)], [network.x(j), network.y(j)], color=color, ls=linestyle, lw=linewidth, arrow='>', arrowsize=20)
#    ax.add_line(line)
#plt.plot([network.x(i),network.x(j)], [network.y(i),network.y(j)], color=color, linestyle=linestyle, linewidth=linewidth, transform=ccrs.Geodetic())
    ax.arrow(network.x(i), network.y(i), 0.95*(network.x(j) - network.x(i)), 0.95*(network.y(j) - network.y(i)), width=0.0005*linewidth, head_width=0.04, head_length=0.05, fc=color, ec=color, ls=linestyle, length_includes_head=True, transform=ccrs.PlateCarree())

if drawAllPlaces:
  for i in network.locations:
    marker = 'D' if network.isCross(i) else 'o'
    plt.plot([network.x(i)], [network.y(i)], marker=marker, markersize=6, color='black', transform=ccrs.PlateCarree())

plt.savefig(outputFileName, dpi=300)
#plt.show()
