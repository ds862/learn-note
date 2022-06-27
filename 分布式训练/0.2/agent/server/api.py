#!/usr/bin/env python3

# Copyright (c) Facebook, Inc. and its affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

import abc
import logging
import socket
import time
from contextlib import closing
from enum import Enum
from typing import Any, Callable, Dict, Tuple

import torchelastic.rendezvous as rdzv
from torchelastic.metrics import prof, put_metric


DEFAULT_ROLE = "default"

log = logging.getLogger(__name__)


class WorkerSpec:
    """
    Worker specifications: worker的详细行为信息

    包含一个worker的详细行为信息。对于给定的role，必须只有一个WorkerSpec。
    Worker spec应该在所有节点(机器)之间保持相同，即每个节点为了particular spec运行相同数量的worker。
    Contains blueprint information about a particular type of worker.
    For a given role, there must only exist a single worker spec.
    Worker spec is expected to be homogenous across all nodes (machine),
    that is each node runs the same number of workers for a particular spec.
    """

    __slots__ = [
        "role",
        "local_world_size",
        "fn",
        "args",
        "rdzv_handler",
        "max_restarts",
        "monitor_interval",
        "master_port",
    ]

    def __init__(
        self,
        role: str,
        local_world_size: int,
        fn: Callable,
        args: Tuple,
        rdzv_handler: rdzv.RendezvousHandler,
        max_restarts: int = 100,
        monitor_interval: float = 5.0,
        master_port=None,
    ):
        r"""

        Arguments:
            role (str): user-defined role for the workers with this spec    用户为具有此规范的worker定义的role
            local_world_size (int): number local workers to run     本地运行的worker数量
            fn (Callable): worker main entry point function     worker main入口点函数
            args (Tuple): arguments to pass to ``fn(args)``     传递给fn()的参数
            rdzv_handler (RendezvousHandler): handles rdzv for this set of workers  为这组worker处理rdzv
            max_restarts: number of max retries for the workers    worker的最大重试次数
        monitor_interval: monitor status of workers every ``n`` seconds    每“n”秒监视worker的状态
        master_port: fixed port to run the c10d store on rank 0    运行c10d的固定端口，存储在rank 0
                     if not specified then will chose a random free port    如果没有指定，那么将选择一个随机的自由端口
        """

        assert local_world_size > 0
        assert max_restarts > 0
        assert monitor_interval > 0

        # Note: role is not used for data parallel, every worker has the same role
        # wiring it in to handle more elaborate situations later
        self.role = role
        self.local_world_size = local_world_size
        self.fn = fn
        self.args = args
        self.rdzv_handler = rdzv_handler
        self.max_restarts = max_restarts
        self.monitor_interval = monitor_interval
        self.master_port = master_port


class Worker:
    """
    表示一个worker实例。将其与表示一个worker规范的 WorkerSpec 进行对比。
    一个 Worker从一个 WorkerSpec 中创建。一个 Worker 对于一个 WorkerSpec 就像一个对象对于一个类一样。
    Represents a worker instance. Contrast this with ``WorkerSpec`` that
    represents the specifications of a worker. A ``Worker`` is created from
    a ``WorkerSpec``. A ``Worker`` is to a ``WorkerSpec`` as an object is to
    a class.

    worker的 id 由 ElasticAgent 的特定实现来解释。
    对于local agent，它可以是worker的 pid (int) ，对于远程agent，它可以被编码为 host: port (string)。
    The ``id`` of the worker is interpreted
    by the specific implementation of ``ElasticAgent``. For a local
    agent, it could be the ``pid (int)`` of the worker, for a remote
    agent it could be encoded as ``host:port (string)``.

    Arguments:
        id (Any): uniquely identifies a worker (interpreted by the agent)   唯一地标识一个worker(由agent解释)
        local_rank (int): local rank of the worker
        global_rank (int): global rank of the worker        worker的global rank
        world_size (int): number of workers (globally)      worker的全部数量
    """

    __slots__ = ["id", "local_rank", "global_rank", "world_size"]

    def __init__(self, local_rank: int):
        # unique identifier for this worker
        self.id: Any = None

        # 由相同的“agent”实例监视的具有相同role的workers中的worker的role。
        # rank of the worker among workers with the same role being monitored
        # by the same ``agent`` instance.
        self.local_rank: int = local_rank

        # 在所有“agent”实例中具有相同role的所有workers中的worker的rank。
        # 在re-rendezvous之间，Global rank是不稳定的。
        #  rank of the worker among all the workers with the same role
        #  across all ``agent`` instances.
        #  Global rank is not stable between re-rendezvous.
        # pyre-fixme[8]: Attribute has type `int`; used as `None`.
        self.global_rank: int = None

        # worker的总数(globally)。由于弹性，world size的大小可能会在re-rendezvous之间改变。
        # total number of workers (globally). Due to elasticity
        # the world size may change between re-rendezvous.
        # pyre-fixme[8]: Attribute has type `int`; used as `None`.
        self.world_size: int = None


class WorkerState(Enum):
    """
    WorkerGroup的状态。一个WorkerGroup中的workers作为一个单元改变状态。
    如果一个WorkerGroup中的一个worker失败，则认为整个集合失败:
    State of the ``WorkerGroup``. Workers in a worker group change state as a unit.
    If a single worker in a worker group fails the entire set is considered
    failed::

      UNKNOWN - agent lost track of worker group state, unrecoverable    agent丢失了工作组状态，不可恢复
      INIT - worker group object created not yet started    创建的Worker组对象尚未启动
      HEALTHY - workers running and healthy     workers正常运行
      UNHEALTHY - workers running and unhealthy     workers不正常运行
      STOPPED - workers stopped (interruped) by the agent   works被agent终止
      SUCCEEDED - workers finished running (exit 0)     workers结束运行（退出值0）
      FAILED - workers failed to successfully finish (exit !0)      workers无法成功结束运行（退出值非0）

    一个worker group从初始状态“INIT”开始，然后发展到"HEALTHY"或"UNHEALTHY"状态，最终到达一个终点'成功'或'失败'状态。
    A worker group starts from an initial ``INIT`` state,
    then progresses to ``HEALTHY`` or ``UNHEALTHY`` states,
    and finally reaches a terminal ``SUCCEEDED`` or ``FAILED`` state.

    Worker groups可以被agent中断并暂时进入 STOPPED 状态。
    STOPPED 状态下的worker在不久的将来由代理重新启动。一些worker进入 STOPPED 状态的例子如下:
    Worker groups can be interrupted and temporarily put into ``STOPPED`` state
    by the agent. Workers in ``STOPPED`` state are scheduled to be restarted
    in the near future by the agent. Some examples of workers being put into
    ``STOPPED`` state are:

    Worker group失败 | 观察到处于unhealthy状态
    检测到成员变更
    1. Worker group failure|unhealthy observed
    2. Membership change detected

    当对 worker group的操作(启动、停止、 rdzv、重试等)失败,并导致操作部分应用于worker group时，状态将是 UNKNOWN。
    这通常发生在未捕获/未处理的情况下,agent上的状态更改事件期间的异常。
    agent不需要恢复处于 UNKNOWN 状态的工作者组，最好自动终止并允许job manager重试节点。
    When actions (start, stop, rdzv, retry, etc) on worker group fails
    and results in the action being partially applied to the worker group
    the state will be ``UNKNOWN``. Typically this happens on uncaught/unhandled
    exceptions during state change events on the agent. The agent is not
    expected to recover worker groups in ``UNKNOWN`` state and is better off
    self terminating and allowing the job manager to retry the node.
    """

    UNKNOWN = 0
    INIT = 1
    HEALTHY = 2
    UNHEALTHY = 4
    STOPPED = 8
    SUCCEEDED = 16
    FAILED = 32

    @staticmethod
    def is_running(state: "WorkerState") -> bool:
        """
        返回True代表workers仍然在运行
        Returns:
             `` True`` if the worker state represents workers still running
              (e.g. that the process exists but not necessarily healthy).
        """
        return state in {WorkerState.HEALTHY, WorkerState.UNHEALTHY}


class WorkerGroup:
    """
    表示由ElasticAgent管理的给定的WorkerSpec的Worker实例集。worker组是否包含跨实例worker取决于代理的实现。
    Represents the set of ``Worker`` instances for the given ``WorkerSpec``
    managed by ``ElasticAgent``. Whether the worker group contains cross
    instance workers or not depends on the implementation of the agent.
    """

    __slots__ = ["spec", "workers", "store", "group_rank", "group_world_size", "state"]

    def __init__(self, spec: WorkerSpec):
        self.spec = spec
        self.workers = [Worker(local_rank=i) for i in range(self.spec.local_world_size)]

        # 在rdzv后分配
        # assigned after rdzv
        self.store = None
        self.group_rank = None
        self.group_world_size = None

        self.state = WorkerState.INIT


class MonitorResult:
    """
    由代理的' _monitor_workers ' API返回。一个持有对象，它持有关于监视结果的信息。
    ret_vals ' '和' exceptions ' '字段根据工作者的全局排名映射每个工作者的返回值(输出)和异常(如果有的话)。
    Returned by the agent's ``_monitor_workers`` API. A holder object
    that holds information about the monitoring results.
    The ``ret_vals`` and ``exceptions`` field map each worker's
    return value (output) and exceptions (if any) accordingly by
    the workers global rank.

    ' state = SUCCEEDED ' '将具有' ' ret_val ' '。' ' state = FAILED ' '将有' ' exceptions ' '。
    对于其他状态，这两个字段都为空。
    ``state = SUCCEEDED`` will have ``ret_val``.
    ``state = FAILED`` will have ``exceptions``.
    For other states both these fields will be empty.
    """

    __slots__ = ["state", "ret_vals", "exceptions"]

    def __init__(
        self,
        state: WorkerState,
        # pyre-fixme[9]: ret_vals has type `Dict[int, typing.Any]`; used as `None`.
        ret_vals: Dict[int, Any] = None,
        # pyre-fixme[9]: exceptions has type `Dict[int, Exception]`; used as `None`.
        exceptions: Dict[int, Exception] = None,
    ):
        self.state = state
        self.ret_vals = ret_vals
        self.exceptions = exceptions


class WorkerGroupFailureException(Exception):
    """
    当agent不能或已经放弃运行workers时抛出。通常会抛出:
    Thrown when the agent cannot or has given up trying to run the workers.
    This is typically thrown:

    1. 超过max_restarts。
    2. Workers失败，errors是“不可重启的”
    1. Exceeded ``max_restarts``.
    2. Workers fail with errors that are deemed ``NonRestartable``

    当构造此异常时，底层worker异常将作为该worker的global rank到异常的映射提供。
    When constructing this exception the underlying worker exceptions
    are provided as a map of the worker's global rank to the exception.
    """

    def __init__(self, msg: str, worker_excs: Dict[int, Exception]):
        super().__init__(msg)
        self._worker_excs = worker_excs

    def get_worker_exceptions(self) -> Dict[int, Exception]:
        return self._worker_excs


def _get_socket_with_port() -> socket.socket:
    """
    通过绑定临时端口，返回本地主机上的空闲端口套接字。在将端口传递给实体之前关闭套接字这需要它。使用例子:
    Returns a free port on localhost that is "reserved" by binding a temporary
    socket on it. Close the socket before passing the port to the entity
    that requires it. Usage example

    ::

    sock = _get_socket_with_port()
    with closing(sock):
        port = sock.getsockname()[1]
        sock.close()
        # there is still a race-condition that some other process
        # may grab this port before func() runs
        func(port)
    """

    addrs = socket.getaddrinfo(
        host="localhost", port=None, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM
    )
    for addr in addrs:
        family, type, proto, _, _ = addr
        s = socket.socket(family, type, proto)
        try:
            s.bind(("localhost", 0))
            s.listen(0)
            return s
        except OSError as e:
            s.close()
            log.info("Socket creation attempt failed.", exc_info=e)
    raise RuntimeError("Failed to create a socket")


def _get_fq_hostname() -> str:
    return socket.getfqdn(socket.gethostname())


class ElasticAgent(abc.ABC):
    """
    agent进程负责管理一个或多个worker进程。worker进程被假定为常规的分布式 PyTorch 脚本。
    当agent创建worker进程时，agent为worker进程提供必要的信息，从而正确初始化一个torch进程组。
    Agent process responsible for managing one or more worker processes.
    The worker processes are assumed to be regular distributed PyTorch scripts.
    When the worker process is created by the agent, the agent provides the
    necessary information for the worker processes to properly initialize
    a torch process group.

    agent对worker的确切部署拓扑和比率取决于agent的具体实现和用户的job首选项。
    例如，要在 GPU 上运行一个分布式训练工作，需要8个trainers(每个 GPU 一个) ，你可以:
    The exact deployment topology and ratio of agent-to-worker is dependent
    on the specific implementation of the agent and the user's job placement
    preferences. For instance, to run a distributed training job on GPU with
    8 trainers (one per GPU) one can:

      使用8个单独的 GPU 实例，每个实例放置一个agent，每个agent管理1个worker。
    1. Use 8 x single GPU instances, place an agent per instance, managing
       1 worker per agent.
    2. Use 4 x double GPU instances, place an agent per instance, managing
       2 workers per agent.
    3. Use 2 x quad GPU instances, place an agent per instance, managing
       4 workers per agent.
      使用1 x 8 GPU 实例，每个实例放置一个agent，每个agent管理8个worker
    4. Use 1 x 8 GPU instance, place an agent per instance, managing
       8 workers per agent.

    Usage
    ::

     try:
         results = agent.run()
         return results[0] # return rank 0's results
     except WorkerGroupFailureException as e:
         exceptions = e.get_worker_exceptions()
         log.exception(f"worker 0 failed with: {exceptions[0]}")
     except Exception as e:
         log.exception(f"error while running agent")

    """

    @abc.abstractmethod
    def run(self, role: str = DEFAULT_ROLE) -> Dict[int, Any]:
        """
        实现见SimpleElasticAgent.run()

        运行agent，在失败时重新尝试启动worker group，直到达到最大重启次数 max _ restarts。
        Runs the agent, retrying the worker group on failures up to
        ``max_restarts``.

        Returns:
            返回每一个worker的global rank的map。如果 worker的函数签名为void ，则返回值为空。
            The return values for each worker mapped by the worker's global rank.
            Empty if workers have void signature.

        Raises:
            workers 没有成功运行
            WorkerGroupFailureException - workers did not successfully run
            异常-任何其他与工作进程无关的失败
            Exception - any other failures NOT related to worker process
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def get_worker_group(self, role: str = DEFAULT_ROLE) -> WorkerGroup:
        """
        Returns:
            给定role的 WorkerGroup。
            请注意，worker group是一个可变的对象，因此在多线程/进程环境中，它可能会改变状态。
            鼓励实现类接口(但不是必需的)返回一个defensive的只读副本。
            The ``WorkerGroup`` for the given ``role``.
            Note that the worker group is a mutable object and hence in a
            multi-threaded/process environment it may change state.
            Implementors are encouraged (but not required) to return
            a defensive read-only copy.
        """
        raise NotImplementedError()


class SimpleElasticAgent(ElasticAgent):
    """
    一个 ElasticAgent,为单个WorkerSpec(例如一个特定类型的worker role)管理worker(WorkerGroup)。
    An ``ElasticAgent`` that manages workers (``WorkerGroup``)
    for a single ``WorkerSpec`` (e.g. one particular type of worker role).
    """

    def __init__(self, spec: WorkerSpec):
        self._worker_group = WorkerGroup(spec)
        self._remaining_restarts = self._worker_group.spec.max_restarts

    # pyre-fixme[14]: `get_worker_group` overrides method defined in `ElasticAgent`
    #  inconsistently.
    def get_worker_group(self) -> WorkerGroup:
        # 返回: 给定role的 WorkerGroup。
        # TODO return an RO copy (need to create an ROWorkerGroup and ROWorkerSpec
        # since both these classes contain non-pure-data pointers - e.g. rdzv_handler)
        return self._worker_group

    @abc.abstractmethod
    def _start_workers(self, worker_group: WorkerGroup) -> Dict[int, Any]:
        r"""
        实现见local_elastic_agent

        根据worker group的worker spec启动 worker_group.spec.local_world_size 数量的worker
        Starts ``worker_group.spec.local_world_size`` number of workers
        according to worker spec for the worker group .

        返回一个``local_rank`` 到 worker id的map(字典)：Dict[local_rank, id]
        Returns a map of ``local_rank`` to worker ``id``.
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def _stop_workers(self, worker_group: WorkerGroup) -> None:
        r"""
        实现见local_elastic_agent

        停止给定worker group中的所有worker。实现者必须处理 WorkerState 定义的所有状态中的worker。
        也就是说，它必须gracefully处理停止不存在的worker、unhealthy (被卡住的)的worker等问题。
        Stops all workers in the given worker group. Implementors
        must deal with workers in all states defined by ``WorkerState``.
        That is, it must gracefully handle stopping non-existent workers,
        unhealthy (stuck) workers, etc.
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def _monitor_workers(self, worker_group: WorkerGroup) -> MonitorResult:
        r"""
        实现见local_elastic_agent

        检查worker的 worker_group ，并返回worker_group的新状态。
        Checks on the workers for the ``worker_group`` and returns
        the new state of the worker group.
        """
        raise NotImplementedError()

    @staticmethod
    def _set_master_addr_port(store, master_port):
        if master_port is None:
            sock = _get_socket_with_port()
            with closing(sock):
                master_port = sock.getsockname()[1]

        store.set("MASTER_ADDR", _get_fq_hostname().encode(encoding="UTF-8"))
        store.set("MASTER_PORT", str(master_port).encode(encoding="UTF-8"))

    @staticmethod
    def _get_master_addr_port(store) -> Tuple[str, int]:
        master_addr = store.get("MASTER_ADDR").decode(encoding="UTF-8")
        master_port = int(store.get("MASTER_PORT").decode(encoding="UTF-8"))
        return (master_addr, master_port)

    @prof
    def _rendezvous(self, worker_group: WorkerGroup) -> None:
        r"""
          为按照worker spec规定的workers运行rendezvous。
          为workers分配一个新的global rank 和 world size。
          更新worker group的rendezvous存储区。
        Runs rendezvous for the workers specified by worker spec.
        Assigns workers a new global rank and world size.
        Updates the rendezvous store for the worker group.
        """

        spec = worker_group.spec
        stride = spec.local_world_size

        #group_rank从这里获得
        store, group_rank, group_world_size = spec.rdzv_handler.next_rendezvous()
        world_size = group_world_size * spec.local_world_size

        worker_group.store = store
        worker_group.group_rank = group_rank
        worker_group.group_world_size = group_world_size

        # rank为0的节点作为master节点
        if group_rank == 0:
            self._set_master_addr_port(store, spec.master_port)

        # 为每一个work分配global_rank
        assigned_global_ranks = []
        for worker in worker_group.workers:
            # 怎样得到worker.local_rank？
            global_rank = (group_rank * stride) + worker.local_rank
            worker.global_rank = global_rank
            worker.world_size = world_size
            assigned_global_ranks.append(global_rank)

        master_addr, master_port = self._get_master_addr_port(store)
        # 重启次数 = 最大重启次数 - 剩余重启次数(默认为max_restarts，每次在run()函数中更改)
        restart_count = spec.max_restarts - self._remaining_restarts
        # 在此处打印log，可以更改这里的变量，观察一下输出结果
        log.info(
            f"[{spec.role}] Rendezvous complete for workers.\n"
            f"Result:\n"
            f"\trestart_count={restart_count}\n"
            f"\tgroup_rank={group_rank}\n"
            f"\tgroup_world_size={group_world_size}\n"
            f"\trank stride={stride}\n"
            f"\tassigned global_ranks={assigned_global_ranks}\n"
            f"\tmaster_addr={master_addr}\n"
            f"\tmaster_port={master_port}\n"
        )

    @prof
    def _initialize_workers(self, worker_group: WorkerGroup) -> None:
        r"""
        为worker_group开始一组新的workers，Essentially a rendezvous，然后是start_workers。
        Starts a fresh set of workers for the worker_group.
        Essentially a rendezvous followed by a start_workers.

        调用方应该首先调用 _stop_workers() ，以便在调用此方法之前停止运行 worker。
        The caller should first call ``_stop_workers()`` to stop running workers
        prior to calling this method.

        乐观地设置刚开始的worker group状态为``HEALTHY``，并将对状态的监控委托给_monitor_workers()函数
        Optimistically sets the state of the worker group that
        just started as ``HEALTHY`` and delegates the actual monitoring
        of state to ``_monitor_workers()`` method
        """
        role = worker_group.spec.role
        log.info(f"[{role}] Rendezvous'ing worker group")

        '''
        在停止worker之后，至少等待monitor_interval*2，
        等待rdzv barrier之前，让不同节点上的workers在一个集合op上fail，
        这样我们可以确保节点在同一时间进入rdzv，减少rdzv超时错误的几率
        '''
        # TODO after stopping workers, wait at least monitor_interval*2 for
        # workers on different nodes to fail on a collective op before waiting
        # on the rdzv barrier, this way we ensure that nodes enter rdzv
        # at around the same time and reduce false positive rdzv timeout errors
        self._rendezvous(worker_group)

        log.info(f"[{role}] Starting worker group")
        # 调用_start_workers
        worker_ids = self._start_workers(worker_group)
        for local_rank, id in worker_ids.items():
            worker = worker_group.workers[local_rank]
            worker.id = id

        worker_group.state = WorkerState.HEALTHY

    @prof
    def _restart_workers(self, worker_group: WorkerGroup) -> None:
        """
        重新启动(停止、rendezvous、启动)group中的所有local workers。
        Restarts (stops, rendezvous, starts) all local workers in the group.
        """

        role = worker_group.spec.role
        log.info(f"[{role}] Stopping worker group")
        # 1.先停止所有的workers
        self._stop_workers(worker_group)
        worker_group.state = WorkerState.STOPPED
        # 再调用_initialize_workers()，其中会调用_start_workers()
        self._initialize_workers(worker_group)

    def run(self, role: str = DEFAULT_ROLE) -> Dict[int, Any]:
        # 定义见ElasticAgent.run()
        # 注意:目前只适用于单个role
        # NOTE: currently only works for a single role

        spec = self._worker_group.spec
        role = spec.role

        log.info(f"[{role}] starting workers for function: {spec.fn.__name__}")

        self._initialize_workers(self._worker_group)
        monitor_interval = spec.monitor_interval
        rdzv_handler = spec.rdzv_handler

        while True:
            assert self._worker_group.state != WorkerState.INIT
            time.sleep(monitor_interval)
            monitor_result = self._monitor_workers(self._worker_group)
            state = monitor_result.state
            self._worker_group.state = state

            put_metric(f"workers.{role}.remaining_restarts", self._remaining_restarts)
            put_metric(f"workers.{role}.{state.name.lower()}", 1)

            if state == WorkerState.SUCCEEDED:
                log.info(f"[{role}] All workers successfully finished.")
                return monitor_result.ret_vals
            elif state in {WorkerState.UNHEALTHY, WorkerState.FAILED}:
                if self._remaining_restarts > 0:
                    log.info(
                        f"[{role}] Worker group {state.name}. "
                        f"{self._remaining_restarts}/{spec.max_restarts} attempts left;"
                        f" will restart worker group"
                    )
                    self._remaining_restarts -= 1
                    self._restart_workers(self._worker_group)
                else:
                    self._stop_workers(self._worker_group)
                    self._worker_group.state = WorkerState.FAILED
                    raise WorkerGroupFailureException(
                        f"[{role}] exceeded max_restarts={spec.max_restarts}",
                        monitor_result.exceptions,
                    )
            elif state == WorkerState.HEALTHY:
                # 成员变更不算作重试
                # membership changes do not count as retries
                num_nodes_waiting = rdzv_handler.num_nodes_waiting()
                group_rank = self._worker_group.group_rank
                if num_nodes_waiting > 0:
                    log.info(
                        f"[{role}] Detected {num_nodes_waiting} "
                        f"new nodes from group_rank={group_rank}; "
                        f"will restart worker group"
                    )
                    self._restart_workers(self._worker_group)
            else:
                raise Exception(f"[{role}] Worker group in {state.name} state")
