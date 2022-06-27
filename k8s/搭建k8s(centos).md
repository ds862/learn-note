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
yum install -y wget git selinux-utils conntrack ipvsadm ipset jq sysstat curl iptables libseccomp2 yum-utils device-mapper-persistent-data lvm2

# 关闭swap：
swapoff -a

# 关闭防火墙
systemctl disable firewalld

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
# 移除现有docker
# sudo yum remove docker \
                docker-client \
                docker-client-latest \
                docker-common \
                docker-latest \
                docker-latest-logrotate \
                docker-logrotate \
                docker-selinux \
                docker-engine-selinux \
                docker-engine
        
# 设置阿里云镜像
sudo yum-config-manager --add-repo http://mirrors.aliyun.com/docker-ce/linux/centos/docker-ce.repo

# 更新yum缓存
sudo yum makecache fast

# 查看可以安装的版本
yum list docker-ce --showduplicates | sort -r

# 安装指定版本（测试环境为20.10.6和kube1.21.1）
sudo yum install -y docker-ce-20.10.6-3.el7

# 或者安装最新版本
# yum -y install docker-ce

# 设置开机自启动
systemctl start docker
systemctl enable docker
systemctl status docker
```

离线安装

```
#下载清华的镜像源文件
wget -O /etc/yum.repos.d/docker-ce.repo https://download.docker.com/linux/centos/docker-ce.repo
sudo sed -i 's+download.docker.com+mirrors.tuna.tsinghua.edu.cn/docker-ce+' /etc/yum.repos.d/docker-ce.repo

# 查询可用版本
sudo yum list docker-ce --showduplicates|sort -r

# 下载到指定文件夹
sudo yum install --downloadonly --downloaddir=./ docker-ce-20.10.6-3.el7

# 安装
rpm -Uvh *.rpm --nodeps --force
```

1. 下载nvidia-docker

在线安装

```
sudo systemctl --now enable docker
distribution=$(. /etc/os-release;echo $ID$VERSION_ID) \
   && curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.repo | sudo tee /etc/yum.repos.d/nvidia-docker.repo
sudo yum clean expire-cache
sudo yum install -y nvidia-docker2

# 添加容器运行时,并设置阿里云镜像加速(可选)
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
# docker load -i $IMAGES_DIR/nvidia_cuda_11.0-base.tar
sudo docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
```

离线安装

```
# 首先下载
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.repo | sudo tee /etc/yum.repos.d/nvidia-docker.repo
yum install --downloadonly nvidia-docker2

# 之后安装
rpm -Uvh *.rpm --nodeps --force

# 重启docker
systemctl restart docker

# 锁定版本（可选）
sudo yum versionlock add docker
```

1. 安装指定kubelet、kubeadm、kubectl



```
# 配置k8s源
cat > /etc/yum.repos.d/kubernetes.repo << EOF
[kubernetes]
name=Kubernetes
baseurl=https://mirrors.aliyun.com/kubernetes/yum/repos/kubernetes-el7-x86_64
enabled=1
gpgcheck=0
repo_gpgcheck=0
gpgkey=https://mirrors.aliyun.com/kubernetes/yum/doc/yum-key.gpg https://mirrors.aliyun.com/kubernetes/yum/doc/rpm-package-key.gpg
EOF

# 可以先查看版本
yum list kubeadm --showduplicates | sort -r
# 再安装指定版本
yum install -y kubelet-1.21.0-0 kubeadm-1.21.0-0 kubectl-1.21.0-0
#yum install -y kubelet-1.18.0-0 kubeadm-1.18.0-0 kubectl-1.18.0-0

# 或者安装最新kubelet、kubeadm、kubectl
# apt-get install -y kubelet kubeadm kubectl

# 锁定版本
yum -y install yum-versionlock
yum versionlock kubelet kubeadm kubectl

# 设置开机启动
systemctl enable kubelet
```

离线

```
# 配置k8s源
cat > /etc/yum.repos.d/kubernetes.repo << EOF
[kubernetes]
name=Kubernetes
baseurl=https://mirrors.aliyun.com/kubernetes/yum/repos/kubernetes-el7-x86_64
enabled=1
gpgcheck=0
repo_gpgcheck=0
gpgkey=https://mirrors.aliyun.com/kubernetes/yum/doc/yum-key.gpg https://mirrors.aliyun.com/kubernetes/yum/doc/rpm-package-key.gpg
EOF

sudo yum install --downloadonly --downloaddir=./ kubelet-1.21.0-0 kubeadm-1.21.0-0 kubectl-1.21.0-0
#sudo yum install --downloadonly --downloaddir=./ kubelet-1.18.0-0 kubeadm-1.18.0-0 kubectl-1.18.0-0
rpm -Uvh *.rpm --nodeps --force
# 锁定版本
yum versionlock kubelet kubeadm kubectl
# 设置开机启动
systemctl enable kubelet
```



### 3. 在master节点执行kubeadm init初始化命令

#### 1. 执行初始化命令

部署Kubernetes Master, 在192.168.1.95，也就是master节点，执行如下命令：

```
# 查看所需镜像
kubeadm config images list --image-repository registry.aliyuncs.com/google_containers --kubernetes-version v1.21.1
# 批量导出离线镜像
docker save -o kubeadm_init_v1.21.1.tar registry.aliyuncs.com/google_containers/kube-apiserver:v1.21.1 registry.aliyuncs.com/google_containers/kube-controller-manager:v1.21.1 registry.aliyuncs.com/google_containers/kube-scheduler:v1.21.1 registry.aliyuncs.com/google_containers/kube-proxy:v1.21.1 registry.aliyuncs.com/google_containers/pause:3.4.1 registry.aliyuncs.com/google_containers/etcd:3.4.13-0 registry.aliyuncs.com/google_containers/coredns/coredns:v1.8.0

# 初始化master节点
kubeadm init --apiserver-advertise-address=192.168.1.109 --image-repository registry.aliyuncs.com/google_containers --kubernetes-version v1.21.1 --service-cidr=10.96.0.0/12  --pod-network-cidr=10.244.0.0/16
```

**该命令执行时间较长（大约2min），若执行完命令出现一些错误，可以查询步骤 2.处理报错** **。**



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

# bash 脚本执行，参考https://stackoverflow.com/questions/58058444/how-to-change-a-clusterrole-with-kubectl-gracefully
# kubectl apply -f <(cat <(kubectl get clusterrole system:coredns -o yaml) append-coredns.yaml)
# kubectl describe clusterrole system:coredns
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



### 5.1 测试k8s集群是否可用（可选）

1. 创建hello-kubernetes.yaml文件，如下：

```
# hello-kubernetes.yaml
apiVersion: v1
kind: Service
metadata:
 name: hello-kubernetes
spec:
 type: LoadBalancer
 ports:
 - port: 80
   targetPort: 8080
 selector:
   app: hello-kubernetes
---
apiVersion: apps/v1
kind: Deployment
metadata:
 name: hello-kubernetes
spec:
 replicas: 1
 selector:
   matchLabels:
     app: hello-kubernetes
 template:
   metadata:
     labels:
       app: hello-kubernetes
   spec:
     containers:
     - name: hello-kubernetes
       image: paulbouwer/hello-kubernetes:1.10
       ports:
       - containerPort: 8080
```

只部署pod（可选，测试用）：

```
apiVersion: v1
kind: Pod
metadata:
  name: hello-kube
spec:
  restartPolicy: OnFailure
  containers:
    - name: hello-kube
      image: "paulbouwer/hello-kubernetes:1.10"
```

1. 执行一下命令，创建服务

```
kubectl apply -f hello-kubernetes.yaml
```

1. 执行以下命令查看端口号

```
kubectl get svc
```

1. 根据执行结果访问网站，可以看到 Hello Word! 字样

```
curl http://192.168.29.212:46685
```

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
# 卸载kubeadm kubelet
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



### 9. 测试torchelstic

```
/ncluster/dushuai/elastic/kubernetes
kubectl apply -k config/default
kubectl get crd
kubectl get pods -n elastic-job
kubectl apply -f config/samples/etcd.yaml
kubectl get svc -n elastic-job

# 修改config/samples/imagenet.yaml,见文档k8s集群运行torchelastic记录
kubectl apply -f config/samples/imagenet.yaml
# 查看pod
kubectl get po -A
# 查看运行情况
kubectl describe elasticjob imagenet -n elastic-job
# 查看训练日志
kubectl logs -f -n elastic-job imagenet-worker-0
```

###  

### 10. 一些可能会出现的错误



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

```bash
error execution phase preflight: [preflight] Some fatal errors occurred:
    [ERROR Swap]: running with swap on is not supported. Please disable swap
```
````

错误原因是需要关闭swap