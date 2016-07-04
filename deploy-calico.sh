mkdir -p ./binaries
mkdir -p ./default
mkdir -p ./conf
mkdir -p ./init
if [ ! -f ./binaries/calicoctl ]; then
    curl -L https://github.com/projectcalico/calico-containers/releases/download/v0.20.0/calicoctl -o ./binaries/calicoctl
fi
if [ ! -f ./binaries/calico ]; then
    curl -L https://github.com/projectcalico/calico-cni/releases/download/v1.3.1/calico -o ./binaries/calico
fi
if [ ! -f ./binaries/calico-ipam ]; then
    curl -L https://github.com/projectcalico/calico-cni/releases/download/v1.3.1/calico-ipam -o ./binaries/calico-ipam
fi

nodes=${nodes:-"vcap@10.10.103.250 vcap@10.10.103.162 vcap@10.10.103.223"}
masterIP="192.168.56.102"
function deploy {
    for i in $nodes
    do
        nodeIP=${i#*@}
        echo $nodeIP
        cat <<EOF > ./default/kubelet
KUBELET_OPTS=" --hostname-override=${nodeIP}  --api-servers=http://$masterIP:8080  --logtostderr=true  --cluster-dns=192.168.3.10  --cluster-domain=cluster.local  --network-plugin=cni  --network-plugin-dir=/etc/cni/net.d  --pod-infra-container-image=docker.io/kubernetes/pause  --config=  "
EOF
        cat <<EOF > ./default/calicoctl
ETCD_AUTHORITY=$masterIP:4001
CALICOCTL_OPTS="node --ip=${nodeIP} --detach=false"
EOF
        cat <<EOF > ./conf/10-calico.conf
{
    "name": "calico-k8s-network",
    "type": "calico",
    "etcd_authority": "$masterIP:4001",
    "log_level": "info",
    "ipam": {
        "type": "calico-ipam"
    }
}
EOF
        ssh ${i} "sudo service flanneld stop"
        ssh ${i} "sudo rm /etc/init/flanneld.conf"
        ssh ${i} "mkdir -p ~/tmp/bin"
        ssh ${i} "mkdir -p ~/tmp/default"
        ssh ${i} "mkdir -p ~/tmp/conf"
        ssh ${i} "mkdir -p ~/tmp/init"
        scp ./binaries/calicoctl ./binaries/calico ./binaries/calico-ipam ${i}:~/tmp/bin
        scp ./default/* ${i}:~/tmp/default
        scp ./conf/* ${i}:~/tmp/conf
        scp ./init/* ${i}:~/tmp/init
        ssh ${i} "sudo mkdir -p /etc/cni/net.d"
        ssh ${i} "sudo mkdir -p /opt/bin"
        ssh ${i} "sudo mkdir -p /opt/cni/bin"
        ssh ${i} "sudo cp ~/tmp/bin/calicoctl /opt/bin"
        ssh ${i} "sudo chmod a+x /opt/bin/calicoctl"
        ssh ${i} "sudo cp ~/tmp/bin/calico ~/tmp/bin/calico-ipam /opt/cni/bin"
        ssh ${i} "sudo chmod a+x /opt/cni/bin/calico"
        ssh ${i} "sudo chmod a+x /opt/cni/bin/calico-ipam"
        ssh ${i} "sudo service calicoctl stop"
        ssh ${i} "sudo service kubelet stop"
        ssh ${i} "sudo cp ~/tmp/default/* /etc/default"
        ssh ${i} "sudo cp ~/tmp/conf/* /etc/cni/net.d"
        ssh ${i} "sudo cp ~/tmp/init/* /etc/init"
        ssh ${i} "sudo service calicoctl start"
        ssh ${i} "sudo service kubelet start"
        rm ./default/kubelet
        rm ./default/calicoctl
        rm ./conf/10-calico.conf
    done
}

function clear {
    for i in $nodes
    do
        ssh ${i} "rm -rf ~/tmp"
        ssh ${i} "sudo service calicoctl stop"
        ssh ${i} "sudo rm /etc/init/calicoctl.conf"
        ssh ${i} "sudo rm /etc/default/calicoctl"
        ssh ${i} "sudo rm -r /opt/bin"
        ssh ${i} "sudo rm -r /opt/cni/bin"
        ssh ${i} "sudo rm -r /etc/cni/net.d"
        ssh ${i} "sudo killall kubelet"
        ssh ${i} "sudo docker rm -f calico-node"
    done
}

function main {
    if [ $1 = "deploy" ]; then
        deploy
    elif [ $1 = "clear" ]; then
        clear
    fi
}

main $*
