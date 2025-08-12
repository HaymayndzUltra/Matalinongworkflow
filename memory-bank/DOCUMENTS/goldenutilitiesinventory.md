Best Practices Inventory & Adoption Guide
Version: 2025-08-07  Author: Code-Audit Bot
Source Docs: code_excellence_audit.md, agentdependency.md, full code scan (Aug-07)
Part 1 · Golden Utilities Inventory & Adoption Matrix

# Golden Utility / Pattern Location (Authoritative File) Currently Used By (2-3 concrete modules) High-Priority Adoption Targets (3-5 key modules)

1 @retry_with_backoff decorator common/utils/network_util.py • common/net/zmq_client.py <br>• main_pc_code/agents/learning_orchestration_service.py <br>• pc2_code/agents/remote_connector_agent.py • ModelManagerSuite <br>• RequestCoordinator <br>• SystemDigitalTwin <br>• ObservabilityHub (pc2) <br>• UnifiedWebAgent
2 env_helpers.get_env & friends (type-safe env vars) common/env_helpers.py • phase1_implementation/consolidated_agents/observability_hub/…/observability_hub.py <br>• services/cross_gpu_scheduler/app.py <br>• main_pc_code/agents/vram_optimizer_agent.py • ALL yaml.load startup scripts (e.g. start_basic_services.py) <br>• MemoryOrchestratorService <br>• ModelManagerSuite <br>• SpeechRelayService <br>• CacheManager
3 PathManager (container-friendly path resolver) common/utils/path_manager.py • scripts/validate_config.py <br>• main_pc_code/agents/face_recognition_agent.py <br>• test/cross_machine_tests.py • SystemDigitalTwin <br>• LearningManager <br>• FileSystemAssistantAgent <br>• VisionProcessingAgent <br>• UnifiedMemoryReasoningAgent
4 CircuitBreaker class (production-ready) main_pc_code/agents/memory_client.py (authoritative copy) • MemoryClient <br>• RequestCoordinator (local adaptation) <br>• AsyncProcessor (pc2) • ModelManagerSuite <br>• UnifiedSystemAgent <br>• CrossMachineGPUScheduler <br>• RemoteConnectorAgent <br>• ObservabilityHub
5 ThreadPoolExecutor pattern (named pools, max-concurrency config) phase1_implementation/consolidated_agents/observability_hub/…/observability_hub.py:869-913 • ObservabilityHub (main_pc) <br>• SelfHealingSupervisor <br>• start_system_v2.py • RequestCoordinator <br>• ModelManagerSuite <br>• GoalManager <br>• LearningOrchestrationService <br>• TaskScheduler
6 AsyncIOManager.batch_process_files (high-performance async I/O) common/utils/async_io.py • main_pc_code/agents/fused_audio_preprocessor.py <br>• pc2_code/agents/unified_web_agent.py <br>• services/streaming_translation_proxy/proxy.py • UnifiedConfigLoader (could async-load overrides) <br>• ObservabilityDashboardAPI <br>• UnifiedWebAgent bulk crawls <br>• DreamWorldAgent <br>• StreamingSpeechRecognition
7 Bulkhead (resource isolation) common/resiliency/bulkhead.py • SelfHealingSupervisor <br>• CentralErrorBus <br>• SpeechRelayService • ModelManagerSuite <br>• RequestCoordinator <br>• ObservabilityHub (pc2) <br>• VRAMOptimizerAgent <br>• TieredResponder
8 UnifiedConfigLoader (hierarchical overrides) common/utils/unified_config_loader.py • ObservabilityHub (main_pc) <br>• System Startup v2 script <br>• pc2_code/agents/unified_utils_agent.py • MemoryOrchestratorService <br>• ModelManagerSuite <br>• StreamingTTSAgent <br>• LearningManager <br>• DreamingModeAgent
9 ObservabilityHub’s environment_detection helper same file as #5 (lines 891-972) • ObservabilityHub (both hosts) • All command-line utilities defaulting to localhost <br>• SystemDigitalTwin <br>• CrossMachineGPUScheduler <br>• AuthenticationAgent <br>• AgentTrustScorer
10 Pydantic data models (common/utils/data_models.py) common/utils/data_models.py • RequestCoordinator <br>• LearningOrchestrationService <br>• pc2_code/agents/resource_manager.py • ModelManagerSuite (raw dicts) <br>• KnowledgeBase <br>• VoiceProfilingAgent <br>• ChitchatAgent <br>• UnifiedMemoryReasoningAgent

> Legend:
> • Authoritative Copy = location regarded as the canonical implementation.
> • High-Priority Adoption Targets were picked by impact (frequency of calls, critical path, or prior incidents).
> Part 2 · Host-Specific Standards Comparison
> Concern main_pc (54 agents) pc2 (25 agents) Key Gaps & Action Items
> Configuration Management Mixed usage. Roughly 60 % still load YAML via yaml.safe_load( open(...)). The remaining rely on UnifiedConfigLoader (e.g. ObservabilityHub, some services). Env vars partly handled via env_helpers. Strong tendency toward utility wrapper in pc2_code/agents/utils/config_loader.py, which includes env-var substitution (${VAR} → os.environ). Only 25 % use UnifiedConfigLoader. 1. Migrate all main_pc agents to UnifiedConfigLoader for parity. <br>2. Back-port ${VAR} substitution helper into the common loader and deprecate pc2-specific copy.
> Error Handling Notable pattern: CircuitBreaker in MemoryClient and a custom clone in RequestCoordinator. Other agents rely on try/except with logging. Unified retry via @retry_with_backoff is sporadic. Generally simpler try/except with printed logs. AsyncProcessor imports the CircuitBreaker but few others. Little retry logic. 1. Extract single shared CircuitBreaker to common/resilience/. <br>2. Enforce @retry_with_backoff on all outbound ZMQ/HTTP calls on both hosts.
> Communication Library / Pattern Heavy ZeroMQ usage (REQ/REP, PUB/SUB). A few HTTP FastAPI servers (ObservabilityHub, ServiceRegistry). There is an emergent common/net/zmq_client.py wrapper already using retry pattern. Also ZeroMQ-centric, but several agents call main_pc services via raw zmq.Socket. Fewer HTTP endpoints; gRPC only in SpeechRelayService. 1. Promote common/net/zmq_client.py as mandatory wrapper on both hosts—eliminates duplicated socket setup. <br>2. Standardise on FastAPI + gRPC for inter-machine APIs (Roadmap Phase 2).
> Quick-Reference Cheat Sheet
> Adopt Immediately: @retry_with_backoff, CircuitBreaker, PathManager, and env_helpers.get_env across all critical-path agents (ModelManagerSuite, RequestCoordinator, SystemDigitalTwin).
> PC2 Alignment: Replace bespoke config_loader.py with the shared UnifiedConfigLoader once ${VAR} substitution is integrated.
> Resource Isolation: Integrate the Bulkhead pattern into high-traffic coordinators before scaling tests.
> Observability: Port the proven ThreadPoolExecutor + environment-detection pattern from ObservabilityHub to the new Unified Observability Center (and to other monitoring-heavy agents).
> Data Models: Migrate raw-dict message payloads to Pydantic models (common/utils/data_models.py) to unlock automatic JSON-schema validation.
> Applying this matrix during consolidation will harmonize practices across both machines, reduce hidden bugs, and accelerate future refactors.
