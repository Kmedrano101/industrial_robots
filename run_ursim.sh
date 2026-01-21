#!/bin/bash
# Run URSim with External Control for ROS2

docker run --rm -it \
  -p 5900:5900 \
  -p 6080:6080 \
  -p 29999:29999 \
  -p 30001:30001 \
  -p 30002:30002 \
  -p 30003:30003 \
  -p 30004:30004 \
  -v ${HOME}/.ursim/urcaps:/urcaps \
  -v ${HOME}/.ursim/programs:/ursim/programs \
  -e ROBOT_MODEL=${ROBOT_MODEL:-UR5} \
  --name ursim \
  universalrobots/ursim_e-series
