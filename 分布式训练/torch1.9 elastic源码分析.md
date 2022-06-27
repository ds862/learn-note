# torch1.9 elastic源码分析

### run.py

torch/distributed/run.py

```python
if __name__ == "__main__":
	main()
      |
      |
      |
      v
def main(args=None):
	args = parse_args(args)
	run(args)
      |
      |
      |
      v
def run(args):
    if args.standalone:
        log.info(
            f"\n**************************************\n"
            f"Rendezvous info:\n"
            f"--rdzv_backend={args.rdzv_backend} "
            f"--rdzv_endpoint={args.rdzv_endpoint} "
            f"--rdzv_id={args.rdzv_id}\n"
            f"**************************************\n"
        )
    config, cmd, cmd_args = config_from_args(args)
 ***elastic_launch***(config=config, entrypoint=cmd, )(*cmd_args)
      |
      |
      |
      v
./launcher/api.py 
```

### launcher.api

torch/distributed/launcher/api.py 

```python
./launcher/api.py 
      |
      |
      |
      v
class elastic_launch:
        def __init__(
        self,
        config: LaunchConfig,
        entrypoint: Union[Callable, str, None],
    ):
        self._config = config
        self._entrypoint = entrypoint

    def __call__(self, *args, **kwargs):
        ***return launch_agent(self._config, self._entrypoint, list(args))***
                     |
                     |
       —— —— —— —— ——     
      |
      v
def launch_agent(
    config: LaunchConfig,
    entrypoint: Union[Callable, str, None],
    args: List[Any],
) -> Dict[int, Any]:
    if not config.run_id:
        ...
    entrypoint_name = _get_entrypoint_name(entrypoint, args)
    logger.info(
        f"Starting elastic_operator with launch configs:\n"
        f"  entrypoint      : {entrypoint_name}\n"   # (就是训练脚本) 
        f"  min_nodes        : {config.min_nodes}\n" 
        f"  max_nodes        : {config.max_nodes}\n"
        f"  nproc_per_node   : {config.nproc_per_node}\n" 
        f"  run_id           : {config.run_id}\n"   # 本次训练任务的id(用户自定义)
        f"  rdzv_backend     : {config.rdzv_backend}\n" # c10d
        f"  rdzv_endpoint    : {config.rdzv_endpoint}\n" # ip:端口号，如192.168.1.109:29400
        ...
    )
    # from torch.distributed.elastic.rendezvous import RendezvousParameters
    rdzv_parameters = RendezvousParameters(    
        backend=config.rdzv_backend,
        endpoint=config.rdzv_endpoint,
        ...
    )
    agent = None
    # import torch.distributed.elastic.rendezvous.registry as rdzv_registry
 ***rdzv_handler = rdzv_registry.get_rendezvous_handler(rdzv_parameters)***   —— —— > elastic.rendezvous.api
    # —— —— >  return handler_registry.create_handler(params) (from .api import rendezvous_handler_registry as handler_registry) —— —— > def create_handler(self, params: RendezvousParameters) -> RendezvousHandler: return handler
    master_addr, master_port = _get_addr_and_port(rdzv_parameters)
    try:
        spec = WorkerSpec(        —— —— —— —— —— —— —— —— —— —— —— > elastic.agent.server.api
            role=config.role,
            local_world_size=config.nproc_per_node,
            ***rdzv_handler=rdzv_handler,***
            ...
        )
        # from torch.distributed.elastic.agent.server.local_elastic_agent import LocalElasticAgent
        # class LocalElasticAgent(SimpleElasticAgent):
        ***agent = LocalElasticAgent(  —— —— —— —— —— —— —— —— —— —— > elastic.agent.server.local_elastic_agent
            spec=spec, start_method=config.start_method, log_dir=config.log_dir
        )***
        # torch.distributed.elastic.agent.server.api
        ***result = agent.run()***    —— —— —— —— —— —— —— —— —— —— —— —— —— —— —— 
        events.record(agent.get_agent_status_event(WorkerState.SUCCEEDED))        | 
        if result.is_failed():                                                    |
    except ChildFailedError:                                                      |  
    except Exception:                                                             | 
    finally:                                                                      |
        rdzv_handler.shutdown()                                                   v
                                                                     elastic.agent.server.api
```



### distributed.elastic.agent.server.api

torch/distributed/elastic/agent/server/api.py 

```python
class SimpleElasticAgent(ElasticAgent):
    def run(self, role: str = DEFAULT_ROLE) -> RunResult:
        start_time = time.monotonic()
        try:
        *** result = self._invoke_run(role) ***
            return result       |
        finally:                |
            self._shutdown()    |
                                |
                                v
    def _invoke_run(self, role: str = DEFAULT_ROLE) -> RunResult:
    *** self._initialize_workers(self._worker_group) ***
        monitor_interval = spec.monitor_interval
        rdzv_handler = spec.rdzv_handler

        while True:
            assert self._worker_group.state != WorkerState.INIT
            time.sleep(monitor_interval)
            run_result = self._monitor_workers(self._worker_group)
            state = run_result.state
            self._worker_group.state = state

            put_metric(f"workers.{role}.remaining_restarts", self._remaining_restarts)
            put_metric(f"workers.{role}.{state.name.lower()}", 1)

            if state == WorkerState.SUCCEEDED:
                log.info(
                    f"[{role}] worker group successfully finished."
                    f" Waiting {self._exit_barrier_timeout} seconds for other agents to finish."
                )
                self._exit_barrier()
                return run_result
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
                    self._exit_barrier()
                    return run_result
            elif state == WorkerState.HEALTHY:
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
                
                
    def _initialize_workers(self, worker_group: WorkerGroup) -> None:
        self._rendezvous(worker_group) 

        log.info(f"[{role}] Starting worker group")
        worker_ids = self._start_workers(worker_group)
        for local_rank, w_id in worker_ids.items():
            worker = worker_group.workers[local_rank]
            worker.id = w_id

        worker_group.state = WorkerState.HEALTHY
        
        
    def _rendezvous(self, worker_group: WorkerGroup) -> None:
        r"""
        Runs rendezvous for the workers specified by worker spec.
        Assigns workers a new global rank and world size.
        Updates the rendezvous store for the worker group.
        """

        spec = worker_group.spec

        ***store, group_rank, group_world_size = spec.rdzv_handler.next_rendezvous()***
        self._store = store

        ***workers = self._assign_worker_ranks(store, group_rank, group_world_size, spec)***
        worker_group.workers = workers
        worker_group.store = store
        worker_group.group_rank = group_rank
        worker_group.group_world_size = group_world_size

        if group_rank == 0:
            self._set_master_addr_port(store, spec.master_addr, spec.master_port)
        master_addr, master_port = self._get_master_addr_port(store)
        restart_count = spec.max_restarts - self._remaining_restarts

        log.info(
            f"[{spec.role}] Rendezvous complete for workers. Result:\n"
            f"  restart_count={restart_count}\n"
            f"  master_addr={master_addr}\n"
            f"  master_port={master_port}\n"
            f"  group_rank={group_rank}\n"
            f"  group_world_size={group_world_size}\n"
            f"  local_ranks={[worker.local_rank for worker in workers]}\n"
            f"  role_ranks={[worker.role_rank for worker in workers]}\n"
            f"  global_ranks={[worker.global_rank for worker in workers]}\n"
            f"  role_world_sizes={[worker.role_world_size for worker in workers]}\n"
            f"  global_world_sizes={[worker.world_size for worker in workers]}\n"
        )
```

