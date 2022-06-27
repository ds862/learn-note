## 一、使用minikube搭建单机下的单节点



1. 安装minikube

```
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube
```

1. 启动集群

```
minikube start --driver=docker
```

   此时可能会出现以下错误：The "docker" driver should not be used with root privileges.具体报错如下：

```
* Automatically selected the docker driver
* The "docker" driver should not be used with root privileges.
* If you are running minikube within a VM, consider using --driver=none:
*   https://minikube.sigs.k8s.io/docs/reference/drivers/none/
X Exiting due to DRV_AS_ROOT: The "docker" driver should not be used with root privileges.
```

这是因为minikube不能在root环境下执行，需要新建用户，具体步骤如下：

```
adduser $USER
#passwd test
```

如果此时切换到新建用户执行，还是会报错，因为新建的用户不在docker组中。因此还需要在root环境下新建docker组，并将新建用户添加到docker组中。

```
#创建docker组
sudo groupadd docker
#将新建的用户添加到该docker组
sudo usermod -aG docker $USER
#激活对组的更改
newgrp docker
```

最后切换到新建用户test并执行即可

```
su $USER
#passwd test
```

1. 测试

```
kubectl get po -A
```

## 二、使用kind搭建单机下的单节点和多节点



参考：https://www.cnblogs.com/charlieroro/p/13711589.html、https://kind.sigs.k8s.io/docs/user/quick-start/#creating-a-cluster



### 搭建单节点



1、安装kubectl



2、安装kind命令：



```
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.9.0/kind-linux-amd64
chmod +x ./kind
mv ./kind /${some-dir-in-your-PATH}/kind
```



3、创建集群，默认的集群名称为`kind`，可以使用参数`--name`指定创建的集群的名称，多集群情况下比较有用



```
kind create cluster
```



- 与集群交互：

1. 1. 获取集群名称，可以看到下面有两个集群

```
# kind get clusters
kind
kind-2
```

1. 1. 切换集群。可以使用如下命令分别切换到集群`kind`和`kind-2`

```
# kubectl cluster-info --context kind-kind
# kubectl cluster-info --context kind-kind-2
```

- 删除集群，如使用如下命令可以删除集群`kind-2`

```
kind delete cluster --name kind-2
```

- 将镜像加载到kind的node中



kind创建的kubernetes会使用它的node上的镜像，因此需要将将镜像加载到node中才能被kubernetes使用(当然在node中也是可以直接拉取公网镜像的)，在无法拉取公网镜像的时候可以手动将镜像load到node上使用。例如，使用如下方式可以将torchelastic/examples镜像加载到名为my-cluster的集群中：



```
kind load docker-image torchelastic/examples:0.2.0 --name my-cluster
```



- 配置kind集群



可以在kind创建集群的时候使用配置文件进行自定义配置。例如可以使用--config指定[配置文件](https://raw.githubusercontent.com/kubernetes-sigs/kind/master/site/content/docs/user/kind-example-config.yaml)来创建集群：



```
kind create cluster --config kind-example-config.yaml
```



### 搭建多节点



上面部署的kubernetes中只有一个node，可以使用配置文件部署多个节点。下面使用官方提供的默认配置文件`kind-config.yaml`来创建集群，该集群含3个work节点：



```
# this config file contains all config fields with comments
# NOTE: this is not a particularly useful config file
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
# patch the generated kubeadm config with some extra settings
kubeadmConfigPatches:
- |
  apiVersion: kubelet.config.k8s.io/v1beta1
  kind: KubeletConfiguration
  evictionHard:
    nodefs.available: "0%"
# patch it further using a JSON 6902 patch
kubeadmConfigPatchesJSON6902:
- group: kubeadm.k8s.io
  version: v1beta2
  kind: ClusterConfiguration
  patch: |
    - op: add
      path: /apiServer/certSANs/-
      value: my-hostname
# 1 control plane node and 3 workers
nodes:
# the control plane node config
- role: control-plane
# the three workers
- role: worker
- role: worker
- role: worker
```



创建上述集群：



```
kind create cluster --name multi-node --config=kind-config.yaml
```



切换到该集群：



```
kubectl cluster-info --context kind-multi-node
```



可以看到该集群下有1个控制面node，以及3个work node：



```
# kubectl get node
NAME                       STATUS   ROLES    AGE     VERSION
multi-node-control-plane   Ready    master   7m57s   v1.19.1
multi-node-worker          Ready    <none>   7m21s   v1.19.1
multi-node-worker2         Ready    <none>   7m21s   v1.19.1
multi-node-worker3         Ready    <none>   7m21s   v1.19.1
```



### 搭建多master节点



一般一个生产使用的kubernetes都会使用多个控制面来保证高可用，使用kind config可以方便地创建多控制面的kubernetes集群。使用如下命令创建一个3控制面，3 work节点的集群：



```
# this config file contains all config fields with comments
# NOTE: this is not a particularly useful config file
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
# patch the generated kubeadm config with some extra settings
kubeadmConfigPatches:
- |
  apiVersion: kubelet.config.k8s.io/v1beta1
  kind: KubeletConfiguration
  evictionHard:
    nodefs.available: "0%"
# patch it further using a JSON 6902 patch
kubeadmConfigPatchesJSON6902:
- group: kubeadm.k8s.io
  version: v1beta2
  kind: ClusterConfiguration
  patch: |
    - op: add
      path: /apiServer/certSANs/-
      value: my-hostname
# 1 control plane node and 3 workers
nodes:
# the control plane node config
- role: control-plane
- role: control-plane
- role: control-plane
# the three workers
- role: worker
- role: worker
- role: worker
```



此时可以看到有3个控制面：



```
# kubectl get node
NAME                  STATUS   ROLES    AGE   VERSION
kind-control-plane    Ready    master   15m   v1.19.1
kind-control-plane2   Ready    master   14m   v1.19.1
kind-control-plane3   Ready    master   13m   v1.19.1
kind-worker           Ready    <none>   12m   v1.19.1
kind-worker2          Ready    <none>   12m   v1.19.1
kind-worker3          Ready    <none>   12m   v1.19.1
```



### 指定Kubernetes的版本



可以通过指定node的镜像版本来修改kubernetes的版本。可以在[官方release页面中](https://github.com/kubernetes-sigs/kind/releases)中查找需要镜像tag，推荐tag带上sha，如



```
kindest/node:v1.19.1@sha256:98cf5288864662e37115e362b23e4369c8c4a408f99cbc06e58ac30ddc721600
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  image: kindest/node:v1.16.4@sha256:b91a2c2317a000f3a783489dfb755064177dbc3a0b2f4147d50f04825d016f55
- role: worker
  image: kindest/node:v1.16.4@sha256:b91a2c2317a000f3a783489dfb755064177dbc3a0b2f4147d50f04825d016f55
```



## 三、使用kubeasz搭建k8s集群

### 1.快速搭建单节点

**注意:** 确保在干净的系统上开始安装，不能使用曾经装过kubeadm或其他k8s发行版的环境

1. 下载工具脚本ezdown，举例使用kubeasz版本3.0.0

```
export release=3.0.0
curl -C- -fLO --retry 3 https://github.com/easzlab/kubeasz/releases/download/${release}/ezdown
chmod +x ./ezdown
```



1. 使用工具脚本下载

默认下载最新推荐k8s/docker等版本（更多关于ezdown的参数，运行./ezdown 查看）

```
./ezdown -D
```

上述脚本运行成功后，所有文件（kubeasz代码、二进制、离线镜像）均放在目录`/etc/kubeasz`

- `/etc/kubeasz` 包含 kubeasz 版本为 ${release} 的发布代码
- `/etc/kubeasz/bin` 包含 k8s/etcd/docker/cni 等二进制文件
- `/etc/kubeasz/down` 包含集群安装时需要的离线容器镜像
- `/etc/kubeasz/down/packages` 包含集群安装时需要的系统基础软件



1. 安装集群

- 容器化运行 kubeasz，详见ezdown 脚本中的 start_kubeasz_docker 函数

```
./ezdown -S
```

- 使用默认配置安装 aio 集群

```
docker exec -it kubeasz ezctl start-aio
```

1. 验证安装

如果提示kubectl: command not found，退出重新ssh登录一下，环境变量生效即可

```
$ kubectl version         # 验证集群版本     
$ kubectl get node        # 验证节点就绪 (Ready) 状态
$ kubectl get pod -A      # 验证集群pod状态，默认已安装网络插件、coredns、metrics-server等
$ kubectl get svc -A      # 验证集群服务状态
```

5.清理

### 2. 搭建多节点

搭建单节点后，通过 **节点添加** 扩容成高可用集群。

#### 1. 增加 kube_node 节点

新增kube_node节点大致流程为：(参考ezctl 里面add-node函数 和 playbooks/22.addnode.yml)

- [可选]新节点安装 chrony 时间同步
- 新节点预处理 prepare
- 新节点安装 docker 服务
- 新节点安装 kube_node 服务
- 新节点安装网络插件相关

操作步骤

首先配置 ssh 免密码登录新增节点，然后执行 (假设待增加节点为 192.168.1.11，k8s集群名为 test-k8s)：

```
$ ezctl add-node test-k8s 192.168.1.11
```

验证

```
# 验证新节点状态
$ kubectl get node

# 验证新节点的网络插件calico 或flannel 的Pod 状态
$ kubectl get pod -n kube-system
```

删除 kube_node 节点

```
$ ezctl del-node test-k8s 192.168.1.11 # 假设待删除节点为 192.168.1.11
```

#### 2. 增加 kube_master 节点

新增`kube_master`节点大致流程为：(参考ezctl 中add-master函数和playbooks/23.addmaster.yml)



- [可选]新节点安装 chrony 时间同步
- 新节点预处理 prepare
- 新节点安装 docker 服务
- 新节点安装 kube_master 服务
- 新节点安装 kube_node 服务
- 新节点安装网络插件相关
- 禁止业务 pod调度到新master节点
- 更新 node 节点 haproxy 负载均衡并重启



首先配置 ssh 免密码登录新增节点，然后执行 (假设待增加节点为 192.168.1.11, 集群名称test-k8s)：



```
$ ezctl add-master test-k8s 192.168.1.11
```



验证



```
# 在新节点master 服务状态
$ systemctl status kube-apiserver 
$ systemctl status kube-controller-manager
$ systemctl status kube-scheduler

# 查看新master的服务日志
$ journalctl -u kube-apiserver -f

# 查看集群节点，可以看到新 master节点 Ready, 并且禁止了POD 调度功能
$ kubectl get node
NAME           STATUS                     ROLES     AGE       VERSION
192.168.1.1    Ready,SchedulingDisabled   <none>    3h        v1.9.3
192.168.1.2    Ready,SchedulingDisabled   <none>    3h        v1.9.3
192.168.1.3    Ready                      <none>    3h        v1.9.3
192.168.1.4    Ready                      <none>    3h        v1.9.3
192.168.1.11   Ready,SchedulingDisabled   <none>    2h        v1.9.3    # 新增 master节点
```



删除 kube_master 节点



```
$ ezctl del-master test-k8s 192.168.1.11  # 假设待删除节点 192.168.1.11
```

#### 3. 管理 etcd 集群

首先确认配置 ssh 免密码登录，然后执行 (假设待操作节点为 192.168.1.11，集群名称test-k8s)：

- 增加 etcd 节点：`$ ezctl add-etcd test-k8s 192.168.1.11`
- 删除 etcd 节点：`$ ezctl del-etcd test-k8s 192.168.1.11`

## 四、使用kubeadm搭建高可用多机多节点

见**文档记录/****使用kubeadm搭建k8s**

## 五、使用二进制方式搭建K8S集群



### 步骤



- 操作系统的初始化
- 为etcd 和 apiserver 自签证书
- 部署etcd集群
- 部署master组件【安装docker、kube-apiserver、kube-controller-manager、kube-scheduler、etcd】
- 部署node组件【安装kubelet、kube-proxy、docker、etcd】
- 部署集群网络



### 操作系统的初始化



首先需要进行一些系列的初始化操作