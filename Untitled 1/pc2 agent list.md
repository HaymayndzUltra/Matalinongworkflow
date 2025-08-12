global_settings:

  environment:

    PYTHONPATH: ${PYTHONPATH}:${PWD}/..

    LOG_LEVEglobal_settings:

  environment:

    PYTHONPATH: ${PYTHONPATH}:${PWD}/..

    LOG_LEVEL: INFO

    DEBUG_MODE: 'false'

  resource_limits:

    cpu_percent: 80

    memory_mb: 4096

    max_threads: 8

  health_checks:

    interval_seconds: 30

    timeout_seconds: 10

    retries: 3

pc2_services:

- name: CentralErrorBus

  script_path: services/central_error_bus/error_bus.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7150

  health_check_port: ${PORT_OFFSET}+8150

  required: true

  dependencies: []

# DECOMMISSIONED: Legacy memory agents replaced by MemoryFusionHub

# - name: MemoryOrchestratorService

#   script_path: pc2_code/agents/memory_orchestrator_service.py

#   host: 0.0.0.0

#   port: ${PORT_OFFSET}+7140

#   health_check_port: ${PORT_OFFSET}+8140

#   required: true

#   dependencies: []

- name: MemoryFusionHub

  script_path: memory_fusion_hub/app.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+5713

  health_check_port: ${PORT_OFFSET}+6713

  required: true

  dependencies:

  - UnifiedObservabilityCenter

  config:

    zmq_port: ${PORT_OFFSET}+5713

    grpc_port: ${PORT_OFFSET}+5714

    metrics_port: ${PORT_OFFSET}+8080

    redis_url: "${REDIS_URL:-redis://localhost:6379/0}"

    sqlite_path: "/workspace/memory.db"

- name: RealTimeAudioPipelinePC2

  script_path: real_time_audio_pipeline/app.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+5557

  health_check_port: ${PORT_OFFSET}+6557

  required: true

  dependencies: []

  config:

    environment: "pc2"

    sample_rate: 16000

    frame_size: 512

    channels: 1

    buffer_size: 100

    max_latency_ms: 50

    zmq_port: ${PORT_OFFSET}+5557

    grpc_port: ${PORT_OFFSET}+5558

- name: TieredResponder

  script_path: pc2_code/agents/tiered_responder.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7100

  health_check_port: ${PORT_OFFSET}+8100

  required: true

  dependencies:

  - ResourceManager

- name: AsyncProcessor

  script_path: pc2_code/agents/async_processor.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7101

  health_check_port: ${PORT_OFFSET}+8101

  required: true

  dependencies:

  - ResourceManager

- name: CacheManager

  script_path: pc2_code/agents/cache_manager.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7102

  health_check_port: ${PORT_OFFSET}+8102

  required: true

  dependencies:

  - MemoryFusionHub

- name: VisionProcessingAgent

  script_path: pc2_code/agents/VisionProcessingAgent.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7160

  health_check_port: ${PORT_OFFSET}+8160

  required: true

  dependencies:

  - CacheManager

- name: DreamWorldAgent

  script_path: pc2_code/agents/DreamWorldAgent.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7104

  health_check_port: ${PORT_OFFSET}+8104

  dependencies:

  - MemoryFusionHub

  required: true

# DECOMMISSIONED: Legacy memory agents replaced by MemoryFusionHub

# - name: UnifiedMemoryReasoningAgent

#   script_path: pc2_code/agents/unified_memory_reasoning_agent.py

#   host: 0.0.0.0

#   port: ${PORT_OFFSET}+7105

#   health_check_port: ${PORT_OFFSET}+8105

#   dependencies:

#   - MemoryOrchestratorService

#   required: true

# - name: ContextManager

#   script_path: pc2_code/agents/context_manager.py

#   host: 0.0.0.0

#   port: ${PORT_OFFSET}+7111

#   health_check_port: ${PORT_OFFSET}+8111

#   dependencies:

#   - MemoryOrchestratorService

#   required: true

# - name: ExperienceTracker

#   script_path: pc2_code/agents/experience_tracker.py

#   host: 0.0.0.0

#   port: ${PORT_OFFSET}+7112

#   health_check_port: ${PORT_OFFSET}+8112

#   dependencies:

#   - MemoryOrchestratorService

#   required: true

- name: ResourceManager

  script_path: pc2_code/agents/resource_manager.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7113

  health_check_port: ${PORT_OFFSET}+8113

  required: true

  dependencies:

  - UnifiedObservabilityCenter

- name: TaskScheduler

  script_path: pc2_code/agents/task_scheduler.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7115

  health_check_port: ${PORT_OFFSET}+8115

  dependencies:

  - AsyncProcessor

  required: true

- name: AuthenticationAgent

  script_path: pc2_code/agents/ForPC2/AuthenticationAgent.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7116

  health_check_port: ${PORT_OFFSET}+8116

  required: true

  dependencies:

  - UnifiedUtilsAgent

- name: UnifiedUtilsAgent

  script_path: pc2_code/agents/ForPC2/unified_utils_agent.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7118

  health_check_port: ${PORT_OFFSET}+8118

  required: true

  dependencies:

  - UnifiedObservabilityCenter

- name: ProactiveContextMonitor

  script_path: pc2_code/agents/ForPC2/proactive_context_monitor.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7119

  health_check_port: ${PORT_OFFSET}+8119

  dependencies:

  - MemoryFusionHub

  required: true

- name: AgentTrustScorer

  script_path: pc2_code/agents/AgentTrustScorer.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7122

  health_check_port: ${PORT_OFFSET}+8122

  required: true

  dependencies:

  - UnifiedObservabilityCenter

- name: FileSystemAssistantAgent

  script_path: pc2_code/agents/filesystem_assistant_agent.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7123

  health_check_port: ${PORT_OFFSET}+8123

  required: true

  dependencies:

  - UnifiedUtilsAgent

- name: RemoteConnectorAgent

  script_path: pc2_code/agents/remote_connector_agent.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7124

  health_check_port: ${PORT_OFFSET}+8124

  required: true

  dependencies:

  - AdvancedRouter

- name: UnifiedWebAgent

  script_path: pc2_code/agents/unified_web_agent.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7126

  health_check_port: ${PORT_OFFSET}+8126

  required: true

  dependencies:

  - FileSystemAssistantAgent

  - MemoryFusionHub

- name: DreamingModeAgent

  script_path: pc2_code/agents/DreamingModeAgent.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7127

  health_check_port: ${PORT_OFFSET}+8127

  dependencies:

  - DreamWorldAgent

  required: true

- name: AdvancedRouter

  script_path: pc2_code/agents/advanced_router.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7129

  health_check_port: ${PORT_OFFSET}+8129

  required: true

  dependencies:

  - TaskScheduler

- name: UnifiedObservabilityCenter

  script_path: unified_observability_center/app.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+9100

  health_check_port: ${PORT_OFFSET}+9110

  required: true

  dependencies: []

  config:

    scope: pc2_agents

    prometheus_port: ${PORT_OFFSET}+9100

    cross_machine_sync: true

    mainpc_hub_endpoint: ${MAINPC_OBS_HUB}

    parallel_health_checks: true

    prediction_enabled: true

- name: TutoringServiceAgent

  script_path: pc2_code/agents/TutoringServiceAgent.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7108

  health_check_port: ${PORT_OFFSET}+8108

  required: true

  dependencies:

  - MemoryFusionHub

- name: SelfHealingSupervisor

  script_path: services/self_healing_supervisor/supervisor.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7009

  health_check_port: ${PORT_OFFSET}+9008

  required: true

  dependencies:

  - UnifiedObservabilityCenter

  config:

    docker_sock: /var/run/docker.sock

- name: SpeechRelayService

  script_path: services/speech_relay/relay.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7130

  health_check_port: ${PORT_OFFSET}+8130

  required: true

  dependencies:

  - VisionProcessingAgent

  - StreamingTTSAgent

health_checks:

  start_period_seconds: 300

pc2_network:

  host: 0.0.0.0

  agent_ports:

    start: 7100

    end: 7199

  health_check_ports:

    start: 8100

    end: 8199

error_bus_port: ${PORT_OFFSET}+7150

docker_groups:

  infra_core:

    description: Core observability & resource management infrastructure

    agents:

    - UnifiedObservabilityCenter

    - ResourceManager

  core_hubs:

    description: Memory Fusion Hub for unified memory management

    agents:

    - MemoryFusionHub

  # DECOMMISSIONED: Legacy memory stack replaced by MemoryFusionHub

  # memory_stack:

  #   description: Memory orchestration & reasoning services

  #   agents:

  #   - MemoryOrchestratorService

  #   - CacheManager

  #   - UnifiedMemoryReasoningAgent

  #   - ContextManager

  #   - ExperienceTracker

  async_pipeline:

    description: Asynchronous task processing & routing pipeline

    agents:

    - AsyncProcessor

    - TaskScheduler

    - AdvancedRouter

    - TieredResponder

    - CacheManager

  tutoring_cpu:

    description: Tutoring and educational agents (CPU-bound)

    agents:

    - TutoringServiceAgent

  vision_dream_gpu:

    description: GPU-intensive vision processing and dream world services

    agents:

    - VisionProcessingAgent

    - DreamWorldAgent

    - DreamingModeAgent

    - SpeechRelayService

  utility_suite:

    description: Support utilities and miscellaneous helpers

    agents:

    - UnifiedUtilsAgent

    - FileSystemAssistantAgent

    - RemoteConnectorAgent

    - AuthenticationAgent

    - AgentTrustScorer

    - ProactiveContextMonitor

  web_interface:

    description: User-facing web interface agents

    agents:

    - UnifiedWebAgent

  error_bus:

    description: Centralised error event bus

    agents:

    - CentralErrorBus

  self_healing:

    description: Auto-restart supervisor for failed agents

    agents:

    - SelfHealingSupervisorL: INFO

    DEBUG_MODE: 'false'

  resource_limits:

    cpu_percent: 80

    memory_mb: 4096

    max_threads: 8

  health_checks:

    interval_seconds: 30

    timeout_seconds: 10

    retries: 3

pc2_services:

- name: CentralErrorBus

  script_path: services/central_error_bus/error_bus.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7150

  health_check_port: ${PORT_OFFSET}+8150

  required: true

  dependencies: []

# DECOMMISSIONED: Legacy memory agents replaced by MemoryFusionHub

# - name: MemoryOrchestratorService

#   script_path: pc2_code/agents/memory_orchestrator_service.py

#   host: 0.0.0.0

#   port: ${PORT_OFFSET}+7140

#   health_check_port: ${PORT_OFFSET}+8140

#   required: true

#   dependencies: []

- name: MemoryFusionHub

  script_path: memory_fusion_hub/app.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+5713

  health_check_port: ${PORT_OFFSET}+6713

  required: true

  dependencies:

  - UnifiedObservabilityCenter

  config:

    zmq_port: ${PORT_OFFSET}+5713

    grpc_port: ${PORT_OFFSET}+5714

    metrics_port: ${PORT_OFFSET}+8080

    redis_url: "${REDIS_URL:-redis://localhost:6379/0}"

    sqlite_path: "/workspace/memory.db"

- name: RealTimeAudioPipelinePC2

  script_path: real_time_audio_pipeline/app.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+5557

  health_check_port: ${PORT_OFFSET}+6557

  required: true

  dependencies: []

  config:

    environment: "pc2"

    sample_rate: 16000

    frame_size: 512

    channels: 1

    buffer_size: 100

    max_latency_ms: 50

    zmq_port: ${PORT_OFFSET}+5557

    grpc_port: ${PORT_OFFSET}+5558

- name: TieredResponder

  script_path: pc2_code/agents/tiered_responder.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7100

  health_check_port: ${PORT_OFFSET}+8100

  required: true

  dependencies:

  - ResourceManager

- name: AsyncProcessor

  script_path: pc2_code/agents/async_processor.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7101

  health_check_port: ${PORT_OFFSET}+8101

  required: true

  dependencies:

  - ResourceManager

- name: CacheManager

  script_path: pc2_code/agents/cache_manager.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7102

  health_check_port: ${PORT_OFFSET}+8102

  required: true

  dependencies:

  - MemoryFusionHub

- name: VisionProcessingAgent

  script_path: pc2_code/agents/VisionProcessingAgent.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7160

  health_check_port: ${PORT_OFFSET}+8160

  required: true

  dependencies:

  - CacheManager

- name: DreamWorldAgent

  script_path: pc2_code/agents/DreamWorldAgent.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7104

  health_check_port: ${PORT_OFFSET}+8104

  dependencies:

  - MemoryFusionHub

  required: true

# DECOMMISSIONED: Legacy memory agents replaced by MemoryFusionHub

# - name: UnifiedMemoryReasoningAgent

#   script_path: pc2_code/agents/unified_memory_reasoning_agent.py

#   host: 0.0.0.0

#   port: ${PORT_OFFSET}+7105

#   health_check_port: ${PORT_OFFSET}+8105

#   dependencies:

#   - MemoryOrchestratorService

#   required: true

# - name: ContextManager

#   script_path: pc2_code/agents/context_manager.py

#   host: 0.0.0.0

#   port: ${PORT_OFFSET}+7111

#   health_check_port: ${PORT_OFFSET}+8111

#   dependencies:

#   - MemoryOrchestratorService

#   required: true

# - name: ExperienceTracker

#   script_path: pc2_code/agents/experience_tracker.py

#   host: 0.0.0.0

#   port: ${PORT_OFFSET}+7112

#   health_check_port: ${PORT_OFFSET}+8112

#   dependencies:

#   - MemoryOrchestratorService

#   required: true

- name: ResourceManager

  script_path: pc2_code/agents/resource_manager.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7113

  health_check_port: ${PORT_OFFSET}+8113

  required: true

  dependencies:

  - UnifiedObservabilityCenter

- name: TaskScheduler

  script_path: pc2_code/agents/task_scheduler.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7115

  health_check_port: ${PORT_OFFSET}+8115

  dependencies:

  - AsyncProcessor

  required: true

- name: AuthenticationAgent

  script_path: pc2_code/agents/ForPC2/AuthenticationAgent.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7116

  health_check_port: ${PORT_OFFSET}+8116

  required: true

  dependencies:

  - UnifiedUtilsAgent

- name: UnifiedUtilsAgent

  script_path: pc2_code/agents/ForPC2/unified_utils_agent.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7118

  health_check_port: ${PORT_OFFSET}+8118

  required: true

  dependencies:

  - UnifiedObservabilityCenter

- name: ProactiveContextMonitor

  script_path: pc2_code/agents/ForPC2/proactive_context_monitor.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7119

  health_check_port: ${PORT_OFFSET}+8119

  dependencies:

  - MemoryFusionHub

  required: true

- name: AgentTrustScorer

  script_path: pc2_code/agents/AgentTrustScorer.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7122

  health_check_port: ${PORT_OFFSET}+8122

  required: true

  dependencies:

  - UnifiedObservabilityCenter

- name: FileSystemAssistantAgent

  script_path: pc2_code/agents/filesystem_assistant_agent.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7123

  health_check_port: ${PORT_OFFSET}+8123

  required: true

  dependencies:

  - UnifiedUtilsAgent

- name: RemoteConnectorAgent

  script_path: pc2_code/agents/remote_connector_agent.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7124

  health_check_port: ${PORT_OFFSET}+8124

  required: true

  dependencies:

  - AdvancedRouter

- name: UnifiedWebAgent

  script_path: pc2_code/agents/unified_web_agent.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7126

  health_check_port: ${PORT_OFFSET}+8126

  required: true

  dependencies:

  - FileSystemAssistantAgent

  - MemoryFusionHub

- name: DreamingModeAgent

  script_path: pc2_code/agents/DreamingModeAgent.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7127

  health_check_port: ${PORT_OFFSET}+8127

  dependencies:

  - DreamWorldAgent

  required: true

- name: AdvancedRouter

  script_path: pc2_code/agents/advanced_router.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7129

  health_check_port: ${PORT_OFFSET}+8129

  required: true

  dependencies:

  - TaskScheduler

- name: UnifiedObservabilityCenter

  script_path: unified_observability_center/app.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+9100

  health_check_port: ${PORT_OFFSET}+9110

  required: true

  dependencies: []

  config:

    scope: pc2_agents

    prometheus_port: ${PORT_OFFSET}+9100

    cross_machine_sync: true

    mainpc_hub_endpoint: ${MAINPC_OBS_HUB}

    parallel_health_checks: true

    prediction_enabled: true

- name: TutoringServiceAgent

  script_path: pc2_code/agents/TutoringServiceAgent.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7108

  health_check_port: ${PORT_OFFSET}+8108

  required: true

  dependencies:

  - MemoryFusionHub

- name: SelfHealingSupervisor

  script_path: services/self_healing_supervisor/supervisor.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7009

  health_check_port: ${PORT_OFFSET}+9008

  required: true

  dependencies:

  - UnifiedObservabilityCenter

  config:

    docker_sock: /var/run/docker.sock

- name: SpeechRelayService

  script_path: services/speech_relay/relay.py

  host: 0.0.0.0

  port: ${PORT_OFFSET}+7130

  health_check_port: ${PORT_OFFSET}+8130

  required: true

  dependencies:

  - VisionProcessingAgent

  - StreamingTTSAgent

health_checks:

  start_period_seconds: 300

pc2_network:

  host: 0.0.0.0

  agent_ports:

    start: 7100

    end: 7199

  health_check_ports:

    start: 8100

    end: 8199

error_bus_port: ${PORT_OFFSET}+7150

docker_groups:

  infra_core:

    description: Core observability & resource management infrastructure

    agents:

    - UnifiedObservabilityCenter

    - ResourceManager

  core_hubs:

    description: Memory Fusion Hub for unified memory management

    agents:

    - MemoryFusionHub

  # DECOMMISSIONED: Legacy memory stack replaced by MemoryFusionHub

  # memory_stack:

  #   description: Memory orchestration & reasoning services

  #   agents:

  #   - MemoryOrchestratorService

  #   - CacheManager

  #   - UnifiedMemoryReasoningAgent

  #   - ContextManager

  #   - ExperienceTracker

  async_pipeline:

    description: Asynchronous task processing & routing pipeline

    agents:

    - AsyncProcessor

    - TaskScheduler

    - AdvancedRouter

    - TieredResponder

    - CacheManager

  tutoring_cpu:

    description: Tutoring and educational agents (CPU-bound)

    agents:

    - TutoringServiceAgent

  vision_dream_gpu:

    description: GPU-intensive vision processing and dream world services

    agents:

    - VisionProcessingAgent

    - DreamWorldAgent

    - DreamingModeAgent

    - SpeechRelayService

  utility_suite:

    description: Support utilities and miscellaneous helpers

    agents:

    - UnifiedUtilsAgent

    - FileSystemAssistantAgent

    - RemoteConnectorAgent

    - AuthenticationAgent

    - AgentTrustScorer

    - ProactiveContextMonitor

  web_interface:

    description: User-facing web interface agents

    agents:

    - UnifiedWebAgent

  error_bus:

    description: Centralised error event bus

    agents:

    - CentralErrorBus

  self_healing:

    description: Auto-restart supervisor for failed agents

    agents:

    - SelfHealingSupervisor