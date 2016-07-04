## Kubernetes with calico integration deployment

### 流程
因为部署 k8s 流程不少，所以这次测试时建立在 KUBERNETES_PROVIDER=ubuntu kube-up.sh 起的集群上的。

1. 整好 3 台机器，一台当 master 用
2. KUBERNETES_PROVIDER=ubuntu ./kube-up.sh 建立 k8s 集群，这个集群上会有 flanneld

以下是 calico 的部署流程 (参照 [kubernetes 官方文档](http://http://kubernetes.io/docs/getting-started-guides/ubuntu-calico/) 但文档用的是 systemd)

1. 下载 calicoctl 并拷贝到 /opt/bin
2. 下载 calico calico-ipam 并拷贝到 /opt/cni/bin (这个路径没有找到是哪里确定的。。。)
3. 创建 /etc/cni/net.d/10-calico.conf 配置 cni

		{
		    "name": "calico-k8s-network",
		    "type": "calico",
		    "etcd_authority": "$masterIP:4001",
		    "log_level": "info",
		    "ipam": {
		        "type": "calico-ipam"
		    }
		}

4. 配置 calicoctl 的 upstart 脚本，用于启动 calico-node 容器
5. 更新 kubelet 的 upstart 脚本使其与 calicoctl 一起启动
6. 配置 calicoctl 的 opts，指定 etcd endpoint 以及 host ip 用于加入集群
7. 更新 kubelet 的 opts 添加 `--network-plugin=cni  --network-plugin-dir=/etc/cni/net.d` 参数，让 kubelet 使用 calico CNI
8. service calicoctl restart; service kubelet restart

至此流程结束，k8s 集群已经使用 calico 提供的网络方案

### Notes
* 自动化的配置流程可以用 `deploy-calico.sh` 脚本进行
* calico 默认配置了一个 ip 池子为 192.168.0.0/16，所以不做任何额外配置启动的容器 ip 都会是从这个池子里取
* CNI 配置项当中的 "name" 字段将作为 calico profile 的名字，容器默认会被加入到这个 profile 当中，所以容器间全部互通没有隔离

### 配置 calico with k8s network policy

1. 在所有节点上将之前创建的 /etc/cni/net.d/10-calico.conf 修改为

		{
		    "name": "calico-k8s-network",
		    "type": "calico",
		    "etcd_authority": "$masterIP:4001",
		    "log_level": "info",
		    "ipam": {
		        "type": "calico-ipam"
		    },
		    "policy": {
		        "type": "k8s",
		        "k8s_api_root": ${K8S_API_URL}" (like: http://192.168.56.102:8080/api/v1")
		    }
		}

2. ubuntu 14.04 没有带 nsenter 所以需要编译之后放到 $PATH 里，可以参照 [why-there-is-no-nsenter-in-util-linux](http://askubuntu.com/questions/439056/why-there-is-no-nsenter-in-util-linux)
3. 装 ethtool
3. 在 master 节点上起 calico/k8s-policy-agent，将 policy-controller.yaml 放进 /etc/kubernetes/manifests 并设置 kubelet 的 --config 目录
4. 创建一个 k8s namespace 名为 `calico-system` 供 calico 使用
5. 重启 kubelet

### 效果

1. 创建两个 namespace eg. space1, space2
2. 分别在两个 ns 当中跑东西 `kubectl run my-nginx --image=nginx --replicas=3 --port=80 --namespace=space{1,2}`
3. 通过 calicoctl 查看 endpoint 信息，可以看到不同 ns 的容器已经被自动分配到不同 profile 当中

		root@master:/opt/bin# ./calicoctl endpoint show --detail
		+----------+-----------------+----------------------------------+----------------------------------+--------------------+-------------------+---------------+--------+
		| Hostname | Orchestrator ID |           Workload ID            |           Endpoint ID            |     Addresses      |        MAC        |    Profiles   | State  |
		+----------+-----------------+----------------------------------+----------------------------------+--------------------+-------------------+---------------+--------+
		|  master  |       k8s       | space1.my-nginx-3800858182-5vxk1 | 55ab44bc3c2f11e686c8080027cf6213 | 192.168.228.211/32 | fa:86:b5:7e:ce:28 | k8s_ns.space1 | active |
		|  master  |       k8s       | space2.my-nginx-3800858182-17drb | 55aa15c43c2f11e686c8080027cf6213 | 192.168.228.210/32 | 2e:18:f2:95:52:aa | k8s_ns.space2 | active |
		|  node1   |       k8s       | space1.my-nginx-3800858182-3flla | ecf6301e3c0911e68280080027521d01 |  192.168.77.81/32  | 7a:bd:d2:1d:cd:aa | k8s_ns.space1 | active |
		|  node1   |       k8s       | space2.my-nginx-3800858182-thldb | eb713ba83c0911e68280080027521d01 |  192.168.77.80/32  | c2:96:78:09:2c:22 | k8s_ns.space2 | active |
		|  node2   |       k8s       | space1.my-nginx-3800858182-fn8w4 | ecfa677e3c0911e688510800279c52cf |  192.168.39.81/32  | d2:bf:d8:ca:20:05 | k8s_ns.space1 | active |
		|  node2   |       k8s       | space2.my-nginx-3800858182-mjlc6 | eb70c4f23c0911e688510800279c52cf |  192.168.39.80/32  | e2:b6:c4:53:8f:b0 | k8s_ns.space2 | active |
		+----------+-----------------+----------------------------------+----------------------------------+--------------------+-------------------+---------------+--------+

4. 默认的行为是 AllowAll

		root@master:/opt/bin# ./calicoctl profile k8s_ns.space1 rule json
		{
		  "id": "k8s_ns.space1",
		  "inbound_rules": [
		    {
		      "action": "allow"
		    }
		  ],
		  "outbound_rules": [
		    {
		      "action": "allow"
		    }
		  ]
		}

5. 我们通过 annotation 改变 网络行为 `kubectl annotate ns space1 "net.alpha.kubernetes.io/network-isolation=yes" --overwrite=true` 此时这个容器的网络被完全隔离，DenyAll

		root@master:/opt/bin# ./calicoctl profile k8s_ns.space1 rule json
		{
		  "id": "k8s_ns.space1",
		  "inbound_rules": [
		    {
		      "action": "deny"
		    }
		  ],
		  "outbound_rules": [
		    {
		      "action": "allow"
		    }
		  ]
		}

6. 更复杂的网络设置需要通过 k8s 的 network policy API 进行配置，我尝试增加 NetworkPolicy 的 yaml，并且 calico 的 policy controller 确实获取到了 policy 变更的通知，但是网络行为没有发生改变，可能是配置不对。这个配置还没有一个正式的文档，所以先调研到这里了~

### 相关文档

* [Kubernetes Network Policy](https://github.com/kubernetes/kubernetes/issues/22469)
* [Calico Policy for Kubernetes](https://github.com/projectcalico/calico-containers/blob/master/docs/cni/kubernetes/NetworkPolicy.md)
* [Blog Aritcle: Kubernetes network policy](https://feiskyer.github.io/2016/02/17/Kubernetes-network-policy/)