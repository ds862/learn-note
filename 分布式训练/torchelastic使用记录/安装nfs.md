# k8s安装默认存储类

通过下面命令，查看Kubernetes集群中的默认存储类



```
kubectl get storageclass
```



发现空空如也，下面给k8s集群安装默认的存储类

## 安装nfs

### 服务端执行

可以在linux系统的k8s集群中任意一个node节点做nfs服务端。 例如：【服务器内网ip：192.168.65.142】

1. 安装nfs相关服务软件包

```
# centos
yum install -y nfs-utils rpcbind

# ubuntu
sudo apt-get install -y nfs-kernel-server
```

1. 创建共享存储文件夹



```
mkdir /nfs
```



1. 配置nfs



```
vi /etc/exports
```

输入以下内容，格式为：`nfs共享目录 nfs客户端地址1(param1, param2,...) nfs客户端地址2(param1, param2,...)`

如：

```
/nfs *(rw,async,no_root_squash)
```

> 创建好共享目录通过`/etc/exports`进行编辑配置，若修改后，可以通过`systemctl reload nfs`或者`exportfs -avr`进行nfs服务的重新加载发布，从而使修改过的`/etc/exports`配置文件生效。

1. 启动服务

```
# centos
systemctl start rpcbind
systemctl enable rpcbind
systemctl enable nfs && systemctl restart nfs

# ubuntu
sudo /etc/init.d/rpcbind restart
sudo /etc/init.d/nfs-kernel-server restart
```

1. 查看服务状态

```
# centos
systemctl status rpcbind
systemctl status nfs
```

1. 查看可用的nfs地址

```
showmount -e localhost
```

### node上执行



1. 安装nfs-utils和rpcbind

```
# centos
yum install -y nfs-utils rpcbind

# ubuntu 
sudo apt-get install -y nfs-common
```

1. 创建挂载的文件夹

```
mkdir -p /nfs/data
```

1. 挂载nfs

```
mount -t nfs 192.168.65.142:/nfs /nfs/data
```

其中：
`mount`：表示挂载命令
`-t`：表示挂载选项
`nfs`：挂载的协议
`192.168.65.142`:nfs服务器的ip地址
`/nfs`：nfs服务器的共享目录
`/nfs/data`：本机客户端要挂载的目录

1. 查看挂载信息
   `$ df -Th`
2. 测试挂载
   可以进入本机的`/nfs/data`目录，上传一个文件，然后去nfs服务器查看/nfs目录中是否有该文件，若有则共享成功。反之在nfs服务器操作`/nfs`目录，查看本机客户端的目录是否共享。
3. 取消挂载(可选)
   `$ umount /nfs/data`



# 基于nfs创建storageclass

在k8s任一节点（可以使用kubectl命令即可，建议在master节点）

### 部署授权

`vi rbac.yaml`，写入以下内容(不用修改，直接复制即可)

```

```



部署并查看结果

```
[root@k8s deploy] kubectl create -f rbac.yaml
[root@k8s deploy] kubectl get sa
NAME                     SECRETS   AGE
default                  1         82d
nfs-client-provisioner   1         25s
```

### 部署插件

`vi deployment.yaml`，写入以下内容(注意需修改NFS服务器的ip地址和共享挂载目录)

```

```



部署并查看结果

```
[root@k8s deploy]# kubectl create -f deployment.yaml
[root@k8s deploy]# kubectl get deploy
NAME                                   READY   UP-TO-DATE   AVAILABLE   AGE
nfs-client-provisioner                 1/1     1            1           10s
```

### 部署storageclass

`vi class.yaml`，写入以下内容(不用修改，直接复制即可)

```

```



部署并查看结果

```
[root@k8s deploy]# kubectl create -f class.yaml
[root@k8s deploy]# kubectl get sc
NAME                  PROVISIONER      AGE
managed-nfs-storage   fuseim.pri/ifs   4s
```

### 设置为默认存储类

```
kubectl patch storageclass managed-nfs-storage -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
```

查看存储类

```
[root@k8s deploy]# kubectl get sc
NAME                            PROVISIONER      AGE
managed-nfs-storage (default)   fuseim.pri/ifs   3m59s
```

> 已有文件直接部署

```
kubectl create -f rbac.yaml
kubectl create -f deployment.yaml
kubectl create -f class.yaml
```



### 测试

#### 测试pvc

```
[root@k8s deploy]# vi test-claim.yaml
kind: PersistentVolumeClaim
apiVersion: v1
metadata:
  name: test-claim
  annotations:
    volume.beta.kubernetes.io/storage-class: "managed-nfs-storage"
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 2Gi
[root@k8s deploy]# kubectl create -f test-claim.yaml
[root@k8s deploy]# kubectl get pvc
NAME                                               STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS          AGE
test-claim                                         Bound    pvc-938bb7ec-8a1f-44dd-afb8-2659e824564a   1Mi        RWX            managed-nfs-storage   10s
```

#### 测试pod

```
[root@k8s deploy]# vi test-pod.yaml
apiVersion: v1
kind: Pod
metadata:
  name: volume-test
  namespace: default
spec:
  containers:
  - name: volume-test
    image: nginx:stable-alpine
    imagePullPolicy: IfNotPresent
    volumeMounts:
    - name: nfs-pvc
      mountPath: /data
    ports:
    - containerPort: 80
  volumes:
  - name: nfs-pvc
    persistentVolumeClaim:
      claimName: test-claim
[root@k8s deploy]# kubectl create -f test-pod.yaml
[root@k8s deploy]# kubectl get pods 
NAME                                                    READY   STATUS        RESTARTS   AGE
volume-test                                              1/1     Running       0          12s
```





## 附录：单节点使用local-path作为默认存储类

1. 设置master节点可调度

```
kubectl taint nodes $(kubectl get nodes | sed '1d' | awk '{print $1}') node-role.kubernetes.io/master:NoSchedule-
```

1. 设置local-path为默认存储类

`vi local-path-storage.yaml` 创建配置文件，并写入

```

```

启用配置

```
mkdir -p /opt/local-path-provisioner
kubectl create -f local-path-storage.yaml
```

1. 查看默认存储类

```
kubectl get sc
```