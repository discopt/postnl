import cartopy
import cartopy.crs as ccrs
import matplotlib.pyplot as plt
import matplotlib
import sys
import math

from common import * 

network = Network(sys.argv[1])

countConnections = {}

if len(sys.argv) > 2:
  trucksFile = open(sys.argv[2], 'r')
  for line in trucksFile.read().split('\n'):
    split = line.split()
    if split and split[0] == 'T':
      source, target, time = int(split[1]), int(split[2]), float(split[3])
      countConnections[source,target] = countConnections.get((source,target), 0) + 1
  trucksFile.close()


drawAllPlaces = True
drawAllConnections = False
drawConnections = True
drawOcean = False

plt.figure(figsize=(6, 8))
ax = plt.axes(projection=cartopy.crs.Mercator(5.2))
ax.add_feature(cartopy.feature.BORDERS, linestyle='-', alpha=1)
ax.add_feature(cartopy.feature.COASTLINE)
if drawOcean:
  ax.add_feature(cartopy.feature.OCEAN, facecolor=(0.0,0.0,1.0))
ax.set_extent ((3.6, 7.1, 50.9, 53.4), cartopy.crs.PlateCarree())

if drawAllConnections:
  for i,j in network.connections:
    plt.plot([network.x(i),network.x(j)], [network.y(i),network.y(j)], color='darkgrey', linewidth=1, marker='o', transform=ccrs.Geodetic())

if drawConnections:
  maxConnections = max(countConnections.values())
  print(f'Maximum #connections = {maxConnections}')
  colormap = matplotlib.cm.get_cmap('cool')
  for i,j in countConnections.keys():
    if countConnections[i,j] <= 0:
      continue
    if countConnections[i,j] == 1:
      color = 'green'
      linestyle = 'dotted'
      linewidth = 0.5
    elif countConnections[i,j] == 2:
      color = 'blue'
      linestyle = 'dashed'
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
    plt.plot([network.x(i),network.x(j)], [network.y(i),network.y(j)], color=color, linestyle=linestyle, linewidth=linewidth, transform=ccrs.Geodetic())

if drawAllPlaces:
  for i in network.locations:
    marker = 'D' if network.isCross(i) else 'o'
    plt.plot([network.x(i)], [network.y(i)], marker=marker, markersize=6, color='black', transform=ccrs.PlateCarree())

plt.show()
