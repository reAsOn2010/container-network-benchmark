## docker 网络方案测试

整个测试分别测试了 calico flannel 和 weave 三种网络，分别测试了连通性，同 host 的两个容器之间和跨 host 的网络性能和抖动

### 测试环境

* 两台 vbox 虚拟机 ubuntu 16.04 LTS with Docker version 1.11.2, build b9f10c9
* Linux 4.4.0-22-generic
* 一个二层网络内

### 测试原理
* 测试过程比较简单：
	1. 搭建网络环境
	2. 通过 ping 测试连通性
	3. 通过 iperf 测试网络性能，分别选取同一个宿主机上的两个容器和跨宿主机的两个容器
		* tcp 模式测试网络带宽
		* udp 模式测试丢包和延时，使用的是 100Mbps 的发送速率

### Notes

* 整个测试基本上参照 [Battlefield-Calico-Flannel-Weave-and-Docker-Overlay-Network](http://chunqi.li/2015/11/15/Battlefield-Calico-Flannel-Weave-and-Docker-Overlay-Network/)
* 可以通过 deploy.py 重现整个测试（依赖安装好 docker etcd calicoctl flannel weave 的两台机器，通过 fabric 运行）
* calico 的测试没有打开 --ipip
* flannel 的测试使用的 type=vxlan
* flannel 的 host-gw 模式没用用到 overlay 网络所以无法跨越二层隔离，一般来说云服务器都没法用这个模式，但理论上性能会比 vxlan 稍好
* CMGS 的文章也比较有价值 [docker-network-cloud](http://cmgs.me/life/docker-network-cloud)
* 一些八卦: ~~CMGS 从豆瓣离职之后去芒果台搞容器，在私有物理机上推行 macvlan 的网络，据说表现很不错，不过之前他又从芒果台离职了~~

## 结论

###Calico

* connectivity ok
* performance

| Env | Bandwidth | Lantency | Packet loss (under 100Mbps) |
| --- | --- | --- | --- |
| same host | 21.4 Gbits/sec | 0.010 ms | None |
| cross host| 1.54 Gbits/sec | 0.043 ms | None |

* pros
	* 性能最好
	* 容易做访问控制，网络设置当中有 profile 概念，在同一个 profile 当中的节点网络互通
* cons
	* 需要通过控制接口将容器添加到 calico 的库中，分配 ip 和配置 profile，才能打通网络
	* 依赖 BGP 路由协议，在集群规模很大的情况下，学习路由可能会有较大开销，但这个现在没有理论依据？
	* 需要自己管理 ip (calico 实现了 CNI 接口并且有提供 ipam，所以这个问题似乎不大)

### flannel

* connectivity ok
* performance

| Env |Bandwidth | Lantency | Packet loss (under 100Mbps) |
| --- | --- | --- | --- |
| same host | 19.8 Gbits/sec | 0.010 ms | None |
| cross host| 1.45 Gbits/sec | 0.049 ms | None |

* pros
	* 不需要侵入 docker 启动方式
	* ip 自动分配
* cons
	* 性能没有 calico 好，但还算不错
	* 需要侵入 docker daemon 的启动参数，也是我们现在使用当中隐含的一个 bug（机器重启后 flanneld 重启，导致随机选取的新子网和以前配置在 DOCKER_OPT 当中的参数不一样，从而使得整个 node 网络不可用）


### weave

* connectivity ok
* performance

| Env |Bandwidth | Lantency | Packet loss (under 100Mbps) |
| --- | --- | --- | --- |
| same host | 21.3 Gbits/sec | 0.010 ms | None |
| cross host| 991 Mbits/sec | 0.141 ms | None |

* pros
	* ip 甚至是域名自动分配
* cons
	* 性能比 flannel 还差一些
	* 需要用包装过的接口启动容器
