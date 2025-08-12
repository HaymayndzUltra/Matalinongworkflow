ModelOps Coordinator – Implementation Blueprint
Author : O3-Pro Architecture Group | Revision : 2025-08-07
Target Environment : Dual-machine cluster (main_pc, pc2) – Python 3.10+
1. High-Level Overview
ModelOps Coordinator (MOC) unifies six legacy agents that separately handled model lifecycle, inference routing, VRAM optimisation, learning workflows, request fan-out, and goal management.
Legacy agents merged ➝ ModelManagerSuite, ModelOrchestrator, VRAMOptimizerAgent, RequestCoordinator, GoalManager, LearningOrchestrationService.
Consolidated Responsibilities
Lifecycle Management – load / unload / warm-up models on demand.
Inference Gateway – receive requests, apply circuit-breaker & bulkhead, dispatch to model workers.
GPU Resource Scheduler – track VRAM, allocate / evict models, coordinate with CrossMachineGPUScheduler.
Goal & Learning Orchestration – schedule fine-tuning / reinforcement jobs, prioritise according to active goals.
Observability & Self-Healing – expose health metrics, retry failed loads, hot-swap models when degraded.
Architecture Pattern: Modular Micro-kernel
Kernel provides concurrency primitives and shared telemetry.
Plug-in managers: LifecycleModule, InferenceModule, GPUManager, LearningModule, GoalModule.
Transport façades: gRPC & ZMQ; HTTP REST kept only for external dashboards.

2. Directory & File Layout

model_ops_coordinator/
├── __init__.py
├── app.py                       # bootstrap & CLI
├── config/
│   ├── default.yaml
│   ├── main_pc.yaml
│   └── pc2.yaml
├── core/
│   ├── kernel.py                # micro-kernel
│   ├── lifecycle.py             # model load/unload
│   ├── inference.py             # request routing
│   ├── gpu_manager.py           # VRAM accounting
│   ├── learning.py              # training / fine-tune jobs
│   ├── goal_manager.py          # goal prioritisation
│   ├── telemetry.py             # Prometheus metrics
│   ├── schemas.py               # Pydantic & Protobuf DTOs
│   └── errors.py
├── adapters/
│   ├── local_worker.py          # executes model inference locally
│   ├── remote_worker.py         # gRPC client to external GPU nodes
│   └── scheduler_client.py      # CrossMachineGPUScheduler gRPC stub
├── resiliency/
│   ├── circuit_breaker.py
│   └── bulkhead.py
├── transport/
│   ├── zmq_server.py
│   ├── grpc_server.py
│   └── rest_api.py              # optional FastAPI for dashboards
├── proto/
│   └── model_ops.proto          # service definition
├── requirements.txt
└── README.md

3. Dependencies & Best-Practice Hooks
requirements.txt

pydantic==1.10.13
pyzmq==26.0.3
grpcio==1.63.0
grpcio-tools==1.63.0
fastapi==0.111.0
uvicorn==0.29.0
prometheus-client==0.20.0
tenacity==8.2.3
torch==2.3.0                # inference workers
psutil==5.9.8
gpustat==1.1.1
redis==5.0.1

Hook-ins from Best-Practice Inventory
@retry_with_backoff – wrap all outbound I/O (GPU scheduler, workers).
Canonical CircuitBreaker & Bulkhead.
Named ThreadPoolExecutor (pattern #5) in kernel.
UnifiedConfigLoader & PathManager.
Pydantic models for DTOs (schemas.py).
4. Configuration Schema (config/default.yaml)

title: ModelOpsCoordinatorConfig
version: 1.0

server:
  zmq_port: 7211
  grpc_port: 7212
  rest_port: 8008
  max_workers: 16              # ThreadPool for inference

resources:
  gpu_poll_interval: 5         # seconds
  vram_soft_limit_mb: 22000
  eviction_threshold_pct: 90

models:
  preload:
    - name: "llama-7b-chat"
      path: "/models/llama-7b-chat.gguf"
      shards: 1
    - name: "whisper-base"
      path: "/models/whisper-base.bin"
      shards: 1
  default_dtype: "float16"
  quantization: true

learning:
  enable_auto_tune: true
  max_parallel_jobs: 2
  job_store: "${LEARNING_STORE:/workspace/learning_jobs.db}"

goals:
  policy: "priority_queue"     # or "round_robin"
  max_active_goals: 10

resilience:
  circuit_breaker:
    failure_threshold: 4
    reset_timeout: 20
  bulkhead:
    max_concurrent: 64
    max_queue_size: 256

Host overrides only change ports, GPU limits, or preload list.
5. Class-Level Design
5.1 Kernel (core/kernel.py)

class Kernel:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.executor = ThreadPoolExecutor(
            max_workers=cfg.server.max_workers,
            thread_name_prefix='ModelOpsWorker'
        )
        self.metrics = Telemetry()
        # dependency graph
        self.gpu_manager = GPUManager(cfg, self.metrics)
        self.lifecycle = LifecycleModule(cfg, self.gpu_manager, self.metrics)
        self.inference = InferenceModule(cfg, self.lifecycle, self.metrics)
        self.learning = LearningModule(cfg, self.lifecycle, self.metrics)
        self.goals = GoalModule(cfg, self.learning, self.metrics)

All modules share a reference to Telemetry (Prometheus counters, histograms).
5.2 GPU Manager (core/gpu_manager.py)
Polls gpustat every gpu_poll_interval secs.
Maintains VRAM allocation map in Redis for cross-process visibility.
Algorithm: First-Fit with eviction when usage ≥ eviction_threshold_pct.
Sends eviction events to lifecycle when needed.
5.3 Lifecycle Module (core/lifecycle.py)

class LifecycleModule:
    def load(self, model_cfg: ModelConfig) -> ModelHandle: ...
    def unload(self, model_name: str) -> None: ...
    def ensure_loaded(self, model_name: str) -> ModelHandle: ...

Uses CircuitBreaker around heavy load/unload.
Registers loaders in _loaders dict keyed by framework (Llama.cpp, HF Transformers).
Preloads models specified in config at boot (async gather).
5.4 Inference Module (core/inference.py)

@bulkhead_guard
async def infer(self, request: InferenceRequest) -> InferenceResponse:
    handle = await self.lifecycle.ensure_loaded(request.model)
    # futures executed in kernel.executor
    result = await asyncio.get_event_loop().run_in_executor(
        self.kernel.executor, handle.run, request.payload
    )
    return result

Adds Pydantic validation, Retry decorator for remote worker dispatch.
Supports batch inference (micro-batching by request id).
5.5 Learning Module (core/learning.py)
Manages fine-tune or RLHF jobs.
Uses SQLite job store; job status tracked with Enum.
Can schedule job on local GPU or delegate via scheduler_client.py.
5.6 Goal Module (core/goal_manager.py)
PriorityQueue of goals with weights; pops goals into learning module.
Exposes CRUD for goal entities.
5.7 Telemetry (core/telemetry.py)
Prometheus counters: inference_requests_total, model_load_latency_seconds, etc.
Gauges for gpu_vram_used_mb, active_models.
5.8 Error Handling (core/errors.py)
Custom exceptions: ModelLoadError, GPUUnavailable, JobFailed.
6. Transport Layer
Channel	Tech	Purpose	Port
gRPC	Bi-directional streaming	High-throughput inference / admin ops	7212
ZeroMQ (REQ/REP)	Compatibility façade for legacy agents	7211	
FastAPI (REST)	Dashboard, Prometheus /metrics, healthcheck	8008	
6.1 transport/grpc_server.py
Generated from proto/model_ops.proto

service ModelOps {
  rpc Infer (InferenceRequest) returns (InferenceResponse);
  rpc LoadModel (ModelLoadRequest) returns (ModelLoadReply);
  rpc UnloadModel (ModelUnloadRequest) returns (ModelUnloadReply);
  rpc ListModels (google.protobuf.Empty) returns (ModelList);
}

Streaming Infer supports client-side batches.
6.2 transport/zmq_server.py
Wrap messages { "action": "infer", "payload": {…} }
Utilises common/net/zmq_client.py wrapper.
6.3 transport/rest_api.py
Endpoints: /health, /metrics, /goals/*, /learning/jobs/*, using FastAPI.
7. Bootstrap & Entry-Point (app.py)

def main():
    cfg = UnifiedConfigLoader(
        base_path=Path(__file__).parent / 'config',
        env_prefix='MOC_'
    ).load()

    kernel = Kernel(cfg)

    # Start servers concurrently
    asyncio.run(start_servers(cfg, kernel))


async def start_servers(cfg, kernel):
    tasks = [
        start_grpc(cfg, kernel),
        start_zmq(cfg, kernel),
        start_rest(cfg, kernel),
    ]
    await asyncio.gather(*tasks)

Graceful shutdown via asyncio.Event, SIGTERM handlers flush executor and save job states.
8. Development & Deployment Steps
Scaffold directory tree: mkdir model_ops_coordinator && cd model_ops_coordinator.
Copy best-practice modules: bulkhead.py, circuit_breaker.py, network_util.py.
Write proto file and compile

   python -m grpc_tools.protoc -Iproto --python_out=model_ops_coordinator/ --grpc_python_out=model_ops_coordinator/ proto/model_ops.proto

Create requirements.txt and install: pip install -r requirements.txt.
Implement modules in core/, ensuring mypy --strict passes.
Unit Tests with pytest: lifecycle, GPU manager mock, inference path.
Integration Test: send 500 concurrent gRPC Infer calls, expect < 50 ms p95.
Containerize: build Docker image using multi-stage build (python:3.10-slim ➝ production).
Deploy two replicas per host via docker-compose or Kubernetes; expose ports via internal service.
Cut-over: update environment variables of dependent agents to new ports; retain old ZMQ schema.
9. Risk Mitigation Checklist ✅
Risk	Mitigation
VRAM fragmentation	GPU Manager defrag algorithm & pre-allocation hints
Model load storms on startup	Exponential backoff + load queue with max concurrency 2
Deadlocks in ThreadPool	Separate executor for blocking I/O vs compute; set thread_name_prefix
Cross-machine GPU contention	Redis-backed lease with TTL; CrossMachineGPUScheduler arbitration
Inference latency spikes	Micro-batch + bulkhead; auto-scale replicas based on inference_requests_total
Training jobs starving inference	LearningModule respects max_parallel_jobs and GPU quotas; priority inversion alert
10. Final Verification Gate
Static Lint / Type: ruff, flake8, mypy strict – no warnings.
Benchmark: 1 k rps mixed Infer + 50 model loads – CPU < 65 %, VRAM utilisation ≤ soft limit, p99 < 120 ms.
HA Test: Kill primary replica, ensure second handles traffic seamlessly (Prometheus http_requests_total continuity).
Rollback Simulation: Toggle feature flag to fall back on legacy ModelManagerSuite; verify zero-downtime.
Security: gRPC TLS enabled; REST endpoints protected by OAuth proxy; secrets loaded via env_helpers.
Documentation: generated OpenAPI spec, gRPC markdown, and Prometheus metrics list stored in docs/.
All checks ✅ → ModelOps Coordinator ready; decommission six superseded agents.
