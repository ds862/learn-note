## Pytorch分布式训练



```python3
## main.py文件
import torch

# 构造模型
model = nn.Linear(10, 10).to(local_rank)

# 前向传播
outputs = model(torch.randn(20, 10).to(rank))
labels = torch.randn(20, 10).to(rank)
loss_fn = nn.MSELoss()
loss_fn(outputs, labels).backward()
# 后向传播
optimizer = optim.SGD(model.parameters(), lr=0.001)
optimizer.step()

## Bash运行
python ddp.py
```

```python
## ddp.py文件
import torch
# 新增：
import torch.distributed as dist

# 新增：从外面得到local_rank参数
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--local_rank", default=-1)
FLAGS = parser.parse_args()
local_rank = FLAGS.local_rank

# 新增：DDP backend初始化
torch.cuda.set_device(local_rank)
dist.init_process_group(backend='nccl')  # nccl是GPU设备上最快、最推荐的后端

# 构造模型
device = torch.device("cuda", local_rank)
model = nn.Linear(10, 10).to(device)
# 新增：构造DDP model
model = DDP(model, device_ids=[local_rank], output_device=local_rank)

# 前向传播
outputs = model(torch.randn(20, 10).to(rank))
labels = torch.randn(20, 10).to(rank)
loss_fn = nn.MSELoss()
loss_fn(outputs, labels).backward()
# 后向传播
optimizer = optim.SGD(model.parameters(), lr=0.001)
optimizer.step()


## Bash运行
# 改变：使用torch.distributed.launch启动DDP模式，
#   其会给ddp.py一个local_rank的参数。这就是之前需要"新增:从外面得到local_rank参数"的原因
python -m torch.distributed.launch --nproc_per_node 4 ddp.py
```

```python
## ddp.py文件
import torch
import argparse

# 新增1:依赖
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel as DDP

# 新增2：从外面得到local_rank参数，在调用DDP的时候，其会自动给出这个参数，后面还会介绍。所以不用考虑太多，照着抄就是了。
#       argparse是python的一个系统库，用来处理命令行调用，如果不熟悉，可以稍微百度一下，很简单！
parser = argparse.ArgumentParser()
parser.add_argument("--local_rank", default=-1)
FLAGS = parser.parse_args()
local_rank = FLAGS.local_rank

# 新增3：DDP backend初始化
#   a.根据local_rank来设定当前使用哪块GPU
torch.cuda.set_device(local_rank)
#   b.初始化DDP，使用默认backend(nccl)就行。如果是CPU模型运行，需要选择其他后端。
dist.init_process_group(backend='nccl')

# 新增4：定义并把模型放置到单独的GPU上，需要在调用`model=DDP(model)`前做哦。
#       如果要加载模型，也必须在这里做哦。
device = torch.device("cuda", local_rank)
model = nn.Linear(10, 10).to(device)
# 可能的load模型...

# 新增5：之后才是初始化DDP模型
model = DDP(model, device_ids=[local_rank], output_device=local_rank)
```

## 基本概念

### 基本概念

在16张显卡，16的并行数下，DDP会同时启动16个进程。下面介绍一些分布式的概念。

**group**

即进程组。默认情况下，只有一个组。这个可以先不管，一直用默认的就行。

**world size**

表示全局的并行数，简单来讲，就是2x8=16。

```python3
# 获取world size，在不同进程里都是一样的，得到16
torch.distributed.get_world_size()
```

**rank**

表现当前进程的序号，用于进程间通讯。对于16的world sizel来说，就是0,1,2,…,15。
注意：rank=0的进程就是master进程。

```text
# 获取rank，每个进程都有自己的序号，各不相同
torch.distributed.get_rank()
```

**local_rank**

又一个序号。这是每台机子上的进程的序号。机器一上有0,1,2,3,4,5,6,7，机器二上也有0,1,2,3,4,5,6,7

```python
# 获取local_rank。一般情况下，你需要用这个local_rank来手动设置当前模型是跑在当前机器的哪块GPU上面的。
torch.distributed.local_rank()
```



## 运行

**单机模式**

```bash
## Bash运行
# 假设我们只在一台机器上运行，可用卡数是2
python -m torch.distributed.launch --nproc_per_node 2 ddp.py
```

**多机模式**

复习一下，master进程就是rank=0的进程。
在使用多机模式前，需要介绍两个参数：

- 通讯的address

- - `--master_address`
  - 也就是master进程的网络地址
  - 默认是：127.0.0.1，只能用于单机。

- 通讯的port

- - `--master_port`
  - 也就是master进程的一个端口，要先确认这个端口没有被其他程序占用了哦。一般情况下用默认的就行
  - 默认是：29500

```bash
## Bash运行
# 假设我们在2台机器上运行，每台可用卡数是8
#    机器1：
python -m torch.distributed.launch --nnodes=2 --node_rank=0 --nproc_per_node 8 \
  --master_adderss $my_address --master_port $my_port ddp.py
#    机器2：
python -m torch.distributed.launch --nnodes=2 --node_rank=1 --nproc_per_node 8 \
  --master_adderss $my_address --master_port $my_port ddp.py
```

```
# 集群
python -m torch.distributed.launch --nnodes=2 --node_rank=0 --nproc_per_node 2 --master_addr=192.168.1.109 --master_port=12346 ddp.py

python -m torch.distributed.launch --nnodes=2 --node_rank=1 --nproc_per_node 2 --master_addr=192.168.1.1 --master_port=12346 ddp.py

python -m torch.distributed.launch --nnodes=3 --node_rank=2 --nproc_per_node 2 --master_addr=192.168.1.95 --master_port=12346 ddp.py

#单机测试
python -m torch.distributed.launch --nnodes=1 --node_rank=0 --nproc_per_node 2 --master_addr=127.0.0.1 --master_port=29500 ddp.py
```



docker运行torchelastic

```text
docker run --shm-size=2g torchelastic/examples:0.2.0 --standalone --nnodes=1 --nproc_per_node=2 /workspace/classy_vision/classy_train.py --config_file /workspace/classy_vision/configs/template_config.json

docker run --shm-size=2g --gpus=all torchelastic/examples:0.2.0 --standalone --nnodes=1 --nproc_per_node=2 /workspace/classy_vision/classy_train.py --device=gpu --config_file /workspace/classy_vision/configs/template_config.json

docker run --shm-size=2g --gpus=all torchelastic/examples:0.2.0 --standalone --nnodes=1 --nproc_per_node=2 /workspace/examples/imagenet/main.py --arch resnet18 --epochs 20 --batch-size 32 /workspace/data/tiny-imagenet-200

# 多机多卡
docker run --shm-size=2g --gpus=all torchelastic/examples:0.2.0 --nnodes=2 --nproc_per_node=2 --rdzv_id=123 --rdzv_backend=etcd --rdzv_endpoint=192.168.1.95:2379 /workspace/examples/imagenet/main.py --arch resnet18 --epochs 20 --batch-size 32 /workspace/data/tiny-imagenet-200
```

```
export TORCHELASTIC_HOME=/ncluster/dushuai/elastic
```







编写脚本运行：

```text
etcd --enable-v2 --listen-client-urls http://0.0.0.0:2379,http://127.0.0.1:4001 --advertise-client-urls http://192.168.1.95:2379
```

```text
python -m torchelastic.distributed.launch --nnodes=1 --nproc_per_node=2 --standalone main.py

python -m torchelastic.distributed.launch --nnodes=2 --nproc_per_node=2 --rdzv_id=123 --rdzv_backend=etcd --rdzv_endpoint=192.168.1.95:2379 main.py

python -m torchelastic.distributed.launch
    --nnodes=1:4
    --nproc_per_node=$NUM_TRAINERS
    --rdzv_id=$JOB_ID
    --rdzv_backend=etcd
    --rdzv_endpoint=$ETCD_HOST:$ETCD_PORT
    YOUR_TRAINING_SCRIPT.py
```













下载etcd：

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



vim清空文件

在命令模式下，首先执行 gg 这里是跳至文件首行 再执行：dG 这样就清空了整个文件！