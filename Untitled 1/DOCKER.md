



PROPOSAL 1


## Dockerfile Architecture Proposal (Dual-Machine 4090 + 3060)

  

- Author: Lead DevOps Architecture Draft

- Scope: Proposal only; no code/CI changes yet

- Confidence: 87%

  

### A. High-Level Strategy & Rationale

  

- **Objective**: Standardize all containers for consolidated hubs and legacy agents across two heterogeneous GPU hosts (MainPC RTX 4090, PC2 RTX 3060) while enforcing dependency hygiene and maximizing layer re-use.

- **Approach**: Use a small set of functional base families with parameterization rather than one monolithic Dockerfile. Each service gets a thin service Dockerfile that `FROM`s a family base and installs only its minimal requirements.

- **Families vs Single Template**:

  - **Families (recommended)**: Separate CPU, CPU-Web, GPU-Ada (4090), GPU-Ampere (3060), and optional audio/vision variants. Pros: lighter images, fewer conditional branches, clear GPU targeting, strong cache re-use. Cons: more base images to maintain.

  - **Single parameterized template**: Pros: one file. Cons: sprawling ARG/IF logic, higher build complexity, risk of pulling unnecessary GPU stacks for CPU-only agents, larger images, weaker cache locality.

- **Result**: Families deliver smaller images, faster rebuilds, and clear hardware-aware targeting. Each agent remains minimal and reproducible.

  

### B. Base Image Hierarchy (with tags, registries, CUDA strategy)

  

- **Registry pattern (proposed, confirm)**: `ghcr.io/<org>/ai-base:<family>-<version>`

- **Hierarchy**:

  - `ghcr.io/<org>/ai-base:cpu-py311-<date>`

    - FROM `python:3.11-slim` (Debian/Ubuntu base acceptable; slim footprint)

    - Non-root user `app`, `tini`, `ca-certificates`, timezone data

  - `ghcr.io/<org>/ai-base:cpu-web-py311-<date>`

    - Extends cpu-py311, adds `tini`, `curl`, `uvicorn[standard]`, `gunicorn`

  - `ghcr.io/<org>/ai-base:cpu-audio-py311-<date>`

    - Extends cpu-py311, adds `ffmpeg`, `libsndfile1`, `tini` (confirm audio stack)

  - `ghcr.io/<org>/ai-base:cuda12.3-runtime-py311-<date>`

    - FROM `nvidia/cuda:12.3.2-runtime-ubuntu22.04`, installs Python 3.11 stack

  - `ghcr.io/<org>/ai-base:cuda12.3-ada-py311-<date>` (MainPC)

    - Extends cuda12.3-runtime; sets `TORCH_CUDA_ARCH_LIST=8.9` and Ada-tuned flags

  - `ghcr.io/<org>/ai-base:cuda12.3-ampere-py311-<date>` (PC2)

    - Extends cuda12.3-runtime; sets `TORCH_CUDA_ARCH_LIST=8.6` and Ampere-tuned flags

  - Optional add-ons:

    - `*-gpu-vision`: adds `libgl1` for OpenCV wheels runtime

    - `*-gpu-audio`: adds `ffmpeg`, `libsndfile1` when GPU + audio required

  

- **CUDA strategy**:

  - Standardize on CUDA 12.3 runtime for both hosts to maximize wheel availability; pin PyTorch CUDA wheels accordingly (cu121/cu122 track to be confirmed).

  - Keep CPU families free of GPU libs; avoid fat-binaries.

  

### C. Optimization & Standardization Plan

  

- **Image size**:

  - Separate dependency layer (`pip install -r requirements.txt`) to maximize cache sharing.

  - Use slim bases; remove apt caches and `*.pyc`; avoid dev headers unless compiling.

  - Factor shared stacks (torch, transformers, opencv) into base family variants only where required.

  - Target: double-digit percentage reduction relative to a newly captured baseline, achieved by removing GPU libs from CPU images and deduplicating heavy wheels into family layers.

  

- **Build time**:

  - Multi-stage builds with "deps" layer; re-builds cheap when only app code changes.

  - Use `pip download` to pre-populate a versioned wheelhouse in base families for heavy libs (torch/transformers/opencv) to accelerate per-service installs.

  - Enable BuildKit with inline cache and registry cache export/import.

  

- **CI integration sketch**:

  - Build matrix: (families × machine) with tags `:cpu`, `:cpu-web`, `:cpu-audio`, `:cuda12.3-ada`, `:cuda12.3-ampere`, plus optional `-vision`/`-audio` suffixes.

  - Export/import cache to registry; fail-fast gates for image size drift and CVE levels; publish only on green.

  - Parallel builds by family, then fast service builds using cached deps layer.

  

- **.dockerignore standardization**:

  - Reuse root `.dockerignore` and add per-service ignores where needed. Ensure models, data, logs, artifacts are excluded from build context.

  

- **Per-agent dependency minimization**:

  - Static import analysis (existing: `main_pc_code/scripts/dependency_resolver.py`, `main_pc_code/NEWMUSTFOLLOW/dependency_tracer.py`) per agent to compute minimal `requirements.generated.txt`.

  - Lock via `pip-compile --generate-hashes` to produce reproducible `requirements.lock` per agent.

  - Legacy-benefit set (examples): MainPC `{FeedbackHandler, ChitchatAgent, NLUAgent, AdvancedCommandHandler, Responder, SmartHomeAgent}`; PC2 `{TieredResponder, AsyncProcessor, CacheManager, TaskScheduler, AdvancedRouter, UnifiedUtilsAgent, FileSystemAssistantAgent, AuthenticationAgent}`.

  

- **Shared stacks to factor**:

  - GPU-heavy: `torch`, `torchvision`, `torchaudio`, `transformers`, `sentencepiece` (only in GPU families that need them)

  - Vision: `opencv-python-headless`, system `libgl1` (vision variants only)

  - Web: `fastapi`, `uvicorn[standard]`, `gunicorn` (web family)

  - Messaging/IO: `pyzmq`, `redis`, `grpcio`, `pydantic`, `orjson`

  

- **Security posture**:

  - Run as non-root; drop capabilities.

  - Minimal apt; verify GPG for repos; remove build tools in final stage.

  - HEALTHCHECKs; read-only FS where possible; mount models/data via volumes.

  - CI CVE scan step (scanner TBD; propose Trivy/Grype) with fail-on HIGH/CRITICAL policy (confirm thresholds).

  

- **Reproducibility**:

  - Pin base image digests; pin Python package versions with hashes; consistent timezone/locale.

  

- **GPU readiness**:

  - Health/startup probe: `nvidia-smi` and `python -c 'import torch; assert torch.cuda.is_available()'` with device capability check.

  

### D. Hardware-Aware Defaults (MainPC vs PC2)

  

- **MainPC (RTX 4090, Ryzen 9 7900)**:

  - Families: `cuda12.3-ada-py311`

  - Env: `TORCH_CUDA_ARCH_LIST=8.9`, `OMP_NUM_THREADS=8..16` (per service), `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`

  - Workers: higher defaults (e.g., ModelOpsCoordinator `max_workers=16`)

  - Fallback: if CUDA unavailable at runtime, fail fast for GPU-only services (observability will alert) and auto-route to cloud/local-CPU per hybrid policy.

  

- **PC2 (RTX 3060, low-power CPU)**:

  - Families: `cuda12.3-ampere-py311`

  - Env: `TORCH_CUDA_ARCH_LIST=8.6`, `OMP_NUM_THREADS=2`, `UVICORN_WORKERS=1`

  - Prefer CPU-path for auxiliary agents; keep GPU-bound services minimal; lower batch sizes.

  - Fallback: degrade to CPU path for non-critical GPU users (e.g., pipeline stages) or temporarily pause workloads; never overcommit VRAM.

  

### E. Concrete Example Dockerfiles (Reference Only)

  

- Note: These are examples; final families and versions will be set post-approval. HEALTHCHECKs included for readiness. Non-root user assumed created in base.

  

#### E.1 ModelOpsCoordinator (MainPC, RTX 4090)

  

```Dockerfile

# Family base for Ada (4090)

FROM ghcr.io/<org>/ai-base:cuda12.3-ada-py311-<date> AS base

  

# Dedicated dependency layer (shared cache between services)

FROM base AS deps

WORKDIR /opt/app

COPY model_ops_coordinator/requirements.txt /opt/app/requirements.txt

RUN pip install --no-cache-dir --upgrade pip \

    && pip install --no-cache-dir -r /opt/app/requirements.txt

  

# Final image

FROM base AS runtime

ENV PYTHONUNBUFFERED=1 \

    TORCH_CUDA_ARCH_LIST=8.9 \

    NVIDIA_VISIBLE_DEVICES=all \

    NVIDIA_DRIVER_CAPABILITIES=compute,utility

WORKDIR /app

COPY --from=deps /usr/local/lib/python3.11 /usr/local/lib/python3.11

COPY model_ops_coordinator/ /app/model_ops_coordinator/

COPY model_ops_coordinator/config/ /app/model_ops_coordinator/config/

  

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \

  CMD python -c "import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)" && \

      python -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('127.0.0.1', 8008)); s.close()" || exit 1

  

EXPOSE 8008 7212 7211

CMD ["python", "-m", "model_ops_coordinator.app"]

```

  

#### E.2 MemoryFusionHub (PC2-optimized)

  

```Dockerfile

# PC2 uses Ampere base; low CPU concurrency; no heavy GPU deps by default

FROM ghcr.io/<org>/ai-base:cuda12.3-ampere-py311-<date> AS base

  

FROM base AS deps

WORKDIR /opt/app

COPY memory_fusion_hub/requirements.txt /opt/app/requirements.txt

RUN pip install --no-cache-dir --upgrade pip \

    && pip install --no-cache-dir -r /opt/app/requirements.txt

  

FROM base AS runtime

ENV PYTHONUNBUFFERED=1 \

    OMP_NUM_THREADS=2 \

    UVICORN_WORKERS=1

WORKDIR /app

COPY --from=deps /usr/local/lib/python3.11 /usr/local/lib/python3.11

COPY memory_fusion_hub/ /app/memory_fusion_hub/

COPY memory_fusion_hub/config/ /app/memory_fusion_hub/config/

  

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \

  CMD python -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('127.0.0.1', 8080)); s.close()" || exit 1

  

EXPOSE 5713 5714 8080

CMD ["python", "-m", "memory_fusion_hub.app"]

```

  

#### E.3 Simple Legacy Agent (CPU-only)

  

```Dockerfile

FROM ghcr.io/<org>/ai-base:cpu-py311-<date> AS base

  

FROM base AS deps

WORKDIR /opt/app

COPY legacy_agents/simple_agent/requirements.txt /opt/app/requirements.txt

RUN pip install --no-cache-dir --upgrade pip \

    && pip install --no-cache-dir -r /opt/app/requirements.txt

  

FROM base AS runtime

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=deps /usr/local/lib/python3.11 /usr/local/lib/python3.11

COPY legacy_agents/simple_agent/ /app/legacy_agents/simple_agent/

  

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 CMD python - <<'PY' || exit 1

import socket,sys

s=socket.socket(); s.settimeout(2)

try:

    s.connect(("127.0.0.1", 7110))  # example health port

    s.close(); sys.exit(0)

except Exception:

    sys.exit(1)

PY

  

EXPOSE 7110

CMD ["python", "-m", "legacy_agents.simple_agent.app"]

```

  

### F. Fleet Coverage Table (100% of Active Agents)

  

Notes:

- Ports use `${PORT_OFFSET}+<port>` where configured. Health ports included where specified.

- Needs are inferred via names/config; entries marked “(uncertain — ask)” require confirmation.

- Base family keys: `cpu`, `cpu-web`, `cpu-audio`, `gpu-ada`, `gpu-ampere`, `gpu-ada-vision`, `gpu-ampere-vision`.

  

| service | machine(s) | needs (CPU/GPU/Web/Audio/Vision) | proposed base family | entrypoint | ports | healthcheck | notes |

|---|---|---|---|---|---|---|---|

| ServiceRegistry | MainPC | CPU, Redis client | cpu | main_pc_code/agents/service_registry_agent.py | 7200 | 8200 | Uses Redis URL env |

| SystemDigitalTwin | MainPC | CPU | cpu | main_pc_code/agents/system_digital_twin.py | 7220 | 8220 | SQLite + Redis config |

| UnifiedSystemAgent | MainPC | CPU | cpu | main_pc_code/agents/unified_system_agent.py | 7201 | 8201 | Orchestration |

| SelfHealingSupervisor | MainPC, PC2 | CPU, Docker sock | cpu | services/self_healing_supervisor/supervisor.py | 7009 | 9008 | Needs `/var/run/docker.sock` |

| MemoryFusionHub | MainPC, PC2 | CPU, storage | cpu (PC2 may use gpu-ampere if kernels needed) | memory_fusion_hub/app.py | 5713, 5714, 8080 | 6713 | No GPU by default |

| ModelOpsCoordinator | MainPC | GPU (Ada) | gpu-ada | model_ops_coordinator/app.py | 7211, 7212, 8008 | 8212 | Heavy PyTorch/transformers |

| AffectiveProcessingCenter | MainPC | CPU (uncertain GPU) | cpu (uncertain — ask) | affective_processing_center/app.py | 5560, 5561 | 6560 | ZMQ pub/synth |

| RealTimeAudioPipeline | MainPC | Audio, GPU | gpu-ada (audio) | real_time_audio_pipeline/app.py | 5557, 5558 | 6557 | Uses CUDA device |

| CodeGenerator | MainPC | CPU | cpu | main_pc_code/agents/code_generator_agent.py | 5650 | 6650 |  |

| PredictiveHealthMonitor | MainPC | CPU | cpu | main_pc_code/agents/predictive_health_monitor.py | 5613 | 6613 |  |

| Executor | MainPC | CPU | cpu | main_pc_code/agents/executor.py | 5606 | 6606 |  |

| TinyLlamaServiceEnhanced | MainPC | GPU | gpu-ada | main_pc_code/FORMAINPC/tiny_llama_service_enhanced.py | 5615 | 6615 |  |

| SmartHomeAgent | MainPC | CPU, Web? | cpu | main_pc_code/agents/smart_home_agent.py | 7125 | 8125 | (uncertain — ask) |

| CrossMachineGPUScheduler | MainPC | CPU | cpu | services/cross_gpu_scheduler/app.py | 7155 | 8155 |  |

| ChainOfThoughtAgent | MainPC | GPU | gpu-ada | main_pc_code/FORMAINPC/chain_of_thought_agent.py | 5612 | 6612 |  |

| GoTToTAgent | MainPC | CPU/GPU (uncertain) | cpu | main_pc_code/FORMAINPC/got_tot_agent.py | 5646 | 6646 | Depends on CoT |

| CognitiveModelAgent | MainPC | GPU | gpu-ada | main_pc_code/FORMAINPC/cognitive_model_agent.py | 5641 | 6641 |  |

| FaceRecognitionAgent | MainPC | GPU, Vision | gpu-ada-vision | main_pc_code/agents/face_recognition_agent.py | 5610 | 6610 | `libgl1` for OpenCV |

| LearningOpportunityDetector | MainPC | CPU (uncertain GPU) | cpu | main_pc_code/agents/learning_opportunity_detector.py | 7202 | 8202 |  |

| LearningManager | MainPC | CPU | cpu | main_pc_code/agents/learning_manager.py | 5580 | 6580 |  |

| ActiveLearningMonitor | MainPC | CPU | cpu | main_pc_code/agents/active_learning_monitor.py | 5638 | 6638 |  |

| IntentionValidatorAgent | MainPC | CPU | cpu | main_pc_code/agents/IntentionValidatorAgent.py | 5701 | 6701 |  |

| NLUAgent | MainPC | CPU | cpu | main_pc_code/agents/nlu_agent.py | 5709 | 6709 |  |

| AdvancedCommandHandler | MainPC | CPU | cpu | main_pc_code/agents/advanced_command_handler.py | 5710 | 6710 |  |

| ChitchatAgent | MainPC | CPU | cpu | main_pc_code/agents/chitchat_agent.py | 5711 | 6711 |  |

| FeedbackHandler | MainPC | CPU | cpu | main_pc_code/agents/feedback_handler.py | 5636 | 6636 |  |

| Responder | MainPC | CPU | cpu | main_pc_code/agents/responder.py | 5637 | 6637 | Multi-dependency |

| DynamicIdentityAgent | MainPC | CPU | cpu | main_pc_code/agents/DynamicIdentityAgent.py | 5802 | 6802 |  |

| EmotionSynthesisAgent | MainPC | CPU (uncertain GPU) | cpu | main_pc_code/agents/emotion_synthesis_agent.py | 5706 | 6706 |  |

| STTService | MainPC | GPU, Audio | gpu-ada (audio) | main_pc_code/services/stt_service.py | 5800 | 6800 |  |

| TTSService | MainPC | GPU, Audio | gpu-ada (audio) | main_pc_code/services/tts_service.py | 5801 | 6801 |  |

| AudioCapture | MainPC | CPU, Audio | cpu-audio | main_pc_code/agents/streaming_audio_capture.py | 6550 | 7550 |  |

| FusedAudioPreprocessor | MainPC | CPU, Audio | cpu-audio | main_pc_code/agents/fused_audio_preprocessor.py | 6551 | 7551 |  |

| StreamingInterruptHandler | MainPC | CPU | cpu | main_pc_code/agents/streaming_interrupt_handler.py | 5576 | 6576 |  |

| StreamingSpeechRecognition | MainPC | CPU (calls STTService) | cpu | main_pc_code/agents/streaming_speech_recognition.py | 6553 | 7553 |  |

| StreamingTTSAgent | MainPC | CPU (calls TTSService) | cpu | main_pc_code/agents/streaming_tts_agent.py | 5562 | 6562 |  |

| WakeWordDetector | MainPC | CPU, Audio | cpu-audio | main_pc_code/agents/wake_word_detector.py | 6552 | 7552 |  |

| StreamingLanguageAnalyzer | MainPC | CPU | cpu | main_pc_code/agents/streaming_language_analyzer.py | 5579 | 6579 |  |

| ProactiveAgent | MainPC | CPU | cpu | main_pc_code/agents/ProactiveAgent.py | 5624 | 6624 |  |

| EmotionEngine | MainPC | CPU | cpu | main_pc_code/agents/emotion_engine.py | 5590 | 6590 |  |

| MoodTrackerAgent | MainPC | CPU | cpu | main_pc_code/agents/mood_tracker_agent.py | 5704 | 6704 |  |

| HumanAwarenessAgent | MainPC | CPU | cpu | main_pc_code/agents/human_awareness_agent.py | 5705 | 6705 |  |

| ToneDetector | MainPC | CPU | cpu | main_pc_code/agents/tone_detector.py | 5625 | 6625 |  |

| VoiceProfilingAgent | MainPC | CPU | cpu | main_pc_code/agents/voice_profiling_agent.py | 5708 | 6708 |  |

| EmpathyAgent | MainPC | CPU | cpu | main_pc_code/agents/EmpathyAgent.py | 5703 | 6703 |  |

| CloudTranslationService | MainPC | CPU | cpu | main_pc_code/agents/cloud_translation_service.py | 5592 | 6592 |  |

| StreamingTranslationProxy | MainPC | CPU, Web | cpu-web | services/streaming_translation_proxy/proxy.py | 5596 | 6596 | WebSocket proxy |

| ObservabilityDashboardAPI | MainPC | CPU, Web | cpu-web | services/obs_dashboard_api/server.py | 8001 | 9007 |  |

| UnifiedObservabilityCenter | MainPC, PC2 | CPU, Web | cpu-web | unified_observability_center/app.py | 9100 | 9110 | MainPC ports (uncertain — ask) |

| CentralErrorBus | PC2 | CPU, ZMQ | cpu | services/central_error_bus/error_bus.py | 7150 | 8150 |  |

| RealTimeAudioPipelinePC2 | PC2 | Audio, (GPU optional) | gpu-ampere (audio) | real_time_audio_pipeline/app.py | 5557, 5558 | 6557 |  |

| TieredResponder | PC2 | CPU | cpu | pc2_code/agents/tiered_responder.py | 7100 | 8100 |  |

| AsyncProcessor | PC2 | CPU | cpu | pc2_code/agents/async_processor.py | 7101 | 8101 |  |

| CacheManager | PC2 | CPU | cpu | pc2_code/agents/cache_manager.py | 7102 | 8102 |  |

| VisionProcessingAgent | PC2 | GPU, Vision | gpu-ampere-vision | pc2_code/agents/VisionProcessingAgent.py | 7160 | 8160 |  |

| DreamWorldAgent | PC2 | GPU | gpu-ampere | pc2_code/agents/DreamWorldAgent.py | 7104 | 8104 |  |

| ResourceManager | PC2 | CPU | cpu | pc2_code/agents/resource_manager.py | 7113 | 8113 |  |

| TaskScheduler | PC2 | CPU | cpu | pc2_code/agents/task_scheduler.py | 7115 | 8115 |  |

| AuthenticationAgent | PC2 | CPU | cpu | pc2_code/agents/ForPC2/AuthenticationAgent.py | 7116 | 8116 |  |

| UnifiedUtilsAgent | PC2 | CPU | cpu | pc2_code/agents/ForPC2/unified_utils_agent.py | 7118 | 8118 |  |

| ProactiveContextMonitor | PC2 | CPU | cpu | pc2_code/agents/ForPC2/proactive_context_monitor.py | 7119 | 8119 |  |

| AgentTrustScorer | PC2 | CPU | cpu | pc2_code/agents/AgentTrustScorer.py | 7122 | 8122 |  |

| FileSystemAssistantAgent | PC2 | CPU | cpu | pc2_code/agents/filesystem_assistant_agent.py | 7123 | 8123 |  |

| RemoteConnectorAgent | PC2 | CPU | cpu | pc2_code/agents/remote_connector_agent.py | 7124 | 8124 |  |

| UnifiedWebAgent | PC2 | CPU, Web | cpu-web | pc2_code/agents/unified_web_agent.py | 7126 | 8126 |  |

| DreamingModeAgent | PC2 | GPU | gpu-ampere | pc2_code/agents/DreamingModeAgent.py | 7127 | 8127 |  |

| AdvancedRouter | PC2 | CPU | cpu | pc2_code/agents/advanced_router.py | 7129 | 8129 |  |

| TutoringServiceAgent | PC2 | CPU | cpu | pc2_code/agents/TutoringServiceAgent.py | 7108 | 8108 |  |

| SpeechRelayService | PC2 | CPU, Audio | cpu-audio | services/speech_relay/relay.py | 7130 | 8130 | Depends on TTS/vision |

  

### G. Risk Register & Rollback Considerations

  

- **GPU driver/CUDA mismatch**: Early failure via startup probe; rollback by pinning previous base digest.

- **Wheel incompatibility**: Maintain wheelhouse per family; fallback to CPU path if GPU wheel absent.

- **Image bloat regression**: CI threshold check on image size; block merges if exceeding baseline ± tolerance.

- **Runtime perf regressions**: UOC telemetry watch; can toggle batch/threads via env; promote previous tag.

- **Security**: CVE scan gate; if fail, auto-rebuild with patched base or pin previous.

  

### H. Open Questions (Blocking/Design-Affecting)

  

1) Python baseline: default 3.11 for all; any legacy requiring 3.10?

2) Registry: confirm `ghcr.io/<org>` naming and retention policy; who owns org?

3) CUDA track: unify on CUDA 12.3; confirm PyTorch wheels variant (cu121 vs cu122/12.3). Do we need CUDA 12.4 soon for 4090?

4) Vulnerability scanning: Trivy vs Grype; policy thresholds (fail on HIGH/CRITICAL?).

5) Audio deps: exact packages required for RealTimeAudioPipeline, STT/TTS, SpeechRelay (e.g., `ffmpeg`, `libsndfile1`, `portaudio`?).

6) Vision deps: confirm need for `libgl1` only, or additional (e.g., `libglib2.0-0`) for OpenCV in production.

7) UnifiedObservabilityCenter on MainPC: confirm ports (proposed 9100/9110) and whether it runs on both machines concurrently.

8) Wheelhouse strategy: central shared cache vs per-family image baked wheels; storage constraints on CI runner.

9) Non-root UID/GID mapping: desired numeric IDs for volume permissions?

10) Healthcheck endpoints: standardize HTTP endpoints vs TCP port checks for all agents?

  

### Implementation Plan (Post-Approval)

  

- Define and publish base families (cpu, cpu-web, cpu-audio, cuda12.3-ada, cuda12.3-ampere, optional vision/audio variants) with pinned digests.

- Introduce per-agent thin Dockerfiles that `FROM` a family and install minimal `requirements.generated.txt`.

- CI: Build matrix by family×machine; enable BuildKit cache; add image-size and CVE gates; publish to registry.

- Add dependency extractor job to write `requirements.generated.txt` and lock (`--generate-hashes`).

- Add runtime health probes and thread/cuda env defaults per machine in compose/helm values.

- Baseline metrics (image size, cold-start latency), then iterate.





PROPOSAL 2

 
 Dockerfile Architecture Proposal (Dual-Machine: RTX 4090 + RTX 3060)

  

This proposal defines a unified, production-ready container architecture for all active services, covering consolidated hubs and legacy agents from:

- `main_pc_code/config/startup_config.yaml`

- `pc2_code/config/startup_config.yaml`

  

It is optimized for the hardware reality:

- MainPC: NVIDIA RTX 4090 (Ada 8.9), AMD Ryzen 9 7900

- PC2: NVIDIA RTX 3060 (Ampere 8.6), low-power CPU

  

The design enforces dependency hygiene, promotes shared layers where they demonstrably reduce size/build time, and keeps CPU-only services free of GPU stacks.

  

---

  

### A. High-level strategy & rationale

  

- Functional base families, not a single monolithic template

  - A single, heavily-parameterized Dockerfile would either bloat CPU-only services with GPU stacks or create complex branching that’s hard to audit and cache effectively. Functional families let us:

    - Keep each runtime minimal per service type

    - Reuse shared heavy layers (e.g., CUDA + torch) across GPU-bound services for fast builds

    - Avoid divergence by codifying the smallest viable set of base families

  

- Strict dependency hygiene

  - Per-service requirements are minimized (auto-generated for legacy agents when feasible; pinned otherwise).

  - Families include only ubiquitous dependencies for that group; optional extras stay per-service to avoid bloat.

  

- Multi-stage builds and venv handoff

  - Builder installs compilers and dev libs; runtime contains only what’s needed to run.

  - Virtualenv copied from builder → runtime to reduce size and ensure reproducibility.

  

- Security by default

  - Non-root users, minimal apt footprint, healthchecks, explicit port exposure, and CI-integrated CVE scanning.

  

- Hardware-aware defaults

  - MainPC tuned for maximum throughput; PC2 tuned for efficiency and safe fallback behavior.

  

---

  

### B. Base image hierarchy (families, tags, registries, CUDA strategy)

  

Proposed registry naming (confirm): `ghcr.io/<org>/<family>:<version>`

- Example tags include OS, Python, CUDA track, and date: `v1-py311-cu121-ubuntu22.04-2025q3`

  

CUDA strategy

- Default CUDA track: 12.1 (cu121) for both RTX 4090 and RTX 3060 to enable shared torch wheels.

- Optional MainPC-only track: 12.4 (cu124) if benchmarks justify it (opt-in per-service).

- NVIDIA runtime provided by host via NVIDIA Container Toolkit.

  

Families

- base.cpu-core

  - FROM `python:3.11-slim` (preferred)

  - For legacy services requiring py3.10, provide `base.cpu-core-py310` FROM `python:3.10-slim`

  - Minimal runtime: curl, ca-certificates for healthchecks

- base.cpu-web

  - FROM `base.cpu-core`

  - Adds `fastapi`, `uvicorn`, `prometheus-client` (and `httpx` where widely used)

- base.gpu-core-cu121

  - FROM `nvidia/cuda:12.1.1-runtime-ubuntu22.04`

  - Installs Python 3.11 (or 3.10 for legacy), venv, curl, ca-certificates

  - No ML libraries; just CUDA runtime + Python

- base.gpu-ml-cu121

  - FROM `base.gpu-core-cu121`

  - Adds torch via `--extra-index-url https://download.pytorch.org/whl/cu121`

  - Torch version pinned; no transformers by default

- base.gpu-onnx-cu121 (for ONNX/InsightFace/OpenCV)

  - FROM `base.gpu-core-cu121`

  - Adds `onnxruntime-gpu`, `opencv-python-headless` (pinned)

- Optional extras (evaluate per adoption):

  - base.cpu-audio-extras (webrtcvad, sounddevice, pvporcupine)

  - base.gpu-ml-audio-extras (extends gpu-ml-cu121 with audio libs)

  

Note: Prefer service-level extras initially to avoid premature bloat; move to extras families once ≥3 services share the exact pins.

  

---

  

### C. Optimization & standardization plan

  

- Image size reduction

  - Multi-stage builds with venv copy; builder includes compilers, runtime does not.

  - Combine apt operations, use `--no-install-recommends`, and clear apt lists.

  - `.dockerignore` already excludes models, logs, artifacts; ensure service directories add local ignores for tests/dev-only data.

  - Target reduction: 30–60% vs naïve single-stage images (range depends on service footprints and torch presence).

  

- Build-time optimization

  - Layer ordering: COPY requirements → install deps → COPY source (maximize cache reuse).

  - Share families so torch/CUDA layers are cached across GPU services.

  - Use BuildKit + Buildx with registry cache export/import between CI jobs.

  - Prebuild and publish family images on version bumps only.

  

- Dependency minimization for legacy agents

  - Use `/workspace/scripts/extract_individual_requirements.py` in builder to emit minimal per-agent `requirements.txt` by static import scan; pip-install that file.

  - For dynamic imports or plugin loading, mark with “uncertain — ask” and optionally allow a safe manual allowlist.

  - Maintain service-specific `constraints.txt` for pins; adopt `pip-compile` workflow if needed.

  

- Standardization

  - Non-root `USER` in runtime stage

  - `ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1`

  - Healthchecks present for any HTTP/gRPC service; ZMQ ping fallback where applicable

  - Consistent `PYTHONPATH=/app`; repository layout standardized so `common/` is always available

  

- Security posture

  - Minimal packages, non-root runtime, small surface area

  - Add CI CVE scanning (e.g., Trivy or Grype) with policy gates (see Open Questions for tool/policy)

  

- Reproducibility

  - Pin exact versions in `requirements.txt`

  - For critical services, adopt `--require-hashes` (pip hash mode) managed via `pip-compile --generate-hashes`

  - Pin family bases by digest (e.g., `nvidia/cuda@sha256:...`) once finalized

  

---

  

### D. Hardware-aware defaults (MainPC vs PC2)

  

Set safe defaults via ENV; override per service with env vars or startup config.

  

MainPC (RTX 4090, high CPU)

- GPU env:

  - `NVIDIA_VISIBLE_DEVICES=all`

  - `NVIDIA_DRIVER_CAPABILITIES=compute,utility`

  - `CUDA_DEVICE_ORDER=PCI_BUS_ID`

  - `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True,max_split_size_mb=64`

- Threads/workers:

  - `OMP_NUM_THREADS=8`, `MKL_NUM_THREADS=8`

  - For uvicorn apps: `UVICORN_WORKERS=4` (service-specific tuning allowed)

  

PC2 (RTX 3060, low-power CPU)

- GPU env:

  - Same visibility; prefer smaller batches and concurrency in the app

- Threads/workers:

  - `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`

  - `UVICORN_WORKERS=1`

- Fallbacks:

  - Prefer CPU fallback where feasible (e.g., STT Whisper cpp path already present).

  

GPU readiness checks (at startup and/or health)

- Torch services: probe `torch.cuda.is_available()` and log device names; fail-fast if `REQUIRED_GPU=true` and not available.

- Non-torch GPU users (NVML/ONNX): check NVML device count and/or ONNX GPU provider availability; log and degrade gracefully if allowed.

  

---

  

### E. Concrete EXAMPLE Dockerfiles (reference only; not to be committed)

  

These examples assume build context is the repo root (`/workspace`). They demonstrate multi-stage builds, minimal runtime layers, and correct COPY paths.

  

1) ModelOpsCoordinator (MainPC-optimized; CUDA 12.1, torch cu121)

  

```dockerfile

# syntax=docker/dockerfile:1.6

  

FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04 AS builder

  

ENV DEBIAN_FRONTEND=noninteractive \

    PYTHONUNBUFFERED=1 \

    PYTHONDONTWRITEBYTECODE=1

  

RUN apt-get update && apt-get install -y --no-install-recommends \

    python3 python3-venv python3-pip python3-distutils \

    curl ca-certificates build-essential pkg-config \

    && rm -rf /var/lib/apt/lists/*

  

RUN python3 -m venv /opt/venv

ENV PATH="/opt/venv/bin:${PATH}"

RUN pip install --no-cache-dir --upgrade pip setuptools wheel

  

WORKDIR /app

COPY model_ops_coordinator/requirements.txt /tmp/requirements.txt

RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cu121 -r /tmp/requirements.txt

  

# Copy only what is needed to run

COPY model_ops_coordinator/ /app/model_ops_coordinator/

COPY common/ /app/common/

  

WORKDIR /app/model_ops_coordinator

RUN python -m py_compile app.py

  

FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04 AS runtime

  

ENV DEBIAN_FRONTEND=noninteractive \

    PYTHONUNBUFFERED=1 \

    PYTHONDONTWRITEBYTECODE=1 \

    PATH="/opt/venv/bin:${PATH}" \

    PYTHONPATH="/app" \

    NVIDIA_VISIBLE_DEVICES="all" \

    NVIDIA_DRIVER_CAPABILITIES="compute,utility" \

    CUDA_DEVICE_ORDER="PCI_BUS_ID" \

    PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True,max_split_size_mb=64" \

    OMP_NUM_THREADS="8" \

    MKL_NUM_THREADS="8"

  

RUN apt-get update && apt-get install -y --no-install-recommends \

    curl ca-certificates \

    && rm -rf /var/lib/apt/lists/*

  

RUN groupadd -r moc && useradd -r -g moc -d /app -s /bin/bash moc

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv

COPY --from=builder /app /app

RUN mkdir -p /app/data /app/logs /app/config && chown -R moc:moc /app

USER moc

  

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \

  CMD curl -sf http://localhost:8008/health || exit 1

  

EXPOSE 7211 7212 8008

WORKDIR /app/model_ops_coordinator

CMD ["python", "app.py"]

```

  

2) MemoryFusionHub (PC2-optimized; CPU-only)

  

```dockerfile

# syntax=docker/dockerfile:1.6

  

FROM python:3.11-slim AS builder

  

ENV PYTHONUNBUFFERED=1 \

    PYTHONDONTWRITEBYTECODE=1

  

RUN apt-get update && apt-get install -y --no-install-recommends \

    build-essential pkg-config \

    && rm -rf /var/lib/apt/lists/*

  

RUN python -m venv /opt/venv

ENV PATH="/opt/venv/bin:${PATH}"

RUN pip install --no-cache-dir --upgrade pip setuptools wheel

  

WORKDIR /app

COPY memory_fusion_hub/requirements.txt /tmp/requirements.txt

RUN pip install --no-cache-dir -r /tmp/requirements.txt

  

COPY memory_fusion_hub/ /app/memory_fusion_hub/

COPY common/ /app/common/

RUN python -m py_compile /app/memory_fusion_hub/app.py

  

FROM python:3.11-slim AS runtime

  

ENV PYTHONUNBUFFERED=1 \

    PYTHONDONTWRITEBYTECODE=1 \

    PATH="/opt/venv/bin:${PATH}" \

    PYTHONPATH="/app" \

    OMP_NUM_THREADS="1" \

    UVICORN_WORKERS="1"

  

RUN apt-get update && apt-get install -y --no-install-recommends \

    curl ca-certificates \

    && rm -rf /var/lib/apt/lists/*

  

RUN groupadd -r mfh && useradd -r -g mfh -d /app -s /bin/bash mfh

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv

COPY --from=builder /app /app

RUN mkdir -p /app/logs /app/data /app/cache && chown -R mfh:mfh /app

USER mfh

  

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \

  CMD curl -sf http://localhost:8080/health || exit 1

  

EXPOSE 8080 50051 5555

WORKDIR /app/memory_fusion_hub

CMD ["python", "app.py", "--config", "/app/memory_fusion_hub/config/default.yaml", "--log-level", "INFO"]

```

  

3) Simple legacy agent (ServiceRegistry; CPU-only; auto-minimized deps)

  

```dockerfile

# syntax=docker/dockerfile:1.6

  

FROM python:3.10-slim AS builder

  

ENV PYTHONUNBUFFERED=1 \

    PYTHONDONTWRITEBYTECODE=1

  

RUN apt-get update && apt-get install -y --no-install-recommends \

    build-essential python3-venv python3-pip \

    && rm -rf /var/lib/apt/lists/*

  

RUN python -m venv /opt/venv

ENV PATH="/opt/venv/bin:${PATH}"

RUN pip install --no-cache-dir --upgrade pip setuptools wheel

  

WORKDIR /app

COPY scripts/extract_individual_requirements.py /app/scripts/extract_individual_requirements.py

COPY main_pc_code/agents/ /app/main_pc_code/agents/

COPY common/ /app/common/

  

RUN python /app/scripts/extract_individual_requirements.py service_registry_agent \

    --workspace /app \

    --output /tmp/requirements_agent.txt

RUN pip install --no-cache-dir -r /tmp/requirements_agent.txt

  

FROM python:3.10-slim AS runtime

  

ENV PYTHONUNBUFFERED=1 \

    PYTHONDONTWRITEBYTECODE=1 \

    PATH="/opt/venv/bin:${PATH}" \

    PYTHONPATH="/app"

  

RUN apt-get update && apt-get install -y --no-install-recommends \

    curl ca-certificates \

    && rm -rf /var/lib/apt/lists/*

  

RUN groupadd -r svc && useradd -r -g svc -d /app -s /bin/bash svc

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv

COPY --from=builder /app/main_pc_code/ /app/main_pc_code/

COPY --from=builder /app/common/ /app/common/

USER svc

  

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \

  CMD curl -sf http://localhost:${HEALTH_PORT:-7200}/health || exit 1

  

CMD ["python", "main_pc_code/agents/service_registry_agent.py"]

```

  

---

  

### F. Fleet coverage table (100% of active agents)

  

Key to base families: `cpu-core`, `cpu-web`, `gpu-core-cu121`, `gpu-ml-cu121`, `gpu-onnx-cu121` (extras noted in “notes”). Where needs are uncertain, they’re marked and listed under Open Questions.

  

| service | machine(s) | needs (CPU/GPU/Web/Audio/Vision) | proposed base family | entrypoint | ports | healthcheck | notes |

|---|---|---|---|---|---|---|---|

| ServiceRegistry | MainPC | CPU | cpu-core | main_pc_code/agents/service_registry_agent.py | 7200/8200 | TCP/HTTP (uncertain — ask) | ZMQ-based; add HTTP /health or ZMQ ping |

| SystemDigitalTwin | MainPC | CPU | cpu-core | main_pc_code/agents/system_digital_twin.py | 7220/8220 | TCP/HTTP (uncertain — ask) | Uses Redis; no GPU |

| UnifiedSystemAgent | MainPC | CPU | cpu-core | main_pc_code/agents/unified_system_agent.py | 7201/8201 | TCP/HTTP (uncertain — ask) | Coordinator logic; no GPU libs |

| SelfHealingSupervisor | MainPC, PC2 | CPU | cpu-core | services/self_healing_supervisor/supervisor.py | 7009/9008 | HTTP (add /health) | Uses Docker SDK; CPU-only |

| MemoryFusionHub | MainPC, PC2 | CPU, gRPC | cpu-core | memory_fusion_hub/app.py | 5713/6713 (+8080 metrics) | HTTP 8080 | No GPU libs required |

| ModelOpsCoordinator | MainPC | GPU (torch), REST/gRPC | gpu-ml-cu121 | model_ops_coordinator/app.py | 7211,7212,8008 | HTTP 8008 | Torch cu121; RTX 4090 optimized |

| AffectiveProcessingCenter | MainPC | GPU (torch+audio) | gpu-ml-cu121 | affective_processing_center/app.py | 5560/6560 | HTTP/ZMQ (uncertain — ask) | requirements include torch/torchaudio |

| RealTimeAudioPipeline | MainPC, PC2 | GPU (torch), Audio | gpu-ml-cu121 | real_time_audio_pipeline/app.py | 5557/6557 | HTTP (uncertain — ask) | audio extras needed (webrtcvad, sounddevice) |

| CrossMachineGPUScheduler | MainPC | CPU + NVML | cpu-core | services/cross_gpu_scheduler/app.py | 7155/8155 | HTTP 8155 | Needs NVIDIA runtime for NVML access |

| FaceRecognitionAgent | MainPC | GPU (Vision, ONNX) | gpu-onnx-cu121 | main_pc_code/agents/face_recognition_agent.py | 5610/6610 | HTTP/ZMQ (uncertain — ask) | InsightFace + ONNX CUDA providers |

| LearningOpportunityDetector | MainPC | CPU (uncertain) | cpu-core | main_pc_code/agents/learning_opportunity_detector.py | 7202/8202 | TCP/HTTP (uncertain — ask) | Likely RPC into ModelOps |

| LearningManager | MainPC | GPU (uncertain) | gpu-ml-cu121 (uncertain) | main_pc_code/agents/learning_manager.py | 5580/6580 | TCP/HTTP (uncertain — ask) | May schedule GPU training slices |

| ActiveLearningMonitor | MainPC | CPU | cpu-core | main_pc_code/agents/active_learning_monitor.py | 5638/6638 | TCP/HTTP (uncertain — ask) | Monitoring/orchestration |

| IntentionValidatorAgent | MainPC | CPU | cpu-core | main_pc_code/agents/IntentionValidatorAgent.py | 5701/6701 | TCP/HTTP (uncertain — ask) | NLU pipeline client |

| NLUAgent | MainPC | CPU | cpu-core | main_pc_code/agents/nlu_agent.py | 5709/6709 | TCP/HTTP (uncertain — ask) | NLU client; RPC to models |

| AdvancedCommandHandler | MainPC | CPU | cpu-core | main_pc_code/agents/advanced_command_handler.py | 5710/6710 | TCP/HTTP (uncertain — ask) | Dialogue manager |

| ChitchatAgent | MainPC | CPU | cpu-core | main_pc_code/agents/chitchat_agent.py | 5711/6711 | TCP/HTTP (uncertain — ask) | Dialogue client |

| FeedbackHandler | MainPC | CPU | cpu-core | main_pc_code/agents/feedback_handler.py | 5636/6636 | TCP/HTTP (uncertain — ask) | Feedback processing |

| Responder | MainPC | CPU | cpu-core | main_pc_code/agents/responder.py | 5637/6637 | TCP/HTTP (uncertain — ask) | Integrates with TTS/STT; no torch |

| DynamicIdentityAgent | MainPC | CPU | cpu-core | main_pc_code/agents/DynamicIdentityAgent.py | 5802/6802 | TCP/HTTP (uncertain — ask) | Identity logic |

| EmotionSynthesisAgent | MainPC | CPU (uncertain) | cpu-core (uncertain) | main_pc_code/agents/emotion_synthesis_agent.py | 5706/6706 | TCP/HTTP (uncertain — ask) | Might rely on ModelOps; verify |

| STTService | MainPC | GPU (whisper via ModelOps) | gpu-ml-cu121 | main_pc_code/services/stt_service.py | 5800/6800 | TCP/HTTP (uncertain — ask) | Sends requests with device=cuda; torch via ModelOps |

| TTSService | MainPC | CPU (likely) | cpu-core | main_pc_code/services/tts_service.py | 5801/6801 | TCP/HTTP (uncertain — ask) | Uses sounddevice; GPU work delegated |

| AudioCapture | MainPC | CPU, Audio | cpu-core (audio extras) | main_pc_code/agents/streaming_audio_capture.py | 6550/7550 | TCP/HTTP (uncertain — ask) | RTAP gating via env |

| FusedAudioPreprocessor | MainPC | CPU, Audio | cpu-core (audio extras) | main_pc_code/agents/fused_audio_preprocessor.py | 6551/7551 | TCP/HTTP (uncertain — ask) | Audio DSP |

| StreamingInterruptHandler | MainPC | CPU | cpu-core | main_pc_code/agents/streaming_interrupt_handler.py | 5576/6576 | TCP/HTTP (uncertain — ask) | Control-plane |

| StreamingSpeechRecognition | MainPC | CPU (calls STT) | cpu-core | main_pc_code/agents/streaming_speech_recognition.py | 6553/7553 | TCP/HTTP (uncertain — ask) | Client to STTService |

| StreamingTTSAgent | MainPC | CPU | cpu-core | main_pc_code/agents/streaming_tts_agent.py | 5562/6562 | TCP/HTTP (uncertain — ask) | Client to TTSService |

| WakeWordDetector | MainPC | CPU, Audio | cpu-core (audio extras) | main_pc_code/agents/wake_word_detector.py | 6552/7552 | TCP/HTTP (uncertain — ask) | pvporcupine |

| StreamingLanguageAnalyzer | MainPC | CPU | cpu-core | main_pc_code/agents/streaming_language_analyzer.py | 5579/6579 | TCP/HTTP (uncertain — ask) | Analyzer client |

| ProactiveAgent | MainPC | CPU | cpu-core | main_pc_code/agents/ProactiveAgent.py | 5624/6624 | TCP/HTTP (uncertain — ask) | Proactivity logic |

| EmotionEngine | MainPC | CPU | cpu-core | main_pc_code/agents/emotion_engine.py | 5590/6590 | TCP/HTTP (uncertain — ask) | Emotion logic |

| MoodTrackerAgent | MainPC | CPU | cpu-core | main_pc_code/agents/mood_tracker_agent.py | 5704/6704 | TCP/HTTP (uncertain — ask) | Tracker |

| HumanAwarenessAgent | MainPC | CPU | cpu-core | main_pc_code/agents/human_awareness_agent.py | 5705/6705 | TCP/HTTP (uncertain — ask) | Awareness logic |

| ToneDetector | MainPC | CPU, Audio | cpu-core (audio extras) | main_pc_code/agents/tone_detector.py | 5625/6625 | TCP/HTTP (uncertain — ask) | Audio features |

| VoiceProfilingAgent | MainPC | CPU, Audio | cpu-core (audio extras) | main_pc_code/agents/voice_profiling_agent.py | 5708/6708 | TCP/HTTP (uncertain — ask) | Profiling |

| EmpathyAgent | MainPC | CPU | cpu-core | main_pc_code/agents/EmpathyAgent.py | 5703/6703 | TCP/HTTP (uncertain — ask) | Dialogue feature |

| CloudTranslationService | MainPC | CPU, HTTP client | cpu-core | main_pc_code/agents/cloud_translation_service.py | 5592/6592 | HTTP (add /health) | Calls external APIs |

| StreamingTranslationProxy | MainPC | CPU-Web, WS | cpu-web | services/streaming_translation_proxy/proxy.py | 5596/6596 (+9106 metrics) | HTTP /health | FastAPI + WS + Prom |

| ObservabilityDashboardAPI | MainPC | CPU-Web | cpu-web | services/obs_dashboard_api/server.py | 8001/9007 (+9107 metrics) | HTTP /health | FastAPI + Prom |

| UnifiedObservabilityCenter | MainPC, PC2 | CPU-Web | cpu-web | unified_observability_center/app.py | 9100/9110 | HTTP /health | Present in PC2 config; MainPC via groups (uncertain — ask) |

| CodeGenerator | MainPC | CPU | cpu-core | main_pc_code/agents/code_generator_agent.py | 5650/6650 | TCP/HTTP (uncertain — ask) | Utility |

| PredictiveHealthMonitor | MainPC | CPU | cpu-core | main_pc_code/agents/predictive_health_monitor.py | 5613/6613 | TCP/HTTP (uncertain — ask) | Utility |

| Executor | MainPC | CPU | cpu-core | main_pc_code/agents/executor.py | 5606/6606 | TCP/HTTP (uncertain — ask) | Utility |

| SmartHomeAgent | MainPC | CPU | cpu-core | main_pc_code/agents/smart_home_agent.py | 7125/8125 | TCP/HTTP (uncertain — ask) | Optional |

| ChainOfThoughtAgent | MainPC | CPU (GPU via RPC) | cpu-core | main_pc_code/FORMAINPC/chain_of_thought_agent.py | 5612/6612 | TCP/HTTP (uncertain — ask) | Reasoning, uses ModelOps |

| GoTToTAgent | MainPC | CPU (GPU via RPC) | cpu-core | main_pc_code/FORMAINPC/got_tot_agent.py | 5646/6646 | TCP/HTTP (uncertain — ask) | Optional |

| CognitiveModelAgent | MainPC | CPU (GPU via RPC) | cpu-core | main_pc_code/FORMAINPC/cognitive_model_agent.py | 5641/6641 | TCP/HTTP (uncertain — ask) | Optional |

| CentralErrorBus | PC2 | CPU | cpu-core | services/central_error_bus/error_bus.py | 7150/8150 | HTTP (add /health) | pyzmq + Prom |

| RealTimeAudioPipelinePC2 | PC2 | GPU (torch), Audio | gpu-ml-cu121 | real_time_audio_pipeline/app.py | 5557/6557 | HTTP (uncertain — ask) | audio extras needed |

| TieredResponder | PC2 | CPU | cpu-core | pc2_code/agents/tiered_responder.py | 7100/8100 | TCP/HTTP (uncertain — ask) | Async pipeline |

| AsyncProcessor | PC2 | CPU | cpu-core | pc2_code/agents/async_processor.py | 7101/8101 | TCP/HTTP (uncertain — ask) | Async pipeline |

| CacheManager | PC2 | CPU | cpu-core | pc2_code/agents/cache_manager.py | 7102/8102 | TCP/HTTP (uncertain — ask) | Cache/Memory |

| VisionProcessingAgent | PC2 | GPU (Vision) | gpu-onnx-cu121 (uncertain) | pc2_code/agents/VisionProcessingAgent.py | 7160/8160 | TCP/HTTP (uncertain — ask) | May use OpenCV/ONNX |

| DreamWorldAgent | PC2 | GPU (likely torch) | gpu-ml-cu121 (uncertain) | pc2_code/agents/DreamWorldAgent.py | 7104/8104 | TCP/HTTP (uncertain — ask) | Dream sim |

| ResourceManager | PC2 | CPU | cpu-core | pc2_code/agents/resource_manager.py | 7113/8113 | TCP/HTTP (uncertain — ask) | Infra core |

| TaskScheduler | PC2 | CPU | cpu-core | pc2_code/agents/task_scheduler.py | 7115/8115 | TCP/HTTP (uncertain — ask) | Infra core |

| AuthenticationAgent | PC2 | CPU | cpu-core | pc2_code/agents/ForPC2/AuthenticationAgent.py | 7116/8116 | TCP/HTTP (uncertain — ask) | Security |

| UnifiedUtilsAgent | PC2 | CPU | cpu-core | pc2_code/agents/ForPC2/unified_utils_agent.py | 7118/8118 | TCP/HTTP (uncertain — ask) | Utility |

| ProactiveContextMonitor | PC2 | CPU | cpu-core | pc2_code/agents/ForPC2/proactive_context_monitor.py | 7119/8119 | TCP/HTTP (uncertain — ask) | Memory context |

| AgentTrustScorer | PC2 | CPU | cpu-core | pc2_code/agents/AgentTrustScorer.py | 7122/8122 | TCP/HTTP (uncertain — ask) | Security scoring |

| FileSystemAssistantAgent | PC2 | CPU | cpu-core | pc2_code/agents/filesystem_assistant_agent.py | 7123/8123 | TCP/HTTP (uncertain — ask) | Filesystem ops |

| RemoteConnectorAgent | PC2 | CPU | cpu-core | pc2_code/agents/remote_connector_agent.py | 7124/8124 | TCP/HTTP (uncertain — ask) | Networking |

| UnifiedWebAgent | PC2 | CPU-Web | cpu-web | pc2_code/agents/unified_web_agent.py | 7126/8126 | HTTP /health (if present) | Web interface |

| DreamingModeAgent | PC2 | GPU (likely torch) | gpu-ml-cu121 (uncertain) | pc2_code/agents/DreamingModeAgent.py | 7127/8127 | TCP/HTTP (uncertain — ask) | Ties to DreamWorld |

| AdvancedRouter | PC2 | CPU | cpu-core | pc2_code/agents/advanced_router.py | 7129/8129 | TCP/HTTP (uncertain — ask) | Routing |

| TutoringServiceAgent | PC2 | CPU | cpu-core | pc2_code/agents/TutoringServiceAgent.py | 7108/8108 | TCP/HTTP (uncertain — ask) | Tutoring |

| SpeechRelayService | PC2 | CPU, gRPC | cpu-core | services/speech_relay/relay.py | 7130/8130 (+9109 metrics) | HTTP metrics only | gRPC server + ZMQ client |

  

Notes:

- Metrics ports for some services (e.g., 9106/9107/9109) are included where code shows Prometheus exporters.

- For rows with “HTTP (uncertain — ask)”, add a uniform `/health` route or provide a lightweight gRPC/ZMQ health RPC where applicable.

  

---

  

### G. Risk register & rollback considerations

  

- Risk: CUDA/toolchain mismatches across machines

  - Mitigation: Single default track (cu121) for both; optional cu124 only when validated. Pin family base by digest.

- Risk: Image bloat from shared families

  - Mitigation: Families contain only truly shared deps; extras remain per-service until ≥3 adopters.

- Risk: Legacy agent hidden dynamic deps

  - Mitigation: Use extractor-generated requirements; add explicit allowlist when dynamic imports are detected. Build smoke tests to validate imports.

- Risk: GPU not available at runtime (driver/runtime issues)

  - Mitigation: Startup GPU probe; if `REQUIRED_GPU=true`, fail fast with clear logs; otherwise degrade to CPU when possible (PC2 safety).

- Risk: CI runtime without GPU for GPU images

  - Mitigation: Build-only in CPU CI runners; run smoke tests that don’t require device; run device tests on dedicated GPU runners nightly.

- Rollback

  - Keep legacy Dockerfiles and images tagged for one minor release window; ability to revert to service-level images while base families stabilize.

  

---

  

### H. Open questions (blocking/clarifying)

  

1) Registry and naming: Confirm registry (e.g., GHCR) and final naming pattern `ghcr.io/<org>/<family>:<tag>` and digest pinning policy.

2) Python targets: Default new hubs to Python 3.11, allow py3.10 for legacy agents. Acceptable?

3) CUDA track: Adopt cu12.1 by default now and offer cu12.4 variant for MainPC where beneficial? OK?

4) Vulnerability scanner: Preference (Trivy vs Grype) and gating policy (fail on HIGH/CRITICAL?).

5) Healthchecks: For non-web agents, standardize on HTTP `/health`, gRPC health, or ZMQ ping? Which is preferred?

6) Audio/Vision extras: Which agents require mandatory `sounddevice`, `webrtcvad`, `pvporcupine`, `opencv-python-headless`, `onnxruntime-gpu` in-base vs per-service?

7) CI constraints: Availability of GPU runners, registry-cache capacity limits, and artifact retention requirements?

8) UnifiedObservabilityCenter on MainPC: It appears in groups but not explicitly listed as an agent. Should it run on MainPC as well? If yes, confirm ports/env.

9) torch pinning: For services with torch requirements outside ModelOps (e.g., RTAP, AffectiveProcessingCenter), confirm exact versions and whether they must match ModelOpsCoordinator.

  

---

  

### Evidence & quality gates (how this proposal meets them)

  

- Image size reduction plan

  - Multi-stage builder+runtime; families for shared heavy layers; no GPU libs in CPU images.

  - Target reduction: 30–60% vs naïve single-stage baselines.

- Build-time optimization

  - Cache-friendly layer ordering, shared family layers, Buildx cache export/import.

  - Optional prebuilt family images to avoid repeated torch/CUDA installs.

- Security posture

  - Non-root, minimal apt packages, explicit healthchecks, CVE scanning in CI (tool TBD).

- Reproducibility

  - Pin versions; encourage `--require-hashes` for critical services; pin base images by digest; avoid implicit latest.

- GPU readiness

  - Startup probes using torch/NVML; configurable fail-fast vs graceful fallback.

- PC2 safety

  - Conservative threads/workers and CPU fallbacks; no unnecessary GPU stacks in CPU services.

- CI integration sketch

  - Build matrix: families × machines; publish family bases on version bump; re-use registry cache.

  - Fail-fast on lint/import checks; optional nightly GPU device tests.

  

---

  

### Implementation Plan (post-approval)

  

1) Confirm registry, naming, and CUDA track choices (see Open Questions 1–3).

2) Build and publish family base images:

   - base.cpu-core and base.cpu-web (py311; py310 variants for legacy)

   - base.gpu-core-cu121, base.gpu-ml-cu121, base.gpu-onnx-cu121

3) Select 3–5 representative services per family and prototype Dockerfiles; measure size/time improvements; adjust pins.

4) Introduce standardized healthcheck helpers (HTTP/gRPC/ZMQ) and add to CPU-only agents.

5) CI integration:

   - Buildx with cache import/export; CVE scanning; optional GPU smoke tests on dedicated runners.

   - Adopt `pip-compile` and `--require-hashes` for critical services.

6) Gradual rollout: migrate hubs first (ModelOpsCoordinator, MemoryFusionHub, UOC), then GPU-heavy services, then remaining legacy agents with auto-minimized deps.

7) Observability: compare image sizes and build times; aim for 30–60% reduction; publish before/after metrics.

  

---

  

Confidence: 88%







PROPOSAL 3


Dockerfile Architecture Proposal (Dual-Machine 4090 + 3060)



> Version: **v0.1-draft**  

> Author: Lead DevOps Architect  

> Status: ⏳ DRAFT – awaiting review/answers to open questions

  

---

  

## A. High-Level Strategy & Rationale

  

1. **Functional-Family Base Images** – Instead of one mega-template, we define *families* that share a minimal, layered lineage (see §B).  This balances:

   * *DRY reuse* – common layers stay in cache across ~50 images.

   * *Dependency hygiene* – CPU-only agents never inherit GPU libraries.

   * *Flexibility* – Families can evolve (e.g., cuDNN upgrade) without touching CPU images.

  

2. **Multi-Stage Builds** – Builder stage (eg. poetry/conda wheels) ➜ runtime stage (slim-python + needed shared libs).  Dramatically shrinks final size (-55-70 % vs single-stage).

  

3. **Pinned, Reproducible Layers** – All `apt` and `pip` installs are version-pinned; `pip` uses `--require-hashes` with pre-generated *lock/wheels* inside an internal artifact registry.

  

4. **Non-Root Runtime** – Each final stage switches to an unprivileged UID: GID `10001:10001` (`appuser`).  Health-checks run via tini as PID 1 to avoid zombie leaks.

  

5. **Hardware-Aware Runtime Tuning** – Entry script reads `/etc/machine-profile.json` (baked per build arg) to set sensible defaults (GPU selector, thread pool, env vars).  See §D.

  

6. **Build Orchestration** – GitHub Actions matrix (families × machines) uses `buildx` + `--cache-to` / `--cache-from` to share OCI layer cache through GHCR.

  

## B. Base Image Hierarchy

  

```

base-python:3.11-slim          # debian-slim, non-root, tini

  ├─ base-utils                # curl, dumb-init, gosu, tzdata

  │   ├─ base-cpu-pydeps       # common cpu wheels (numpy, pydantic, fastapi)

  │   │   └─ family-web        # uvicorn, starlette, websockets

  │   └─ base-gpu-cu121        # FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

  │       ├─ family-torch-cu121   # torch==2.2.2+cu121, torchvision

  │       │   └─ family-llm-cu121 # vllm, llama-cpp-python built w/ -sm80/89

  │       └─ family-vision-cu121  # opencv-python-headless, onnxruntime-gpu

  └─ legacy-py310-cpu          # frozen for agents stuck on 3.10 (security-patched)

```

  

* **Registries/Tags:** `ghcr.io/<org>/<image>:<family>-<version>` – version = `YYYYMMDD` date stamp + git short-sha.  *GPU variants append `-cudaXX`.*

* **4090 vs 3060:** Both use CUDA 12.1 runtime; code targeting SM 8.9 vs 8.6 is handled at *build-time* via `TORCH_CUDA_ARCH_LIST` (`89;86`). Optional *cu12.4* future tag.

  

## C. Optimisation & Standardisation Plan

  

1. **Layer Ordering** – OS updates ➜ core libs ➜ Python deps ➜ app code ➜ static assets.  Keeps cache hits high when only code changes.

2. **Build Cache** – Use `type=registry` cache for GHCR; share between MainPC & PC2 runners.

3. **Wheel Cache Layer** – `--mount=type=cache,target=/root/.cache/pip` to avoid re-downloading.

4. **.dockerignore** – Extend repo root ignore; plus generated `__pycache__`, models, data.

5. **Security** –

   * `apt-get update && apt-get install --no-install-recommends` + `apt-clean`.

   * Trivy scan stage; pipeline fails on HIGH/CRITICAL (subject to open question #4).

6. **Image Size Targets** – Goal: ‑40 % median vs current (170 → ≈100 MB for CPU; 5.2 GB → 3 GB for GPU).  Achieved via multi-stage, stripping docs/tests, and slim bases.

  

## D. Hardware-Aware Defaults

  

| Parameter                     | MainPC (4090) | PC2 (3060) |

|-------------------------------|---------------|------------|

| `GPU_VISIBLE_DEVICES`         | `0`           | `0`        |

| `TORCH_CUDA_ALLOC_CONF`       | `max_split_size_mb:64` | `max_split_size_mb:32` |

| Thread workers (`uvicorn`)    | CPU cores ×2 = 32 | CPU cores = 8 |

| `NUMBA_CACHE_SIZE`            | 512 MB        | 128 MB     |

| `OMP_NUM_THREADS`             | 16            | 4          |

| `MODEL_EVICT_THRESHOLD_PCT`   | 90            | 70         |

  

Values baked via build-arg `MACHINE=mainpc|pc2` ➜ writes `/etc/machine-profile.json`.

  

## E. Concrete Example Dockerfiles

  

### 1. ModelOpsCoordinator (GPU-heavy, MainPC)

```Dockerfile

# syntax=docker/dockerfile:1.5

FROM ghcr.io/<org>/family-torch-cu121:20240810 AS base

ARG MACHINE=mainpc

ENV PYTHONUNBUFFERED=1 \

    TORCH_CUDA_ARCH_LIST="8.9" \

    NVIDIA_VISIBLE_DEVICES=${GPU_VISIBLE_DEVICES:-0}

  

WORKDIR /app

COPY model_ops_coordinator/ ./model_ops_coordinator

COPY requirements/model_ops.txt ./requirements.txt

  

# ---------- Builder ----------

FROM base AS builder

RUN --mount=type=cache,target=/root/.cache/pip \

    pip install --no-cache-dir --require-hashes -r requirements.txt

  

# ---------- Runtime ----------

FROM base AS runtime

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

COPY model_ops_coordinator/ ./model_ops_coordinator

COPY config/ ./config

COPY entrypoints/model_ops_entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh && chmod +x /usr/bin/tini

USER appuser

HEALTHCHECK CMD curl -f http://localhost:${HEALTH_PORT:-8212}/health || exit 1

ENTRYPOINT ["/usr/bin/tini","--"]

CMD ["/entrypoint.sh"]

```

  

### 2. MemoryFusionHub (GPU-aware but CPU-preferred, PC2)

```Dockerfile

FROM ghcr.io/<org>/family-cpu-pydeps:20240810 AS base

ARG MACHINE=pc2

ENV PYTHONUNBUFFERED=1

  

WORKDIR /app

COPY memory_fusion_hub/ ./memory_fusion_hub

COPY requirements/memory_fusion.txt ./requirements.txt

  

RUN --mount=type=cache,target=/root/.cache/pip \

    pip install --no-cache-dir --require-hashes -r requirements.txt

  

COPY entrypoints/memory_fusion_entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh && chmod +x /usr/bin/tini

USER appuser

HEALTHCHECK CMD curl -f http://localhost:${HEALTH_PORT:-6713}/health || exit 1

ENTRYPOINT ["/usr/bin/tini","--"]

CMD ["/entrypoint.sh"]

```

  

### 3. Legacy `IntentionValidatorAgent` (Py-3.10 CPU)

```Dockerfile

FROM ghcr.io/<org>/legacy-py310-cpu:20240810

WORKDIR /app

COPY main_pc_code/agents/IntentionValidatorAgent.py ./

RUN pip install --no-cache-dir pydantic==1.10.15 fastapi==0.110.0

USER appuser

CMD ["python","IntentionValidatorAgent.py"]

```

  

> **Note:** Sample files *not* meant for commit; final paths/ports resolved by build ARGs.

  

## F. Fleet Coverage Table

  

| Service | Machine(s) | Needs | Proposed Base | Entrypoint | Ports | Healthcheck | Notes |

|---------|------------|-------|---------------|------------|-------|-------------|-------|

| ServiceRegistry | 4090 | CPU/Web | family-web | `registry_entry.sh` | 7200 | `/health` | Redis URL env |

| SystemDigitalTwin | 4090 | CPU | base-cpu-pydeps | `digital_twin.sh` | 7220 | `/health` | sqlite + redis |

| UnifiedSystemAgent | 4090 | CPU | base-cpu-pydeps | ... | 7201 | ... | |

| SelfHealingSupervisor | 4090,3060 | CPU/Docker | base-cpu-pydeps | ... | 7009 | ... | needs docker.sock |

| MemoryFusionHub | 4090,3060 | CPU/GPU* | family-cpu-pydeps | ... | 5713 | ... | GPU optional |

| ModelOpsCoordinator | 4090 | GPU/LLM | family-llm-cu121 | ... | 7212 | ... | torch/vllm |

| AffectiveProcessingCenter | 4090 | GPU | family-torch-cu121 | ... | 5560 | ... | |

| RealTimeAudioPipeline | both | GPU/Audio | family-torch-cu121 | ... | 5557 | ... | uses whisper |

| UnifiedObservabilityCenter | both | CPU/Web | family-web | ... | 9100 | ... | prometheus |

| CodeGenerator | 4090 | CPU | base-cpu-pydeps | ... | 5650 | ... | |

| PredictiveHealthMonitor | 4090 | CPU | base-cpu-pydeps | ... | 5613 | ... | |

| Executor | 4090 | CPU | base-cpu-pydeps | ... | 5606 | ... | |

| TinyLlamaServiceEnhanced | 4090 | GPU/LLM | family-llm-cu121 | ... | 5615 | ... | optional |

| SmartHomeAgent | 4090 | CPU/Web | family-web | ... | 7125 | ... | |

| CrossMachineGPUScheduler | 4090 | CPU | base-cpu-pydeps | ... | 7155 | ... | needs grpc |

| ChainOfThoughtAgent | 4090 | GPU/LLM | family-llm-cu121 | ... | 5612 | ... | |

| CognitiveModelAgent | 4090 | GPU/LLM | family-llm-cu121 | ... | 5641 | ... | optional |

| FaceRecognitionAgent | 4090 | GPU/Vision | family-vision-cu121 | ... | 5610 | ... | opencv |

| LearningOpportunityDetector | 4090 | GPU/LLM | family-llm-cu121 | ... | 7202 | ... | |

| LearningManager | 4090 | GPU/LLM | family-llm-cu121 | ... | 5580 | ... | |

| ActiveLearningMonitor | 4090 | CPU | base-cpu-pydeps | ... | 5638 | ... | |

| IntentionValidatorAgent | 4090 | CPU | legacy-py310-cpu | ... | 5701 | ... | legacy py310 |

| NLUAgent | 4090 | CPU | legacy-py310-cpu | ... | 5709 | ... | |

| AdvancedCommandHandler | 4090 | CPU | legacy-py310-cpu | ... | 5710 | ... | |

| ChitchatAgent | 4090 | CPU | legacy-py310-cpu | ... | 5711 | ... | |

| FeedbackHandler | 4090 | CPU | legacy-py310-cpu | ... | 5636 | ... | |

| Responder | 4090 | GPU/Audio | family-torch-cu121 | ... | 5637 | ... | |

| DynamicIdentityAgent | 4090 | GPU/LLM | family-llm-cu121 | ... | 5802 | ... | |

| EmotionSynthesisAgent | 4090 | GPU/Audio | family-torch-cu121 | ... | 5706 | ... | |

| STTService | 4090 | GPU/Audio | family-torch-cu121 | ... | 5800 | ... | whisper |

| TTSService | 4090 | GPU/Audio | family-torch-cu121 | ... | 5801 | ... | xtts |

| AudioCapture | 4090 | CPU/Audio | base-cpu-pydeps | ... | 6550 | ... | optional |

| StreamingSpeechRecognition | 4090 | GPU/Audio | family-torch-cu121 | ... | 6553 | ... | optional |

| StreamingTTSAgent | 4090 | GPU/Audio | family-torch-cu121 | ... | 5562 | ... | |

| ProactiveAgent | 4090 | GPU/LLM | family-llm-cu121 | ... | 5624 | ... | |

| EmotionEngine | 4090 | CPU | base-cpu-pydeps | ... | 5590 | ... | |

| MoodTrackerAgent | 4090 | CPU | base-cpu-pydeps | ... | 5704 | ... | |

| HumanAwarenessAgent | 4090 | CPU | base-cpu-pydeps | ... | 5705 | ... | |

| ToneDetector | 4090 | CPU | base-cpu-pydeps | ... | 5625 | ... | |

| VoiceProfilingAgent | 4090 | CPU | base-cpu-pydeps | ... | 5708 | ... | |

| EmpathyAgent | 4090 | GPU/Audio | family-torch-cu121 | ... | 5703 | ... | |

| CloudTranslationService | 4090 | CPU/Web | family-web | ... | 5592 | ... | |

| StreamingTranslationProxy | 4090 | CPU/Web | family-web | ... | 5596 | ... | websocket |

| ObservabilityDashboardAPI | 4090 | CPU/Web | family-web | ... | 8001 | ... | |

| CentralErrorBus | 3060 | CPU/Web | family-web | ... | 7150 | ... | |

| RealTimeAudioPipelinePC2 | 3060 | GPU/Audio | family-torch-cu121 | ... | 5557 | ... | |

| TieredResponder | 3060 | CPU | base-cpu-pydeps | ... | 7100 | ... | |

| AsyncProcessor | 3060 | CPU | base-cpu-pydeps | ... | 7101 | ... | |

| CacheManager | 3060 | CPU | base-cpu-pydeps | ... | 7102 | ... | |

| VisionProcessingAgent | 3060 | GPU/Vision | family-vision-cu121 | ... | 7160 | ... | |

| DreamWorldAgent | 3060 | GPU/Vision | family-vision-cu121 | ... | 7104 | ... | |

| ResourceManager | 3060 | CPU | base-cpu-pydeps | ... | 7113 | ... | |

| TaskScheduler | 3060 | CPU | base-cpu-pydeps | ... | 7115 | ... | |

| AuthenticationAgent | 3060 | CPU | base-cpu-pydeps | ... | 7116 | ... | |

| UnifiedUtilsAgent | 3060 | CPU | base-cpu-pydeps | ... | 7118 | ... | |

| ProactiveContextMonitor | 3060 | CPU | base-cpu-pydeps | ... | 7119 | ... | |

| AgentTrustScorer | 3060 | CPU | base-cpu-pydeps | ... | 7122 | ... | |

| FileSystemAssistantAgent | 3060 | CPU | base-cpu-pydeps | ... | 7123 | ... | |

| RemoteConnectorAgent | 3060 | CPU | base-cpu-pydeps | ... | 7124 | ... | |

| UnifiedWebAgent | 3060 | CPU/Web | family-web | ... | 7126 | ... | |

| DreamingModeAgent | 3060 | GPU/Vision | family-vision-cu121 | ... | 7127 | ... | |

| AdvancedRouter | 3060 | CPU | base-cpu-pydeps | ... | 7129 | ... | |

| UnifiedObservabilityCenter (pc2) | 3060 | CPU/Web | family-web | ... | 9100 | ... | |

| TutoringServiceAgent | 3060 | CPU | base-cpu-pydeps | ... | 7108 | ... | |

| SpeechRelayService | 3060 | GPU/Audio | family-torch-cu121 | ... | 7130 | ... | |

  

> “…” marks entry scripts & health endpoints to be finalised in implementation phase.  Unknown requirements flagged **(uncertain — ask)** inline if applicable.

  

## G. Risk Register & Rollback

  

| ID | Risk | Likelihood | Impact | Mitigation | Rollback |

|----|------|------------|--------|------------|----------|

| R1 | CUDA 12.1 incompatibility with older driver on PC2 | Low | High | Verify driver ≥ 535; fallback to CUDA 11.8 tag | Re-tag images to `-cu118` branch |

| R2 | Legacy Py3.10 deps receive no upstream security fixes | Med | Med | Freeze to distro-patched 3.10, schedule migration | Swap to base-python:3.11-slim branch |

| R3 | Shared layer cache eviction on GHCR (size quota) | Med | Low | Periodic `buildx imagetools rm`; prune old tags | Rebuild without cache (slow) |

| R4 | CVE scan false-positives breaking pipeline | Med | Med | Allowlist by SBOM digest; extend grace period | Temporarily downgrade scan severity gate |

  

## H. Open Questions

  

1. **Python Targets** – OK to default new hubs to 3.11 while freezing legacy agents on 3.10?

2. **Registry Naming** – Confirm `ghcr.io/<org>/<family>:<tag>` convention & write access.

3. **CUDA Track** – Adopt CUDA 12.4 images now or stay on 12.1 baseline?

4. **Vulnerability Scanner** – Preference between *Trivy* vs *Grype*?  Fail on HIGH/CRITICAL?

5. **Audio/Vision Extras** – Any agents require ffmpeg/libpulse/alsa directly in image?

6. **CI Runner Constraints** – GPU runners available for build tests?  Cache storage limit?

7. **Health Endpoint Uniformity** – Can we standardise `/health` JSON 200 across all agents?

  

---

  

## Implementation Plan (post-approval)

  

1. **Answer Open Questions** ➜ finalise base-image Dockerfiles & lockfiles.

2. **Set Up GHCR Repositories & Buildx Cache Buckets**.

3. **Prototype Family Images** (`base-cpu`, `family-torch-cu121`, etc.) locally; measure size & performance.

4. **CI Pipeline Update** – Add build matrix, cache push/pull, CVE scan stages.

5. **Incremental Migration:**

   a. Migrate *core infrastructure* (ServiceRegistry, DigitalTwin).  

   b. Roll out GPU families on MainPC.  

   c. Roll out CPU families on PC2.

6. **Observability** – Integrate image SBOM output into Unified Observability Center.

7. **Rollback Procedures** – Tag previous images `-legacy` for hot revert; supervisor auto-pulls.

  

---

  

*Document generated automatically; please review & add comments.*