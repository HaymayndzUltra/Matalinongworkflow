global_settings:

  environment:

    PYTHONPATH: /app

    LOG_LEVEL: INFO

    DEBUG_MODE: 'false'

    ENABLE_METRICS: 'true'

    ENABLE_TRACING: 'true'

    ENABLE_DATA_OPTIMIZER: 'true'

    DATA_OPTIMIZER_METHOD: compressed_msgpack

    ENABLE_HYBRID_INFERENCE: 'true'

    HYBRID_QUALITY_THRESHOLD: '0.85'

  features:

    RTAP_ENABLED: ${RTAP_ENABLED:-false}

  resource_limits:

    cpu_percent: 80

    memory_mb: 2048

    max_threads: 4

  health_checks:

    interval_seconds: 30

    timeout_seconds: 10

    retries: 3

  performance_tuning:

    dynamic_batch_tuning: true

    tuning_source: UnifiedObservabilityCenter

    batch_optimization: true

    memory_optimization: true

    gpu_memory_fraction: 0.9

hybrid_inference_policy:

  strategy: local_first

  quality_check:

    method: score_threshold

    threshold: 0.85

    evaluation_model: gpt-3.5-turbo

  local_backend:

    engine: llama_cpp

    gpu_device: RTX_4090

    models:

      text_generation:

      - name: phi-2

        path: models/phi-2.Q4_0.gguf

      - name: phi-3-mini-128k-instruct

        path: models/phi-3-mini-128k-instruct.gguf

      speech_to_text:

      - name: whisper-large-v3

        path: models/whisper-large-v3

      text_to_speech:

      - name: xtts-v2

        path: models/xtts-v2

  cloud_backends:

  - provider: openai

    model: gpt-4o

    api_key_env: OPENAI_API_KEY

  - provider: anthropic

    model: claude-3-opus

    api_key_env: ANTHROPIC_API_KEY

  log_fallbacks: true

  fallback_log_path: logs/cloud_fallbacks.log

agent_groups:

  foundation_services:

    ServiceRegistry:

      script_path: main_pc_code/agents/service_registry_agent.py

      port: ${PORT_OFFSET}+7200

      health_check_port: ${PORT_OFFSET}+8200

      required: true

      dependencies: []

      config:

        backend: ${SERVICE_REGISTRY_BACKEND:-redis}

        redis:

          url: ${SERVICE_REGISTRY_REDIS_URL:-redis://localhost:6379/0}

          prefix: ${SERVICE_REGISTRY_PREFIX:-service_registry:}

    SystemDigitalTwin:

      script_path: main_pc_code/agents/system_digital_twin.py

      port: ${PORT_OFFSET}+7220

      health_check_port: ${PORT_OFFSET}+8220

      config:

        db_path: data/unified_memory.db

        redis:

          host: localhost

          port: ${PORT_OFFSET}+6379

          db: 0

        zmq_request_timeout: 5000

      required: true

      dependencies:

      - ServiceRegistry

    # DECOMMISSIONED: Replaced by ModelOpsCoordinator

    # RequestCoordinator:

    #   script_path: main_pc_code/agents/request_coordinator.py

    #   port: 26002

    #   health_check_port: 27002

    #   required: true

    #   dependencies:

    #   - SystemDigitalTwin

    # DECOMMISSIONED: Replaced by ModelOpsCoordinator

    # ModelManagerSuite:

    #   script_path: main_pc_code/model_manager_suite.py

    #   port: ${PORT_OFFSET}+7211

    #   health_check_port: ${PORT_OFFSET}+8211

    #   required: true

    #   dependencies:

    #   - SystemDigitalTwin

    #   config:

    #     models_dir: models

    #     vram_budget_percentage: 80

    #     idle_timeout: 300

    #     hybrid_inference_policy_ref: global

    # DECOMMISSIONED: Replaced by ModelOpsCoordinator

    # VRAMOptimizerAgent:

    #   script_path: main_pc_code/agents/vram_optimizer_agent.py

    #   port: ${PORT_OFFSET}+5572

    #   health_check_port: ${PORT_OFFSET}+6572

    #   required: true

    #   dependencies:

    #   - ModelManagerSuite

    #   - RequestCoordinator

    #   - SystemDigitalTwin

    # ObservabilityHub retired; use UnifiedObservabilityCenter instead

    # ObservabilityHub:

    #   script_path: phase1_implementation/consolidated_agents/observability_hub/backup_observability_hub/observability_hub.py

    #   port: ${PORT_OFFSET}+9000

    #   health_check_port: ${PORT_OFFSET}+9001

    #   required: false

    #   dependencies:

    #   - SystemDigitalTwin

    #   config:

    #     prometheus_enabled: true

    #     parallel_health_checks: true

    #     prediction_enabled: true

    #     dynamic_batch_tuning: true

    UnifiedSystemAgent:

      script_path: main_pc_code/agents/unified_system_agent.py

      port: ${PORT_OFFSET}+7201

      health_check_port: ${PORT_OFFSET}+8201

      required: true

      dependencies:

      - SystemDigitalTwin

    SelfHealingSupervisor:

      script_path: services/self_healing_supervisor/supervisor.py

      port: ${PORT_OFFSET}+7009

      health_check_port: ${PORT_OFFSET}+9008

      required: true

      dependencies:

      - UnifiedObservabilityCenter

      config:

        docker_sock: /var/run/docker.sock

    MemoryFusionHub:

      script_path: memory_fusion_hub/app.py

      port: ${PORT_OFFSET}+5713

      health_check_port: ${PORT_OFFSET}+6713

      required: true

      dependencies:

      - ServiceRegistry

      - UnifiedObservabilityCenter

      config:

        zmq_port: ${PORT_OFFSET}+5713

        grpc_port: ${PORT_OFFSET}+5714

        metrics_port: ${PORT_OFFSET}+8080

        redis_url: "${REDIS_URL:-redis://localhost:6379/0}"

        sqlite_path: "/workspace/memory.db"

    ModelOpsCoordinator:

      script_path: model_ops_coordinator/app.py

      port: ${PORT_OFFSET}+7212

      health_check_port: ${PORT_OFFSET}+8212

      required: true

      dependencies:

      - SystemDigitalTwin

      - UnifiedObservabilityCenter

      config:

        zmq_port: ${PORT_OFFSET}+7211

        grpc_port: ${PORT_OFFSET}+7212

        rest_port: ${PORT_OFFSET}+8008

        max_workers: 16

        vram_soft_limit_mb: 22000

        eviction_threshold_pct: 90

        redis_url: "${REDIS_URL:-redis://localhost:6379/1}"

        learning_store: "/workspace/learning_jobs.db"

        models_dir: models

        enable_auto_tune: true

        max_parallel_jobs: 2

    AffectiveProcessingCenter:

      script_path: affective_processing_center/app.py

      port: ${PORT_OFFSET}+5560

      health_check_port: ${PORT_OFFSET}+6560

      required: true

      dependencies:

      - ModelOpsCoordinator

      - MemoryFusionHub

      config:

        pub_address: "tcp://*:5560"

        synth_address: "tcp://*:5561"

        zmq_endpoints:

        - "tcp://localhost:5555"

        - "tcp://localhost:5556"

        redis_url: "${REDIS_URL:-redis://localhost:6379/0}"

        cache_ttl: 3600

        batch_size: 10

    RealTimeAudioPipeline:

      script_path: real_time_audio_pipeline/app.py

      port: ${PORT_OFFSET}+5557

      health_check_port: ${PORT_OFFSET}+6557

      required: true

      dependencies:

      - ModelOpsCoordinator

      config:

        environment: "main_pc"

        sample_rate: 16000

        frame_size: 512

        channels: 1

        buffer_size: 100

        max_latency_ms: 50

        zmq_port: ${PORT_OFFSET}+5557

        grpc_port: ${PORT_OFFSET}+5558

        cuda_device: "cuda:0"

    # UnifiedObservabilityCenter defined in foundation services; duplicate removed

    # DECOMMISSIONED: Legacy memory agents replaced by MemoryFusionHub

    # memory_system:

    #   MemoryClient:

    #     script_path: main_pc_code/agents/memory_client.py

    #     port: ${PORT_OFFSET}+5713

    #     health_check_port: ${PORT_OFFSET}+6713

    #     required: true

    #     dependencies:

    #     - SystemDigitalTwin

    #   SessionMemoryAgent:

    #     script_path: main_pc_code/agents/session_memory_agent.py

    #     port: ${PORT_OFFSET}+5574

    #     health_check_port: ${PORT_OFFSET}+6574

    #     required: true

    #     dependencies:

    #     - RequestCoordinator

    #     - SystemDigitalTwin

    #     - MemoryClient

    #   KnowledgeBase:

    #     script_path: main_pc_code/agents/knowledge_base.py

    #     port: ${PORT_OFFSET}+5715

    #     health_check_port: ${PORT_OFFSET}+6715

    #     required: true

    #     dependencies:

    #     - MemoryClient

    #     - SystemDigitalTwin

  utility_services:

    CodeGenerator:

      script_path: main_pc_code/agents/code_generator_agent.py

      port: ${PORT_OFFSET}+5650

      health_check_port: ${PORT_OFFSET}+6650

      required: true

      dependencies:

      - SystemDigitalTwin

      - ModelOpsCoordinator

    PredictiveHealthMonitor:

      script_path: main_pc_code/agents/predictive_health_monitor.py

      port: ${PORT_OFFSET}+5613

      health_check_port: ${PORT_OFFSET}+6613

      required: true

      dependencies:

      - SystemDigitalTwin

    Executor:

      script_path: main_pc_code/agents/executor.py

      port: ${PORT_OFFSET}+5606

      health_check_port: ${PORT_OFFSET}+6606

      required: true

      dependencies:

      - CodeGenerator

      - SystemDigitalTwin

    TinyLlamaServiceEnhanced:

      script_path: main_pc_code/FORMAINPC/tiny_llama_service_enhanced.py

      port: ${PORT_OFFSET}+5615

      health_check_port: ${PORT_OFFSET}+6615

      required: false

      dependencies:

      - ModelOpsCoordinator

      - SystemDigitalTwin

    SmartHomeAgent:

      script_path: main_pc_code/agents/smart_home_agent.py

      port: ${PORT_OFFSET}+7125

      health_check_port: ${PORT_OFFSET}+8125

      required: false

      dependencies:

      - SystemDigitalTwin

      config:

        voice_control: enabled

        intelligent_control: enabled

        device_scan_interval: 60

  gpu_infrastructure:

    CrossMachineGPUScheduler:

      script_path: services/cross_gpu_scheduler/app.py

      port: ${PORT_OFFSET}+7155

      health_check_port: ${PORT_OFFSET}+8155

      required: true

      dependencies:

      - ModelOpsCoordinator

      - UnifiedObservabilityCenter

  reasoning_services:

    ChainOfThoughtAgent:

      script_path: main_pc_code/FORMAINPC/chain_of_thought_agent.py

      port: ${PORT_OFFSET}+5612

      health_check_port: ${PORT_OFFSET}+6612

      required: true

      dependencies:

      - ModelOpsCoordinator

      - SystemDigitalTwin

    GoTToTAgent:

      script_path: main_pc_code/FORMAINPC/got_tot_agent.py

      port: ${PORT_OFFSET}+5646

      health_check_port: ${PORT_OFFSET}+6646

      required: false

      dependencies:

      - ModelOpsCoordinator

      - SystemDigitalTwin

      - ChainOfThoughtAgent

    CognitiveModelAgent:

      script_path: main_pc_code/FORMAINPC/cognitive_model_agent.py

      port: ${PORT_OFFSET}+5641

      health_check_port: ${PORT_OFFSET}+6641

      required: false

      dependencies:

      - ChainOfThoughtAgent

      - SystemDigitalTwin

  vision_processing:

    FaceRecognitionAgent:

      script_path: main_pc_code/agents/face_recognition_agent.py

      port: ${PORT_OFFSET}+5610

      health_check_port: ${PORT_OFFSET}+6610

      required: true

      dependencies:

      - ModelOpsCoordinator

      - SystemDigitalTwin

  learning_knowledge:

    # DECOMMISSIONED: Replaced by ModelOpsCoordinator

    # LearningOrchestrationService:

    #   script_path: main_pc_code/agents/learning_orchestration_service.py

    #   port: ${PORT_OFFSET}+7210

    #   health_check_port: ${PORT_OFFSET}+8212

    #   required: true

    #   dependencies:

    #   - ModelManagerSuite

    #   - SystemDigitalTwin

    LearningOpportunityDetector:

      script_path: main_pc_code/agents/learning_opportunity_detector.py

      port: ${PORT_OFFSET}+7202

      health_check_port: ${PORT_OFFSET}+8202

      required: true

      dependencies:

      - ModelOpsCoordinator

      - MemoryFusionHub

      - SystemDigitalTwin

    LearningManager:

      script_path: main_pc_code/agents/learning_manager.py

      port: ${PORT_OFFSET}+5580

      health_check_port: ${PORT_OFFSET}+6580

      required: true

      dependencies:

      - MemoryFusionHub

      - ModelOpsCoordinator

      - SystemDigitalTwin

    ActiveLearningMonitor:

      script_path: main_pc_code/agents/active_learning_monitor.py

      port: ${PORT_OFFSET}+5638

      health_check_port: ${PORT_OFFSET}+6638

      required: true

      dependencies:

      - LearningManager

      - SystemDigitalTwin

  language_processing:

    # DECOMMISSIONED: Replaced by ModelOpsCoordinator

    # ModelOrchestrator:

    #   script_path: main_pc_code/agents/model_orchestrator.py

    #   port: ${PORT_OFFSET}+7213

    #   health_check_port: ${PORT_OFFSET}+8213

    #   required: true

    #   dependencies:

    #   - RequestCoordinator

    #   - ModelManagerSuite

    #   - SystemDigitalTwin

    # DECOMMISSIONED: Replaced by ModelOpsCoordinator

    # GoalManager:

    #   script_path: main_pc_code/agents/goal_manager.py

    #   port: ${PORT_OFFSET}+7205

    #   health_check_port: ${PORT_OFFSET}+8205

    #   required: true

    #   dependencies:

    #   - RequestCoordinator

    #   - ModelOrchestrator

    #   - SystemDigitalTwin

    #   - MemoryFusionHub

    IntentionValidatorAgent:

      script_path: main_pc_code/agents/IntentionValidatorAgent.py

      port: ${PORT_OFFSET}+5701

      health_check_port: ${PORT_OFFSET}+6701

      required: true

      dependencies:

      - ModelOpsCoordinator

      - SystemDigitalTwin

    NLUAgent:

      script_path: main_pc_code/agents/nlu_agent.py

      port: ${PORT_OFFSET}+5709

      health_check_port: ${PORT_OFFSET}+6709

      required: true

      dependencies:

      - SystemDigitalTwin

    AdvancedCommandHandler:

      script_path: main_pc_code/agents/advanced_command_handler.py

      port: ${PORT_OFFSET}+5710

      health_check_port: ${PORT_OFFSET}+6710

      required: true

      dependencies:

      - NLUAgent

      - CodeGenerator

      - SystemDigitalTwin

    ChitchatAgent:

      script_path: main_pc_code/agents/chitchat_agent.py

      port: ${PORT_OFFSET}+5711

      health_check_port: ${PORT_OFFSET}+6711

      required: true

      dependencies:

      - NLUAgent

      - SystemDigitalTwin

    FeedbackHandler:

      script_path: main_pc_code/agents/feedback_handler.py

      port: ${PORT_OFFSET}+5636

      health_check_port: ${PORT_OFFSET}+6636

      required: true

      dependencies:

      - NLUAgent

      - SystemDigitalTwin

    Responder:

      script_path: main_pc_code/agents/responder.py

      port: ${PORT_OFFSET}+5637

      health_check_port: ${PORT_OFFSET}+6637

      required: true

      dependencies:

      - EmotionEngine

      - FaceRecognitionAgent

      - NLUAgent

      - StreamingTTSAgent

      - SystemDigitalTwin

      - TTSService

    DynamicIdentityAgent:

      script_path: main_pc_code/agents/DynamicIdentityAgent.py

      port: ${PORT_OFFSET}+5802

      health_check_port: ${PORT_OFFSET}+6802

      required: true

      dependencies:

      - ModelOpsCoordinator

      - SystemDigitalTwin

    EmotionSynthesisAgent:

      script_path: main_pc_code/agents/emotion_synthesis_agent.py

      port: ${PORT_OFFSET}+5706

      health_check_port: ${PORT_OFFSET}+6706

      required: true

      dependencies:

      - ModelOpsCoordinator

      - SystemDigitalTwin

  speech_services:

    STTService:

      script_path: main_pc_code/services/stt_service.py

      port: ${PORT_OFFSET}+5800

      health_check_port: ${PORT_OFFSET}+6800

      required: true

      dependencies:

      - ModelOpsCoordinator

      - SystemDigitalTwin

    TTSService:

      script_path: main_pc_code/services/tts_service.py

      port: ${PORT_OFFSET}+5801

      health_check_port: ${PORT_OFFSET}+6801

      required: true

      dependencies:

      - ModelOpsCoordinator

      - SystemDigitalTwin

  audio_interface:

    AudioCapture:

      script_path: main_pc_code/agents/streaming_audio_capture.py

      port: "${PORT_OFFSET}+6550"

      health_check_port: "${PORT_OFFSET}+7550"

      required: ${RTAP_ENABLED:-false} == 'false'

      dependencies:

      - SystemDigitalTwin

    FusedAudioPreprocessor:

      script_path: main_pc_code/agents/fused_audio_preprocessor.py

      port: "${PORT_OFFSET}+6551"

      health_check_port: "${PORT_OFFSET}+7551"

      required: ${RTAP_ENABLED:-false} == 'false'

      dependencies:

      - AudioCapture

      - SystemDigitalTwin

    StreamingInterruptHandler:

      script_path: main_pc_code/agents/streaming_interrupt_handler.py

      port: ${PORT_OFFSET}+5576

      health_check_port: ${PORT_OFFSET}+6576

      required: ${RTAP_ENABLED:-false} == 'false'

      dependencies:

      - StreamingSpeechRecognition

      - StreamingTTSAgent

      - SystemDigitalTwin

    StreamingSpeechRecognition:

      script_path: main_pc_code/agents/streaming_speech_recognition.py

      port: "${PORT_OFFSET}+6553"

      health_check_port: "${PORT_OFFSET}+7553"

      required: ${RTAP_ENABLED:-false} == 'false'

      dependencies:

      - FusedAudioPreprocessor

      - STTService

      - SystemDigitalTwin

    StreamingTTSAgent:

      script_path: main_pc_code/agents/streaming_tts_agent.py

      port: ${PORT_OFFSET}+5562

      health_check_port: ${PORT_OFFSET}+6562

      required: true

      dependencies:

      - ModelOpsCoordinator

      - TTSService

      - SystemDigitalTwin

      - UnifiedSystemAgent

    WakeWordDetector:

      script_path: main_pc_code/agents/wake_word_detector.py

      port: "${PORT_OFFSET}+6552"

      health_check_port: "${PORT_OFFSET}+7552"

      required: ${RTAP_ENABLED:-false} == 'false'

      dependencies:

      - AudioCapture

      - FusedAudioPreprocessor

      - SystemDigitalTwin

    StreamingLanguageAnalyzer:

      script_path: main_pc_code/agents/streaming_language_analyzer.py

      port: ${PORT_OFFSET}+5579

      health_check_port: ${PORT_OFFSET}+6579

      required: ${RTAP_ENABLED:-false} == 'false'

      dependencies:

      - StreamingSpeechRecognition

      - SystemDigitalTwin

      - CloudTranslationService

    ProactiveAgent:

      script_path: main_pc_code/agents/ProactiveAgent.py

      port: ${PORT_OFFSET}+5624

      health_check_port: ${PORT_OFFSET}+6624

      required: true

      dependencies:

      - ModelOpsCoordinator

      - SystemDigitalTwin

  emotion_system:

    EmotionEngine:

      script_path: main_pc_code/agents/emotion_engine.py

      port: ${PORT_OFFSET}+5590

      health_check_port: ${PORT_OFFSET}+6590

      required: true

      dependencies:

      - SystemDigitalTwin

    MoodTrackerAgent:

      script_path: main_pc_code/agents/mood_tracker_agent.py

      port: ${PORT_OFFSET}+5704

      health_check_port: ${PORT_OFFSET}+6704

      required: true

      dependencies:

      - EmotionEngine

      - SystemDigitalTwin

    HumanAwarenessAgent:

      script_path: main_pc_code/agents/human_awareness_agent.py

      port: ${PORT_OFFSET}+5705

      health_check_port: ${PORT_OFFSET}+6705

      required: true

      dependencies:

      - EmotionEngine

      - SystemDigitalTwin

    ToneDetector:

      script_path: main_pc_code/agents/tone_detector.py

      port: ${PORT_OFFSET}+5625

      health_check_port: ${PORT_OFFSET}+6625

      required: true

      dependencies:

      - EmotionEngine

      - SystemDigitalTwin

    VoiceProfilingAgent:

      script_path: main_pc_code/agents/voice_profiling_agent.py

      port: ${PORT_OFFSET}+5708

      health_check_port: ${PORT_OFFSET}+6708

      required: true

      dependencies:

      - EmotionEngine

      - SystemDigitalTwin

    EmpathyAgent:

      script_path: main_pc_code/agents/EmpathyAgent.py

      port: ${PORT_OFFSET}+5703

      health_check_port: ${PORT_OFFSET}+6703

      required: true

      dependencies:

      - EmotionEngine

      - StreamingTTSAgent

      - SystemDigitalTwin

  translation_services:

    CloudTranslationService:

      script_path: main_pc_code/agents/cloud_translation_service.py

      port: ${PORT_OFFSET}+5592

      health_check_port: ${PORT_OFFSET}+6592

      required: true

      dependencies:

        - SystemDigitalTwin

    StreamingTranslationProxy:

      script_path: services/streaming_translation_proxy/proxy.py

      port: ${PORT_OFFSET}+5596

      health_check_port: ${PORT_OFFSET}+6596

      required: true

      dependencies:

      - CloudTranslationService

      - SystemDigitalTwin

    ObservabilityDashboardAPI:

      script_path: services/obs_dashboard_api/server.py

      port: ${PORT_OFFSET}+8001

      health_check_port: ${PORT_OFFSET}+9007

      required: true

      dependencies:

      - UnifiedObservabilityCenter

  docker_groups:

    infra_core:

      description: Core service discovery & digital-twin infrastructure

      agents:

      - ServiceRegistry

      - SystemDigitalTwin

  # NOTE: Legacy “observability” docker group removed; unified on UOC

  # DECOMMISSIONED: Legacy coordination services replaced by ModelOpsCoordinator

  # coordination:

  #   description: Request routing, GPU model lifecycle & VRAM optimisation

  #   agents:

#   - RequestCoordinator

  #   - ModelManagerSuite

  #   - VRAMOptimizerAgent

  observability:

    description: Centralised telemetry, metrics, prediction & health

    agents:

    - UnifiedObservabilityCenter

  core_hubs:

    description: Unified core service hubs (All 5 consolidated hubs)

    agents:

    - MemoryFusionHub

    - ModelOpsCoordinator

    - AffectiveProcessingCenter

    - RealTimeAudioPipeline

    - UnifiedObservabilityCenter

  # DECOMMISSIONED: Legacy memory stack replaced by MemoryFusionHub

  # memory_stack:

  #   description: Short/long-term memory services

  #   agents:

  #   - MemoryClient

  #   - SessionMemoryAgent

  #   - KnowledgeBase

  vision_gpu:

    description: GPU-bound vision processing services

    agents:

    - FaceRecognitionAgent

  speech_gpu:

    description: GPU-bound STT/TTS & audio streaming pipeline

    agents:

    - STTService

    - TTSService

    - AudioCapture

    - FusedAudioPreprocessor

    - StreamingSpeechRecognition

    - StreamingTTSAgent

    - WakeWordDetector

    - StreamingInterruptHandler

    - StreamingLanguageAnalyzer

  learning_gpu:

    description: Active/self learning pipeline using GPU training slices

    agents:

    - LearningManager

    - LearningOpportunityDetector

    - ActiveLearningMonitor

  reasoning_gpu:

    description: Large-context reasoning agents utilising GPU inference

    agents:

    - ChainOfThoughtAgent

    - CognitiveModelAgent

  language_stack:

    description: High-level dialogue, NLU, identity & emotional synthesis

    agents:

    - NLUAgent

    - IntentionValidatorAgent

    - AdvancedCommandHandler

    - ChitchatAgent

    - FeedbackHandler

    - Responder

    - DynamicIdentityAgent

    - EmotionSynthesisAgent

    - ProactiveAgent

  utility_cpu:

    description: Miscellaneous CPU-bound utility agents

    agents:

    - CodeGenerator

    - Executor

    - PredictiveHealthMonitor

    - SmartHomeAgent

  # emotion_system group removed (duplicate of detailed agent definitions above)

  gpu_scheduler:

    description: Cross-machine GPU load balancer

    agents:

    - CrossMachineGPUScheduler

  translation_proxy:

    description: Low-latency WebSocket translation proxy

    agents:

    - StreamingTranslationProxy

  observability_ui:

    description: Dashboard UI + API for system metrics

    agents:

    - ObservabilityDashboardAPI

  self_healing:

    description: Auto-restart supervisor for failed agents

    agents:

    - SelfHealingSupervisor