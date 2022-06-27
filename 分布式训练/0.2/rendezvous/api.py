#!/usr/bin/env/python3

# Copyright (c) Facebook, Inc. and its affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

import abc
from typing import Tuple


class RendezvousClosedException(Exception):
    """
    当关闭指定run_id的集合时将引发。这用于向延迟到达的节点发送完成信号.
    Raised when a rendezvous for the specified run_id is closed.
    This is used to signal completion to nodes that arrive late.
    """

    pass


class RendezvousTimeoutException(Exception):
    """
    从``rendezvous.next_rendezvous()``引发，
    以表示在分配的时间内rendezvous未成功。这意味着将被解释为不可重试的故障类型。
    Raised from ``RendezvousHandler.next_rendezvous()`` to signal that the
    rendezvous did not
    succeed within the allocated time. This is meant to be interpreted
    as a non-retryable type of failure.
    """

    pass


class RendezvousNonRetryableError(Exception):
    """
    当发生不应该用同一工作进程重试的失败时，从“rendezvous shandler”的任何函数中引发。
    Raised from any of the ``RendezvousHandler`` methods when a failure
    occured that should not be retried with the same worker process.
    """

    pass


class RendezvousHandler(abc.ABC):
    """
    rendezvous主接口
    注意:torchelastic使用者通常**不**需要执行他们自己的RendezvousHandler。
        基于etcd的实现已经提供，并且推荐给大多数使用者，前提是他们可以在自己的环境中部署它。
    警告：torchelastic目前被认为是实验性的，所以api可能会改变

    Main rendezvous interface.
    .. note:: torchelastic users normally **do not** need to implement their
              own ``RendezvousHandler``. An implementation based on
              `etcd <https://etcd.io/>`__ is already provided, and is recommended
              for most users, provided they can deploy it in their environment.

    .. warning:: torchelastic is currently considered experimental,
                 so the APIs may change!
    """

    @abc.abstractmethod
    # pyre-fixme[11]: Annotation `Store` is not defined as a type.
    def next_rendezvous(self) -> Tuple["torch.distributed.Store", int, int]:
        """
        rendezvous barrier()的主要入口。
        阻塞，直到rendezvous完成(当前进程包含在形成的worker group中)，或发生超时，或rendezvous被标记为关闭。

        返回值:一个元组(``c10d Store``, ``rank``, ``world size``)
        raises:
            RendezvousClosedException - 如果当前作业的rendezvous已关闭
            RendezvousTimeoutException - 超时


        Main entry-point into the rendezvous barrier.
        Blocks until the rendezvous is complete (and the current
        process is included in the formed worker group), or a timeout occurs, or
        rendezvous was marked closed.

        Returns: a tuple of (``c10d Store``, ``rank``, ``world size``)

        Raises:
            RendezvousClosedException - if rendezvous for the current
               job is closed.
            RendezvousTimeoutException - on timeout
        """
        pass

    @abc.abstractmethod
    def is_closed(self) -> bool:
        """
        检查当前job的rendezvous是否已经关闭，这意味着所有未来重新re-rendezvous的尝试(在同一job内)将失败。
        注意: ``is_closed``和``set_closed`` 具有最终传播的语义，不应该用于同步。
        这里的目的是，如果至少有一个worker决定工作已经完成，它将关闭rendezvous，其他worker将很快观察到这一点，并停止训练/rendezvous。

        Checks whether rendezvous for current job has been closed,
        which means all future attempts to re-rendezvous (within same job) will
        fail.

        .. note:: ``is_closed`` and ``set_closed`` have semantics of eventual
                  propagation, and should not be used for synchronization.
                  The intention here is that if at least one worker decides
                  the job is finished, it will close the rendezvous, and
                  other workers will soon observe this and stop
                  training/rendezvous-ing as well.
        """
        pass

    @abc.abstractmethod
    def set_closed(self):
        """
        用于将rendezvous(当前job)标记为关闭。
        Used to mark the rendezvous (for current job) as closed.
        """
        pass

    @abc.abstractmethod
    def num_nodes_waiting(self) -> int:
        """
        返回晚到rendezvous barrier的worker的数量，因此不包括在当前的worker group中。
        调用方应该定期调用此方法，以检查是否有新成员在等待加入作业，
        如果是，则通过调用 next_rendezvous() (re-rendezvous)来允许它们加入作业。

        Returns number of workers who *arrived late* at
        the rendezvous barrier, hence weren’t included in the current worker
        group.

        Callers should periodically call this method to check whether
        new members are waiting to join the job and if so admit them by
        calling ``next_rendezvous()`` (re-rendezvous).
        """
        pass
