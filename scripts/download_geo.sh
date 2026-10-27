#!/bin/sh
# Download the raw geometry the basemap and border scripts start from (not kept in git).
set -e
cd "$(dirname "$0")/../geo"
NE=https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson
OP=https://raw.githubusercontent.com/openpolis/geojson-italy/master/geojson
for f in ne_50m_land ne_50m_lakes ne_10m_rivers_lake_centerlines; do curl -fsSL -o "$f.geojson" "$NE/$f.geojson"; done
curl -fsSL -o limits_IT_regions.geojson "$OP/limits_IT_regions.geojson"
curl -fsSL -o limits_IT_provinces.geojson "$OP/limits_IT_provinces.geojson"
echo "downloaded into geo/"
