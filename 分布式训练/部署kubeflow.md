```

gcr.io/kubeflow-images-public/profile-controller                  v1.0.0-ge50a8531      18c3beaa9fa7   16 months ago   68.7MB
gcr.io/kubeflow-images-public/notebook-controller                 v1.0.0-gcd65ce25      68b3c9f7213e   17 months ago   59.2MB
gcr.io/tfx-oss-public/ml_metadata_store_server                    v0.21.1               c2d797257121   17 months ago   76.2MB
gcr.io/kubeflow-images-public/katib/v1alpha3/katib-ui             v0.8.0                540d9308c9f6   17 months ago   54.4MB
gcr.io/kubeflow-images-public/katib/v1alpha3/katib-controller     v0.8.0                7c5162abd775   17 months ago   53.8MB
gcr.io/kubeflow-images-public/katib/v1alpha3/katib-db-manager     v0.8.0                32229959fe81   17 months ago   28.5MB
gcr.io/kubeflow-images-public/jupyter-web-app                     v1.0.0-g2bd63238      5bacdc6f95d2   17 months ago   587MB
gcr.io/kubeflow-images-public/centraldashboard                    v1.0.0-g3ec0de71      9f00e2a39bbc   17 months ago   191MB
gcr.io/kubeflow-images-public/tf_operator                         v1.0.0-g92389064      9b0dfe79cc7b   17 months ago   103MB
gcr.io/kubeflow-images-public/pytorch-operator                    v1.0.0-g047cf0f       5fe0aabaeb2c   17 months ago   319MB
gcr.io/kubeflow-images-public/kfam                                v1.0.0-gf3e09203      74f3ad73be69   17 months ago   58.6MB
gcr.io/kubeflow-images-public/admission-webhook                   v1.0.0-gaf96e4e3      1a428aefc8b4   17 months ago   98.5MB
gcr.io/ml-pipeline/viewer-crd-controller                          0.2.0                 12a870637495   18 months ago   114MB
gcr.io/ml-pipeline/api-server                                     0.2.0                 026c8cc0354c   18 months ago   210MB
gcr.io/ml-pipeline/frontend                                       0.2.0                 157f267077c4   18 months ago   212MB
gcr.io/ml-pipeline/visualization-server                           0.2.0                 746afe0a960e   18 months ago   2.37GB
gcr.io/ml-pipeline/scheduledworkflow                              0.2.0                 53525495c99c   18 months ago   83.1MB
gcr.io/ml-pipeline/persistenceagent                               0.2.0                 bc6fe40b644f   18 months ago   42.7MB
smartliby/activator                                               latest                ed7494dc9c8b   19 months ago   59.3MB
<none>                                                            <none>                58ea2bbc929e   19 months ago   55.4MB
<none>                                                            <none>                41790f0ff89b   19 months ago   65.9MB
<none>                                                            <none>                c2abe28efd6d   19 months ago   58.2MB
<none>                                                            <none>                0f31355fcc59   19 months ago   57MB
<none>                                                            <none>                27c5e95e9d66   19 months ago   59.8MB
gcr.io/kfserving/kfserving-controller                             0.2.2                 313dd190a523   19 months ago   115MB
gcr.io/kubeflow-images-public/metadata                            v0.1.11               3bcae1aea61c   20 months ago   4.17GB
gcr.io/ml-pipeline/envoy                                          metadata-grpc         2f8df377d0c0   21 months ago   219MB
gcr.io/spark-operator/spark-operator                              v1beta2-1.0.0-2.4.4   703198993a84   22 months ago   418MB
gcr.io/kubeflow-images-public/metadata-frontend                   v0.1.8                e54fb386ae67   2 years ago     135MB
gcr.io/kubeflow-images-public/kubernetes-sigs/application         1.0-beta              dbc28d2cd449   2 years ago     119MB
metacontroller/metacontroller                                     v0.3.0                5f0e4bc196e2   2 years ago     97.5MB
gcr.io/kubebuilder/kube-rbac-proxy                                v0.4.0                8323481d9085   2 years ago     39.6MB
gcr.io/kubeflow-images-public/ingress-setup                       latest                0cd6060b6372   2 years ago     256MB
gcr.io/google_containers/spartakus-amd64                          v1.1.0                3802a2e9f1b7   4 years ago     52.2MB

```



gcr.io/kubeflow-images-public/ingress-setup:latest

1. 安装Kustomize(可选)

   ```
   wget https://github.com/kubernetes-sigs/kustomize/releases/download/kustomize%2Fv4.1.3/kustomize_v4.1.3_linux_amd64.tar.gz
   #解压
   tar -zvxf kustomize_v4.1.3_linux_amd64.tar.gz kustomize
   
   mv kustomize /usr/local/bin/kustomize
   
   chmod u+x /usr/local/bin/kustomize
   
   kustomize version
   
   #
   
   ```

   

2. 安装pip yaml

   ```
   sudo yum -y install epel-release
   sudo yum -y install python-pip
   pip install pyyaml
   ```

   

修改替换：

1.  imagePullPolicy: Always -->  imagePullPolicy: IfNotPresent
2. policy=Always --> policy=IfNotPresent

{{ .Values.global.imagePullPolicy }}

gcr.io/kubeflow-images-public/ingress-setup:latest
imagePullPolicy: IfNotPresent



1. 实现了kubeflow1.0和kubeflow1.3在国内环境下的一键部署。
首先在海外服务器上成功安装了kubeflow1.0、kubeflow1.2、kubeflow1.3，然后对官方安装工具kfctl进行解析，发现其本质是使用使用了 kustomize 进行kubeflow的安装，分别下载kubeflow官方的manifests 1.0、1.2和1.3版本后，比较发现最新的1.3版本和前两个版本存在一些差异，因此最终打通了以下两个版本的一键部署流程：
- 对于kubeflow1.0版本，使用离线安装镜像包的方式。

在海外机器上进行了如下工作：（1）下载kfctl工具、kfctl_k8s_istio.v1.0.1.yaml文件以及manifests 1.0文件夹 （2）从manifests文件夹中找出所有安装kubeflow所需的镜像,并导出到images.txt文件 （3）编写脚本dockers pull txt文件中的所有镜像，并打tag保存到本地（大约10G），之后将manifests文件夹中所有镜像的imagePullPolicy: Always改为imagePullPolicy: IfNotPresent。（在这一过程中也尝试了将镜像push到阿里云镜像仓库，并修改manifests中所有镜像的名称，但实际操作后发现安装失败，分析发现有些镜像名是变量加后缀的方式，修改起来太过繁琐，若有后续版本升级很难实现自动化流程）（4）将修改后的manifests文件夹推送到远程仓库，将kfctl_k8s_istio.v1.0.1.yaml文件中的repos：uri: 字段修改为manifests文件的地址。

在国内机器上测试：下载保存的离线镜像包，并且docker load 所有镜像, 之后运行kfctl apply -V -f kfctl_k8s_istio.v1.0.1.yaml即可成功安装。

- 对于kubeflow1.3版本，使用远程pull阿里云镜像仓库的问题。
在海外机器上：（1）下载kustomize工具和manifests 1.3文件夹 （2）使用kustomize build 构建安装kubeflow所需的yaml文件 （3）编写脚本找出所有yaml文件中的镜像，并pull到本地，修改tag后push到阿里云镜像仓库（4）修改yaml文件中的镜像名为阿里云镜像仓库中对应的镜像名 （5）针对安装后无法启动的Pod打补丁 （6）将所有文件打包，并推送到远程仓库

在国内机器上：解压文件，运行python install.py，等待所有镜像拉取完成，即可安装成功。

2. 了解etcd源码中的raft算法，使用go语言实现了raft算法。

