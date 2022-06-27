## vim命令

1. 移至文件首行 gg

2. 移至文件尾行 shift + g

3. 移至文件任一行 num + gg

4. 移至行首 home

   移至行尾 end

5. dG 清空后续的文本

## Shell脚本

1. 将dos脚本改为unix

   ```
   # 打开文件
   vi test.sh
   
   # 查看原格式
   :set ff
   fileformat=dos
   
   # 修改编码格式
   :set ff=unix
   
   # 保存退出
   :wq
   
   ```

   

   

2. 判断软件包是否已经安装

   ```
   if apt list installed nvidia-docker2 >/dev/null 2>&1; then
       echo "==============nvidia docker installed==============="
   else
       echo "==============no nvidia docker==============="
   fi
   ```

3. shell 中执行远程主机的脚本，并使用本地的变量

   ```
   # 拷贝安装包
   # scp -r ../${INSTALLATION_VER}/ ${SSH_USER}@${WORKER_NODE}:~/
   ssh ${SSH_USER}@${WORKER_NODE} << EXITSSH
   echo "shh到worker节点，进行worker初始化"
   cd ${INSTALLATION_VER}
   pwd
   ls
   echo "=============添加worker节点==========="
   echo "===========${INSTALLATION_VER}=========="
   exit
   EXITSSH
   echo done!
   ```



## 其他

### tar 压缩解压缩

1、*.tar 用 tar –xvf 解压

2、*.gz 用 gzip -d或者gunzip 解压

3、*.tar.gz和*.tgz 用 tar –xzvf 解压

```
tar -cvf file.tar file/
tar -xvf file.tar

-c: 建立压缩档案
-x：解压
-v：显示所有过程
-f: 使用档案名字，切记，这个参数是最后一个参数，后面只能接档案名.参数-f是必须的
-z：有gzip属性的
```

/mnt/dushuai/kubeDeploy-ubuntu/kubeDeploy-ubuntu.sh

/mnt/dushuai/kubeDeploy-centos/kubeDeploy-centos.sh

/mnt/dushuai/kubeDeploy-ubuntu/kubeDeploy-ubuntu-v1.18.0.tar

/mnt/dushuai/kubeDeploy-ubuntu/kubeDeploy-ubuntu-v1.21.1.tar

/mnt/dushuai/kubeDeploy-centos/kubeDeploy-centos-v1.18.0.tar

/mnt/dushuai/kubeDeploy-centos/kubeDeploy-centos-v1.21.1.tar

### 查看文件大小

du -hs file.tar 查看文件大小





### 免密登录

本地客户端生成公私钥：（一路回车默认即可）

```bash
ssh-keygen
```

上面这个命令会在用户目录.ssh文件夹下创建公私钥

1. id_rsa （私钥）
2. id_rsa.pub (公钥)

把id_rsa.pub (公钥)中的内容写到服务器上的ssh目录下的authorized_keys即可

 Linux_shell自动输入y或yes

```
# 一次
echo yes|[命令] # 输入 yes
echo y|[命令] # 输入 y
# 多次
yes yes|[命令] # 输入 yes
yes y|[命令] # 输入 y

# 例
yes yes|docker exec -i gitlab gitlab-rake gitlab:backup:restore 
```



### scp上传下载文件

1、从服务器下载文件

```
scp username@servername:/path/filename /tmp/local_destination
```


 2、上传本地文件到服务器

```
scp /path/local_filename username@servername:/path  
```

3、从服务器下载整个目录

```ruby
scp -r username@servername:remote_dir/ /tmp/local_dir 
```

4、上传目录到服务器

```ruby
scp  -r /tmp/local_dir username@servername:remote_dir
```





### 查看linux系统版本：

lsb_release -a

cat /etc/centos-release





### apt删除软件包：

apt-get purge / apt-get --purge remove
删除已安装包（不保留配置文件)。
如软件包a，依赖软件包b，则执行该命令会删除a，而且不保留配置文件

apt-get autoremove
删除为了满足依赖而安装的，但现在不再需要的软件包（包括已安装包），保留配置文件。

apt-get remove
删除已安装的软件包（保留配置文件），不会删除依赖软件包，且保留配置文件。



### 

### 批量终止进程：

```
# 终止GPU上的进程
for LINE in `nvidia-smi -q | grep 'Process ID' | awk -F ':' '{print $NF}'`; do
  kill -9 $LINE
done;


# 终止其他
killall -9 rtprecv

ef | grep main.py | grep -v grep | awk '{print "kill -9 "$2}'|sh
```



### 添加GOPATH

```
export GO111MODULE=off

go env -w GOPATH=/ncluster/dushuai/distributed/
```





### 添加用户：

useradd -m 用户名 然后设置密码 passwd 用户名

删除用户：userdel -r 用户名

命令行窗口下用户的相互切换：
su 用户名
说明：su是switch user的缩写，表示用户切换

新用户添加root权限

切换到root用户下，`cd root`,运行`visudo`命令,`visudo`命令是用来编辑修改`/etc/sudoers`配置文件

```shell
[root@master ~]# visudo
```

找到如下图所示，标出红线的一行

```shell
root  ALL=(ALL)    ALL1
```

给du 添加sudo权限
在“root ALL=(ALL) ALL”这一行下面，再加入一行：

```shell
du ALL=(ALL)     ALL
```



### 查看文件个数

- 统计当前目录下文件的个数（不包括目录）

```
$ ls -l | grep "^-" | wc -l
```

- 统计当前目录下文件的个数（包括子目录）

```
$ ls -lR| grep "^-" | wc -l
```

- 查看某目录下文件夹(目录)的个数（包括子目录）

```
$ ls -lR | grep "^d" | wc -l
```