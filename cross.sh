#!/bin/bash

NETWORK=$1
BASE_SEED=$2

for SEED in `cat private2/seeds.txt`; do
  python mip.py private2/net_base.network 0.5 0 private2/trolleys_${SEED}.csv -i private2/net_${NETWORK}_trolleys_${BASE_SEED}.30-best.sol -o private2/cross_${NETWORK}_${BASE_SEED}_${SEED}.sol -d 0.1 -t 3600 -c -m >& private2/cross_${NETWORK}_${BASE_SEED}_${SEED}.log
done
