# 安装etcd

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



192.168.64.237

192.168.64.233

192.168.64.234



# 使用etcd

用户通常通过设置或者获取键的值来和 etcd 交互。这一节描述如何使用 etcdctl 来操作， etcdctl 是一个和 etcd 服务器交互的命令行工具。这里描述的概念也适用于 gRPC API 或者客户端类库 API。

默认，为了向后兼容 etcdctl 使用 v2 API 来和 etcd 服务器通讯。为了让 etcdctl 使用 v3 API 来和etcd通讯，API 版本必须通过环境变量 `ETCDCTL_API` 设置为版本3。



```
export ETCDCTL_API=3
```

# 查找版本

在查找适当命令以便对 etcd 执行各种操作时，etcdctl 版本和 Server API 版本很有用。

以下是查找版本的命令：



```
$ etcdctl version
etcdctl version: 3.1.0-alpha.0+git
API version: 3.1
```

# 写入键

应用通过写入键来储存键到 etcd 中。每个存储的键通过 Raft 协议复制到 etcd 集群的所有成员来实现一致性和可靠性。

这是设置键 `foo` 的值为 `bar` 的命令:



```
$ etcdctl put foo bar
OK
```

而且可以通过附加租约的方式为键设置特定时间间隔。

这是将键 foo1 的值设置为 bar1 并维持 10s 的命令：



```
$ etcdctl put foo1 bar1 --lease=1234abcd
OK
```

注意: 上面命令中的租约id `1234abcd` 是创建租约时返回的. 这个 id 随即被附加到键。

# 读取键

应用可以从 etcd 集群中读取键的值。查询可以读取单个 key，或者某个范围的键。

假设 etcd 集群存储有下面的键：



```
foo = bar
foo1 = bar1
foo2 = bar2
foo3 = bar3
```

这是读取键 `foo` 的值的命令：



```
$ etcdctl get foo
foo
bar
```

这是以16进制格式读取键的值的命令：



```
$ etcdctl get foo --hex
\x66\x6f\x6f          # 键
\x62\x61\x72          # 值
```

这是只读取键 foo 的值的命令：



```
$ etcdctl get foo --print-value-only
bar
```

这是范围覆盖从 `foo` to `foo3` 的键的命令：



```
$ etcdctl get foo foo3
foo
bar
foo1
bar1
foo2
bar2
```

注意 `foo3` 不在范围之内，因为范围是半开区间 [foo, foo3), 不包含 `foo3`.

这是范围覆盖以 `foo` 为前缀的所有键的命令：



```
$ etcdctl get --prefix foo
foo
bar
foo1
bar1
foo2
bar2
foo3
bar3
```

这是范围覆盖以 `foo` 为前缀的所有键的命令，结果数量限制为2：



```
$ etcdctl get --prefix --limit=2 foo
foo
bar
foo1
bar1
```

# 读取键过往版本的值

应用可能想读取键的被替代的值。例如，应用可能想通过访问键的过往版本来回滚到旧的配置。或者，应用可能想通过多个请求来得到一个覆盖多个键的统一视图，而这些请求可以通过访问键历史记录而来。因为 etcd 集群上键值存储的每个修改都会增加 etcd 集群的全局修订版本，应用可以通过提供旧有的 etcd 修改版本来读取被替代的键。

假设 etcd 集群已经有下列键：



```
foo = bar         # revision = 2
foo1 = bar1       # revision = 3
foo = bar_new     # revision = 4
foo1 = bar1_new   # revision = 5
```

这里是访问键的过往版本的例子：



```
$ etcdctl get --prefix foo # 访问键的最新版本foobar_newfoo1bar1_new
$ etcdctl get --prefix --rev=4 foo # 访问修订版本为 4 时的键的版本foobar_newfoo1bar1
$ etcdctl get --prefix --rev=3 foo # 访问修订版本为 3 时的键的版本foobarfoo1bar1
$ etcdctl get --prefix --rev=2 foo # 访问修订版本为 2 时的键的版本foobar
$ etcdctl get --prefix --rev=1 foo # 访问修订版本为 1 时的键的版本
```

# 读取大于等于指定键的 byte 值的键

应用可能想读取大于等于指定键 的 byte 值的键.

假设 etcd 集群已经有下列键：



```
a = 123
b = 456
z = 789
```

这是读取大于等于键 `b` 的 byte 值的键的命令：



```
$ etcdctl get --from-key b
b
456
z
789
```

# 删除键

应用可以从 etcd 集群中删除一个键或者特定范围的键。

假设 etcd 集群已经有下列键：



```
foo = bar
foo1 = bar1
foo3 = bar3
zoo = val
zoo1 = val1
zoo2 = val2
a = 123
b = 456
z = 789
```

这是删除键 `foo` 的命令：



```
$ etcdctl del foo
1 # 删除了一个键
```

这是删除从 `foo` to `foo9` 范围的键的命令：



```
$ etcdctl del foo foo9
2 # 删除了两个键
```

这是删除键 zoo 并返回被删除的键值对的命令：



```
$ etcdctl del --prev-kv zoo
1   # 一个键被删除
zoo # 被删除的键
val # 被删除的键的值
```

这是删除前缀为 `zoo` 的键的命令：



```
$ etcdctl del --prefix zoo
2 # 删除了两个键
```

这是删除大于等于键 b 的 byte 值的键的命令：



```
$ etcdctl del --from-key b
2 # 删除了两个键
```

# 观察键的变化

应用可以观察一个键或者范围内的键来监控任何更新。

这是在键 `foo` 上进行观察的命令：



```
$ etcdctl watch foo
# 在另外一个终端: etcdctl put foo bar
foo
bar
```

这是以16进制格式在键 `foo` 上进行观察的命令：



```
$ etcdctl watch foo --hex
# 在另外一个终端: etcdctl put foo bar
PUT
\x66\x6f\x6f          # 键
\x62\x61\x72          # 值
```

这是观察从 `foo` to `foo9` 范围内键的命令：



```
$ etcdctl watch foo foo9
# 在另外一个终端: etcdctl put foo bar
PUT
foo
bar
# 在另外一个终端: etcdctl put foo1 bar1
PUT
foo1
bar1
```

这是观察前缀为 `foo` 的键的命令:



```
$ etcdctl watch --prefix foo
# 在另外一个终端: etcdctl put foo bar
PUT
foo
bar
# 在另外一个终端: etcdctl put fooz1 barz1
PUT
fooz1
barz1
```

这是观察多个键 `foo` 和 `zoo` 的命令:



```
$ etcdctl watch -i
$ watch foo
$ watch zoo
# 在另外一个终端: etcdctl put foo bar
PUT
foo
bar
# 在另外一个终端: etcdctl put zoo val
PUT
zoo
val
```

# 观察 key 的历史改动

应用可能想观察 etcd 中键的历史改动。例如，应用想接收到某个键的所有修改。如果应用一直连接到 etcd，那么 `watch` 就足够好了。但是，如果应用或者 etcd 出错，改动可能发生在出错期间，这样应用就没能实时接收到这个更新。为了保证更新被交付，应用必须能够观察到键的历史变动。为了做到这点，应用可以在观察时指定一个历史修订版本，就像读取键的过往版本一样。

假设我们完成了下列操作序列：



```
$ etcdctl put foo bar         # revision = 2
OK
$ etcdctl put foo1 bar1       # revision = 3
OK
$ etcdctl put foo bar_new     # revision = 4
OK
$ etcdctl put foo1 bar1_new   # revision = 5
OK
```

这是观察历史改动的例子：



```
# 从修订版本 2 开始观察键 `foo` 的改动
$ etcdctl watch --rev=2 foo
PUT
foo
bar
PUT
foo
bar_new
```



```
# 从修订版本 3 开始观察键 `foo` 的改动
$ etcdctl watch --rev=3 foo
PUT
foo
bar_new
```

这是从上一次历史修改开始观察的例子(注：貌似原文有误，这里应该是观察变更时同时返回修改之前的值)：



```
# 在键 `foo` 上观察变更并返回被修改的值和上个修订版本的值
$ etcdctl watch --prev-kv foo
# 在另外一个终端: etcdctl put foo bar_latest
PUT
foo         # 键
bar_new     # 在修改前键foo的上一个值
foo         # 键
bar_latest  # 修改后键foo的值
```

# 压缩修订版本

如我们提到的，etcd 保存修订版本以便应用可以读取键的过往版本。但是，为了避免积累无限数量的历史数据，压缩过往的修订版本就变得很重要。压缩之后，etcd 删除历史修订版本，释放资源来提供未来使用。所有修订版本在压缩修订版本之前的被替代的数据将不可访问。

这是压缩修订版本的命令：



```
$ etcdctl compact 5compacted revision 5
# 在压缩修订版本之前的任何修订版本都不可访问$ etcdctl get --rev=4 fooError:  rpc error: code = 11 desc = etcdserver: mvcc: required revision has been compacted
```

注意： etcd 服务器的当前修订版本可以在任何键(存在或者不存在)以json格式使用get命令来找到。下面展示的例子中 mykey 是在 etcd 服务器中不存在的：



```
$ etcdctl get mykey -w=json
{"header":{"cluster_id":14841639068965178418,"member_id":10276657743932975437,"revision":15,"raft_term":4}}
```

# 授予租约

应用可以为 etcd 集群里面的键授予租约。当键被附加到租约时，它的存活时间被绑定到租约的存活时间，而租约的存活时间相应的被 `time-to-live` (TTL)管理。在租约授予时每个租约的最小TTL值由应用指定。租约的实际 TTL 值是不低于最小 TTL，由 etcd 集群选择。一旦租约的 TTL 到期，租约就过期并且所有附带的键都将被删除。

这是授予租约的命令：



```
# 授予租约，TTL为10秒$ etcdctl lease grant 10lease 32695410dcc0ca06 granted with TTL(10s)
# 附加键 foo 到租约32695410dcc0ca06$ etcdctl put --lease=32695410dcc0ca06 foo barOK
```

# 撤销租约

应用通过租约 id 可以撤销租约。撤销租约将删除所有它附带的 key。

假设我们完成了下列的操作：



```
$ etcdctl lease grant 10
lease 32695410dcc0ca06 granted with TTL(10s)
$ etcdctl put --lease=32695410dcc0ca06 foo bar
OK
```

这是撤销同一个租约的命令：



```
$ etcdctl lease revoke 32695410dcc0ca06lease 32695410dcc0ca06 revoked
$ etcdctl get foo# 空应答，因为租约撤销导致foo被删除
```

# 维持租约

应用可以通过刷新键的 TTL 来维持租约，以便租约不过期。

假设我们完成了下列操作：



```
$ etcdctl lease grant 10
lease 32695410dcc0ca06 granted with TTL(10s)
```

这是维持同一个租约的命令：



```
$ etcdctl lease keep-alive 32695410dcc0ca06
lease 32695410dcc0ca06 keepalived with TTL(10)
lease 32695410dcc0ca06 keepalived with TTL(10)
lease 32695410dcc0ca06 keepalived with TTL(10)
...
```

# 获取租约信息

应用程序可能想知道租约信息，以便可以更新或检查租约是否仍然存在或已过期。应用程序也可能想知道有那些键附加到了特定租约。

假设我们完成了下列操作序列：



```
# 授予租约，TTL为500秒$ etcdctl lease grant 500lease 694d5765fc71500b granted with TTL(500s)
# 将键 zoo1 附加到租约 694d5765fc71500b$ etcdctl put zoo1 val1 --lease=694d5765fc71500bOK
# 将键 zoo2 附加到租约 694d5765fc71500b$ etcdctl put zoo2 val2 --lease=694d5765fc71500bOK
```

这是获取租约信息的命令：



```
$ etcdctl lease timetolive 694d5765fc71500b
lease 694d5765fc71500b granted with TTL(500s), remaining(258s)
```

这是获取租约信息和租约附带的键的命令：



```
$ etcdctl lease timetolive --keys 694d5765fc71500blease 694d5765fc71500b granted with TTL(500s), remaining(132s), attached keys([zoo2 zoo1])
# 如果租约已经过期或者不存在，它将给出下面的应答:Error:  etcdserver: requested lease not found
```