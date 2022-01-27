import sys
from common1 import *
import matplotlib.pyplot as plt
from mpl_toolkits.basemap import Basemap


if len(sys.argv) <= 2:
  sys.stderr.write(f'Usage: {sys.argv[0]} INSTANCE-FILE ROUTES-FILE\nCreates a map of the routes.\n')
  sys.exit(1)

instance = Instance(sys.argv[1])
sys.stderr.write(f'Read instance with {len(instance.places)} places, {len(instance.trolleys)} trolleys and time range [{instance.start},{instance.end}].\n')
instance.readRoutes2use(sys.argv[2])

lat_min = 999999
lat_max = -999999
lon_min = 999999
lon_max = -999999
for t,data in instance.places.items():
    if data.lattitude < lat_min:
        lat_min = data.lattitude
    if data.lattitude > lat_max:
        lat_max = data.lattitude
    if data.longitude < lon_min:
        lon_min = data.longitude
    if data.longitude > lon_max:
        lon_max = data.longitude

    
m = Basemap(projection = 'merc', llcrnrlat=lat_min - 2,urcrnrlat=lat_max + 2, llcrnrlon=lon_min - 2, urcrnrlon=lon_max + 2, lat_ts=40, resolution='h')

for t,data in instance.routes2use.items(): 
    if instance.places[data.origin].isCross or instance.places[data.destination].isCross:
        lat = [instance.places[data.origin].lattitude, instance.places[data.destination].lattitude] 
        lon = [instance.places[data.origin].longitude, instance.places[data.destination].longitude] 
        x, y = m(lon, lat)
        if instance.places[data.origin].isCross and instance.places[data.destination].isCross:
            lineColor = 'red'
        elif instance.places[data.origin].isCross:
            lineColor= 'blue'
        else:
            lineColor= 'green'
        m.plot(x, y, marker=None, markersize=5, linewidth=0.5, color=lineColor) 

m.drawcoastlines()
m.fillcontinents(color='grey')
m.drawmapboundary(fill_color='white')
m.drawcountries(color='black')
plt.title("Routes")
plt.savefig('routesCross.png', dpi = 300)
plt.show() 

