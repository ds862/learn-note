http://www.ruanyifeng.com/blog/2018/02/docker-tutorial.html

https://www.cnblogs.com/H4ck3R-XiX/p/12227485.html

#### 镜像相关操作

```
docker search mmdetection # 搜索镜像

docker pull qianjaingyuan/mmdetection  # 拉去镜像

docker images # 列出镜像

docker rmi mmdetection # 删除镜像

docker save -o mmdet.tar 镜像ID # 保存镜像为本地文件

docker load -i mmdet.tar # 加载镜像文件

docker tag 镜像ID mmdet:v1
```

#### 容器相关操作

```
# 运行容器，如果需要使用GPU，使用nvidia-docker
nvidia-docker run -itd --ipc=host -v $PWD/data/:/mmdetection/data/ -v $PWD/result/:/mmdetection/work_dirs 镜像ID /bin/bash

# 解释
# -i 交互式操作
# -t 终端
# -d 后台运行
# --ipc=host 容器与主机共享内存
# -v 将宿主的目录挂载到容器
docker ps # 列出当前正在运行的容器
docker ps -a # 列出所有容器



docker stop <容器 ID> # 停止容器

docker restart <容器 ID> # 容器容器

docker exec -it <容器 ID> /bin/bash # 进入容器，退出容器终端，不会导致容器的停止

docker rm -f <容器 ID> # 删除容器

docker commit <容器 ID> <镜像名：镜像标签> # 通过容器提交镜像
```

```
# 将主机/www/runoob目录拷贝到容器96f7f14e99ab的/www目录下
docker cp /www/runoob 96f7f14e99ab:/www/

# 将主机/www/runoob目录拷贝到容器96f7f14e99ab中，目录重命名为www
docker cp /www/runoob 96f7f14e99ab:/www

# 将容器96f7f14e99ab的/www目录拷贝到主机的/tmp目录中
docker cp  96f7f14e99ab:/www /tmp/
```

启动一个容器，即docker run操作。

```text
[root@xxx ~]# docker run -it centos:latest /bin/bash
```

这里-it是两个参数：-i和-t。前者表示打开并保持stdout，后者表示分配一个终端（pseudo-tty）。此时如果使用exit退出，则容器的状态处于Exit，而不是后台运行。如果想让容器一直运行，而不是停止，可以使用快捷键 ctrl+p ctrl+q 退出，此时容器的状态为Up。

除了这两个参数之外，run命令还有很多其他参数。其中比较有用的是-d后台运行：

```text
[root@xxx ~]# docker run centos:latest /bin/bash -c "while true; do echo hello; sleep 1; done"
[root@xxx ~]# docker run -d centos:latest /bin/bash -c "while true; do echo hello; sleep 1; done"
```

这里第二条命令使用了-d参数，使这个容器处于后台运行的状态，不会对当前终端产生任何输出，所有的stdout都输出到log，可以使用docker logs container_name/container_id查看。

启动、停止、重启容器命令：

```text
[root@xxx ~]# docker start container_name/container_id
[root@xxx ~]# docker stop container_name/container_id
[root@xxx ~]# docker restart container_name/container_id
```

后台启动一个容器后，如果想进入到这个容器，可以使用attach命令：

```text
[root@xxx ~]# docker attach container_name/container_id
```

删除容器的命令前边已经提到过了：

```text
[root@xxx ~]# docker rm container_name/container_id

# 删除所有镜像（强制）
docker rmi -f $(docker images -q)
```

进入容器内部（在已有容器内部运行shell）：

```
docker exec -it id bash
```

新建docker组，并将新建用户添加到docker组中。

```
#创建docker组
sudo groupadd docker
#将您的用户添加到该docker组
sudo usermod -aG docker $USER
#激活对组的更改
newgrp docker
```

保存和加载镜像：

```
# 将 python:3 镜像导出
docker save -o python_3.tar python:3
# 加载
docker load -i python_3.tar
# 或者
docker load < python_3.tar
```

```

docker save -o nvidia_cuda_11.0-base.tar nvidia/cuda:11.0-base

docker save -o kube-apiserver_v1.21.1.tar registry.aliyuncs.com/google_containers/kube-apiserver:v1.21.1


# 批量导出
docker save -o kubeadm_init_v1.20.0.tar registry.aliyuncs.com/google_containers/kube-apiserver:v1.20.0 registry.aliyuncs.com/google_containers/kube-controller-manager:v1.20.0 registry.aliyuncs.com/google_containers/kube-scheduler:v1.20.0 registry.aliyuncs.com/google_containers/kube-proxy:v1.20.0 registry.aliyuncs.com/google_containers/pause:3.2 registry.aliyuncs.com/google_containers/etcd:3.4.13-0 registry.aliyuncs.com/google_containers/coredns:1.7.0


```

```
docker load -i $RESOURCE_FILE/nvidia_cuda_11.0-base

docker load -i $RESOURCE_FILE/kube-apiserver_v1.21.1.tar
docker load -i $RESOURCE_FILE/kube-controller-manager_v1.21.1.tar
docker load -i $RESOURCE_FILE/kube-scheduler_v1.21.1.tar
docker load -i $RESOURCE_FILE/kube-proxy_v1.21.1.tar
docker load -i $RESOURCE_FILE/pause_3.4.1.tar
docker load -i $RESOURCE_FILE/etcd_3.4.13-0.tar
docker load -i $RESOURCE_FILE/coredns_v1.8.0.tar

```

```
#!/bin/bash
#load当前目录下所有*tar.gz镜像文件
path=$1
files=$(ls $path)
for filename in $files
do
 if [[ $filename == *.tar ]];then
 	docker load < ${filename}
 fi
done
```

修改tag:

```
docker tag coredns/coredns:latest registry.aliyuncs.com/google_containers/coredns/coredns:v1.8.0

```



脚本批量导入上传

pull

```
# vim pull_images.sh 
#!/bin/bash
G=`tput setaf 2`
C=`tput setaf 6`
Y=`tput setaf 3`
Q=`tput sgr0`

echo -e "${C}\n\n镜像下载脚本:${Q}"
echo -e "${C}pull_images.sh将读取images.txt中的镜像，拉取并保存到images.tar.gz中\n\n${Q}"

# 清理本地已有镜像
# echo "${C}start: 清理镜像${Q}"
# for rm_image in $(cat images.txt)
# do 
#  docker rmi $aliNexus$rm_image
# done
# echo -e "${C}end: 清理完成\n\n${Q}"

# 创建文件夹
mkdir images

# pull
echo "${C}start: 开始拉取镜像...${Q}"
for pull_image in $(cat images.txt)
do    
  echo "${Y}    开始拉取$pull_image...${Q}"
  fileName=${pull_image//:/_}
  docker pull $pull_image
done
echo "${C}end: 镜像拉取完成...${Q}"

# save镜像
IMAGES_LIST=($(docker images | sed '1d' | awk '{print $1}'))
IMAGES_NM_LIST=($(docker images | sed  '1d' | awk '{print $1"-"$2}'| awk -F/ '{print $NF}'))
IMAGES_NUM=${#IMAGES_LIST[*]}
echo "镜像列表....."
docker images
# docker images | sed '1d' | awk '{print $1}'
for((i=0;i<$IMAGES_NUM;i++))
do
  echo "正在save ${IMAGES_LIST[$i]} image..."
  docker save "${IMAGES_LIST[$i]}" -o ./images/"${IMAGES_NM_LIST[$i]}".tar.gz
done
ls images
echo -e "${C}end: 保存完成\n\n${Q}"

# 打包镜像
#tag_date=$(date "+%Y%m%d%H%M")
echo "${C}start: 打包镜像：images.tar.gz${Q}"
tar -czvf images.tar.gz images
echo -e "${C}end: 打包完成\n\n${Q}"

# 上传镜像包到OSS，如果没有oss的可以自行更换自己内网可以访问到的其他仓库
# echo "${C}start: 将镜像包images.tar.gz上传到OSS${Q}"
# ossutil64 cp images.tar.gz oss://aicloud-deploy/kubeflow-images/
# echo -e "${C}end: 镜像包上传完成\n\n${Q}"
# 清理镜像
read -p "${C}是否清理本地镜像(Y/N,默认N)?:${Q}" is_clean
 if [ -z "${is_clean}" ];then
   is_clean="N"
 fi
 if [ "${is_clean}" == "Y" ];then
   rm -rf images/*
   rm -rf images.tar.gz
   for clean_image in $(cat images.txt)
   do    
     docker rmi $clean_image
   done
   echo -e "${C}清理结束~\n\n${Q}"
 fi

echo -e "${C}执行结束~\n\n${Q}"
```



拉取所以版本

```
docker pull -a <image_name>
```



```
#!/bin/bash

# gcr.io/kubebuilder/kube-rbac-proxy:v0.4.0 修改为 :kube-rbac-proxy_v0.4.0

G=`tput setaf 2`
C=`tput setaf 6`
Y=`tput setaf 3`
Q=`tput sgr0`
COUNT=1

echo -e "${C}\n\n镜像上传脚本:${Q}"

# 获取内网镜像仓库地址
nexusAddr="registry.cn-beijing.aliyuncs.com/ecs-kube/kubeflow"
echo "nexusAddr 为：  $nexusAddr"

#push镜像
echo "${C}start: 开始push镜像...${Q}"
# IMAGES_LIST=($(docker images | sed '1d' | awk '{print $1":"$2}'))
for origin_image in $(docker images | sed '1d' | awk '{print $1":"$2}')
do
  #origin_image: gcr.io/kubebuilder/kube-rbac-proxy:v0.4.0
  echo -e "${Y}    开始推送$origin_image ${Q}"
  # 镜像名: kube-rbac-proxy:v0.4.0
  push_image=($(echo $origin_image | awk -F "/" '{print $NF}'))
  # 镜像名前缀：kube-rbac-proxy
  push_image_pre=($(echo $push_image |awk -F ":" '{print $1}'))
  # 镜像名后缀：v0.4.0
  push_image_suf=($(echo $push_image |awk -F ":" '{print $NF}'))
  # 上传到阿里云的镜像名(也就是要修改成版本号):kube-rbac-proxy_v0.4.0
  push_image=${push_image_pre}"_"${push_image_suf}
  #echo "push images:  $push_image"
  #echo -e "给镜像$origin_image打tag，为：   $nexusAddr:$push_image"
  docker tag $origin_image $nexusAddr:$push_image
  #echo -e "${Y}    push $nexusAddr:$push_image"
  docker push $nexusAddr:$push_image
  echo "第${COUNT}个镜像：$nexusAddr:$push_image 推送完成..."
  COUNT=`expr $COUNT + 1`
done

echo -e "${C}end: 全部镜像推送完成\n\n${Q}"

```

```
# push_2

#!/bin/bash
G=`tput setaf 2`
C=`tput setaf 6`
Y=`tput setaf 3`
Q=`tput sgr0`
COUNT=1

echo -e "${C}\n\n镜像上传脚本:${Q}"

# 获取内网镜像仓库地址
nexusAddr="registry.cn-beijing.aliyuncs.com/ecs-kube/kubeflow"
echo "nexusAddr 为：  $nexusAddr"

#push镜像
echo "${C}start: 开始push镜像...${Q}"
# IMAGES_LIST=($(docker images | sed '1d' | awk '{print $1":"$2}'))
for origin_image in $(docker images | sed '1d' | awk '{print $1":"$2}')
do
  echo -e "${Y}    开始推送$origin_image ${Q}"
  push_image=($(echo $origin_image | awk -F "/" '{print $NF}'))
  push_image_pre=($(echo $push_image |awk -F ":" '{print $1}'))
  push_image_suf=($(echo $push_image |awk -F ":" '{print $NF}'))
  push_image=${push_image_pre}"_"${push_image_suf}
  #echo "push images:  $push_image"
  #echo -e "给镜像$origin_image打tag，为：   $nexusAddr:$push_image"
  docker tag $origin_image $nexusAddr:$push_image
  #echo -e "${Y}    push $nexusAddr:$push_image"
  docker push $nexusAddr:$push_image
  echo "第${COUNT}个镜像：$nexusAddr:$push_image 推送完成..."
  COUNT=`expr $COUNT + 1`
done

echo -e "${C}end: 全部镜像推送完成\n\n${Q}"

```



