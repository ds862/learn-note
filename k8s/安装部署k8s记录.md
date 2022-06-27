# 搭建k8s集群记录

------------

## 一、使用minikube搭建单机下的单节点

1. 安装minikube

   ```
   curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
   sudo install minikube-linux-amd64 /usr/local/bin/minikube
   ```

   

2. 启动集群

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

   ​	这是因为minikube不能在root环境下执行，需要新建用户，具体步骤如下：

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



## 二、使用kind搭建单机下的单节点和多节点

参考：https://www.cnblogs.com/charlieroro/p/13711589.html、https://kind.sigs.k8s.io/docs/user/quick-start/#creating-a-cluster

### 搭建单节点

1、安装kubectl

2、安装kind命令：

```shell
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.9.0/kind-linux-amd64
chmod +x ./kind
mv ./kind /${some-dir-in-your-PATH}/kind
```

3、创建集群，默认的集群名称为`kind`，可以使用参数`--name`指定创建的集群的名称，多集群情况下比较有用

```shell
kind create cluster
```

- 与集群交互：

  1. 获取集群名称，可以看到下面有两个集群

     ```shell
     # kind get clusters
     kind
     kind-2
     ```

  2. 切换集群。可以使用如下命令分别切换到集群`kind`和`kind-2`

     ```shell
     # kubectl cluster-info --context kind-kind
     # kubectl cluster-info --context kind-kind-2
     ```

- 删除集群，如使用如下命令可以删除集群`kind-2`

  ```
  kind delete cluster --name kind-2
  ```

- 将镜像加载到kind的node中

kind创建的kubernetes会使用它的node上的镜像，因此需要将将镜像加载到node中才能被kubernetes使用(当然在node中也是可以直接拉取公网镜像的)，在无法拉取公网镜像的时候可以手动将镜像load到node上使用。例如，使用如下方式可以将torchelastic/examples镜像加载到名为my-cluster的集群中：

```shell
kind load docker-image torchelastic/examples:0.2.0 --name my-cluster
```

- 配置kind集群

可以在kind创建集群的时候使用配置文件进行自定义配置。例如可以使用--config指定[配置文件](https://raw.githubusercontent.com/kubernetes-sigs/kind/master/site/content/docs/user/kind-example-config.yaml)来创建集群：

```shell
kind create cluster --config kind-example-config.yaml
```

### 搭建多节点

上面部署的kubernetes中只有一个node，可以使用配置文件部署多个节点。下面使用官方提供的默认配置文件`kind-config.yaml`来创建集群，该集群含3个work节点：

```yaml
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

```shell
kind create cluster --name multi-node --config=kind-config.yaml
```

切换到该集群：

```shell
kubectl cluster-info --context kind-multi-node
```

可以看到该集群下有1个控制面node，以及3个work node：

```shell
# kubectl get node
NAME                       STATUS   ROLES    AGE     VERSION
multi-node-control-plane   Ready    master   7m57s   v1.19.1
multi-node-worker          Ready    <none>   7m21s   v1.19.1
multi-node-worker2         Ready    <none>   7m21s   v1.19.1
multi-node-worker3         Ready    <none>   7m21s   v1.19.1
```

### 搭建多master节点

一般一个生产使用的kubernetes都会使用多个控制面来保证高可用，使用kind config可以方便地创建多控制面的kubernetes集群。使用如下命令创建一个3控制面，3 work节点的集群：

```yaml
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

```shell
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





## 三、使用kubeadm搭建高可用多机多节点

kubeadm是官方社区推出的一个用于快速部署kubernetes集群的工具。

这个工具能通过两条指令完成一个kubernetes集群的部署：

```bash
# 创建一个 Master 节点
kubeadm init

# 将一个 Node 节点加入到当前集群中
kubeadm join <Master节点的IP和端口 >
```

### 集群环境

| hostname | IP              |
| -------- | --------------- |
| kmaster  | 192.168.177.130 |
| knode1   | 192.168.177.131 |
| knode2   | 192.168.177.132 |

hosts文件如下：

192.168.1.94    knode1 knode1
192.168.1.95    kmaster kmaster
192.168.1.96    knode2 knode2

源文件（留作备份）

192.168.1.94    iZhp3efeqtz5qdhyspgtl4Z iZhp3efeqtz5qdhyspgtl4Z
192.168.1.95    iZhp320kvjes0yyb6w701tZ iZhp320kvjes0yyb6w701tZ
192.168.1.96    iZhp32z20xxdiynjdpzfweZ iZhp32z20xxdiynjdpzfweZ
192.168.1.93    iZhp34ve1pwh9m1cuyk6wlZ 

### 主要步骤

使用kubeadm方式搭建K8s集群主要分为以下几步：

- 对三个节点的系统进行初始化操作
- 在三个节点安装 docker kubelet kubeadm kubectl
- 在master节点执行kubeadm init命令初始化
- 在node节点上执行 kubeadm join命令，把node节点添加到当前集群
- 配置CNI网络插件，用于节点之间的连通【失败了可以多试几次】
- 通过拉取一个nginx进行测试，能否进行外网测试

### 具体流程

1. 更新源并下载工具

```
apt-get update && apt-get install -y apt-transport-https curl
```

2. 添加公钥

```
curl -s https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add -
```


公司集群的网络无法访问，此时会报错

点击此链接 https://packages.cloud.google.com/apt/doc/apt-key.gpg ，获取pgp文件，然后通过` apt-key add apt-key.gpg `来加载。

3. 添加kubernetes源

官方源（公司集群不可用，可以使用国内源）

```
cat <<EOF >/etc/apt/sources.list.d/kubernetes.list
deb https://apt.kubernetes.io/ kubernetes-xenial main
EOF
```


国内源

```
cat <<EOF >/etc/apt/sources.list.d/kubernetes.list
deb http://mirrors.ustc.edu.cn/kubernetes/apt kubernetes-xenial main
EOF
```


再次更新源

```
apt-get update
```

4. 安装最新kubelet、kubeadm、kubectl

```
apt-get install -y kubelet kubeadm kubectl
```

如果要安装指定版本，可以先查看版本：

```
apt-cache madison  kubeadm kubelet kubectl
```

再安装指定版本

```
apt-get install -y kubelet=1.15.1-00 kubeadm=1.15.1-00 kubectl=1.15.1-00
```

5. 锁定版本

```
apt-mark hold kubelet kubeadm kubectl
```

6. 设置常见功能:

```shell
# 关闭swap：
# 临时关闭：
swapoff -a
# 持久关闭：
vim  /etc/fstab

# 关闭防火墙
ufw disable

# 关闭selinux
# 永久关闭
sed -i 's/enforcing/disabled/' /etc/selinux/config  
# 临时关闭
setenforce 0  

# 根据规划设置主机名【master节点上操作】
hostnamectl set-hostname kmaster
# 根据规划设置主机名【node1节点操作】
hostnamectl set-hostname knode1
# 根据规划设置主机名【node2节点操作】
hostnamectl set-hostname knode2

# 将桥接的IPv4流量传递到iptables的链
cat <<EOF | sudo tee /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-ip6tables = 1
net.bridge.bridge-nf-call-iptables = 1
EOF
sysctl --system

# 时间同步
```

7. 部署Kubernetes Master【master节点】

在192.168.1.95，也就是master节点，执行如下命令：

```
kubeadm init --apiserver-advertise-address=192.168.1.93 --image-repository registry.aliyuncs.com/google_containers --kubernetes-version v1.21.1 --service-cidr=10.96.0.0/12  --pod-network-cidr=10.244.0.0/16

```

此时会发生报错，信息如下：

```
failed to pull image "registry.cn-hangzhou.aliyuncs.com/google_containers/coredns/coredns:v1.8.0": output: Error response from daemon: pull access denied for registry.cn-hangzhou.aliyuncs.com/google_containers/coredns/coredns, repository does not exist or may require 'docker login': denied: requested access to the resource is denied,error: exit status 1
```

解决方法如下：

```
1.手动下载镜像（在所有节点执行）
docker pull coredns/coredns

2.查看kubeadm需要镜像，并修改名称
kubeadm config images list --config new.yaml
docker images

3.打标签，修改名称
docker tag coredns/coredns:latest registry.aliyuncs.com/google_containers/coredns/coredns:v1.8.0

4.删除多余镜像
docker rmi coredns/coredns:latest
```

当我们下面的情况时，表示kubernetes的镜像已经安装成功

![image-20200929094620145](C:\Users\du\Desktop\k8s\K8S\3_使用kubeadm方式搭建K8S集群\images\image-20200929094620145.png)

按照提示，继续进行：

使用kubectl工具 【master节点操作】

```
mkdir -p $HOME/.kube
sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config
```

执行完成后，我们使用下面命令，查看我们正在运行的节点

```
kubectl get nodes
```

会发现目前有一个master节点已经运行了，但是还处于未准备状态

下面还需要在Node节点执行其它的命令，将node1和node2加入到master节点上

8. 加入Kubernetes Node【Slave节点】

   下面需要到 node1 和 node2服务器，执行下面的代码向集群添加新节点

   执行在kubeadm init输出的kubeadm join命令：

   > 注意，以下的命令是在master初始化完成后，需要复制每次生成的

   ```bash
   kubeadm join 192.168.1.95:6443 --token n68l5i.ltv0xm3veo8xt2pd \
           --discovery-token-ca-cert-hash sha256:f70f30012c356714291af71b6b29095e7f8fa8260b0b09de1db6d876e080b7ba
   ```

   默认token有效期为24小时，当过期之后，该token就不可用了。这时就需要重新创建token，操作如下：

   ```
   kubeadm token create --print-join-command
   ```

   当把两个节点都加入进来后，就可以去Master节点 执行下面命令查看情况

   ```bash
   kubectl get node
   ```

   ![image-20201113165358663](C:\Users\du\Desktop\k8s\K8S\3_使用kubeadm方式搭建K8S集群\images\image-20201113165358663.png)

   上面的状态还是NotReady，需要网络插件，来进行联网访问

9. 部署CNI网络插件

   ```
   # 下载网络插件配置
   wget https://raw.githubusercontent.com/coreos/flannel/master/Documentation/kube-flannel.yml
   # 添加
   kubectl apply -f https://raw.githubusercontent.com/coreos/flannel/master/Documentation/kube-flannel.yml
   ```

   运行完成后，查看节点状态可以发现，已经变成了Ready状态了。

   但此时可能会出现coredns是Running状态，但是没有READY。

   ![coredns_issue.png](http://www.fanfan.show/assets/img/coredns_issue.9e052cf2.png) 

   

   运行命令kubectl describe pod coredns-545d6fc579-cn8k6 -n kube-system，显示如下：

   ```
   Events:
     Type     Reason     Age                   From     Message
     ----     ------     ----                  ----     -------
     Normal   BackOff    18m (x371 over 103m)  kubelet  Back-off pulling image "registry.aliyuncs.com/google_containers/coredns/coredns:v1.8.0"
     Warning  Unhealthy  3m31s (x74 over 15m)  kubelet  Readiness probe failed: HTTP probe failed with statuscode: 503
   
   ```

   使用`kubectl logs coredns-57d4cbf879-28szb -n kube-system`查看日志如下：

   ```text
   [INFO] plugin/ready: Still waiting on: "kubernetes"
   [INFO] plugin/ready: Still waiting on: "kubernetes"
   [INFO] plugin/ready: Still waiting on: "kubernetes"
   [INFO] plugin/ready: Still waiting on: "kubernetes"
   E0602 02:11:25.299934       1 reflector.go:138] pkg/mod/k8s.io/client-go@v0.21.1/tools/cache/reflector.go:167: Failed to watch *v1.EndpointSlice: failed to list *v1.EndpointSlice: endpointslices.discovery.k8s.io is forbidden: User "system:serviceaccount:kube-system:coredns" cannot list resource "endpointslices" in API group "discovery.k8s.io" at the cluster scope
   ```

   **解决方法**
   确认这是coredns的一个bug, 需要修改coredns角色权限。使用下面命令进行编辑

   ```bash
   $ kubectl edit clusterrole system:coredns
   ```

   编辑内容如下，可以在最后面追加

   ```yaml
   - apiGroups:
     - discovery.k8s.io
     resources:
     - endpointslices
     verbs:
     - list
     - watch
   ```

   编辑完成后，coredns恢复正常。

10. 在node节点启用kubectl

    在Kubernetes的从节点上运行命令【kubectl】出现了如下错误

```
# kubectl get pod
The connection to the server localhost:8080 was refused - did you specify the right host or port?
```

  出现这个问题的原因是kubectl命令需要使用kubernetes-admin来运行，解决      方法如下，将主节点中的【/etc/kubernetes/admin.conf】文件拷贝到从节点相同目录下，然后配置环境变量：

```
echo "export KUBECONFIG=/etc/kubernetes/admin.conf" >> ~/.bash_profile
```

立即生效

```
source ~/.bash_profile
```

接着再运行kubectl命令就OK了

### 启用GPU支持

1. 安装nvidia-docker

   安装指导https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html#docker

   ```
   curl https://get.docker.com | sh \
     && sudo systemctl --now enable docker
   ```

   ```
   distribution=$(. /etc/os-release;echo $ID$VERSION_ID) \
      && curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add - \
      && curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
   ```

   ```
   curl -s -L https://nvidia.github.io/nvidia-container-runtime/experimental/$distribution/nvidia-container-runtime.list | sudo tee /etc/apt/sources.list.d/nvidia-container-runtime.list
   ```

   ```
   sudo apt-get update
   
   sudo apt-get install -y nvidia-docker2
   ```

   ```
   sudo systemctl restart docker
   ```

   ```
   #测试
   sudo docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
   ```

2. 配置 Containerd 使用 Nvidia container runtime

   编辑`/etc/docker/daemon.json`文件，增加`"default-runtime": "nvidia"`键值对，此时该文件的内容应该如下所示（registry-mirrors是之前添加的国内镜像下载地址）：

   ```
   {
       "default-runtime": "nvidia",
       "runtimes": {
           "nvidia": {
               "path": "/usr/bin/nvidia-container-runtime",
               "runtimeArgs": []
           }
       },
       "registry-mirrors": ["https://registry.docker-cn.com"]
   }
   
   ```

   重启docker

   ```
   systemctl restart docker
   ```

   查看docker info，可以看到runtime

   ```
   docker info
   ```

3. 部署 NVIDIA 设备插件

   ```
   kubectl create -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/1.0.0-beta4/nvidia-device-plugin.yml
   ```

4. 测试

在节点运行

```
kubectl describe node knode1
```

可以得到

```
Capacity:
  cpu:                16
  ephemeral-storage:  309505004Ki
  hugepages-1Gi:      0
  hugepages-2Mi:      0
  memory:             123778656Ki
  nvidia.com/gpu:     2
  pods:               110

```

5. 在 Pod 中测试 GPU 可用性。

   先创建部署清单：gpu-pod.yaml

```
apiVersion: v1
kind: Pod
metadata:
  name: cuda-vector-add
spec:
  restartPolicy: OnFailure
  containers:
    - name: cuda-vector-add
      image: "docker.io/mirrorgooglecontainers/cuda-vector-add:v0.1"
      resources:
        limits:
          nvidia.com/gpu: 1
```

执行 `kubectl apply -f ./gpu-pod.yaml` 创建 Pod。使用 `kubectl get pod` 可以看到该 Pod 已经启动成功：

```
$ kubectl get pod
NAME                              READY   STATUS      RESTARTS   AGE
cuda-vector-add                   0/1     Completed   0          3s
```

查看 Pod 日志：

```
$ kubectl logs cuda-vector-add
[Vector addition of 50000 elements]
Copy input data from the host memory to the CUDA device
CUDA kernel launch with 196 blocks of 256 threads
Copy output data from the CUDA device to the host memory
Test PASSED
Done
```

可以看到成功运行。这也说明 Kubernetes 完成了对 GPU 资源的调用。需要注意的是，目前 Kubernetes 只支持卡级别的调度，并且显卡资源是独占，无法在多个容器之间分享。



### 一些其他的报错

1. 报错：node节点pod无法启动/节点删除网络重置，提示语："cni0" already has an IP address different from

   ```
   Warning  FailedCreatePodSandBox  33m                    kubelet            Failed to create pod sandbox: rpc error: code = Unknown desc = failed to set up sandbox container "c1b34628724a9e1a6cfc99f25f36006f594d5c4a8a41c8ec1862fe22b38005fe" network for pod "elastic-job-k8s-controller-f8ff9f758-gc27r": networkPlugin cni failed to set up pod "elastic-job-k8s-controller-f8ff9f758-gc27r_elastic-job" network: failed to set bridge addr: "cni0" already has an IP address different from 10.244.3.1/24
   ```

解决：

原因：node1之前反复添加过,添加之前需要清除下网络

在Node上执行如下操作：重置kubernetes服务，重置网络。删除网络配置，link 

```
kubeadm reset
systemctl stop kubelet
systemctl stop docker
rm -rf /var/lib/cni/
rm -rf /var/lib/kubelet/*
rm -rf /etc/cni/
ifconfig cni0 down
ifconfig flannel.1 down
ifconfig docker0 down
ip link delete cni0
ip link delete flannel.1
systemctl start docker
systemctl start kubelet
```

获取master的join token

```
kubeadm token create --print-join-command
```


重新加入节点

```
kubeadm join 
```



## 四、使用二进制方式搭建K8S集群

### 步骤

- 操作系统的初始化
- 为etcd 和 apiserver 自签证书
- 部署etcd集群
- 部署master组件【安装docker、kube-apiserver、kube-controller-manager、kube-scheduler、etcd】
- 部署node组件【安装kubelet、kube-proxy、docker、etcd】
- 部署集群网络

### 操作系统的初始化

首先需要进行一些系列的初始化操作

