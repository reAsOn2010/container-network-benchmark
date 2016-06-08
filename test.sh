#!/bin/bash
function place-init-docker-script {
  sed -e "s~\${REGISTRY_MIRROR}~${REGISTRY_MIRROR}~" -e "s~\${CONFIG_PATH}~${1}~" restart-docker.sh > /etc/init.d/flannel-docker
  chmod ugo+x /etc/init.d/flannel-docker
  update-rc.d flannel-docker defaults
}

place-init-docker-script $*
