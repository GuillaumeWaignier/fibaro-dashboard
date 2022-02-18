#!/bin/bash

##################################################
# Convert a kibana export into a jinja template  #
##################################################

INPUT=`cat export.ndjson`
OUTPUT="kibana.ndjson.j2"

echo "{% raw %}${INPUT}{% endraw %}" > ${OUTPUT}

sed -i -e "s/hc3_fibaro_power-/{% endraw %}{{elasticsearch_index_power}}{% raw %}/g" ${OUTPUT}
sed -i -e "s/hc3_fibaro_climate/{% endraw %}{{elasticsearch_index}}{% raw %}/g" ${OUTPUT}
sed -i -e "s/hc3_fibaro_resources/{% endraw %}{{elasticsearch_index_resources}}{% raw %}/g" ${OUTPUT}
