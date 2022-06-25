#!/bin/bash

OUTPUTDIR=~/maps/

python map.py data/net_base.network /tmp/only-direct.png data/net_U44_trolleys_1234.30-best.out direct
convert /tmp/only-direct.png -crop 945x1100+510+180 ${OUTPUTDIR}/only-direct.png
python map.py data/net_base.network /tmp/only-cross.png data/net_U44_trolleys_1234.30-best.out cross
convert /tmp/only-cross.png -crop 945x1100+510+180 ${OUTPUTDIR}/only-cross.png
python map.py data/net_base.network /tmp/only-used.png data/net_U44_trolleys_1234.30-best.out used
convert /tmp/only-used.png -crop 945x1100+510+180 ${OUTPUTDIR}/only-used.png

python map.py data/net_base.network /tmp/times18.png data/net_U44_trolleys_1234.30-best.out times 18 18.9 
python map.py data/net_base.network /tmp/times19.png data/net_U44_trolleys_1234.30-best.out times 19 19.9 
python map.py data/net_base.network /tmp/times20.png data/net_U44_trolleys_1234.30-best.out times 20 20.9 
python map.py data/net_base.network /tmp/times21.png data/net_U44_trolleys_1234.30-best.out times 21 21.9 
python map.py data/net_base.network /tmp/times22.png data/net_U44_trolleys_1234.30-best.out times 22 22.9 
python map.py data/net_base.network /tmp/times23.png data/net_U44_trolleys_1234.30-best.out times 23 23.9 
python map.py data/net_base.network /tmp/times24.png data/net_U44_trolleys_1234.30-best.out times 24 24.9 
python map.py data/net_base.network /tmp/times25.png data/net_U44_trolleys_1234.30-best.out times 25 25.9 
python map.py data/net_base.network /tmp/times26.png data/net_U44_trolleys_1234.30-best.out times 26 26.9 
python map.py data/net_base.network /tmp/times27.png data/net_U44_trolleys_1234.30-best.out times 27 27.9 
python map.py data/net_base.network /tmp/times28.png data/net_U44_trolleys_1234.30-best.out times 28 28.9 
python map.py data/net_base.network /tmp/times29.png data/net_U44_trolleys_1234.30-best.out times 29 29.9 
python map.py data/net_base.network /tmp/times30.png data/net_U44_trolleys_1234.30-best.out times 30 30.9 
python map.py data/net_base.network /tmp/times31.png data/net_U44_trolleys_1234.30-best.out times 31 31.9 
python map.py data/net_base.network /tmp/times32.png data/net_U44_trolleys_1234.30-best.out times 32 32.9 
python map.py data/net_base.network /tmp/times33.png data/net_U44_trolleys_1234.30-best.out times 33 33.9 
python map.py data/net_base.network /tmp/times34.png data/net_U44_trolleys_1234.30-best.out times 34 34.9 
python map.py data/net_base.network /tmp/times35.png data/net_U44_trolleys_1234.30-best.out times 35 35.9 
python map.py data/net_base.network /tmp/times36.png data/net_U44_trolleys_1234.30-best.out times 36 36.9 
python map.py data/net_base.network /tmp/times37.png data/net_U44_trolleys_1234.30-best.out times 37 37.9 
for T in `seq 18 37`; do
  convert /tmp/times${T}.png -crop 945x1100+510+180 ${OUTPUTDIR}/times${T}.png
done

LOCATIONS=`python map.py data/net_base.network /home/matthias/commodity_1_1.png data/net_base_trolleys_1234.30-9.out shift UNKNOWN 1 | tail -n 1 | sed -e 's/,/ /g'`
for LOCATION in ${LOCATIONS}; do
  for SHIFT in `seq 1 9`; do
    python map.py data/net_base.network /tmp/commodity_${LOCATION}_${SHIFT}.png data/net_base_trolleys_1234.30-9.out shift ${LOCATION} ${SHIFT}
    convert /tmp/commodity_${LOCATION}_${SHIFT}.png -crop 945x1100+510+180 ${OUTPUTDIR}/commodity_${LOCATION}_${SHIFT}.png
  done
done
