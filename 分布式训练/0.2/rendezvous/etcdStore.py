import datetime
import json
import logging
import sys
import threading
import random
import time
from base64 import b64decode, b64encode
from typing import Optional

import etcd

_log_fmt = logging.Formatter("%(levelname)s %(asctime)s %(message)s")
_log_handler = logging.StreamHandler(sys.stderr)
_log_handler.setFormatter(_log_fmt)

log = logging.getLogger(__name__)
log.propagate = False
log.setLevel(logging.INFO)
log.addHandler(_log_handler)


CONST_RUNID_SUBROOT_TTL = 7200  # 2 hours

def cas_delay():
    time.sleep(random.uniform(0, 0.1))

def setup_etcd_store(self, rdzv_version):
    store_path = self.get_path(f"/rdzv/v_{rdzv_version}/kv")
    self.create_path_if_not_exists(store_path)
    return EtcdStore(etcd_client=self.client, etcd_store_prefix=store_path)


class EtcdRendezvous(object):
    """
    一个使用`etcd`作为后端存储的rendezvous实现。
    """

    def __init__(
        self,
        endpoints,
        prefix,
        run_id,
    ):
        self._endpoints = endpoints
        self._prefix = prefix
        self._run_id = run_id

        # 用于清除TTL刷新线程(用于临时keys)
        # For cleaning up TTL refresher threads (for ephemeral keys)
        self._lease_run_id_stop = None
        self._lease_this_rank_stop = None

        if not self._prefix.endswith("/"):
            self._prefix += "/"

        self.client = etcd.Client(host=endpoints, allow_reconnect=True)
        log.info("Etcd machines: " + str(self.client.machines))

        # 如果不存在，则设置一个永久前缀dir
        if self._prefix != "/":
            self.create_path_if_not_exists(self._prefix)

        # lease:租约，是ETCD的重要特性，用于实现key定时删除功能。与Redis的定时删除功能基本一致。
        # 租用特定于此job实例的“sub-root”节点(run_id)
        # Lease a "sub-root" node specific to this job instance (run_id)
        self.create_path_if_not_exists(self.get_path(""), ttl=CONST_RUNID_SUBROOT_TTL)
        self._lease_run_id_stop = self.setup_lease_renewal(
            self.get_path(""), ttl=CONST_RUNID_SUBROOT_TTL
        )

        # 所有rendezvous工作的子目录
        self.create_path_if_not_exists(self.get_path("/rdzv"))

        # Create a rendezvous version counter, if doesn't exist
        try:
            self.client.write(
                key=self.get_path("/rdzv/version_counter"), value="0", prevExist=False
            )
        except etcd.EtcdAlreadyExist:
            pass

    def __del__(self):
        if self._lease_run_id_stop is not None:
            self._lease_run_id_stop.set()

        if self._lease_this_rank_stop is not None:
            self._lease_this_rank_stop.set()

    def get_path(self, path):
        if not path.startswith("/"):
            path = "/" + path

        return "{prefix}run_{run_id}{path}".format(
            prefix=self._prefix, run_id=self._run_id, path=path
        )

    def get_rdzv_state(self):
        active_version = self.client.get(key=self.get_path("/rdzv/active_version"))
        return active_version, json.loads(active_version.value)


    def create_path_if_not_exists(self, full_path, ttl=None):
        try:
            self.client.write(
                key=full_path, value=None, dir=True, prevExist=False, ttl=ttl
            )
        except etcd.EtcdAlreadyExist:
            pass

    def setup_lease_renewal(self, full_path, ttl):
        # 注意:要使临时密钥TTL更新(~lease)正确工作，请确保您没有调用任何没有释放Python的GIL的长阻塞方法!
        # 这方面的一个例子是调用一个阻塞/长时间运行的pybind11扩展函数，但没有执行GIL的作用域发布。
        # NOTE: For ephemeral key TTL renewal (~lease) to work correctly,
        # make sure you don't call any long-blocking methods that do not
        # release the Python's GIL! An example of this is calling a pybind11
        # extension function that is blocking / long-running, but is not
        # doing a scoped release of the GIL.
        def lease_worker(client, path, ttl, stop_event):
            while True:
                try:
                    client.refresh(path, ttl=ttl)
                except etcd.EtcdKeyNotFound:
                    break

                if stop_event.wait(timeout=ttl / 2):
                    break

        lease_stop_event = threading.Event()
        lease_thread = threading.Thread(
            target=lease_worker, args=(self.client, full_path, ttl, lease_stop_event)
        )

        lease_thread.daemon = True
        lease_thread.start()

        return lease_stop_event

    def setup_kv_store(self, rdzv_version):
        store_path = self.get_path(f"/rdzv/v_{rdzv_version}/kv")
        self.create_path_if_not_exists(store_path)
        return EtcdStore(etcd_client=self.client, etcd_store_prefix=store_path)


class EtcdStore():
    """
    通过在rdzv etcd实例上piggybacking（捎带）来实现一个c10存储接口。这是由“EtcdRendezvous”返回的存储对象
    Implements a c10 Store interface by piggybacking on the rendezvous etcd
    instance. This is the store object returned by ``EtcdRendezvous``
    """

    def __init__(
        self,
        etcd_client,
        etcd_store_prefix,
        timeout: Optional[datetime.timedelta] = None,
    ):

        self.client = etcd_client
        self.prefix = etcd_store_prefix
        self.timeout = (
            timeout if timeout is not None else datetime.timedelta(seconds=300)
        )
        if not self.prefix.endswith("/"):
            self.prefix += "/"

    def set(self, key, value, ttl_val=None):
        """
        在 EtcdStore 中写入一个键/值对。键和值可以是 str 或者是 bytes。
        """
        if ttl_val is None:
            self.client.set(key=self.prefix + self._encode(key), value=self._encode(value))
        else:
            self.client.set(key=self.prefix + self._encode(key), value=self._encode(value), ttl=ttl_val)

    def get(self, key) -> bytes:
        """
        通过key获取一个value，如果key没有立即出现，则在最长的超时期间或直到key被发布时进行阻塞等待。
        Returns:
            value ``(bytes)``
        Raises:
            LookupError - If key still not published after timeout
        """
        b64_key = self.prefix + self._encode(key)
        kvs = self._try_wait_get([b64_key])

        if kvs is None:
            raise LookupError(f"Key {key} not found in EtcdStore")

        return self._decode(kvs[b64_key])

    def delete(self, key):
        """
            删除键
        """
        self.client.delete(key=self.prefix + self._encode(key))

    def refresh(self, key, ttl_val):
        """
            刷新键的存活时间
        """
        try:
            self.client.refresh(key=self.prefix + self._encode(key), ttl=ttl_val)
        except etcd.EtcdKeyNotFound:
            return


    def wait(self, keys, override_timeout: Optional[datetime.timedelta] = None):
        """
        等待所有键发布，直到超时。
        """
        b64_keys = [self.prefix + self._encode(key) for key in keys]
        kvs = self._try_wait_get(b64_keys, override_timeout)
        if kvs is None:
            raise LookupError("Timeout while waiting for keys in EtcdStore")
        # No return value on success

    # 使用base64编码键/值数据，这样就可以在EtcdStore中存储任意的二进制数据。输入可以是'str'或'bytes'。
    def _encode(self, value) -> str:
        if type(value) == bytes:
            return b64encode(value).decode()
        elif type(value) == str:
            return b64encode(value.encode()).decode()
        raise ValueError("Value must be of type str or bytes")

    # 解码一个base64字符串(类型为str或bytes)。返回类型是bytes，这样使用Store接口更方便。
    def _decode(self, value) -> bytes:
        if type(value) == bytes:
            return b64decode(value)
        elif type(value) == str:
            return b64decode(value.encode())
        raise ValueError("Value must be of type str or bytes")

    # 一次获取所有(base64编码的)etcd键，或者等待所有键被发布或发生超时。
    # 如果成功，将返回一个字典{etcd key -> etcd value}。超时返回None。
    def _try_wait_get(self, b64_keys, override_timeout=None):
        timeout = self.timeout if override_timeout is None else override_timeout
        deadline = time.time() + timeout.total_seconds()

        while True:
            # Read whole directory (of keys), filter only the ones waited for
            all_nodes = self.client.get(key=self.prefix)
            req_nodes = {
                node.key: node.value
                for node in all_nodes.children
                if node.key in b64_keys
            }

            if len(req_nodes) == len(b64_keys):
                # All keys are available
                return req_nodes

            watch_timeout = deadline - time.time()
            if watch_timeout <= 0:
                return None

            try:
                self.client.watch(
                    key=self.prefix,
                    recursive=True,
                    timeout=watch_timeout,
                    index=all_nodes.etcd_index + 1,
                )
            except etcd.EtcdWatchTimedOut:
                if time.time() >= deadline:
                    return None
                else:
                    continue
            except etcd.EtcdEventIndexCleared:
                continue

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="[%(levelname)s] %(asctime)s %(module)s: %(message)s"
    )
    etcd_endpoints = "127.0.0.1:2379"
    etcd_prefix = "/torchelastic/p2p"
    run_id = 0
    etcd_rdzv = EtcdRendezvous(
        endpoints=etcd_endpoints,
        prefix=etcd_prefix,
        run_id=run_id,
    )
    rdzv_version = 11
    store = etcd_rdzv.setup_kv_store(rdzv_version)