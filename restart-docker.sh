#!/bin/bash
set -e

### BEGIN INIT INFO
# Provides:           caicloud
# Required-Start:     $syslog $remote_fs
# Required-Stop:      $syslog $remote_fs
# Should-Start:       cgroupfs-mount cgroup-lite
# Should-Stop:        cgroupfs-mount cgroup-lite
# Default-Start:      2 3 4 5
# Default-Stop:       0 1 6
# Short-Description:  make sure docker starts with flannel config 
# Description:
### END INIT INFO

attempt=0
while true; do
  echo "Attempt $(($attempt+1)) to check for subnet.env set by flannel"
  if [[ -f /run/flannel/subnet.env ]] && \
      grep -q "FLANNEL_SUBNET" /run/flannel/subnet.env && \
      grep -q "FLANNEL_MTU" /run/flannel/subnet.env ; then
    break
  else
    if (( attempt > 60 )); then
      echo "timeout waiting for subnet.env from flannel"
      exit 2
    fi
      attempt=$((attempt+1))
      sleep 3
  fi
done

# In order for docker to correctly use flannel setting, we first stop docker,
# flush nat table, delete docker0 and then start docker. Missing any one of
# the steps may result in wrong iptable rules, see:
# https://github.com/caicloud/caicloud-kubernetes/issues/25
sudo service docker stop
sudo iptables -t nat -F
sudo ip link set dev docker0 down
sudo brctl delbr docker0

source /run/flannel/subnet.env
echo DOCKER_OPTS=\"-H tcp://127.0.0.1:4243 -H unix:///var/run/docker.sock \
     --bip=${FLANNEL_SUBNET} --mtu=${FLANNEL_MTU} \
     --registry-mirror=${REGISTRY_MIRROR} \" > ${CONFIG_PATH}
sudo service docker start
