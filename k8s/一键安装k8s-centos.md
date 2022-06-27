```shell
#!/bin/bash

# 安装版本
KUBE_VERSION=v1.21.1
# 获取hostname
HOST_NAME=$(hostname)
# 默认的SSH_USER
SSH_USER=root
# 镜像仓库地址
IMAGE_REPOSITORY=registry.cn-beijing.aliyuncs.com/google_containers_kube

# 参数信息
[ "$#" == "0" ] && help::usage
while [ "${1:-}" != "" ]; do
  case "$1" in
    init )                  INIT_TAG=1
                            ;;
    add )                   ADD_TAG=1
                            ;;
    test )                  TEST_TAG=1
                            ;;
    workerInit )            WORKER_INIT_TAG=1
                            ;;
    reset )                 RESET_TAG=1
                            ;;                       
    del )                   DEL_TAG=1
                            ;;
    -m | --master )         shift
                            MASTER_NODE=${1:-$MASTER_NODE}
                            ;;
    -w | --worker )         shift
                            WORKER_NODE=${1:-$WORKER_NODE}
                            ;;
    -v | --version )        shift
                            KUBE_VERSION=${1:-$KUBE_VERSION}
                            ;;
    -n | --name )           shift
                            WORKER_HOST_NAME=${1:-$WORKER_HOST_NAME}
                            ;;
    -u | --user )           shift
                            SSH_USER=${1:-$SSH_USER}
                            ;;
    -p | --password )       shift
                            SSH_PASSWORD=${1:-$SSH_PASSWORD}
                            ;;  
    * )                     help::usage
                            exit 1  
  esac  
  shift  
done

# 安装包目录
INSTALLATION_DIR=/root/kubeDeploy-centos-${KUBE_VERSION}
# 离线docker目录
DOCKER_DIR=${INSTALLATION_DIR}/docker
# 离线nvidia-docker目录
NVIDIA_DOCKER_DIR=${INSTALLATION_DIR}/nvidia-docker
# 离线k8s目录
KUBE_DIR=${INSTALLATION_DIR}/kube
# 离线镜像目录
IMAGES_DIR=${INSTALLATION_DIR}/images-offline
# 配置文件
CONFIG_DIR=${INSTALLATION_DIR}/config


# 1.设置基础功能
function basic_setting(){
  # 安装需要用的软件
  echo "==============  start setting  ==============="
  yum install -y wget selinux-utils conntrack ipvsadm ipset jq sysstat curl iptables libseccomp2 yum-utils device-mapper-persistent-data lvm2 yum-versionlock
  # 关闭分区
  swapoff -a
  # 关闭防火墙
  systemctl disable firewalld
  # 关闭selinux
  setenforce 0 
  # 将桥接的IPv4流量传递到iptables的链
  cat <<EOF | sudo tee /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-ip6tables = 1
net.bridge.bridge-nf-call-iptables = 1
EOF
  sysctl --system
  echo "==========  setting sucess  =========="
}


# 2.安装docker
function install_docker(){
  if [ -x "$(command -v docker)" ]; then
      echo "==========  docker has been installed  =========="
  else
      echo "========== start install docker  =========="
      rpm -ivh ${DOCKER_DIR}/*.rpm --nodeps --force
  fi
}


# 3.启用docker GPU支持
function install_gpu_docker(){
  # if dpkg -s nvidia-docker2 >/dev/null 2>&1; then
  if yum list installed nvidia-docker2 >/dev/null 2>&1; then
      echo "==========  nvidia docker has been installed  =========="
  else
      echo "==========  start install nvidia docker  =========="
      sudo systemctl --now enable docker
      rpm -Uvh ${NVIDIA_DOCKER_DIR}/*.rpm --nodeps --force
  fi
  # 添加容器运行时以及阿里云镜像加速
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
}


# 4.安装kubelet、kubeadm、kubectl
function install_kube(){
  if [ -x "$(command -v kubeadm)" ]; then
      echo "==========  kube has been installed  =========="
  else
      echo "==========  start install kube  =========="
      # 离线安装
      # rpm -ivh ${KUBE_DIR}/*.rpm --nodeps --force
      rpm -ivh ${KUBE_DIR}/*.rpm --nodeps --force
      # 锁定版本
      yum versionlock kubelet kubeadm kubectl
  fi
}

# 5.0.拉取特殊镜像，如registry.aliyuncs.com/google_containers/coredns/coredns:v1.8.0
function pull_special_images(){
  for origin_image in $(kubeadm config images list --image-repository ${IMAGE_REPOSITORY} --kubernetes-version ${KUBE_VERSION})
  do
    # registry.aliyuncs.com/google_containers/coredns/coredns:v1.8.0
    # echo "$origin_image"
    # coredns:v1.8.0
    image_name=($(echo $origin_image | awk -F "/" '{print $NF}'))
    # coredns
    image_name_pre=($(echo $image_name |awk -F ":" '{print $1}'))
    # v1.8.0
    image_name_suf=($(echo $image_name |awk -F ":" '{print $NF}'))
    # echo "image_name:  $image_name"
    # echo "image_name_pre:  $image_name_pre"
    # echo "image_name_suf:  $image_name_suf"
    # registry.aliyuncs.com/google_containers/coredns
    image_pre=($(echo $origin_image | awk -F '/[^/]*$' '{print $1}'))
    # coredns
    image_pre_suf=($(echo $image_pre |awk -F "/" '{print $NF}'))
    if [ ${image_name_pre} == ${image_pre_suf} ]
    then
      docker pull ${IMAGE_REPOSITORY}/${image_name_pre}:${image_name_suf}
      docker tag ${IMAGE_REPOSITORY}/${image_name_pre}:${image_name_suf} ${IMAGE_REPOSITORY}/${image_name_pre}/${image_name_pre}:${image_name_suf}
    fi
  done
}


# 5.启用master节点
function kubeadm_init(){
  #coredns镜像存在多级命名空间问题，因此需要单独拉取修改tag
  pull_special_images
  #docker load -i $IMAGES_DIR/kubeadm_init_${KUBE_VERSION}.tar
  # 开始初始化
  kubeadm init --apiserver-advertise-address=${MASTER_NODE} --image-repository ${IMAGE_REPOSITORY} --kubernetes-version ${KUBE_VERSION} --service-cidr=10.96.0.0/12  --pod-network-cidr=10.244.0.0/16
  # 配置kube
  mkdir -p $HOME/.kube
  sudo cp /etc/kubernetes/admin.conf $HOME/.kube/config
  sudo chown $(id -u):$(id -g) $HOME/.kube/config
}


# 6.安装网络插件
function cni_install(){
  docker load -i $IMAGES_DIR/flannel.tar
  kubectl apply -f ${CONFIG_DIR}/kube-flannel.yml
}

# 6.1解决coredns是Running状态，但是没有READY
function coredns_fix(){
  kubectl apply -f <(cat <(kubectl get clusterrole system:coredns -o yaml) ${CONFIG_DIR}/append-coredns.yaml)
}


# 7.在k8s中启用docker gpu
function k8s_gpu_docker(){
  kubectl create -f ${CONFIG_DIR}/nvidia-device-plugin.yml
}


# 8.初始化master节点
function init_master(){
  basic_setting
  install_docker
  install_gpu_docker
  install_kube
  kubeadm_init
  cni_install
  if [[ $KUBE_VERSION == "v1.21.0" || $KUBE_VERSION == "v1.21.1" ]]
  then
    coredns_fix
  fi
  k8s_gpu_docker
}


# 9.添加worker节点
function add_worker(){
  # 创建加入命令
  JOIN_COMMAND=$(kubeadm token create --print-join-command)
  # 拷贝安装包
  scp -o StrictHostKeyChecking=no "$0" ${SSH_USER}@${WORKER_NODE}:/root/
  scp -o StrictHostKeyChecking=no -r ${INSTALLATION_DIR} ${SSH_USER}@${WORKER_NODE}:/root/
  # ssh到worker节点，进行worker初始化
  ssh -o StrictHostKeyChecking=no ${SSH_USER}@${WORKER_NODE} << EXITSSH
  cd /root/
  bash $0 workerInit -v ${KUBE_VERSION}
  eval $JOIN_COMMAND
exit
EXITSSH
  # 在worker节点上启用kubectl
  scp -o StrictHostKeyChecking=no /etc/kubernetes/admin.conf ${SSH_USER}@${WORKER_NODE}:/etc/kubernetes/admin.conf
  ssh -o StrictHostKeyChecking=no ${SSH_USER}@${WORKER_NODE} << EXITSSH
  echo "export KUBECONFIG=/etc/kubernetes/admin.conf" >> ~/.bash_profile
  source ~/.bash_profile
exit
EXITSSH
}


# 9.1 初始化worker节点
function init_worker(){
  basic_setting
  install_docker
  install_gpu_docker
  install_kube
  load_test_images
}


# 10.加载测试镜像
function load_test_images(){
  docker load -i ${IMAGES_DIR}/hello-kubernetes.tar
}

# 11.测试k8s是否可用
function test_k8s(){
  docker load -i ${IMAGES_DIR}/hello-kubernetes.tar
  kubectl apply -f ${CONFIG_DIR}/hello-kubernetes.yaml
  echo "========== testing... it takes about 10 seconds =========="
  sleep 10s
  str_command=$(kubectl logs hello-kubernetes)
  str_result="hello-kubernetes@1.10.0 start"
  result=$(echo $str_command | grep "${str_result}")
  if [[ "$result" != "" ]]
  then
    echo "The status of K8S is normal"
  else
    echo "The status of K8S is unnormal"
  fi
}


# 12.测试k8s gpu是否可用
function test_k8s_gpu(){
  # docker load -i ${IMAGES_DIR}/.tar
  kubectl apply -f ${CONFIG_DIR}/gpu-pod.yaml
  echo "========== testing... it takes about 10 seconds =========="
  sleep 10s
  str_command=$(kubectl logs cuda-vector-add)
  str_result="Test PASSED"
  result=$(echo $str_command | grep "${str_result}")
  if [[ "$result" != "" ]]
  then
    echo "K8S gpu is available"
  else
    echo "K8S gpu is unavailable"
  fi
}


# 13.reset节点配置信息
function reset_node_config(){
  echo y|kubeadm reset
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
}

# 14.reset worker节点
function reset_worker(){
  kubectl drain ${WORKER_HOST_NAME} --delete-local-data --force --ignore-daemonsets
  ssh -o StrictHostKeyChecking=no ${SSH_USER}@${WORKER_NODE} << EXITSSH
  $(typeset -f reset_node_config)
  reset_node_config
  echo "=============  reset success  ==========="
exit
EXITSSH
  kubectl delete node ${WORKER_HOST_NAME}
}

# 15. 仅reset worker节点，不在master节点删除信息
function only_reset_worker(){
  ssh -o StrictHostKeyChecking=no ${SSH_USER}@${WORKER_NODE} << EXITSSH
  $(typeset -f reset_node_config)
  reset_node_config
  echo "==========  reset success  =========="
exit
EXITSSH
}

# 16.reset master节点
function reset_master(){  
  reset_node_config
  echo "==========  reset success  =========="
}

# 17. reset集群
function reset_cluster(){
  nodes=(${WORKER_NODE//\,/ })
  for host in ${nodes[@]}
    do
        ssh -o StrictHostKeyChecking=no ${SSH_USER}@${host} << EXITSSH
        echo "========== reset ${host} =========="
        $(typeset -f reset_node_config)
        reset_node_config  
        echo "========== reset ${host} success! =========="
        exit
EXITSSH
    done
  echo "==========  reset master  =========="
  reset_node_config
  echo "==========  reset master done!  =========="
  echo "==========  reset k8s cluster done!  =========="
}

# 18. re-init集群
function reinit_cluster(){
nodes=(${WORKER_NODE//\,/ })
for host in ${nodes[@]}
  do
      ssh -o StrictHostKeyChecking=no ${SSH_USER}@${host} << EXITSSH
      echo "========== reset ${host} =========="
      $(typeset -f reset_node_config)
      reset_node_config
      echo "==========  reset success  =========="
      exit
EXITSSH
  done
echo "==========  reset master  =========="
reset_node_config 
echo "==========  init master  =========="
kubeadm_init
cni_install
if [[ $KUBE_VERSION == "v1.21.0" || $KUBE_VERSION == "v1.21.1" ]]
  then
    coredns_fix
fi
k8s_gpu_docker
}


# 使用帮助
function help::usage {
  cat << EOF
One key to install kubernetes cluster on centos.

Usage:
  $(basename "$0") [command]

Available Commands:
  init              Init Kubernetes cluster.
  add               Add nodes to the cluster. 
  test              Test whether the K8S is installed successfully.
  reset             Reset Kubernetes cluster.
  del               Remove node from the cluster.

Flag:
  -m,--master          master node, default: ''
  -w,--worker          work node, default: ''
  -v,--version         kube version, default: v1.21.1
  -n,--name            work hostname, default: ''
  -u,--user            ssh user, default: root
  -p,--password        ssh password

Example:
  [init cluster]
  $0 init \\
  --master 192.168.1.96 \\
  --version v1.21.1
  [add worker]
  $0 add \\
  --worker 192.168.1.95 \\
  --version v1.21.1
  [test kube]
  $0 test -v v1.21.1
  [reset worker node]
  $0 reset \\
  --worker 192.168.1.95 \\
  --name worker1 
  [reset k8s cluster]
  $0 reset \\
  
  [other]
  To be added...
  
EOF
  exit 1
}


# echo "========= master ip: ${MASTER_NODE} ==========="
# echo "========= worker ip: ${WORKER_NODE} ==========="
echo "========= KUBE_VERSION: ${KUBE_VERSION} =========="
echo "========= INSTALLATION_DIR: ${INSTALLATION_DIR} =========="


if [[ "${INIT_TAG:-}" == "1" ]]; then
  echo "========== init master =========="
  init_master
elif [[ "${ADD_TAG:-}" == "1" ]]; then
  add_worker
elif [[ "${TEST_TAG:-}" == "1" ]]; then
  echo "========== test k8s =========="
  test_k8s
elif [[ "${WORKER_INIT_TAG:-}" == "1" ]]; then
  echo "========== init worker =========="
  init_worker
elif [[ "${RESET_TAG:-}" == "1" ]]; then
  if [[ "$MASTER_NODE" == "" && "$WORKER_NODE" != "" && "$WORKER_HOST_NAME" != "" ]]; then
    echo "========== reset worker =========="
    reset_worker
  elif [[ "$MASTER_NODE" == "" && "$WORKER_NODE" != "" && "$WORKER_HOST_NAME" == "" ]]; then
    echo "========== reset worker =========="
    only_reset_worker
  elif [[ "$MASTER_NODE" != "" && "$WORKER_NODE" == "" ]]; then
    echo "========== reset master =========="
    reset_master
  else
  help::usage
  fi
else
  help::usage
fi

```

