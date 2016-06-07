###Calico

1. 性能最好
2. --ipip 模式下 不能发 udp 包
3. ACL 容易做
4. 需要自己管理 ip ？
5. 3和4其实相关

### flannel

1. 性能没有 calico 好
2. 不需要侵入 docker 启动

### weave

1. 性能比 flannel 还差一些
2. 通过域名访问？
3. 需要用包装过的接口启动容器