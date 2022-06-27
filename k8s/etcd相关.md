1. 安装etcd
curl -L https://storage.googleapis.com/etcd/v3.4.16/etcd-v3.4.16-linux-amd64.tar.gz -o /tmp/etcd-v3.4.16-linux-amd64.tar.gz
cd /tmp/
tar -zvxf etcd-v3.4.16-linux-amd64.tar.gz
mv etcd-v3.4.16-linux-amd64 etcd
cd etcd
cp etcd* /usr/local/bin/
etcd --version

2. #部署etcd集群
etcd --enable-v2 --name infra00 --initial-advertise-peer-urls http://192.168.1.95:2380 --listen-peer-urls http://192.168.1.95:2380 --listen-client-urls http://192.168.1.95:2379,http://127.0.0.1:2379 --advertise-client-urls http://192.168.1.95:2379 --initial-cluster-token etcd-cluster-2 --initial-cluster infra00=http://192.168.1.95:2380,infra11=http://192.168.1.94:2380,infra22=http://192.168.1.96:2380 --initial-cluster-state new

etcd --enable-v2 --name infra11 --initial-advertise-peer-urls http://192.168.1.94:2380 \
  --listen-peer-urls http://192.168.1.94:2380 \
  --listen-client-urls http://192.168.1.94:2379,http://127.0.0.1:2379 \
  --advertise-client-urls http://192.168.1.94:2379 \
  --initial-cluster-token etcd-cluster-2 \
  --initial-cluster infra00=http://192.168.1.95:2380,infra11=http://192.168.1.94:2380,infra22=http://192.168.1.96:2380 \
  --initial-cluster-state new


etcd --enable-v2 --name infra22 --initial-advertise-peer-urls http://192.168.1.96:2380 \
  --listen-peer-urls http://192.168.1.96:2380 \
  --listen-client-urls http://192.168.1.96:2379,http://127.0.0.1:2379 \
  --advertise-client-urls http://192.168.1.96:2379 \
  --initial-cluster-token etcd-cluster-2 \
  --initial-cluster infra00=http://192.168.1.95:2380,infra11=http://192.168.1.94:2380,infra22=http://192.168.1.96:2380 \
  --initial-cluster-state new

3. 测试环境
etcdctl --endpoints=http://192.168.1.95:2379 put /testdir/testkey "Hello world"
etcdctl get /testdir/testkey --endpoints=http://192.168.1.95:2379

etcdctl put /testdir/testkey "test elastic"
etcdctl get /testdir/testkey

etcdctl member list
etcdctl --endpoints="http://192.168.1.95:2379,http://192.168.1.94:2379,http://192.168.1.94:2379"  endpoint  health

4. 添加节点
在etcd集群中的任意节点上使用etcdctl member add <memberName> [options] [flags]命令向集群中添加新节点的信息，其中需要指定memberName和--peer-urls参数。
 etcdctl member add infra3 --peer-urls=http://192.168.64.233:2380

Member 280b55dd4cc3232f added to cluster 1ce7ec0197a02727

ETCD_NAME="infra3"
ETCD_INITIAL_CLUSTER="infra3=http://192.168.64.233:2380,infra2=http://192.168.64.237:2380,infra1=http://192.168.64.234:2380"
ETCD_INITIAL_ADVERTISE_PEER_URLS="http://192.168.64.233:2380"
ETCD_INITIAL_CLUSTER_STATE="existing"
接下来，根据add命令生成的环境变量，在新节点上输入如下命令，导入环境变量：
注意，不要导入ETCD_INITIAL_ADVERTISE_PEER_URLS="http://192.168.64.233:2380"，否则会发生冲突
export ETCD_NAME="infra3"
export ETCD_INITIAL_CLUSTER="infra3=http://192.168.64.233:2380,infra2=http://192.168.64.237:2380,infra1=http://192.168.64.234:2380"
export ETCD_INITIAL_CLUSTER_STATE="existing"

之后，在新节点上运行如下命令，即可启用该节点：
etcd --listen-client-urls http://192.168.64.233:2379 \
  --advertise-client-urls http://192.168.64.233:2379 --listen-peer-urls http://192.168.64.233:2380 \
  --initial-advertise-peer-urls http://192.168.64.233:2380 



