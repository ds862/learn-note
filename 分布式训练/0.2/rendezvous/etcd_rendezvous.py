#!/usr/bin/env python3

# Copyright (c) Facebook, Inc. and its affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

import datetime
import json
import logging
import random
import sys
import threading
import time
from base64 import b64decode, b64encode
from typing import Optional

import etcd
from torch.distributed import Store, TCPStore, register_rendezvous_handler
from torchelastic.rendezvous import (
    RendezvousClosedException,
    RendezvousHandler,
    RendezvousNonRetryableError,
    RendezvousTimeoutException,
)


_log_fmt = logging.Formatter("%(levelname)s %(asctime)s %(message)s")
_log_handler = logging.StreamHandler(sys.stderr)
_log_handler.setFormatter(_log_fmt)

log = logging.getLogger(__name__)
log.propagate = False
log.setLevel(logging.INFO)
log.addHandler(_log_handler)

'''
重试失败异常意味着我们来不及进行理想的状态转换(例如，由于竞争条件)，现在应该从头开始重新启动。
建议使用一个小的延迟，以避免滥发Etcd。
'''
# Retryable failure exception means the we were too late to make
# a desired state transition (e.g. because of a race condition),
# and should now restart from the beginning.
# A small delay is recommended to avoid spamming Etcd.
class EtcdRendezvousRetryableFailure(Exception):
    pass

# 类似于失败时重试，不同的是可以立即重试，即不需要“安全延迟”。
# Similar to retryable failure, but the new state we observed suggests we
# can re-try immediately, i.e. without a need for "safety delay".
class EtcdRendezvousRetryImmediately(Exception):
    pass


# rendezvous barrier的默认总超时时间
# Default overall timeout for rendezvous barrier.
CONST_DEFAULT_OVERALL_TIMEOUT = 600

# 到达num_min_workers后的额外等待时间，因为rensezvous是弹性的(min != max)
# Additional waiting amount after reaching num_min_workers,
# for the case rendezvous is elastic (min != max):
CONST_DEFAULT_LAST_CALL_TIMEOUT = 30

# Etcd Rendezvous内部使用的各种常量
# Various constants used internally in EtcdRendezvous
CONST_ETCD_SETUP_TTL = 5
CONST_ETCD_FROZEN_TTL = 10
CONST_ETCD_JOINABLE_EPHEMERAL_TTL = 10

# worker的keep-alive键的临时节点TTL
# Ephemeral node TTL for worker's keep-alive key:
CONST_WORKER_KEEPALIVE_TTL = 10

'''
临时run_id指定目录的TTL。特定run_id(job实例)的所有rendezvous状态数据都包含在目录中。
它的唯一作用是清理以前运行的rendezvous数据(对于etcd服务器是持久化的情况)，
并且对校正没有影响，但是应该大于worker进程预期存活的任何timeout
'''
# TTL for the ephemeral run_id-specific directory. All rendezvous state data
# for a specific run_id (job instance) is contained within directory.
# Its only role is to clean-up rendezvous data from old runs (for the case when
# etcd server is persistent), and has no affect on correctnes, but should be
# larger than any timeouts that a worker process is expected to survive:
CONST_RUNID_SUBROOT_TTL = 7200  # 2 hours

# 小随机量的延迟(睡眠)以减少CAS故障。这不会影响正确性，但会减少对etcd服务器的请求。
# Delay (sleep) for a small random amount to reduce CAS failures.
# This does not affect correctness, but will reduce requests to etcd server.
def cas_delay():
    time.sleep(random.uniform(0, 0.1))


class EtcdRendezvousHandler(RendezvousHandler):
    """
      实现了一个python类:“torchelastic.rendezvous.RendezvousHandler`的接口，该接口
      由 :py:class: torchelastic.rendezvous.etcd_rendezvous.EtcdRendezvous支持。
    Implements a :py:class:`torchelastic.rendezvous.RendezvousHandler`
    interface backed by
    :py:class:`torchelastic.rendezvous.etcd_rendezvous.EtcdRendezvous`.

      Torchelastic使用一个URL来配置要使用的rendezvous类型，并将特定于实现的配置传递给rendezvous模块。
      基本的etcd rdzv的配置URL如下所示：
    Torchelastic uses a URL to configure the type of rendezvous to use and
    to pass implementation specific configurations to the rendezvous module.
    The basic etcd rendezvous configuration URL looks like the following
    ::
     etcd://<etcd_address>:<port>/<job_id>?min_workers=<min_workers>&max_workers=<max_workers> # noqa W605
     -- example --
     etcd://localhost:2379/1234?min_workers=1&max_workers=3

      上述URL解释如下：
      1. 使用在''etcd''方案中注册的rendezvous处理程序
      2. etcd 的端口是``localhost:2379``
      3. ''job_id == 1234''被用作etcd中的前缀(这允许一个节点共享一个公共的etcd服务器，只要保证''job_id''是唯一的)。
         请注意，job_id可以是任何字符串(例如，不需要是数字)，只要它是唯一的。
      4. ''min_workers=1''和'max_workers=3'指定了一个成员大小的范围——只要集群大小大于或等于''min_workers''，
         并且允许'' max_workers ''进入集群，torchelastic就会开始运行job。
    The URL above is interpreted as follows:
    1. Use the rendezvous handler that is registered with the ``etcd``
       scheme
    2. The ``etcd`` endpoint to use is ``localhost:2379``
    3. ``job_id == 1234`` is used as the prefix in etcd (this allows one to
       share a common etcd server for multiple jobs so long as the
       ``job_ids`` are guaranteed to be unique). Note that the job id can be
       any string (e.g. does not need to be a number) as long as it is
       unique.
    4. ``min_workers=1`` and ``max_workers=3`` specifies a range for
       membership size - torchelastic starts running the job as long as the
       cluster size is greater than or equal to ``min_workers`` and admits
       up to ``max_workers`` into the cluster.

      下面是可以传递给etcd rendezvous的参数的完整列表
    Below are a full list of the parameters that can be passed to etcd
    rendezvous:

    +--------------------------------------------+--------------------------+
    | Parameter                                  | Description              |
    +============================================+==========================+
    | min_workers                                | minimum number of        |
    |                                            | workers for the          |
    |                                            | rendezvous to be valid   |
    +--------------------------------------------+--------------------------+
    | max_workers                                | maximum number of        |
    |                                            | workers to admit         |
    +--------------------------------------------+--------------------------+
    | timeout                                    | total timeout within     | 预计next_rendezvous成功的总超时时间(默认600秒)
    |                                            | which next_rendezvous is |
    |                                            | expected to succeed      |
    |                                            | (default 600s)           |
    +--------------------------------------------+--------------------------+
    | last_call_timeout                          | additional wait amount   |  达到最小worker数后的额外等待时间(最后一次调用)
    |                                            | (“last call”) after min  |  (默认为30s)
    |                                            | number of workers has    |
    |                                            | been reached (defaults   |
    |                                            | to 30s)                  |
    +--------------------------------------------+--------------------------+
    | etcd_prefix                                | path prefix (from etcd   | 路径前缀(来自etcd根目录)，
    |                                            | root), inside which all  | 所有etcd节点将在其中创建
    |                                            | etcd nodes will be       |(默认为''/torchelastic/p2p'')
    |                                            | created (defaults to     |
    |                                            | ``/torchelastic/p2p``)   |
    +--------------------------------------------+--------------------------+
    """

    def __init__(self, rdzv_impl):
        self._rdzv_impl = rdzv_impl
    def __del__(self):
        # TODO: look into using weakref here instead.
        del self._rdzv_impl

    def next_rendezvous(self):
        rdzv_version, rank, world_size = self._rdzv_impl.rendezvous_barrier()

        log.info("Creating EtcdStore as the c10d::Store implementation")
        store = self._rdzv_impl.setup_kv_store(rdzv_version)

        return store, rank, world_size

    def is_closed(self):
        try:
            _, state = self._rdzv_impl.get_rdzv_state()
            return state["status"] == "closed"
        except etcd.EtcdKeyNotFound:
            # No rendezvous state, so it cannot be closed.
            return False

    def set_closed(self):
        self._rdzv_impl.set_closed()

    def num_nodes_waiting(self):
        try:
            _, state = self._rdzv_impl.get_rdzv_state()
            if state["status"] == "final":
                return state["num_workers_waiting"]
        except etcd.EtcdKeyNotFound:
            pass
        return 0

'''
TODO: 我们可能应该处理一些额外的错误，如EtcdLeaderElectionInProgress和EtcdWatcherCleared。
这些只与多节点Etcd集成相关。一个简单的重试可以工作，但是在任何地方添加都是冗长的。
考虑将客户端调用包装为针对这些错误的自动重试?
'''
# TODO: we should probably handle a few additional errors,
# like EtcdLeaderElectionInProgress and EtcdWatcherCleared. These are
# only relevant for multi-node Etcd ensemble. A simple retry would work,
# but is verbose to add everywhere. Consider wrapping the client calls
# into auto-retry for these errors?
#
class EtcdRendezvous(object):
    """
    一个使用`etcd`作为后端存储的rendezvous实现。
    A rendezvous implementation that uses `etcd <https://etcd.io/>`__ as
    the backend store.
    """

    def __init__(
        self,
        endpoints,
        prefix,
        run_id,
        num_min_workers,
        num_max_workers,
        timeout,
        last_call_timeout,
        **kwargs,
    ):
        self._prefix = prefix
        self._run_id = run_id
        self._num_min_workers = num_min_workers
        self._num_max_workers = num_max_workers
        self._timeout = timeout
        self._last_call_timeout = last_call_timeout

        # 用于清除TTL刷新线程(用于临时keys)
        # For cleaning up TTL refresher threads (for ephemeral keys)
        self._lease_run_id_stop = None
        self._lease_this_rank_stop = None

        if not self._prefix.endswith("/"):
            self._prefix += "/"

        self.client = etcd.Client(host=endpoints, allow_reconnect=True, **kwargs)
        log.info("Etcd machines: " + str(self.client.machines))

        # 如果不存在，则设置一个永久前缀dir
        # Setup a permanent prefix dir, if didn't exist
        if self._prefix != "/":
            self.create_path_if_not_exists(self._prefix)

        # lease:租约，是ETCD的重要特性，用于实现key定时删除功能。与Redis的定时删除功能基本一致。
        # 租用特定于此job实例的“子根”节点(run_id)
        # Lease a "sub-root" node specific to this job instance (run_id)
        self.create_path_if_not_exists(self.get_path(""), ttl=CONST_RUNID_SUBROOT_TTL)
        self._lease_run_id_stop = self.setup_lease_renewal(
            self.get_path(""), ttl=CONST_RUNID_SUBROOT_TTL
        )

        # 所有rendezvous工作的子目录
        # Subdir for all rendezvous work
        self.create_path_if_not_exists(self.get_path("/rdzv"))

        # Create a rendezvous version counter, if doesn't exist
        try:
            self.client.write(
                key=self.get_path("/rdzv/version_counter"), value="0", prevExist=False
            )
        except etcd.EtcdAlreadyExist:
            pass

    def __del__(self):
        # TODO: look into using weakref here instead.
        if self._lease_run_id_stop is not None:
            self._lease_run_id_stop.set()

        if self._lease_this_rank_stop is not None:
            self._lease_this_rank_stop.set()

    def rendezvous_barrier(self):
        """
          next rendezvous的主要入口点。此方法将阻塞，直到rendezvous成功或发生超时。
        Main entry point for next rendezvous.
        This method is blocking until rendezvous succeeds or a timeout occurs.

        Returns:
             ``(rdzv_version, rank, world_size)``

        Raises:
            RendezvousTimeoutException - timeout waiting for rendezvous     // rendezvous超时
            RendezvousNonRetryableError - other persistent errors that
             render the rendezvous non-retryable                            // 其他导致rendezvous不可重试的持久错误
            RendezvousClosedException - rendezvous is or was closed while   // rendezvous在等待期间关闭了
             waiting
        """
        # rendezvous终止时间（如果在这段时间内没有完成rdzv，将引发异常）
        self._rendezvous_deadline = time.time() + self._timeout
        while True:
            # 时间大于rendezvous死亡时间，引发超时异常
            if time.time() > self._rendezvous_deadline:
                raise RendezvousTimeoutException()

            log.info("Attempting to join next rendezvous")
            try:
                # 如果之前的rendezvous存在的话，Dis-own our lease
                # Dis-own our lease in the previous rendezvous, if exists
                '''
                def confirm_membership(self, expected_version, this_rank):
                    self._lease_this_rank_stop = self.setup_lease_renewal(
                        this_lease_key, ttl=CONST_WORKER_KEEPALIVE_TTL
                    )
                '''
                if self._lease_this_rank_stop is not None:
                    self._lease_this_rank_stop.set()

                return self.init_phase()

            except EtcdRendezvousRetryImmediately:
                # 此种失败的类型表明我们可以立即重试
                # The type of failure suggests we can retry without delay
                pass

            except EtcdRendezvousRetryableFailure:
                # 此种异常需要等待一段时间的延迟
                # In case of retryable failure, wait a small delay
                # to avoid spamming etcd
                time.sleep(1)

            except RendezvousTimeoutException:
                log.info("Rendezvous timeout occured in EtcdRendezvousHandler")
                raise

            except RendezvousClosedException:
                log.info(
                    f"Rendezvous for run_id={self._run_id} was observed to be closed"
                )
                raise

            except RendezvousNonRetryableError:
                raise

            except Exception as e:
                # 在一般异常的情况下，等待一个小的延迟，以避免滥发etcd
                # In case of a general exception, wait a small delay
                # to avoid spamming etcd
                # FIXME: there are a few things that fall under this like
                # etcd.EtcdKeyNotFound, etc, which could be handled more explicitly.
                log.info("Rendezvous attempt failed, will retry. Reason: " + str(e))
                time.sleep(1)

    def init_phase(self):
        """
          最初，预计rendezvous状态为:
          1. empty - 将尝试创建一个新的
          2. joinable - 尝试加入
          3. final - 我们宣布在等待，然后进入监控模式
          任何其他的状态都被认为是过渡性的，并将在短暂的延迟后重新尝试。
        Initially, the rendezvous state is expected to be one of:
        1. empty (non-existent) - in this case we try to create a new one.
        2. joinable - we try to join it.
        3. final - we announce ourselves as waiting, and go into monitoring mode

        Any other state is considered transitional, and will be retried after
        a short delay.

        Returns:
            ``(rdzv_version, rank, world_size)``

        Raises:
            RendezvousClosedException - current rendezvous was/is closed
            EtcdRendezvousRetryableFailure - observed some intermediate     观察到一些中间状态，最好稍后重试处理
             state, which is best handled by retrying later
        """
        try:
            active_version = self.try_create_rendezvous()
            state = json.loads(active_version.value)
            log.info("New rendezvous state created: " + str(state))
        except etcd.EtcdAlreadyExist:
            active_version, state = self.get_rdzv_state()
            # 注意:上面的查询可能会失败(etcd.etcdkeynotfound)，但这对我们来说没问题——只是意味着我们将从头开始。
            # Note: it is possible for above query to fail (etcd.EtcdKeyNotFound),
            # but this is ok for us - just means we'll restart from beginning.
            log.info("Observed existing rendezvous state: " + str(state))

        if state["status"] == "closed":
            raise RendezvousClosedException()

        if state["status"] == "joinable":
            return self.join_phase(state["version"])

        if state["status"] == "final":
            self.handle_existing_rendezvous(state["version"])
            raise EtcdRendezvousRetryImmediately()

        self.try_wait_for_state_change(etcd_index=active_version.etcd_index + 1)
        raise EtcdRendezvousRetryableFailure()

    def join_phase(self, expected_version):
        """
        我们在'joinable'状态中观察到一个rendezvous状态，并尝试加入这个特定version，然后等待所有其他peer加入。
        We observed a rendezvous state in 'joinable' state, and attempt to join this
        particular version, and then wait for all other peers to join.
        """
        # 加入失败将会抛出异常，导致重新进入。
        # Failure to join will propagate an exception, causing a re-entry.
        active_version, this_rank = self.join_rendezvous(expected_version)
        state = json.loads(active_version.value)
        log.info(
            "Joined rendezvous version {} as rank {}. Full state: {}".format(
                state["version"], this_rank, state
            )
        )

        '''
        如果这个worker首先达到num_min_workers的要求，并且rendezvous仍然是joinable的(因此它是弹性的)，
        那么这个worker将负责等待“最后一个加入节点”的timeout，然后关闭rendezvous(即转换为“frozen”)。
        为了防止这个worker有可能失败(在最后一次调用超时期间)，当到达min_num_workers时，集合状态被设置为临时状态。
        '''
        # If this worker was first to reach num_min_workers requirement,
        # and rendezvous is still joinable (therefore it is elastic),
        # then this worker will be repsonsible for waiting out the "last call"
        # timeout and closing (i.e. transitioning to 'frozen') the rendezvous
        # afterwards.
        # As a safety against a potential failure of this worker (during the
        # last call timeout), the rendezvous state is made ephemeral
        # when min_num_workers is reached.
        if this_rank == self._num_min_workers - 1 and state["status"] == "joinable":
            log.info("Rank {} is responsible for join last call.".format(this_rank))
            last_call_deadline = time.time() + self._last_call_timeout
            self.handle_join_last_call(expected_version, last_call_deadline)
            log.info("Rank {} finished join last call.".format(this_rank))

        #等待rdzv状态被冻结，这意味着一组固定的peer
        # Wait for rendezvous state to be frozen, which means a fixed set of peers
        log.info("Waiting for remaining peers.")
        active_version = self.wait_for_peers(expected_version)
        state = json.loads(active_version.value)

        assert (
            state["version"] == expected_version
        ), "Logic error: failed to observe version mismatch"

        return self.confirm_phase(expected_version, this_rank)

    def confirm_phase(self, expected_version, this_rank):
        """
        一旦rendezvous状态从“joinable”过渡到“frozen”，我们让每个参与者确认他们的成员身份，
        并设置每个成员保持生存的TTL键，然后等待所有其他参与者确认，这将成功结束这次rendezvous。
        Once the rendezvous state trainsitions from 'joinable' to 'frozen',
        we have every participant confirm their membership and setup per-member
        keep-alive TTL keys, and then wait for all other participants to confirm,
        which would then successfully conclude this rendezvous.
        """

        log.info("All peers arrived. Confirming membership.")
        self.confirm_membership(expected_version, this_rank)

        log.info("Waiting for confirmations from all peers.")
        active_version = self.wait_for_final(expected_version)
        state = json.loads(active_version.value)

        log.info(
            "Rendezvous version {} is complete. Final state: {}".format(
                state["version"], state
            )
        )

        # Rendezvous version number; our rank in it; world size
        return state["version"], this_rank, len(state["participants"])

    def handle_existing_rendezvous(self, expected_version):
        """
        当有一个已经存在的(状态为 final)rendezvous的情况下，我们必须宣布自己在等待，并等待下一次rendezvous的机会。
        Handle the case when there's an existing (state 'final) rendezvous already
        in place, and we have to announce ourselves waiting, and wait until
        the next rendezvous opportunity.
        """

        '''
        如果state是'final' -> 增加num_workers_waiting。 然后，观察状态变化:
        1. 如果它不再是final,跳出并且尝试：
        2. 如果keep alives are missing，摧毁它，然后跳出。
        '''
        # If state is 'final' -> increment num_workers_waiting
        # Then, observe state changes:
        #   1. if it's no longer final -> bail out and re-try
        #   2. if keep alives are missing, destroy it and bail out.
        active_state = self.announce_self_waiting(expected_version)
        log.info(
            "Added self to waiting list. Rendezvous full state: {}".format(
                active_state.value
            )
        )

        self.wait_for_rendezvous_to_free(expected_version)
        log.info("Previously existing rendezvous state changed. Will re-try joining.")

    def try_create_rendezvous(self):
        """
        创建新的rendezvous状态或引发一个指示未预料到的状态的异常(例如已经存在)
        Create new rendezvous state or raise an exception that indicates
        an unexpected state (e.g. already exists)

        Raises:
             RendezvousNonRetryableError - on unexpected state  意想不到的状态
        """

        '''
        最初的active_version是临时的-这是为了处理可能无法完成设置事务的可能性，即“setup”->"joinable"的转换。
        '''
        # Initially active_version is ephemeral - this is to handle the
        # possibility that might fail to complete the setup transaction,
        # i.e. the transition "setup" -> "joinable".
        active_version = self.client.write(
            key=self.get_path("/rdzv/active_version"),
            value=json.dumps({"status": "setup"}),
            prevExist=False,
            ttl=CONST_ETCD_SETUP_TTL,
        )

        try:
            version_counter = self.client.get(self.get_path("/rdzv/version_counter"))
            version_counter.value = str(int(version_counter.value) + 1)
            self.client.update(version_counter)
        except (etcd.EtcdKeyNotFound, etcd.EtcdCompareFailed):
            raise RendezvousNonRetryableError(
                "Unexpected state of EtcdRendezvousHandler, worker needs to die."
            )

        # 以下任何失败都将导致宣布retryable rendezvous失败。临时的 /rdzv/active_version 将失效，然后重新尝试setup进程。
        # Any failure below results in declaring a retryable rendezvous failure.
        # The ephemeral /rdzv/active_version will expire and someone can then
        # re-try the setup process.

        # 为参与者数据创建目录节点
        # Create directory node for participant data
        self.client.write(
            key=self.get_path("/rdzv/v_{}".format(version_counter.value)),
            value=None,
            dir=True,
            prevExist=False,
        )

        # 发布rendezvous版本，并表示它已准备好加入。如果rendezvous在此之前设置为关闭，将发生重试，此时将处理关闭的条件。
        # Publish rendezvous version and signal it is ready-to-be-joined.
        # If rendezvous was set closed just before this, a retry will happen,
        # where the closed condition will be handled.
        return self.client.test_and_set(
            key=self.get_path("/rdzv/active_version"),
            value=json.dumps(
                {
                    "status": "joinable",
                    "version": version_counter.value,
                    "participants": [],
                }
            ),
            prev_value=active_version.value,
        )

    def join_rendezvous(self, expected_version):
        """
        join phase的辅助方法。
        """

        # 使用compare-and-swap将self添加到rendezvous状态
        # Use compare-and-swap to add self to rendezvous state:
        while True:
            cas_delay()
            '''
             def get_rdzv_state(self):
                active_version = self.client.get(key=self.get_path("/rdzv/active_version"))
                return active_version, json.lfwoads(active_version.value)
            '''
            active_version, state = self.get_rdzv_state()

            if state["status"] != "joinable":
                raise EtcdRendezvousRetryableFailure(
                    "Rendezvous state became non-joinable before we could join. "
                    "Must join next one."
                )

            if state["version"] != expected_version:
                raise EtcdRendezvousRetryImmediately(
                    "Rendezvous version changed. Must try join the new one."
                )

            assert (
                len(state["participants"]) < self._num_max_workers
            ), "Logic error: joinable rendezvous should always have space left"

            # 在这里确定rank
            this_rank = len(state["participants"])
            state["participants"].append(this_rank)

            # 当到达min workers时，或者将状态更改为frozen时，将active_version节点设置为ephemeral。
            if len(state["participants"]) == self._num_max_workers:
                state["status"] = "frozen"
                state["keep_alives"] = []
                set_ttl = CONST_ETCD_FROZEN_TTL
            elif len(state["participants"]) >= self._num_min_workers:
                set_ttl = CONST_ETCD_JOINABLE_EPHEMERAL_TTL
            else:
                set_ttl = None

            try:
                # Compare-and-swap.
                active_version = self.client.test_and_set(
                    key=self.get_path("/rdzv/active_version"),
                    value=json.dumps(state),
                    prev_value=active_version.value,
                    ttl=set_ttl,
                )
                # We succeeded joining.
                return active_version, this_rank

            except etcd.EtcdCompareFailed:
                log.info("Join rendezvous CAS unsuccessful, retrying")

    def wait_for_peers(self, expected_version):
        """
        Helper method for the join phase.
        """
        active_version, state = self.get_rdzv_state()
        while True:
            if state["status"] == "frozen" and state["version"] == expected_version:
                # Success, all peers arrived.
                return active_version

            elif state["status"] == "joinable" and state["version"] == expected_version:
                # 继续等待
                # Continue waiting for any interesting events.
                active_version, state = self.try_wait_for_state_change(
                    etcd_index=active_version.etcd_index + 1
                )

            else:
                # No valid transition possible at this point
                raise EtcdRendezvousRetryableFailure(
                    "Rendezvous state transition no longer possible. Must re-enter."
                )

    def confirm_membership(self, expected_version, this_rank):
        """
        confirm phase的辅助方法
        Helper method for the confirm phase
        """

        # Compare-and-swap loop
        while True:
            cas_delay()
            active_version, state = self.get_rdzv_state()

            if state["status"] != "frozen":
                raise EtcdRendezvousRetryImmediately(
                    "Rendezvous no longer frozen, before we confirmed. "
                    "Must join next one"
                )
            if state["version"] != expected_version:
                raise EtcdRendezvousRetryImmediately(
                    "Rendezvous version changed. Must try join the new one."
                )

            this_lease_key = self.get_path(
                "/rdzv/v_{}/rank_{}".format(expected_version, this_rank)
            )
            self.client.set(this_lease_key, value=None, ttl=CONST_WORKER_KEEPALIVE_TTL)

            state["keep_alives"].append(this_lease_key)
            if len(state["keep_alives"]) == len(state["participants"]):
                # Everyone confirmed (this rank is last to do so)
                state["status"] = "final"
                state["num_workers_waiting"] = 0
                finalize = True
            else:
                finalize = False

            try:
                # 比较并交换。如果新状态仍处于冻结状态，则保持其短暂性。
                # Compare-and-swap. If new state is still frozen, keep it ephemeral.
                active_version = self.client.test_and_set(
                    key=self.get_path("/rdzv/active_version"),
                    value=json.dumps(state),
                    prev_value=active_version.value,
                    ttl=None if finalize else CONST_ETCD_FROZEN_TTL,
                )

                self._lease_this_rank_stop = self.setup_lease_renewal(
                    this_lease_key, ttl=CONST_WORKER_KEEPALIVE_TTL
                )
                return active_version

            except etcd.EtcdCompareFailed:
                log.info("Confirm membership CAS unsuccessful, retrying")

    def wait_for_final(self, expected_version):
        """
        Helper method for the confirm phase
        """
        active_version, state = self.get_rdzv_state()
        while True:
            if state["status"] == "final" and state["version"] == expected_version:
                # Succcess. This rendezvous is final, and we accept it.
                return active_version

            elif state["status"] == "frozen" and state["version"] == expected_version:
                # Continue waiting for any interesting events.
                active_version, state = self.try_wait_for_state_change(
                    etcd_index=active_version.etcd_index + 1
                )

            else:
                # No valid transition possible at this point
                raise EtcdRendezvousRetryableFailure(
                    "Rendezvous state transition no longer possible. Must re-enter."
                )

    def announce_self_waiting(self, expected_version):
        """
        宣布这个worker正在等待(通过 num_workers_waiting counter)加入下一个rendezvous，但只有在状态和版本匹配的情况下。
        Announce this worker is waiting (via num_workers_waiting counter) to join next
        rendezvous, but only if state and version match.
        """

        while True:
            cas_delay()
            active_version, state = self.get_rdzv_state()

            if state["status"] != "final" or state["version"] != expected_version:
                raise EtcdRendezvousRetryImmediately()

            # Increment counter to signal an additional waiting worker.
            state["num_workers_waiting"] += 1

            try:
                active_version = self.client.test_and_set(
                    key=self.get_path("/rdzv/active_version"),
                    value=json.dumps(state),
                    prev_value=active_version.value,
                )
                return active_version

            except etcd.EtcdCompareFailed:
                log.info("Announce self as waiting CAS unsuccessful, retrying")

    def wait_for_rendezvous_to_free(self, expected_version):
        """
        当有一个现有的rdzv处于状态’final’时，我们必须等待，直到下一个机会去加入。
        这样的机会可能来自:
        1. rdzv状态被其他worker改变了，在这种情况下，我们要解锁并重试。
        2. rdzv无效，因为至少有一个成员没有更新他们租用的 keep_alive 节点。我们侦测到这个，然后摧毁rdzv。

        When there's an existing valid rendezvous in state 'final', we have to
        wait until the next opportunity to join.

        Such opportunity may come from:
        1. rendezvous state changed by someone else, in which case we unblock and retry.
        2. rendezvous becomes invalid because at least one member failed to renew their
           leased keep_alive node. We detect this, and destroy the rendezvous.
        """
        active_version, state = self.get_rdzv_state()
        while True:
            if state["status"] != "final" or state["version"] != expected_version:
                return
            # 检查当前的集合状态是否有效，即它的所有成员都是活着的(更新它们的租约)。
            # 如果没有，试着摧毁这个集合，这样就可以创建一个新的集合。
            # Check if current rendezvous state is valid, in the sense that all
            # its members are alive (renewing their lease).
            # If not, try destroy this rendezvous, so a new one can be created.
            alive_members = self.client.get(
                self.get_path("/rdzv/v_{version}".format(version=expected_version))
            )
            keep_alive_keys = [ch.key for ch in alive_members.children]

            for key in state["keep_alives"]:
                if key not in keep_alive_keys:
                    # This participant didn't renew their lease. We'll declare this
                    # rendezvous version as dead (but only if it hadn't changed)
                    log.info("Keep-alive key {} is not renewed.".format(key))
                    log.info(
                        "Rendevous version {} is incomplete. ".format(expected_version)
                    )
                    log.info("Attempting to destroy it.")

                    # Compare-and-delete operation. Throws if compare failed,
                    # which means rendezvous was already destroyed/re-created/closed,
                    # and we can try to re-enter the barrier.
                    self.client.delete(
                        key=self.get_path("/rdzv/active_version"),
                        prevValue=active_version.value,
                    )

                    log.info(
                        "Destroyed rendezvous version {} successfully.".format(
                            expected_version
                        )
                    )

                    # We can return (and retry) immediately
                    return

            # Existing rendezvous seems valid, no reason to destroy it.
            # We just have to wait until something changes and re-check.
            try:
                overall_timeout = (
                    max(self._rendezvous_deadline - time.time(), 0.0) + 1.0
                )
                self.client.watch(
                    key=self.get_path("/rdzv"),
                    index=active_version.etcd_index + 1,
                    recursive=True,
                    timeout=overall_timeout,
                )
            except (etcd.EtcdEventIndexCleared, etcd.EtcdWatchTimedOut):
                pass

            if time.time() > self._rendezvous_deadline:
                raise RendezvousTimeoutException()
            active_version, state = self.get_rdzv_state()

    def handle_join_last_call(self, expected_version, deadline):
        """
        当我们达到最小的worker数量后，一个特定的work负责在关闭连接窗口之前等待额外的超时时间。
        如果负责的worker失败，rdzv将因 TTL 到期而被摧毁，其他参与者将重新rdzv。

        这里我们期望看到状态 <joinable, expected_version>
        如果满足以下条件，将会gracefully退出:
        1. 状态变为<frozen, expected_version>
        2. 超时发生(到达最后期限) ，在这种情况下，我们尝试将转为 <frozen，expected_version>
        否则直接退出。

        After we reach min number of workers, one particular worker takes on the
        responsibility of waiting an additional timeout before closing the join window.
        If the worker responsible for this fails, the rendezvous will be destroyed due
        to expiring TTL, and the other participants will re-rendezvous.

        Here we expect to see state <joinable, expected_version>
        Exit gracefully if either:
        1. state becomes <frozen, expected_version>
        2. timeout happens (reaching deadline), in which case
           we try the transition to <frozen, expected_version>

        Exit with exception otherwise.
        """

        active_version, state = self.get_rdzv_state()
        while True:
            if state["status"] == "frozen" and state["version"] == expected_version:
                # Worker set在最后一次呼叫超时前被frozen。当在超时之前到达num_max_workers时，这是可能的。
                # Worker set became frozen before last-call timeout. This is possible
                # when num_max_workers is reached before the tiemout.
                return

            if state["status"] != "joinable" or state["version"] != expected_version:
                raise EtcdRendezvousRetryableFailure(
                    "Rendezvous state transition no longer possible. Must re-enter."
                )

            # 超时
            # If timeout occurred, attempt a state transition (joinable -> frozen)
            if time.time() >= deadline:
                state["status"] = "frozen"
                state["keep_alives"] = []
                try:
                    active_version = self.client.test_and_set(
                        key=self.get_path("/rdzv/active_version"),
                        value=json.dumps(state),
                        prev_value=active_version.value,
                        ttl=CONST_ETCD_FROZEN_TTL,
                    )
                    # We successfully made this rendezvous frozen.
                    return
                except etcd.EtcdCompareFailed:
                    log.info("Join last-call transition CAS unsuccessful. Will retry")
                    cas_delay()
                    active_version, state = self.get_rdzv_state()
                    continue
            # 超时没有发生，因此我们必须刷新TTL，并等待进一步的更改。
            # 注意:我们只希望在状态仍然是可连接的情况下刷新TTL，因此我们在这里使用CAS，即使我们不更改任何数据。
            # Timeout did not occur, so we must refresh TTL, and wait for
            # further changes. Note: we only want TTL to be refreshed if
            # state is still joinable, hence we use CAS for that here,
            # even though we don't change any of the data.
            try:
                active_version = self.client.test_and_set(
                    key=self.get_path("/rdzv/active_version"),
                    value=active_version.value,
                    prev_value=active_version.value,
                    ttl=CONST_ETCD_JOINABLE_EPHEMERAL_TTL,
                )

                # Minimize "oversleeping":
                timeout = min(
                    CONST_ETCD_JOINABLE_EPHEMERAL_TTL / 2,
                    deadline - time.time() + 1.0,  # Oversleeping by 1s is ok.
                )
                active_version, state = self.try_wait_for_state_change(
                    etcd_index=active_version.etcd_index + 1, timeout=timeout
                )
            except etcd.EtcdCompareFailed:
                log.info("Join last-call TTL refresh CAS unsuccessful, will retry")
                cas_delay()
                active_version, state = self.get_rdzv_state()

    def set_closed(self):
        """
        标记当前run_id 的 rdzv “关闭 ”，用于通知其他参与者不要试图执行(重新)rdzv。
        当其中一个worker认为工作已经完成时，这是非常有用的。
        Mark rendezvous 'closed' for current run_id, which is used to signal other
        participants to not attempt to perform (re-)rendezvous. This is useful
        when one of the workers decides the job is complete.
        """
        while True:
            active_version, state = self.get_rdzv_state()

            if state["status"] == "closed":
                # Already closed by someone else.
                return

            state["status"] = "closed"
            try:
                self.client.test_and_set(
                    key=self.get_path("/rdzv/active_version"),
                    value=json.dumps(state),
                    prev_value=active_version.value,
                )
                return

            except etcd.EtcdCompareFailed:
                log.info("Set closed CAS unsuccessful, retrying")
                cas_delay()

    def get_rdzv_state(self):
        active_version = self.client.get(key=self.get_path("/rdzv/active_version"))
        return active_version, json.loads(active_version.value)

    def try_wait_for_state_change(self, etcd_index, timeout=None):
        ## 不要在截止时间后休眠(至少超过1秒)
        # Don't sleep past the overall deadline (at least more than by 1s)
        overall_timeout = max(self._rendezvous_deadline - time.time(), 0.0) + 1.0
        timeout = overall_timeout if timeout is None else min(timeout, overall_timeout)

        try:
            self.client.watch(
                self.get_path("/rdzv/active_version"), index=etcd_index, timeout=timeout
            )
        except (etcd.EtcdEventIndexCleared, etcd.EtcdWatchTimedOut):
            pass

        if time.time() > self._rendezvous_deadline:
            raise RendezvousTimeoutException()

        # 不幸的是，为了获得last etcd_index，我们必须进行另一次fetch。
        # Unfortunately, we have to do another fetch in order to get last etcd_index.
        return self.get_rdzv_state()

    def get_path(self, path):
        if not path.startswith("/"):
            path = "/" + path

        return "{prefix}run_{run_id}{path}".format(
            prefix=self._prefix, run_id=self._run_id, path=path
        )

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

    def store_extra_data(self, rdzv_version, key, value):
        node = self.get_path("/rdzv/v_{}/extra_data".format(rdzv_version))
        try:
            # If first time we are storing anything:
            extra_data = self.client.write(
                key=node, value=json.dumps({key: value}), prevExist=False
            )
            return
        except etcd.EtcdAlreadyExist:
            pass

        # CAS循环，以确保我们不会丢失并发存储。
        # CAS loop, to make sure we don't lose concurrent stores.
        while True:
            # 我们从不删除extra_data。这里的失败是致命的，没有特殊处理。
            # We never delete extra_data. Failure here should be fatal, no special handling.
            extra_data = self.client.get(node)

            new_extra_data_value = json.loads(extra_data.value)
            new_extra_data_value[key] = value

            try:
                extra_data = self.client.test_and_set(
                    key=node,
                    value=json.dumps(new_extra_data_value),
                    prev_value=extra_data.value,
                )
                return
            except etcd.EtcdCompareFailed:
                log.info("Store extra_data CAS unsuccessful, retrying")
                time.sleep(0.1)

    def load_extra_data(self, rdzv_version, key, timeout=None):
        # 'extra_data' node itself, and the directory it is located in:
        node = self.get_path("/rdzv/v_{}/extra_data".format(rdzv_version))
        node_dir = self.get_path("/rdzv/v_{}".format(rdzv_version))

        # TODO: implement timeout
        # https://github.com/pytorch/elastic/issues/12
        while True:
            # Combined wait for the node itself, and the key inside it.
            root = self.client.get(node_dir)

            # Find the extra_data node, if it exists
            extra_data = [n for n in root.children if n.key == node]
            assert len(extra_data) <= 1

            # Node for extra_data exists, check the desired key inside it.
            if len(extra_data) == 1:
                extra_data_dict = json.loads(extra_data[0].value)
                if key in extra_data_dict:
                    return extra_data_dict[key]
            # 'extra_data'节点不存在，或者它们的键还没有发布。等待extra_data节点上有兴趣的事件，然后重试。
            # The 'extra_data' node doesn't exist, or they key isn't published yet.
            # Wait for interesting events on the extra_data node and retry.
            try:
                self.client.watch(node, index=root.etcd_index + 1)
            except (etcd.EtcdEventIndexCleared, etcd.EtcdWatchTimedOut):
                pass

    def setup_kv_store(self, rdzv_version):
        store_path = self.get_path(f"/rdzv/v_{rdzv_version}/kv")
        self.create_path_if_not_exists(store_path)
        return EtcdStore(etcd_client=self.client, etcd_store_prefix=store_path)


# pyre-fixme[11]: Annotation `Store` is not defined as a type.
class EtcdStore(Store):
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
        super().__init__()  # required for pybind trampoline.

        self.client = etcd_client
        self.prefix = etcd_store_prefix
        # 默认超时时间与c10d/Store.hpp相同
        # Default timeout same as in c10d/Store.hpp
        self.timeout = (
            timeout if timeout is not None else datetime.timedelta(seconds=300)
        )
        if not self.prefix.endswith("/"):
            self.prefix += "/"

    def set(self, key, value):
        """
        在 EtcdStore 中写入一个键/值对。键和值可以是 python str 或者是 bytes。
        Write a key/value pair into ``EtcdStore``.
        Both key and value may be either Python ``str`` or ``bytes``.
        """
        self.client.set(key=self.prefix + self._encode(key), value=self._encode(value))

    def get(self, key) -> bytes:
        """
        通过key获取一个value，可能需要进行阻塞等待。
        如果key没有立即出现，则在最长的超时期间或直到key被发布时进行阻塞等待。

        Get a value by key, possibly doing a blocking wait.

        If key is not immediately present, will do a blocking wait
        for at most ``timeout`` duration or until the key is published.


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

    def add(self, key, num: int) -> int:
        """
        原子地将值增加一个整数值。该整数用以10为基数的字符串表示。如果键不存在，则假定缺省值为0。
        返回：新的(递增的)的值

        Atomically increment a value by an integer amount. The integer is
        represented as a string using base 10. If key is not present,
        a default value of ``0`` will be assumed.

        Returns:
             the new (incremented) value


        """
        b64_key = self._encode(key)
        # c10d Store假定value是一个用十进制字符串表示的整数
        # c10d Store assumes value is an integer represented as a decimal string
        try:
            # 假设默认值“0”，如果这个键不存在:
            # Assume default value "0", if this key didn't yet:
            node = self.client.write(
                key=self.prefix + b64_key,
                value=self._encode(str(num)),  # i.e. 0 + num
                prevExist=False,
            )
            return int(self._decode(node.value))
        except etcd.EtcdAlreadyExist:
            pass

        while True:
            # 注意:c10d Store没有一个删除键的方法，所以我们可以确保它仍然在那里。
            # Note: c10d Store does not have a method to delete keys, so we
            # can be sure it's still there.
            node = self.client.get(key=self.prefix + b64_key)
            new_value = self._encode(str(int(self._decode(node.value)) + num))
            try:
                node = self.client.test_and_set(
                    key=node.key, value=new_value, prev_value=node.value
                )
                return int(self._decode(node.value))
            except etcd.EtcdCompareFailed:
                cas_delay()

    def wait(self, keys, override_timeout: Optional[datetime.timedelta] = None):
        """
        等待直到所有键发布，或者等到超时。
        Waits until all of the keys are published, or until timeout.

        Raises:
            LookupError - if timeout occurs
        """
        b64_keys = [self.prefix + self._encode(key) for key in keys]
        kvs = self._try_wait_get(b64_keys, override_timeout)
        if kvs is None:
            raise LookupError("Timeout while waiting for keys in EtcdStore")
        # No return value on success

    def check(self, keys) -> bool:
        """
        检查所有的key是否立即到位(不用等待)。
        Check if all of the keys are immediately present (without waiting).
        """
        b64_keys = [self.prefix + self._encode(key) for key in keys]
        kvs = self._try_wait_get(
            b64_keys,
            override_timeout=datetime.timedelta(microseconds=1),  # as if no wait
        )
        return kvs is not None

    def set_timeout(self, timeout: datetime.timedelta):
        """
        更改用于所有未来操作的timeout。
        Change the timeout used for all future operations.
        """
        self.timeout = timeout

    #
    # Encode key/value data in base64, so we can store arbitrary binary data
    # in EtcdStore. Input can be `str` or `bytes`.
    # In case of `str`, utf-8 encoding is assumed.
    #
    def _encode(self, value) -> str:
        if type(value) == bytes:
            return b64encode(value).decode()
        elif type(value) == str:
            return b64encode(value.encode()).decode()
        raise ValueError("Value must be of type str or bytes")

    #
    # Decode a base64 string (of type `str` or `bytes`).
    # Return type is `bytes`, which is more convenient with the Store interface.
    #
    def _decode(self, value) -> bytes:
        if type(value) == bytes:
            return b64decode(value)
        elif type(value) == str:
            return b64decode(value.encode())
        raise ValueError("Value must be of type str or bytes")

    # 一次获取所有(base64编码的)etcd键，或者等待所有键被发布或发生超时。这是公共接口方法的辅助方法。
    # Get all of the (base64-encoded) etcd keys at once, or wait until all the keys
    # are published or timeout occurs.
    # This is a helper method for the public interface methods.
    #
    # 如果成功，将返回一个字典{etcd key -> etcd value}。超时返回None。
    # On success, a dictionary of {etcd key -> etcd value} is returned.
    # On timeout, None is returned.
    #
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


def _get_socket_with_port():
    import socket

    addrs = socket.getaddrinfo(
        host="localhost", port=None, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM
    )
    for addr in addrs:
        family, type, proto, _, _ = addr
        try:
            s = socket.socket(family, type, proto)
            s.bind(("localhost", 0))
            s.listen(0)
            return s
        except OSError as e:
            s.close()
            log.info("Socket creation attempt failed: " + e)

    raise RuntimeError("Failed to create a socket")


# Helper for _etcd_rendezvous_handler(url)
def _parse_etcd_client_params(params):
    kwargs = {}
    if "protocol" in params:
        protocol = params["protocol"]
        assert protocol in ["http", "https"], "Protocol must be http or https."
        kwargs["protocol"] = protocol
    if "cacert" in params:
        kwargs["ca_cert"] = params["cacert"]
    if "cert" in params:
        if "key" in params:
            # python-etcd client expects key as a second element of `cert` tuple
            kwargs["cert"] = (params["cert"], params["key"])
        else:
            kwargs["cert"] = params["cert"]
    return kwargs


# Handler for torch.distributed "static" registration
def _etcd_rendezvous_handler(url):
    """
    Example URLs:
        etcd://localhost:2379/123?min_workers=4&max_workers=8&timeout=300
        etcd://192.168.0.42/123?etcd_prefix=/custom_prefix/foo&min_workers=4
        etcd://localhost:2379/123?min_workers=4&protocol=https&cacert=/etc/kubernetes/certs/ca.crt&cert=/etc/kubernetes/certs/client.crt&key=/etc/kubernetes/certs/client.key

    Where:
        123 - the run_id (unique id for this training job instance),
        min_workers=4 - min number of workers expected to join the rendezvous,
        max_workers=8 - max number of workers allowed to join the rendezvous,
                        defaults to min_workers is not specified.
        timeout=300 - total timeout within which next_rendezvous is expected to
                      succeed; a RendezvousTimeoutException is raised otherwise;
                      Defaults is 600 (10 minutes).
        last_call_timeout - additional wait amount ("last call") after
                            min number of workers has been reached.
                            Defaults to 30 seconds.
        etcd_prefix - path prefix (from etcd root), inside which all
                      etcd nodes will be created.
                      Default is "/torchelastic/p2p".
        protocol=https - http (default) or https to access etcd.
        cacert=/etc/kubernetes/certs/ca.crt - CA cert to access etcd,
                    only makes sense with https.
        cert=/etc/kubernetes/certs/client.crt - client cert to access etcd,
                    only makes sense with https.
        key=/etc/kubernetes/certs/client.key - client key to access etcd,
                    only makes sense with https.

    """
    import re
    from urllib.parse import urlparse

    url = urlparse(url)
    assert url.scheme == "etcd"

    # Etcd endpoints. (Current url format only allows a single host)
    endpoint = url.netloc
    match = re.match(r"(.+):(\d+)$", endpoint)  # check if port was provided
    if match:
        etcd_endpoints = ((match.group(1), int(match.group(2))),)
    else:
        # Use default etcd port
        etcd_endpoints = ((endpoint, 2379),)

    # Run ID value -> unique identifier of this training job instance:
    # typically a job_id or name assigned by the scheduler or user
    run_id = url.path.strip("/")

    # Parse all of query parameters:
    params = dict(pair.split("=") for pair in filter(None, url.query.split("&")))

    etcd_prefix = params.get("etcd_prefix", "/torchelastic/p2p")
    num_min_workers = int(params["min_workers"])
    num_max_workers = int(params.get("max_workers", num_min_workers))
    assert num_min_workers >= 1, "Min number of workers should be at least 1"
    assert (
        num_max_workers >= num_min_workers
    ), "Max number of workers cannot be less than min number of workers"

    timeout = int(params.get("timeout", CONST_DEFAULT_OVERALL_TIMEOUT))
    last_call_timeout = int(
        params.get("last_call_timeout", CONST_DEFAULT_LAST_CALL_TIMEOUT)
    )

    kwargs = _parse_etcd_client_params(params)

    # Etcd rendezvous implementation
    etcd_rdzv = EtcdRendezvous(
        endpoints=etcd_endpoints,
        prefix=etcd_prefix,
        run_id=run_id,
        num_min_workers=num_min_workers,
        num_max_workers=num_max_workers,
        timeout=timeout,
        last_call_timeout=last_call_timeout,
        **kwargs,
    )
    return EtcdRendezvousHandler(rdzv_impl=etcd_rdzv)


# torchelastic.rendezvous.RendezvousHandler using etcd (API v2):
register_rendezvous_handler("etcd", _etcd_rendezvous_handler)
