## 一、概述

kubeadm是官方社区推出的一个用于快速部署kubernetes集群的工具。



这个工具能通过两条指令完成一个kubernetes集群的部署：



```
# 创建一个 Master 节点
kubeadm init
# 将一个 Node 节点加入到当前集群中
kubeadm join <Master节点的IP和端口 >
```



这里在ubuntu环境下，以三个节点（1个master节点，2个worker节点）为例，使用kubeadm搭建k8s集群。

## 二、集群环境

| hostname | IP              |
| -------- | --------------- |
| kmaster  | 192.168.177.130 |
| knode1   | 192.168.177.131 |
| knode2   | 192.168.177.132 |



hosts文件如下：



192.168.1.94   knode1 knode1

192.168.1.95   kmaster kmaster

192.168.1.96   knode2 knode2



原文件（这里是我记录的备份，直接忽略）

31  192.168.1.94   iZhp3efeqtz5qdhyspgtl4Z iZhp3efeqtz5qdhyspgtl4Z

73  192.168.1.95   iZhp320kvjes0yyb6w701tZ iZhp320kvjes0yyb6w701tZ

47  192.168.1.96   iZhp32z20xxdiynjdpzfweZ iZhp32z20xxdiynjdpzfweZ

189  192.168.1.93    iZhp34ve1pwh9m1cuyk6wlZ 

## 三、具体流程



使用kubeadm方式搭建K8s集群主要分为以下几步：



- 对三个节点的系统进行初始化操作
- 在三个节点安装 docker kubelet kubeadm kubectl
- 在master节点执行kubeadm init命令初始化
- 在node节点上执行 kubeadm join命令，把node节点添加到当前集群
- 配置CNI网络插件，用于节点之间的连通【失败了可以多试几次】
- 通过拉取一个nginx进行测试，能否进行外网测试



### 1. 初始化节点（在三个节点上都运行）



设置基本功能:



```
# 根据规划设置主机名【在kmaster节点上操作】
hostnamectl set-hostname kmaster
# 根据规划设置主机名【在knode1节点操作】
hostnamectl set-hostname knode1
# 根据规划设置主机名【在knode2节点操作】
hostnamectl set-hostname knode2

# 安装需要用的软件
apt-get update
sudo apt-get install -y ufw wget git selinux-utils conntrack ipvsadm ipset jq sysstat curl iptables libseccomp2 

# 关闭swap：
swapoff -a

# 关闭防火墙
ufw disable

# 关闭selinux
# 永久关闭
sed -i 's/enforcing/disabled/' /etc/selinux/config  
# 临时关闭
setenforce 0  

# 将桥接的IPv4流量传递到iptables的链
cat <<EOF | sudo tee /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-ip6tables = 1
net.bridge.bridge-nf-call-iptables = 1
EOF
sysctl --system

# 时间同步(公司集群已同步，所以这里我没有做，在其他环境下可能需要此步)
```





### 2. 安装 docker kubelet kubeadm kubectl（在三个节点上都运行）

1. 安装docker

```
# 卸载docker
apt-get purge -y docker docker-ce-* docker-engine  docker.io  containerd runc
apt-get purge -y docker-ce docker-ce-cli containerd.io
dpkg -l |grep ^rc|awk '{print $2}' |sudo xargs dpkg -P
sudo rm -rf /etc/systemd/system/docker.service.d
sudo rm -rf /var/lib/docker
sudo rm -rf /etc/docker
# 方式一：脚本安装（安装k8s时不推荐）
# curl -fsSL https://get.docker.com | bash -s docker --mirror Aliyun
# 方式二：手动安装
#更新 apt 包索引。
sudo apt-get update

# 安装 apt 依赖包，用于通过HTTPS来获取仓库:
sudo apt-get install \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg-agent \
    software-properties-common

#添加 Docker 的官方 GPG 密钥：
curl -fsSL https://mirrors.aliyun.com/docker-ce/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# 向 sources.list 中添加 Docker 软件源
echo \
  "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://mirrors.aliyun.com/docker-ce/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null


#安装 Docker Engine-Community
sudo apt-get update

# 安装最新版本的 Docker Engine-Community 和 containerd ，：
sudo apt-get install docker-ce docker-ce-cli containerd.io

# 或者安装特定版本,查看可安装版本
sudo apt-get update
apt-cache madison docker-ce
# 安装特定版本，例如 5:18.09.1~3-0~ubuntu-xenial。
sudo apt-get install docker-ce=<VERSION_STRING> docker-ce-cli=<VERSION_STRING> containerd.io
```



离线安装

```
# 1.apt下载 
sudo apt-get install -y --download-only -o dir::cache::archives=./ docker-ce docker-ce-cli containerd.io

# 2.直接再在网站下载
wget https://download.docker.com/linux/ubuntu/dists/bionic/pool/stable/amd64/containerd.io_1.4.4-1_amd64.deb
wget https://download.docker.com/linux/ubuntu/dists/bionic/pool/stable/amd64/docker-ce-cli_20.10.6~3-0~ubuntu-bionic_amd64.deb
wget https://download.docker.com/linux/ubuntu/dists/bionic/pool/stable/amd64/docker-ce_20.10.6~3-0~ubuntu-bionic_amd64.deb
wget https://download.docker.com/linux/ubuntu/dists/bionic/pool/stable/amd64/docker-ce-rootless-extras_20.10.6~3-0~ubuntu-bionic_amd64.deb

# 安装
dpkg -i ./*.deb
```

1. 下载nvidia-docker

```
distribution=$(. /etc/os-release;echo $ID$VERSION_ID) \
   && curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add - \
   && curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

curl -s -L https://nvidia.github.io/nvidia-container-runtime/experimental/$distribution/nvidia-container-runtime.list | sudo tee /etc/apt/sources.list.d/nvidia-container-runtime.list

sudo apt-get update

sudo apt-get install -y nvidia-docker2
# 只下载
# apt-get install -y --download-only -o dir::cache::archives=./ nvidia-docker2


# 添加容器运行时
cat > /etc/docker/daemon.json << EOF
{
  "default-runtime": "nvidia",
    "runtimes": {
        "nvidia": {
            "path": "/usr/bin/nvidia-container-runtime",
            "runtimeArgs": []
        }
    },
    "registry-mirrors": ["https://g2gthrxx.mirror.aliyuncs.com"]
}
EOF

# 重启docker
systemctl restart docker
# 测试gpu_docker是否可用
sudo docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
```

离线安装

```
# 下载（在在线安装导入源后）
apt download libnvidia-container1
apt download libnvidia-container-tools
apt download nvidia-container-toolkit
apt download nvidia-container-runtime
apt download nvidia-docker2
# 或者
apt-get install -y --download-only -o dir::cache::archives=./ nvidia-docker2

# 安装
dpkg -i libnvidia* nvidia*
```

1. 安装最新版本kubelet、kubeadm、kubectl



```
# 配置apt
apt-get update && apt-get install -y apt-transport-https curl
# 添加key
curl https://mirrors.aliyun.com/kubernetes/apt/doc/apt-key.gpg | apt-key add - 
# 添加阿里云kubernetes源
cat <<EOF >/etc/apt/sources.list.d/kubernetes.list
deb https://mirrors.aliyun.com/kubernetes/apt/ kubernetes-xenial main
EOF
# 更新源
apt-get update

# 安装最新kubelet、kubeadm、kubectl
# The following NEW packages will be installed:
# conntrack cri-tools ebtables kubeadm kubectl kubelet kubernetes-cni socat 
apt-get install -y kubelet kubeadm kubectl
# 锁定版本
apt-mark hold kubelet kubeadm kubectl
# 解锁
# apt-mark unhold kubelet kubeadm kubectl
```



如果要安装指定版本：



```
# 可以先查看版本
apt-cache madison  kubeadm kubelet kubectl
# 再安装指定版本
apt-get install -y kubelet=1.21.1-00 kubeadm=1.21.1-00 kubectl=1.21.1-00
```



离线安装

```
# 导入源后不安装，只下载指定版本(暂时存在问题)
VERSION=1.21.1-00
apt-get install -y --download-only -o dir::cache::archives=/ncluster/dushuai/kubeDeploy-ubuntu16.04-v1.21.1/kube kubelet=$VERSION kubeadm=$VERSION kubectl=$VERSION

# 安装
dpkg -i ./*.deb
```

### 3. 在master节点执行kubeadm init初始化命令

#### 1. 执行初始化命令

部署Kubernetes Master, 在192.168.1.95，也就是master节点，执行如下命令：

```
# 查看所需镜像
kubeadm config images list --image-repository registry.aliyuncs.com/google_containers --kubernetes-version v1.21.1
# 初始化master节点
kubeadm init --apiserver-advertise-address=192.168.1.95 --image-repository registry.aliyuncs.com/google_containers --kubernetes-version v1.21.1 --service-cidr=10.96.0.0/12  --pod-network-cidr=10.244.0.0/16
```

**若执行完命令出现一些错误，按可以查询步骤 2.处理报错** **。**



当出现成功说明时，表示kubernetes的镜像已经安装成功。

按照提示，继续进行：

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



#### 2. 处理报错

1）报错1：



报错信息如下：

```
failed to pull image "registry.cn-hangzhou.aliyuncs.com/google_containers/coredns/coredns:v1.8.0": output: Error response from daemon: pull access denied for registry.cn-hangzhou.aliyuncs.com/google_containers/coredns/coredns, repository does not exist or may require 'docker login': denied: requested access to the resource is denied,error: exit status 1
```



主要是因为该镜像在阿里云已经不存在了，解决方法如下：



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





### 4. 在node节点上执行 kubeadm join命令，把node节点添加到当前集群



下面需要分别到 node1 和 node2服务器上，执行下面的代码向集群添加新节点
执行上面在执行 kubeadm init 命令后输出的 kubeadm join命令：

> 注意，以下的命令是在master初始化完成后，需要复制每次生成的

```
kubeadm join 192.168.1.95:6443 --token n68l5i.ltv0xm3veo8xt2pd \
        --discovery-token-ca-cert-hash sha256:f70f30012c356714291af71b6b29095e7f8fa8260b0b09de1db6d876e080b7ba
```

默认token有效期为24小时，当过期之后，该token就不可用了。这时就需要重新创建token，操作如下：

```
# 在master节点执行
kubeadm token create --print-join-command
```



当把两个节点都加入进来后，就可以去Master节点 执行下面命令查看情况

```
# 在master执行
kubectl get node
```



状态显示还是NotReady，需要网络插件，来进行联网访问





### 5. 配置CNI网络插件，用于节点之间的连通

在master节点执行如下命令：

```
# 在master节点执行
kubectl apply -f https://raw.githubusercontent.com/coreos/flannel/master/Documentation/kube-flannel.yml
```



运行完成后，查看节点状态可以发现，已经变成了Ready状态了。
但此时可能会出现coredns是Running状态，但是没有READY。
![image](https://intranetproxy.alipay.com/skylark/lark/0/2021/png/18057116/1623141541681-96faa2fd-aa6f-4e9c-9af2-ea4cebb26c10.png)



运行命令kubectl describe pod coredns-545d6fc579-cn8k6 -n kube-system，显示如下：

```
Events:
  Type     Reason     Age                   From     Message
  ----     ------     ----                  ----     -------
  Normal   BackOff    18m (x371 over 103m)  kubelet  Back-off pulling image "registry.aliyuncs.com/google_containers/coredns/coredns:v1.8.0"
  Warning  Unhealthy  3m31s (x74 over 15m)  kubelet  Readiness probe failed: HTTP probe failed with statuscode: 503
```

使用`kubectl logs coredns-57d4cbf879-28szb -n kube-system`查看日志如下：

```
[INFO] plugin/ready: Still waiting on: "kubernetes"
[INFO] plugin/ready: Still waiting on: "kubernetes"
[INFO] plugin/ready: Still waiting on: "kubernetes"
[INFO] plugin/ready: Still waiting on: "kubernetes"
E0602 02:11:25.299934       1 reflector.go:138] pkg/mod/k8s.io/client-go@v0.21.1/tools/cache/reflector.go:167: Failed to watch *v1.EndpointSlice: failed to list *v1.EndpointSlice: endpointslices.discovery.k8s.io is forbidden: User "system:serviceaccount:kube-system:coredns" cannot list resource "endpointslices" in API group "discovery.k8s.io" at the cluster scope
```

**解决方法：**
确认这是coredns的一个bug, 需要修改coredns角色权限。在master节点使用下面命令进行编辑

```
$ kubectl edit clusterrole system:coredns
```

在打开的文件最后面手动追加：

```
- apiGroups:
  - discovery.k8s.io
  resources:
  - endpointslices
  verbs:
  - list
  - watch
```



编辑完成后，coredns恢复正常。





### 6. 在node节点启用kubectl

完成上述步骤后，若在Kubernetes的从节点上运行命令【kubectl】，会出现如下错误



```
# kubectl get pod
The connection to the server localhost:8080 was refused - did you specify the right host or port?
```



出现这个问题的原因是kubectl命令需要使用kubernetes-admin来运行，解决方法如下，将主节点中的【/etc/kubernetes/admin.conf】文件拷贝到从节点相同目录下，然后配置环境变量：



```
#在master上
scp /etc/kubernetes/admin.conf root@192.168.1.94:/etc/kubernetes/admin.conf

#在node节点上
echo "export KUBECONFIG=/etc/kubernetes/admin.conf" >> ~/.bash_profile
source ~/.bash_profile
```





接着再运行kubectl命令就OK了



### 7. 清除kubeadm节点（不卸载kube组件）

```
#在node节点上
kubectl drain <node name> --delete-local-data --force --ignore-daemonsets
kubeadm reset
iptables -F && iptables -t nat -F && iptables -t mangle -F && iptables -X
ipvsadm -C
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

#在master节点上
kubectl delete node <node name>
```



### 8. 启用GPU支持



1. 部署 NVIDIA 设备插件

```
# 在master节点执行
kubectl create -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/1.0.0-beta4/nvidia-device-plugin.yml
```

1. 测试是否成功

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



最后，在 Pod 中测试 GPU 可用性。
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
$ kubectl apply -f ./gpu-pod.yaml
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



### 9. 一些可能会出现的错误



1. 报错：node节点pod无法启动/节点删除网络重置，提示语："cni0" already has an IP address different from

```
Warning  FailedCreatePodSandBox  33m                    kubelet            Failed to create pod sandbox: rpc error: code = Unknown desc = failed to set up sandbox container "c1b34628724a9e1a6cfc99f25f36006f594d5c4a8a41c8ec1862fe22b38005fe" network for pod "elastic-job-k8s-controller-f8ff9f758-gc27r": networkPlugin cni failed to set up pod "elastic-job-k8s-controller-f8ff9f758-gc27r_elastic-job" network: failed to set bridge addr: "cni0" already has an IP address different from 10.244.3.1/24
```





原因：node1之前反复添加过,添加之前需要清除下网络



解决：在Node上执行如下操作：重置kubernetes服务，重置网络，删除网络配置，link



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



再次获取master的join token



```
# 在master节点执行
kubeadm token create --print-join-command
```



重新加入节点



```
# 在node节点执行
kubeadm join...
```



1. 在给node1节点使用 kubernetes join命令的时，出现以下错误

````
我们在给node1节点使用 kubernetes join命令的时候，出现以下错误

​```bash
error execution phase preflight: [preflight] Some fatal errors occurred:
    [ERROR Swap]: running with swap on is not supported. Please disable swap
```
````

错误原因是需要关闭swap
````



## 四、自动化脚本

```

```



