# torchelastic使用记录

## 1. 环境配置

1. 安装pytorch

   ```
   conda install pytorch torchvision torchaudio cudatoolkit=11.0 -c pytorch -c nvidia
   ```

   注意要先安装pytorch，而不能先安装torchelastic，否则会导致版本不匹配，运行时会报错，如下：

   ```
   AttributeError: module 'torch' has no attribute 'distributed'
   ```

2. 安装torchelastic

   ```
   pip install torchelastic
   ```

3. 安装etcd：

   ```
   curl -L https://storage.googleapis.com/etcd/v3.4.16/etcd-v3.4.16-linux-amd64.tar.gz -o /tmp/etcd-v3.4.16-linux-amd64.tar.gz
   ```

   ```
   cd /tmp/
   tar -zvxf etcd-v3.4.16-linux-amd64.tar.gz
   mv etcd-v3.4.16-linux-amd64 etcd
   cd etcd
   cp etcd* /usr/local/bin/
   etcd --version
   ```

4. 安装Kustomize(可选)

   ```
   wget https://github.com/kubernetes-sigs/kustomize/releases/download/kustomize%2Fv4.1.3/kustomize_v4.1.3_linux_amd64.tar.gz
   #解压
   tar -zvxf kustomize_v4.1.3_linux_amd64.tar.gz kustomize
   
   mv kustomize /usr/local/bin/kustomize
   
   chmod u+x /usr/local/bin/kustomize
   
   kustomize version
   
   # 
   
   ```

   

6. 安装go（可选）

   ```
   wget https://golang.org/dl/go1.16.4.linux-amd64.tar.gz
   
   rm -rf /usr/local/go && tar -C /usr/local -xzf go1.16.4.linux-amd64.tar.gz
   
   export PATH=$PATH:/usr/local/go/bin
   
   go version
   ```

   

7. 其他(可选)：

   使用NVIDIA PyTorch

   ```
   docker pull nvcr.io/nvidia/pytorch:21.04-py3
   ```

   ```
   docker run --gpus all -it --rm -v local_dir:container_dir nvcr.io/nvidia/pytorch:xx.xx-py3
   ```

   


## 2. 使用torchelastic

### 2.1 官方docker镜像示例

1. 安装docker(ubuntu)

   ```
   curl -fsSL https://get.docker.com | bash -s docker --mirror Aliyun
   ```

   安装docker-Compose

   ```
   sudo curl -L "https://github.com/docker/compose/releases/download/1.29.1/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
   
   #将可执行权限应用于二进制文件：
   sudo chmod +x /usr/local/bin/docker-compose
   
   # 创建软连链接
   sudo ln -s /usr/local/bin/docker-compose /usr/bin/docker-compose
   
   # 测试是否成功
   docker-compose --version
   ```

2. 安装nvidia-docker

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

   

3. 下载官方docker镜像：torchelastic/examples

   ```
   docker pull torchelastic/examples:0.2.0
   ```

4. CPU运行：（单机多卡）

   ```
   docker run --shm-size=2g torchelastic/examples:0.2.0 --standalone --nnodes=1 --nproc_per_node=2 /workspace/classy_vision/classy_train.py --config_file /workspace/classy_vision/configs/template_config.json
   ```

5. GPU运行：（单机多卡）

   ```
   docker run --shm-size=2g --gpus=all torchelastic/examples:0.2.0 --standalone --nnodes=1 --nproc_per_node=2 /workspace/examples/imagenet/main.py --arch resnet18 --epochs 20 --batch-size 32 /workspace/data/tiny-imagenet-200
   ```

   进入容器后台查看：`docker exec -it id bash `

6. GPU多机多卡：

   ```
   # 启用etcd
   etcd --enable-v2 --listen-client-urls http://0.0.0.0:2379,http://127.0.0.1:4001 --advertise-client-urls http://192.168.1.95:2379 
   	
   # 在每个机器上运行
   docker run --shm-size=2g --gpus=all torchelastic/examples:0.2.0 --nnodes=1:4 --nproc_per_node=2 --rdzv_id=123 --rdzv_backend=etcd --rdzv_endpoint=192.168.1.95:2379 /workspace/examples/imagenet/main.py --arch resnet18 --epochs 20 --batch-size 32 /workspace/data/tiny-imagenet-200 
   ```

   报错如下：

   ![](.\images\elasticUse_1.png)

   ![](.\images\elasticUse_2.png)

#### 2.1.2 多容器运行

1. 从GitHub下载elastic:

   ```
   git clone https://github.com/pytorch/elastic.git
   ```

2. 加入环境变量

   ```
   export TORCHELASTIC_HOME=~/elastic
   ```

3. 运行示例：

   ```
   cd $TORCHELASTIC_HOME/examples/multi_container && docker-compose up
   ```

   运行结束后elastic/examples容器退出，etcd容器后台继续运行。如下：

   运行前：

   ![](.\images\elasticUse_3.png)

    运行后：![](.\images\elasticUse_4.png)







### 2.2 自建脚本运行

1. 编写脚本

   首先代码已经支持 **torch.distributed.launch** ，在这基础上仅有几处不同之处：

   - 不需要传递 **RANKE** , **MASTER_ADDR** 和 **MASTER_PORT** 这几个环境变量
   - 需要配置参数**rdzv_id** ，**rdzv_backend** 和 **rdzv_endpoint** 参数（--rdzv_id 是这个job 的一个名字，不同的worker这个需要相同。--rdzv_backend 是指 monitor 的后端默认是 etcd。--rdzv_endpoint 是 monitor 的 ip 和 端口。）
   - 代码中需要支持 **load_checkpoint(path)** 和 **save_checkpoint(path)** ，当有worker出错恢复现场或者做弹性伸缩时，都会用到这个checkpoint，用以恢复现场，包括参数和进度等
   - **use_end** 参数已被移除。从 **LOCAL_RANK** 环境变量中获取local_rank (e.g.os.environ["LOCAL_RANK"])

2. 启用一个单节点的etcd服务

   ```
   etcd    --enable-v2
           --listen-client-urls http://0.0.0.0:2379,http://127.0.0.1:4001    
           --advertise-client-urls PUBLIC_HOSTNAME:2379
           
   etcd --enable-v2 --listen-client-urls http://0.0.0.0:2379,http://127.0.0.1:4001   --advertise-client-urls http://192.168.1.95:2379
   # 参数
   --listen-client-urls:监听的用于客户端通信的url,对外提供服务的地址，客户端会连接到这里和 etcd 交互，同样可以监听多个。
   --advertise-client-urls：建议使用的客户端通信url,该值用于etcd代理或etcd成员与etcd节点通信，即服务的url。
   ```
   
3. 单节点运行

   ```
   python -m torchelastic.distributed.launch --nnodes=1 --nproc_per_node=2 --standalone main.py
   ```

   无法训练：

   ![](.\images\elasticUse_5.png)

   

   运行imagenet/main.py：

   ```
   #imagenet
   python -m torchelastic.distributed.launch --nnodes=1 --nproc_per_node=2 --standalone main.py --arch resnet18 --epochs 20 --batch-size 32 ./data/tiny-imagenet-200
   
   #一些修改
   from torch.distributed.elastic.utils.data import ElasticDistributedSampler改为：from torchelastic.utils.data import ElasticDistributedSampler
   
   
   ```

   

4. 多节点运行(在每台机器上运行以下代码)

   ```
   python -m torchelastic.distributed.launch --nnodes=2 --nproc_per_node=2 --rdzv_id=123 --rdzv_backend=etcd --rdzv_endpoint=192.168.1.95:2379 main.py
   
   docker run --shm-size=2g --gpus=all torchelastic/examples:0.2.0 --nnodes=1:4 --nproc_per_node=2 --rdzv_id=123 --rdzv_backend=etcd --rdzv_endpoint=192.168.1.95:2379 /workspace/examples/imagenet/main.py --arch resnet18 --epochs 20 --batch-size 32 ./data/tiny-imagenet-200
   ```

   

   运行imagenet/main.py：

   ```
   python -m torchelastic.distributed.launch --nnodes=1:3 --nproc_per_node=2 --rdzv_id=0 --rdzv_backend=etcd --rdzv_endpoint=192.168.1.95:2379 main.py --arch resnet18 --epochs 20 --batch-size 32 ./data/tiny-imagenet-200
   
   python -m torchelastic.distributed.launch --nnodes=1 --nproc_per_node=2 --rdzv_id=0 --rdzv_backend=etcd --rdzv_endpoint=127.0.0.1:2379 main.py --arch resnet18 --epochs 20 --batch-size 32 ./data/tiny-imagenet-200
   
   
   ```

totch1.9运行

单节点

```
python -m torch.distributed.run --nnodes=1 --nproc_per_node=2 --standalone main.py --arch resnet18 --epochs 20 --batch-size 32 ./data/tiny-imagenet-200
```

多节点

```
python -m torch.distributed.run --nnodes=2 --nproc_per_node=2 --rdzv_id=11 --rdzv_backend=c10d --rdzv_endpoint=192.168.1.109:29400 main.py --arch resnet18 --epochs 30 --batch-size 32 ./data/tiny-imagenet-200
        
```





测试结果：

1. 启动三台机器，每台机器两张卡：

   启动命令如下：

   ```
   python -m torchelastic.distributed.launch --nnodes=3 --nproc_per_node=2 --rdzv_id=0 --rdzv_backend=etcd --rdzv_endpoint=192.168.1.94:2379 main.py --arch resnet18 --epochs 20 --batch-size 32 ./data/tiny-imagenet-200
   ```

   - 成功：

   ![](.\文档记录\images\使用etcd启动3台机器成功.png)

- 杀掉一个进程后（停用一张卡）

​        三台机器上的训练程序同时重新启动![](.\images\杀掉一张卡上的进程后_1.png)

![](.\images\杀掉一张卡上的进程后_2.png)

- 停掉一台机器后，其他两台机器卡在当前epoch（尚在测试）



2. 弹性启动三台机器，每台机器两张卡：

   命令如下：

   ```
   python -m torchelastic.distributed.launch --nnodes=1:3 --nproc_per_node=2 --rdzv_id=0 --rdzv_backend=etcd --rdzv_endpoint=192.168.1.94:2379 main.py --arch resnet18 --epochs 20 --batch-size 32 ./data/tiny-imagenet-200
   ```

- 成功与固定三个节点启动相同
- 启动两个节点

等待一段时间后，以两个节点运行

![弹性启动3个节点，只运行2个节点.png](https://intranetproxy.alipay.com/skylark/lark/0/2021/png/18057116/1621933973201-a697896d-5e54-403e-af5e-b709b8949d48.png)

- 启动三个节点后，停用一个节点



报错：

   ```
   假设在两台机器上使用torchelastic，运行以下命令为什么会报错ValueError: host not found: Name or service not known
   在机器1上：
   etcd --enable-v2 --listen-client-urls http://0.0.0.0:2379,http://127.0.0.1:4001 --advertise-client-urls http://192.168.1.11:2379
   python -m torchelastic.distributed.launch --nnodes=2 --nproc_per_node=2 --rdzv_id=0 --rdzv_backend=etcd --rdzv_endpoint=192.168.1.11:2379 main.py
   在机器2上：
   python -m torchelastic.distributed.launch --nnodes=2 --nproc_per_node=2 --rdzv_id=0 --rdzv_backend=etcd --rdzv_endpoint=192.168.1.11:2379 main.py
   
   Traceback (most recent call last):
     File "main.py", line 597, in <module>
       dist.init_process_group(backend="nccl", init_method="env://", timeout=timedelta(seconds=10))
     File "/root/miniconda/envs/aiacct_tr1.7.0_cu11.0_py36/lib/python3.6/site-packages/torch/distributed/distributed_c10d.py", line 436, in init_process_group
       store, rank, world_size = next(rendezvous_iterator)
     File "/root/miniconda/envs/aiacct_tr1.7.0_cu11.0_py36/lib/python3.6/site-packages/torch/distributed/rendezvous.py", line 179, in _env_rendezvous_handler
       store = TCPStore(master_addr, master_port, world_size, start_daemon, timeout)
   ValueError: host not found: Name or service not known
   
   ```



注意，要使用etcd官方文档的集群部署方式

   ```
   #部署etcd集群
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
   ```



测试etcd环境

```
etcdctl --endpoints=http://192.168.1.95:2379 put /testdir/testkey "Hello world"
etcdctl get /testdir/testkey --endpoints=http://192.168.1.95:2379

etcdctl put /testdir/testkey "test elastic"
etcdctl get /testdir/testkey

etcdctl member list
etcdctl --endpoints="http://192.168.1.95:2379,http://192.168.1.94:2379,http://192.168.1.94:2379"  endpoint  health
```

 





pip install torch===1.5.0

pip uninstall torchaudio

pip install torchvision==0.6.0