#!/usr/bin/env python3

# Copyright (c) Facebook, Inc. and its affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

import logging
import os
from typing import Any, Dict

import torch.multiprocessing as mp
from torchelastic.agent.server.api import (
    MonitorResult,
    SimpleElasticAgent,
    Worker,
    WorkerGroup,
    WorkerSpec,
    WorkerState,
)
from torchelastic.metrics.api import prof


log = logging.getLogger(__name__)


class _DistInfo:
    """
    用于创建torch进程组所需信息的container。在agent的进程中创建并传递给worker子进程。
    因此，该对象需要是没有状态的纯数据对象，最好只有基本成员变量
    Container for information required to create a torch process group.
    To be created on the agent's process and passed to the worker sub-process.
    Hence this object needs to be a pure data object with no state and
    preferably only primitive member variables
    """

    __slots__ = [
        "rank",
        "group_rank",
        "local_world_size",
        "world_size",
        "master_addr",
        "master_port",
        "restart_count",
        "max_restarts",
    ]

    def __init__(
        self,
        rank: int,
        group_rank: int,
        local_world_size: int,
        world_size: int,
        master_addr: str,
        master_port: int,
        restart_count: int,
        max_restarts: int,
    ):
        self.rank = rank
        self.group_rank = group_rank
        self.local_world_size = local_world_size
        self.world_size = world_size
        self.master_addr = master_addr
        self.master_port = master_port
        self.restart_count = restart_count
        self.max_restarts = max_restarts


def _wrap(local_rank, ret_vals, dist_infos, fn, args):
    info = dist_infos[local_rank]
    os.environ["LOCAL_RANK"] = str(local_rank)
    os.environ["RANK"] = str(info.rank)
    os.environ["GROUP_RANK"] = str(info.group_rank)
    os.environ["LOCAL_WORLD_SIZE"] = str(info.local_world_size)
    os.environ["WORLD_SIZE"] = str(info.world_size)
    os.environ["MASTER_ADDR"] = info.master_addr
    os.environ["MASTER_PORT"] = str(info.master_port)
    os.environ["TORCHELASTIC_RESTART_COUNT"] = str(info.restart_count)
    os.environ["TORCHELASTIC_MAX_RESTARTS"] = str(info.max_restarts)
    ret = fn(*args)
    ret_vals[info.rank] = ret


class LocalElasticAgent(SimpleElasticAgent):
    """
    一个处理host-local workers的 Torchelastic.agent.server.ElasticAgent 的实现。
    这个agent部署在每个主机上，并配置为 n 个工作线程。当使用 gpu 时，n 为主机上可用的 gpu数量。
    An implementation of :py:class:`torchelastic.agent.server.ElasticAgent`
    that handles host-local workers.
    This agent is deployed per host and is configured to spawn ``n`` workers.
    When using GPUs, ``n`` maps to the number of GPUs available on the host.

    本地agent不与部署在其他主机上的其他本地agent通信，即使workers可以在主机间通信。
    worker id 被解释为本地进程。agent作为一个单元启动和停止所有工作进程。
    The local agent does not communicate to other local agents deployed on
    other hosts, even if the workers may communicate inter-host. The worker id
    is interpreted to be a local process. The agent starts and stops all worker
    processes as a single unit.

    传递给worker函数的工作者函数和参数必须与 python 多处理兼容。
    要将多处理数据结构传递给worker线程，您可以在与指定的 start _ method 相同的多处理上下文中创建数据结构，并将其作为函数参数传递。
    The worker function and argument passed to the worker function must be
    python multiprocessing compatible. To pass multiprocessing data structures
    to the workers you may create the data structure in the same multiprocessing
    context as the specified ``start_method`` and pass it as a function argument.

    Example

    ::

        def trainer(shared_queue):
            pass

        def main():
            start_method="spawn"
            shared_queue= multiprocessing.get_context(start_method).Queue()
            spec = WorkerSpec(
                        role="trainer",
                        local_world_size=nproc_per_process,
                        fn=trainer,
                        args=(shared_queue,),
                        ...<OTHER_PARAMS...>)
            agent = LocalElasticAgent(spec, start_method)
            agent.run()
    """

    def __init__(self, spec: WorkerSpec, start_method="spawn"):
        super().__init__(spec)
        self._start_method = start_method
        # pyre-fixme[8]: Attribute has type `ProcessContext`; used as `None`.
        self._process_context: mp.ProcessContext = None
        # a map that holds return values for each worker fn
        # ret_val[0] holds the return value for worker_0 (global rank 0)
        self._manager = mp.get_context(start_method).Manager()
        self._ret_vals = self._manager.dict()

    @prof
    def _stop_workers(self, worker_group: WorkerGroup) -> None:
        for proc in self._process_context.processes:
            if proc.is_alive():
                proc.terminate()
            proc.join()

    @prof
    def _start_workers(self, worker_group: WorkerGroup) -> Dict[int, Any]:
        spec = worker_group.spec
        store = worker_group.store
        master_addr, master_port = super()._get_master_addr_port(store)
        restart_count = spec.max_restarts - self._remaining_restarts

        dist_infos: Dict[int, _DistInfo] = {}
        for worker in worker_group.workers:
            local_rank = worker.local_rank
            dist_infos[local_rank] = _DistInfo(
                worker.global_rank,
                worker_group.group_rank,
                worker_group.spec.local_world_size,
                worker.world_size,
                master_addr,
                master_port,
                restart_count,
                spec.max_restarts,
            )

        self._ret_vals.clear()
        self._process_context = mp.start_processes(
            fn=_wrap,
            args=(self._ret_vals, dist_infos, spec.fn, spec.args),
            nprocs=spec.local_world_size,
            join=False,
            daemon=False,
            start_method=self._start_method,
        )

        return {
            local_rank: pid
            for local_rank, pid in enumerate(self._process_context.pids())
        }

    @prof
    def _monitor_workers(self, worker_group: WorkerGroup) -> MonitorResult:
        role = worker_group.spec.role

        '''
        torch进程上下文join()并不是传统意义上的真正的join，
        如果所有的worker都成功完成，它将返回True，
        如果一些/所有的worker都还在运行，它将返回False，并在一些/所有的worker都失败时抛出一个异常，
        传递timeout < 0表示检查worker状态并立即返回
        '''
        # torch process context join() isn't really a join in the
        # traditional sense, it returns True if all the workers have
        # successfully finished, False if some/all are still running
        # and throws an Exception if some/all of them failed
        # passing timeout < 0 means check worker status and return immediately

        worker_pids = {w.id for w in worker_group.workers}
        pc_pids = set(self._process_context.pids())
        if worker_pids != pc_pids:
            log.error(f"[{role}] worker pids do not match process_context pids")
            return MonitorResult(WorkerState.UNKNOWN)

        try:
            if self._process_context.join(timeout=-1):
                # copy ret_vals since we do not want to return an mp map
                return MonitorResult(WorkerState.SUCCEEDED, dict(self._ret_vals))
            else:
                return MonitorResult(WorkerState.HEALTHY)
        except Exception as e:
            log.exception(f"[{role}] Worker group failed")
            return MonitorResult(
                WorkerState.FAILED,
                exceptions={w.global_rank: e for w in worker_group.workers},
            )
