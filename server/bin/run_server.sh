#!/usr/bin/env bash

source ../venv/bin/activate

killall python3
killall npm

python3 bin/main.py development.ini &
P1=$!
sleep 5
python3 bin/run_image_processor.py development.ini &
P2=$!
python3 bin/run_multi_image_analysis.py development.ini &
P3=$!
python3 bin/run_time_series_analysis.py development.ini &
P4=$!
sleep 5
python3 bin/image_collector.py &
P5=$!

cd ../client
npm start &
P6=$!

wait $P1 $P2 $P3 $P4 $P5 $P6
kill $P1 -s 9
kill $P2 -s 9
kill $P3 -s 9
kill $P4 -s 9
kill $P5 -s 9
kill $P6 -s 9
