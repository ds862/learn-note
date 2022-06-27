pycharm远程调试

1. 创建项目和文件夹

2. 打开tools，deployment, configration ,  点击左上角+号，SFTP，输入名称

- 配置 host:9.112.238.101     Username:caizhuo.  Password:

-  Root path选择远程服务器文件夹
- 点击上面Mappings，在Deployment path输入/

3. 选择Setting, 添加interpreter，

   点击SSH interpreter，配置host，usename，点击next

   输入password，next

   输入远程服务器的interpreter：/home/caizhuo/anaconda3/envs/torchenv/bin/python，点击ok

4. 点击project interpreter，找到刚才添加的interpreter，点击左下角小铅笔修改

   选中SSH Credentials进行配置





