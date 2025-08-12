# Phase 4.2 Pre-Analysis — docker_arch_impl_20250810

Quoted IMPORTANT NOTE (from Phase 4):

> This phase involves modifying the runtime of every service. Coordinate deployments carefully, especially for core infrastructure, to minimize downtime. Use the `FORCE_IMAGE_TAG` environment variable for targeted testing.

Scope: MainPC 4090 GPU-heavy services

- ModelOpsCoordinator
- AffectiveProcessingCenter
- RealTimeAudioPipeline
- TinyLlamaServiceEnhanced
- ChainOfThoughtAgent, CognitiveModelAgent, LearningOpportunityDetector, LearningManager, DynamicIdentityAgent, ProactiveAgent
- FaceRecognitionAgent
- Responder, EmotionSynthesisAgent, STTService, TTSService, StreamingSpeechRecognition, StreamingTTSAgent, EmpathyAgent

Plan: Align Dockerfiles to canonical base families, standardize health checks, and prepare build commands with registry tagging.

Base image mapping (family → services)

- family-llm-cu121: ModelOpsCoordinator; ChainOfThoughtAgent; CognitiveModelAgent; LearningOpportunityDetector; LearningManager; DynamicIdentityAgent; ProactiveAgent; TinyLlamaServiceEnhanced
- family-torch-cu121: AffectiveProcessingCenter; RealTimeAudioPipeline; STTService; TTSService; StreamingSpeechRecognition; StreamingTTSAgent; Responder; EmotionSynthesisAgent; EmpathyAgent
- family-vision-cu121: FaceRecognitionAgent

Key edits implemented

- Converted service/group Dockerfiles to accept `ARG BASE_IMAGE` and `FROM ${BASE_IMAGE}`:
  - `model_ops_coordinator/Dockerfile` (also added `NVIDIA_*` env, retained HEALTHCHECK)
  - `affective_processing_center/Dockerfile` (added `NVIDIA_*` env, HEALTHCHECK exists)
  - `real_time_audio_pipeline/Dockerfile` (added `NVIDIA_*` env, HEALTHCHECK present)
  - `main_pc_code/Dockerfile.speech_pipeline` (ARG base, ports exposed, HEALTHCHECK via `${HEALTH_PORT}`)
  - `main_pc_code/Dockerfile.reasoning_suite` (ARG base)
  - `main_pc_code/Dockerfile.vision_suite` (ARG base)
  - `main_pc_code/Dockerfile.coordination` (ARG base)
  - `main_pc_code/Dockerfile.emotion_system` (ARG base)

Build-time mapping (to be passed via --build-arg BASE_IMAGE)

- ModelOpsCoordinator → `ghcr.io/<org>/family-llm-cu121:<date>-<git_sha>`
- AffectiveProcessingCenter → `ghcr.io/<org>/family-torch-cu121:<date>-<git_sha>`
- RealTimeAudioPipeline → `ghcr.io/<org>/family-torch-cu121:<date>-<git_sha>`
- Reasoning Suite (ChainOfThought, CognitiveModel, Learning* , DynamicIdentity, Proactive) → `ghcr.io/<org>/family-llm-cu121:<date>-<git_sha>`
- Speech Pipeline (STT, TTS, Streaming*, Responder, Empathy, EmotionSynthesis, TinyLlama) → `ghcr.io/<org>/family-torch-cu121:<date>-<git_sha>`
- Vision Suite (FaceRecognition) → `ghcr.io/<org>/family-vision-cu121:<date>-<git_sha>`

Health checks

- Standardize to `curl -f http://localhost:${HEALTH_PORT}/health || exit 1` or service script:
  - MOC: 8008
  - APC: 8008
  - RTAP: `/app/healthcheck.sh` (already present)
  - Suites: use `${HEALTH_PORT}` default 8080; override per-service if needed

Risks

- CUDA/driver mismatch causing runtime failures (ensure host CUDA runtime supports cu121)
- Missing `libgl1/libgomp1/libpulse/ffmpeg` in runtime layers for specific agents (validated in Phase 2; recheck at runtime)
- Port collisions with existing services (enforce blueprint ports; expose only necessary)
- Health endpoint mismatch (ensure each service provides `/health`)
- Registry/auth issues on GHCR (ensure PAT and `docker login ghcr.io`)

Prerequisites

- Phases 1–3 completed with base images pushed to GHCR
- Known `<org>` and GHCR PAT available in env
- 4090 host with drivers compatible with CUDA 12.1

Validation steps (not executed here)

1) Build with BuildKit ARG-in-FROM support:
   - `docker buildx build -f main_pc_code/Dockerfile.speech_pipeline --build-arg BASE_IMAGE=ghcr.io/<org>/family-torch-cu121:<date>-<git_sha> -t ghcr.io/<org>/ai_system/speech_pipeline:<date>-<git_sha> .`
   - `docker buildx build -f main_pc_code/Dockerfile.reasoning_suite --build-arg BASE_IMAGE=ghcr.io/<org>/family-llm-cu121:<date>-<git_sha> -t ghcr.io/<org>/ai_system/reasoning_suite:<date>-<git_sha> .`
   - `docker buildx build -f main_pc_code/Dockerfile.vision_suite --build-arg BASE_IMAGE=ghcr.io/<org>/family-vision-cu121:<date>-<git_sha> -t ghcr.io/<org>/ai_system/vision_suite:<date>-<git_sha> .`
   - `docker buildx build -f model_ops_coordinator/Dockerfile --build-arg BASE_IMAGE=ghcr.io/<org>/family-llm-cu121:<date>-<git_sha> -t ghcr.io/<org>/ai_system/model_ops_coordinator:<date>-<git_sha> model_ops_coordinator`
   - `docker buildx build -f affective_processing_center/Dockerfile --build-arg BASE_IMAGE=ghcr.io/<org>/family-torch-cu121:<date>-<git_sha> -t ghcr.io/<org>/ai_system/affective_processing_center:<date>-<git_sha> affective_processing_center`
   - `docker buildx build -f real_time_audio_pipeline/Dockerfile --build-arg BASE_IMAGE=ghcr.io/<org>/family-torch-cu121:<date>-<git_sha> -t ghcr.io/<org>/ai_system/real_time_audio_pipeline:<date>-<git_sha> real_time_audio_pipeline`

2) Push to GHCR and canary deploy with `FORCE_IMAGE_TAG=<date>-<git_sha>` in the deployment supervisor.

Gate readiness for 4.2 execution

- All required Dockerfiles updated for base family injection and health checks
- Build commands prepared; execution deferred to deployment step

Confidence: 92%

