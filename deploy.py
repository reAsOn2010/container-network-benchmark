#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

import time
import fabric.api as fab
from fabric.api import env, run, sudo, task
from fabric.context_managers import cd, settings

env.use_ssh_config = True
env.roledefs = {
    'node1': ['192.168.56.101'],
    'node2': ['192.168.56.102'],
}

CALICOCTL = '/root/calicoctl'
ETCD = '/root/etcd/etcd'
ETCDCTL = '/root/etcd/etcdctl'
WEAVE = '/root/weave'


def run_etcd():
    assert(len(fab.env.roles) == 1)
    role = fab.env.roles[0]
    ip = env.roledefs[role][0]
    sudo('%s --name %s --initial-advertise-peer-urls http://%s:2380 \
            --listen-peer-urls http://0.0.0.0:2380 \
            --listen-client-urls http://0.0.0.0:2379,http://127.0.0.1:4001 \
            --advertise-client-urls http://0.0.0.0:2379 \
            --initial-cluster-token etcd-cluster \
            --initial-cluster node1=http://192.168.56.101:2380,node2=http://192.168.56.102:2380 \
            --initial-cluster-state new' % (ETCD, role, ip))

def run_calico_env(ipip='yes'):
    with open('./calico_benchmark.txt', 'w') as f:
        pass
    time.sleep(5)
    sudo('%s node --ip=%s' % (CALICOCTL, env.host_string))
    if ipip == 'yes':
        sudo('%s pool add 192.168.100.0/24 --ipip --nat-outgoing' % CALICOCTL)
    else:
        sudo('%s pool add 192.168.100.0/24 --nat-outgoing' % CALICOCTL)
    if env.host_string in env.roledefs['node1']:
        sudo('docker run -v /bin:/tmp/bin -v /usr/bin:/tmp/usr/bin --net=none --name worker-1 -tid ubuntu /tmp/usr/bin/iperf -s')
        sudo('docker run -v /bin:/tmp/bin -v /usr/bin:/tmp/usr/bin --net=none --name worker-2 -tid ubuntu /tmp/usr/bin/iperf -s -u')
        sudo('%s container add worker-1 192.168.100.1' % CALICOCTL)
        sudo('%s container add worker-2 192.168.100.2' % CALICOCTL)
        sudo('%s profile add PROF_1' % CALICOCTL)
        sudo('%s profile add PROF_2' % CALICOCTL)
        sudo('%s container worker-1 profile append PROF_1' % CALICOCTL)
        sudo('%s container worker-2 profile append PROF_2' % CALICOCTL)
    elif env.host_string in env.roledefs['node2']:
        sudo('docker run -v /bin:/tmp/bin -v /usr/bin:/tmp/usr/bin --net=none --name worker-3 -tid ubuntu')
        sudo('%s container add worker-3 192.168.100.3' % CALICOCTL)
        sudo('%s container worker-3 profile append PROF_1' % CALICOCTL)

def run_calico_tests():
    with settings(warn_only=True):
        if env.host_string in env.roledefs['node1']:
            sudo('docker exec worker-1 /tmp/bin/ping -c 4 192.168.100.3')
            sudo('docker exec worker-1 /tmp/bin/ping -c 4 192.168.100.2')
            sudo('%s container worker-2 profile append PROF_1' % CALICOCTL)
            sudo('docker exec worker-2 /tmp/bin/ping -c 4 192.168.100.3')
            same_host_result = sudo('docker exec worker-2 /tmp/usr/bin/iperf -c 192.168.100.1')
            with open('./calico_benchmark.txt', 'a') as f:
                print('same host:', file=f)
                print(same_host_result, file=f)
            same_host_result = sudo('docker exec worker-1 /tmp/usr/bin/iperf -c 192.168.100.2 -u -b 100m')
            with open('./calico_benchmark.txt', 'a') as f:
                print('same host:', file=f)
                print(same_host_result, file=f)
        elif env.host_string in env.roledefs['node2']:
            sudo('docker exec worker-3 /tmp/bin/ping -c 4 192.168.100.1')
            cross_host_result = sudo('docker exec worker-3 /tmp/usr/bin/iperf -c 192.168.100.1')
            with open('./calico_benchmark.txt', 'a') as f:
                print('cross host:', file=f)
                print(cross_host_result, file=f)
            cross_host_result = sudo('docker exec worker-3 /tmp/usr/bin/iperf -c 192.168.100.2 -u -b 100m')
            with open('./calico_benchmark.txt', 'a') as f:
                print('cross host:', file=f)
                print(cross_host_result, file=f)

def stop_calico():
    with settings(warn_only=True):
        if env.host_string in env.roledefs['node1']:
            sudo('%s container remove worker-1' % CALICOCTL)
            sudo('%s container remove worker-2' % CALICOCTL)
            sudo('docker rm -f worker-1 worker-2')
        elif env.host_string in env.roledefs['node2']:
            sudo('%s container remove worker-3' % CALICOCTL)
            sudo('docker rm -f worker-3')
        sudo('docker rm -f calico-node')
        sudo('%s pool remove 192.168.100.0/24' % CALICOCTL)
        sudo('%s profile remove PROF_1' % CALICOCTL)
        sudo('%s profile remove PROF_2' % CALICOCTL)


ip1 = None
ip2 = None
ip3 = None

def run_flannel_env(t='vxlan'):
    global ip1, ip2, ip3
    with open('./flannel_benchmark.txt', 'w') as f:
        pass
    sudo('%s set /coreos.com/network/config \
            \'{"Network": "192.168.0.0/16", \
            "SubnetLen": 24, \
            "SubnetMin": "192.168.1.0", \
            "SubnetMax": "192.168.99.0", \
            "Backend": { \
                "Type": "%s"}}\'' % (ETCDCTL, t))
    sudo('service docker stop')
    sudo('dtach -n `mktemp -u /tmp/flanneld.XXXX` /root/flannel/bin/flanneld -iface="enp0s3"')
    time.sleep(1)
    sudo('source /run/flannel/subnet.env; ifconfig docker0 ${FLANNEL_SUBNET}')
    sudo('source /run/flannel/subnet.env; dtach -n `mktemp -u /tmp/docker.XXXX` docker daemon --bip=${FLANNEL_SUBNET} --mtu=${FLANNEL_MTU}')
    time.sleep(5)
    sudo('docker ps')

    if env.host_string in env.roledefs['node1']:
        sudo('docker run -v /bin:/tmp/bin -v /usr/bin:/tmp/usr/bin --name worker-1 -tid ubuntu /tmp/usr/bin/iperf -s')
        sudo('docker run -v /bin:/tmp/bin -v /usr/bin:/tmp/usr/bin --name worker-2 -tid ubuntu /tmp/usr/bin/iperf -s -u')
        tmp = sudo('docker exec worker-1 /tmp/bin/ip addr')
        ip1 = tmp[tmp.find('192.168'):].split('/')[0]
        tmp = sudo('docker exec worker-2 /tmp/bin/ip addr')
        ip2 = tmp[tmp.find('192.168'):].split('/')[0]
    elif env.host_string in env.roledefs['node2']:
        sudo('docker run -v /bin:/tmp/bin -v /usr/bin:/tmp/usr/bin --name worker-3 -tid ubuntu')
        tmp = sudo('docker exec worker-3 /tmp/bin/ip addr')
        ip3 = tmp[tmp.find('192.168'):].split('/')[0]
    print(ip1, ip2, ip3)

def run_flannel_tests():
    global ip1, ip2, ip3
    if env.host_string in env.roledefs['node1']:
        sudo('docker exec worker-1 /tmp/bin/ping -c 4 %s' % ip2)
        sudo('docker exec worker-1 /tmp/bin/ping -c 4 %s' % ip3)
        same_host_result = sudo('docker exec worker-2 /tmp/usr/bin/iperf -c %s' % ip1)
        with open('./flannel_benchmark.txt', 'a') as f:
            print('same host:', file=f)
            print(same_host_result, file=f)
        same_host_result = sudo('docker exec worker-1 /tmp/usr/bin/iperf -c %s -u -b 100m' % ip2)
        with open('./flannel_benchmark.txt', 'a') as f:
            print('same host:', file=f)
            print(same_host_result, file=f)
    elif env.host_string in env.roledefs['node2']:
        cross_host_result = sudo('docker exec worker-3 /tmp/usr/bin/iperf -c %s' % ip1)
        with open('./flannel_benchmark.txt', 'a') as f:
            print('cross host:', file=f)
            print(cross_host_result, file=f)
        cross_host_result = sudo('docker exec worker-3 /tmp/usr/bin/iperf -c %s -u -b 100m' % ip2)
        with open('./flannel_benchmark.txt', 'a') as f:
            print('cross host:', file=f)
            print(cross_host_result, file=f)

def stop_flannel():
    with settings(warn_only=True):
        if env.host_string in env.roledefs['node1']:
            sudo('docker rm -f worker-1 worker-2')
        elif env.host_string in env.roledefs['node2']:
            sudo('docker rm -f worker-3')
        sudo('killall flanneld')
        sudo('killall docker')
        sudo('%s rm /coreos.com/network/config' % ETCDCTL)
        sudo('service docker start')


def run_weave_env():
    with open('./weave_benchmark.txt', 'w') as f:
        pass
    if env.host_string in env.roledefs['node1']:
        sudo('%s launch' % WEAVE)
        sudo('%s run -v /bin:/tmp/bin -v /usr/bin:/tmp/usr/bin -itd --name=worker-1 ubuntu /tmp/usr/bin/iperf -s' % WEAVE)
        sudo('%s run -v /bin:/tmp/bin -v /usr/bin:/tmp/usr/bin -itd --name=worker-2 ubuntu /tmp/usr/bin/iperf -s -u' % WEAVE)
    elif env.host_string in env.roledefs['node2']:
        sudo('%s launch 192.168.56.101' % WEAVE)
        sudo('%s run -v /bin:/tmp/bin -v /usr/bin:/tmp/usr/bin -itd --name=worker-3 ubuntu' % WEAVE)


def run_weave_tests():
    if env.host_string in env.roledefs['node1']:
        sudo('docker exec worker-1 /tmp/bin/ping -c 4 worker-2')
        sudo('docker exec worker-1 /tmp/bin/ping -c 4 worker-3')
        same_host_result = sudo('docker exec worker-2 /tmp/usr/bin/iperf -c worker-1')
        with open('./weave_benchmark.txt', 'a') as f:
            print('same host:', file=f)
            print(same_host_result, file=f)
        same_host_result = sudo('docker exec worker-2 /tmp/usr/bin/iperf -c worker-2 -u -b 100m')
        with open('./weave_benchmark.txt', 'a') as f:
            print('same host:', file=f)
            print(same_host_result, file=f)
    elif env.host_string in env.roledefs['node2']:
        sudo('docker exec worker-3 /tmp/bin/ping -c 4 worker-1')
        cross_host_result = sudo('docker exec worker-3 /tmp/usr/bin/iperf -c worker-1')
        with open('./weave_benchmark.txt', 'a') as f:
            print('cross host:', file=f)
            print(cross_host_result, file=f)
        cross_host_result = sudo('docker exec worker-3 /tmp/usr/bin/iperf -c worker-2 -u -b 100m')
        with open('./weave_benchmark.txt', 'a') as f:
            print('cross host:', file=f)
            print(cross_host_result, file=f)


def stop_weave():
    with settings(warn_only=True):
        if env.host_string in env.roledefs['node1']:
            sudo('docker rm -f worker-1 worker-2')
        elif env.host_string in env.roledefs['node2']:
            sudo('docker rm -f worker-3')
        sudo('%s stop' % WEAVE)
