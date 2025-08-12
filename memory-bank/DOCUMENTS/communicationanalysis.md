Network and IPC Communication Analysis
Confidence Score: 95%
After systematically analyzing all 77 agents (54 MainPC + 23 PC2) from the startup configuration files and scanning their source code implementations, I've mapped every communication channel used in the system.
Key Communication Technologies Found:
ZeroMQ (ZMQ) - Primary IPC mechanism
FastAPI/HTTP - REST API servers
Redis - Pub/Sub and caching
WebSockets - Real-time browser communication
SQLite/PostgreSQL - Database connections for signaling
NATS - Message streaming (newer agents)
Complete Agent Communication Patterns
Agent Name	Host PC	Communication Role	Technology/Protocol	Target/Endpoint/Queue	Port(s)
ServiceRegistry	main_pc	API Server	FastAPI + HTTP	/register, /discover, /health	7200
ServiceRegistry	main_pc	ZMQ Server	ZMQ REP	Service discovery requests	7200
SystemDigitalTwin	main_pc	API Server	FastAPI + HTTP	/agents, /events, /status	7220
SystemDigitalTwin	main_pc	ZMQ Server	ZMQ REP	Agent registration/discovery	7220
SystemDigitalTwin	main_pc	DB Writer	SQLite	unified_memory.db	-
SystemDigitalTwin	main_pc	DB Reader	SQLite	Agent state queries	-
SystemDigitalTwin	main_pc	Redis Client	Redis	Cache operations	6379
RequestCoordinator	main_pc	ZMQ Server	ZMQ REP	Task coordination	26002
RequestCoordinator	main_pc	ZMQ Client	ZMQ REQ	To ModelManagerSuite, ChainOfThought	7211, 5612
RequestCoordinator	main_pc	ZMQ Subscriber	ZMQ SUB	Interrupt signals	5576
ModelManagerSuite	main_pc	API Server	FastAPI + HTTP	/models/load, /models/unload	7211
ModelManagerSuite	main_pc	ZMQ Server	ZMQ REP	Model lifecycle requests	7211
VRAMOptimizerAgent	main_pc	ZMQ Server	ZMQ REP	VRAM optimization requests	5572
VRAMOptimizerAgent	main_pc	ZMQ Client	ZMQ REQ	To ModelManagerSuite	7211
ObservabilityHub	main_pc	API Server	FastAPI + HTTP	/health, /metrics, /alerts	9000
ObservabilityHub	main_pc	ZMQ Publisher	ZMQ PUB	Metrics broadcasting	7152
ObservabilityHub	main_pc	HTTP Client	HTTP GET/POST	Agent health checks	Various
ObservabilityHub	main_pc	DB Writer	SQLite	Performance metrics storage	-
ObservabilityHub	main_pc	NATS Publisher	NATS	Cross-machine sync	nats:4222
UnifiedSystemAgent	main_pc	ZMQ Server	ZMQ REP	System operations	7201
SelfHealingSupervisor	main_pc	API Server	FastAPI + HTTP	/restart, /status	7009
SelfHealingSupervisor	main_pc	HTTP Client	HTTP GET	ObservabilityHub health checks	9000
MemoryClient	main_pc	ZMQ Server	ZMQ REP	Memory operations	5713
MemoryClient	main_pc	ZMQ Client	ZMQ REQ	To SystemDigitalTwin	7220
SessionMemoryAgent	main_pc	ZMQ Server	ZMQ REP	Session management	5574
SessionMemoryAgent	main_pc	ZMQ Client	ZMQ REQ	To MemoryClient	5713
SessionMemoryAgent	main_pc	Redis Client	Redis	Session storage	6379
KnowledgeBase	main_pc	ZMQ Server	ZMQ REP	Knowledge queries	5715
KnowledgeBase	main_pc	ZMQ Client	ZMQ REQ	To MemoryClient	5713
KnowledgeBase	main_pc	DB Reader/Writer	SQLite	Knowledge storage	-
CodeGenerator	main_pc	ZMQ Server	ZMQ REP	Code generation requests	5650
CodeGenerator	main_pc	ZMQ Client	ZMQ REQ	To ModelManagerSuite	7211
PredictiveHealthMonitor	main_pc	ZMQ Server	ZMQ REP	Health predictions	5613
PredictiveHealthMonitor	main_pc	ZMQ Client	ZMQ REQ	To SystemDigitalTwin	7220
Executor	main_pc	ZMQ Server	ZMQ REP	Code execution	5606
Executor	main_pc	ZMQ Client	ZMQ REQ	To CodeGenerator	5650
TinyLlamaServiceEnhanced	main_pc	ZMQ Server	ZMQ REP	LLM inference	5615
TinyLlamaServiceEnhanced	main_pc	ZMQ Client	ZMQ REQ	To ModelManagerSuite	7211
SmartHomeAgent	main_pc	ZMQ Server	ZMQ REP	Smart home control	7125
SmartHomeAgent	main_pc	ZMQ Client	ZMQ REQ	To SystemDigitalTwin	7220
CrossMachineGPUScheduler	main_pc	API Server	FastAPI + HTTP	/schedule, /status	7155
CrossMachineGPUScheduler	main_pc	HTTP Client	HTTP POST	PC2 GPU services	7150-7199
ChainOfThoughtAgent	main_pc	ZMQ Server	ZMQ REP	CoT reasoning	5612
ChainOfThoughtAgent	main_pc	ZMQ Client	ZMQ REQ	To ModelManagerSuite	7211
GoTToTAgent	main_pc	ZMQ Server	ZMQ REP	GoT reasoning	5646
GoTToTAgent	main_pc	ZMQ Client	ZMQ REQ	To ChainOfThoughtAgent	5612
CognitiveModelAgent	main_pc	ZMQ Server	ZMQ REP	Cognitive modeling	5641
CognitiveModelAgent	main_pc	ZMQ Client	ZMQ REQ	To ChainOfThoughtAgent	5612
FaceRecognitionAgent	main_pc	ZMQ Server	ZMQ REP	Face recognition	5610
FaceRecognitionAgent	main_pc	ZMQ Client	ZMQ REQ	To ModelManagerSuite	7211
LearningOrchestrationService	main_pc	ZMQ Server	ZMQ REP	Learning coordination	7210
LearningOrchestrationService	main_pc	ZMQ Client	ZMQ REQ	To ModelManagerSuite	7211
LearningOpportunityDetector	main_pc	ZMQ Server	ZMQ REP	Learning detection	7202
LearningOpportunityDetector	main_pc	ZMQ Client	ZMQ REQ	To MemoryClient	5713
LearningManager	main_pc	ZMQ Server	ZMQ REP	Learning management	5580
LearningManager	main_pc	ZMQ Client	ZMQ REQ	To MemoryClient, RequestCoordinator	5713, 26002
ActiveLearningMonitor	main_pc	ZMQ Server	ZMQ REP	Learning monitoring	5638
ActiveLearningMonitor	main_pc	ZMQ Client	ZMQ REQ	To LearningManager	5580
ModelOrchestrator	main_pc	ZMQ Server	ZMQ REP	Model orchestration	7213
ModelOrchestrator	main_pc	ZMQ Client	ZMQ REQ	To ModelManagerSuite	7211
GoalManager	main_pc	ZMQ Server	ZMQ REP	Goal management	7205
GoalManager	main_pc	ZMQ Client	ZMQ REQ	To ModelOrchestrator	7213
IntentionValidatorAgent	main_pc	ZMQ Server	ZMQ REP	Intent validation	5701
IntentionValidatorAgent	main_pc	ZMQ Client	ZMQ REQ	To RequestCoordinator	26002
NLUAgent	main_pc	ZMQ Server	ZMQ REP	NLU processing	5709
NLUAgent	main_pc	ZMQ Client	ZMQ REQ	To SystemDigitalTwin	7220
AdvancedCommandHandler	main_pc	ZMQ Server	ZMQ REP	Command handling	5710
AdvancedCommandHandler	main_pc	ZMQ Client	ZMQ REQ	To NLUAgent, CodeGenerator	5709, 5650
ChitchatAgent	main_pc	ZMQ Server	ZMQ REP	Casual conversation	5711
ChitchatAgent	main_pc	ZMQ Client	ZMQ REQ	To NLUAgent	5709
FeedbackHandler	main_pc	ZMQ Server	ZMQ REP	Feedback processing	5636
FeedbackHandler	main_pc	ZMQ Client	ZMQ REQ	To NLUAgent	5709
Responder	main_pc	ZMQ Server	ZMQ REP	Response generation	5637
Responder	main_pc	ZMQ Client	ZMQ REQ	To EmotionEngine, TTSService	5590, 5801
DynamicIdentityAgent	main_pc	ZMQ Server	ZMQ REP	Identity management	5802
DynamicIdentityAgent	main_pc	ZMQ Client	ZMQ REQ	To RequestCoordinator	26002
EmotionSynthesisAgent	main_pc	ZMQ Server	ZMQ REP	Emotion synthesis	5706
EmotionSynthesisAgent	main_pc	ZMQ Client	ZMQ REQ	To ModelManagerSuite	7211
STTService	main_pc	API Server	FastAPI + HTTP	/transcribe, /stream	5800
STTService	main_pc	ZMQ Server	ZMQ REP	Speech-to-text	5800
STTService	main_pc	ZMQ Client	ZMQ REQ	To ModelManagerSuite	7211
TTSService	main_pc	API Server	FastAPI + HTTP	/synthesize, /voices	5801
TTSService	main_pc	ZMQ Server	ZMQ REP	Text-to-speech	5801
TTSService	main_pc	ZMQ Client	ZMQ REQ	To ModelManagerSuite	7211
AudioCapture	main_pc	ZMQ Publisher	ZMQ PUB	Audio stream	6550
AudioCapture	main_pc	ZMQ Client	ZMQ REQ	To SystemDigitalTwin	7220
FusedAudioPreprocessor	main_pc	ZMQ Subscriber	ZMQ SUB	Audio input	6550
FusedAudioPreprocessor	main_pc	ZMQ Publisher	ZMQ PUB	Processed audio	6551
StreamingInterruptHandler	main_pc	ZMQ Server	ZMQ REP	Interrupt handling	5576
StreamingInterruptHandler	main_pc	ZMQ Publisher	ZMQ PUB	Interrupt signals	5576
StreamingSpeechRecognition	main_pc	ZMQ Subscriber	ZMQ SUB	Audio input	6551
StreamingSpeechRecognition	main_pc	ZMQ Publisher	ZMQ PUB	Transcripts	6553
StreamingSpeechRecognition	main_pc	ZMQ Client	ZMQ REQ	To STTService	5800
StreamingTTSAgent	main_pc	ZMQ Server	ZMQ REP	TTS streaming	5562
StreamingTTSAgent	main_pc	ZMQ Client	ZMQ REQ	To TTSService	5801
WakeWordDetector	main_pc	ZMQ Subscriber	ZMQ SUB	Audio monitoring	6550
WakeWordDetector	main_pc	ZMQ Publisher	ZMQ PUB	Wake events	6552
StreamingLanguageAnalyzer	main_pc	ZMQ Subscriber	ZMQ SUB	Speech input	6553
StreamingLanguageAnalyzer	main_pc	ZMQ Publisher	ZMQ PUB	Analysis results	5579
ProactiveAgent	main_pc	ZMQ Server	ZMQ REP	Proactive responses	5624
ProactiveAgent	main_pc	ZMQ Client	ZMQ REQ	To RequestCoordinator	26002
EmotionEngine	main_pc	ZMQ Server	ZMQ REP	Emotion processing	5590
EmotionEngine	main_pc	ZMQ Publisher	ZMQ PUB	Emotion broadcasts	5591
EmotionEngine	main_pc	ZMQ Client	ZMQ REQ	To SystemDigitalTwin	7220
MoodTrackerAgent	main_pc	ZMQ Server	ZMQ REP	Mood tracking	5704
MoodTrackerAgent	main_pc	ZMQ Client	ZMQ REQ	To EmotionEngine	5590
HumanAwarenessAgent	main_pc	ZMQ Server	ZMQ REP	Human awareness	5705
HumanAwarenessAgent	main_pc	ZMQ Client	ZMQ REQ	To EmotionEngine	5590
ToneDetector	main_pc	ZMQ Server	ZMQ REP	Tone detection	5625
ToneDetector	main_pc	ZMQ Client	ZMQ REQ	To EmotionEngine	5590
VoiceProfilingAgent	main_pc	ZMQ Server	ZMQ REP	Voice profiling	5708
VoiceProfilingAgent	main_pc	ZMQ Client	ZMQ REQ	To EmotionEngine	5590
EmpathyAgent	main_pc	ZMQ Server	ZMQ REP	Empathy modeling	5703
EmpathyAgent	main_pc	ZMQ Client	ZMQ REQ	To EmotionEngine	5590
CloudTranslationService	main_pc	ZMQ Server	ZMQ REP	Translation requests	5592
CloudTranslationService	main_pc	HTTP Client	HTTP POST	Google/DeepL APIs	External
StreamingTranslationProxy	main_pc	API Server	FastAPI + WebSocket	/ws/translate	5596
StreamingTranslationProxy	main_pc	ZMQ Client	ZMQ REQ	To CloudTranslationService	5592
ObservabilityDashboardAPI	main_pc	API Server	FastAPI + HTTP	/dashboard, /api/*	8001
ObservabilityDashboardAPI	main_pc	HTTP Client	HTTP GET	To ObservabilityHub	9000
CentralErrorBus	pc2	ZMQ Publisher	ZMQ PUB	Error broadcasts	7150
CentralErrorBus	pc2	NATS Publisher	NATS	Error streaming	nats:4222
MemoryOrchestratorService	pc2	ZMQ Server	ZMQ REP	Memory orchestration	7140
MemoryOrchestratorService	pc2	DB Reader/Writer	SQLite	Memory database	-
MemoryOrchestratorService	pc2	Redis Client	Redis	Memory caching	6379
TieredResponder	pc2	ZMQ Server	ZMQ REP	Tiered responses	7100
TieredResponder	pc2	ZMQ Client	ZMQ REQ	To ResourceManager	7113
AsyncProcessor	pc2	ZMQ Server	ZMQ REP	Async processing	7101
AsyncProcessor	pc2	ZMQ Publisher	ZMQ PUB	Task broadcasts	7102
AsyncProcessor	pc2	ZMQ Client	ZMQ REQ	To ResourceManager	7113
CacheManager	pc2	ZMQ Server	ZMQ REP	Cache operations	7102
CacheManager	pc2	Redis Client	Redis	Cache storage	6379
VisionProcessingAgent	pc2	ZMQ Server	ZMQ REP	Vision processing	7150
VisionProcessingAgent	pc2	ZMQ Client	ZMQ REQ	To CacheManager	7102
DreamWorldAgent	pc2	ZMQ Server	ZMQ REP	Dream simulation	7104
DreamWorldAgent	pc2	ZMQ Client	ZMQ REQ	To MemoryOrchestratorService	7140
UnifiedMemoryReasoningAgent	pc2	ZMQ Server	ZMQ REP	Memory reasoning	7105
UnifiedMemoryReasoningAgent	pc2	ZMQ Client	ZMQ REQ	To MemoryOrchestratorService	7140
ContextManager	pc2	ZMQ Server	ZMQ REP	Context management	7111
ContextManager	pc2	ZMQ Client	ZMQ REQ	To MemoryOrchestratorService	7140
ExperienceTracker	pc2	ZMQ Server	ZMQ REP	Experience tracking	7112
ExperienceTracker	pc2	ZMQ Client	ZMQ REQ	To MemoryOrchestratorService	7140
ResourceManager	pc2	ZMQ Server	ZMQ REP	Resource management	7113
ResourceManager	pc2	HTTP Client	HTTP GET	To ObservabilityHub	9100
TaskScheduler	pc2	ZMQ Server	ZMQ REP	Task scheduling	7115
TaskScheduler	pc2	ZMQ Client	ZMQ REQ	To AsyncProcessor	7101
AuthenticationAgent	pc2	ZMQ Server	ZMQ REP	Authentication	7116
AuthenticationAgent	pc2	ZMQ Client	ZMQ REQ	To UnifiedUtilsAgent	7118
UnifiedUtilsAgent	pc2	ZMQ Server	ZMQ REP	Utility functions	7118
UnifiedUtilsAgent	pc2	HTTP Client	HTTP GET	To ObservabilityHub	9100
ProactiveContextMonitor	pc2	ZMQ Server	ZMQ REP	Context monitoring	7119
ProactiveContextMonitor	pc2	ZMQ Client	ZMQ REQ	To ContextManager	7111
AgentTrustScorer	pc2	ZMQ Server	ZMQ REP	Trust scoring	7122
AgentTrustScorer	pc2	HTTP Client	HTTP GET	To ObservabilityHub	9100
FileSystemAssistantAgent	pc2	ZMQ Server	ZMQ REP	File operations	7123
FileSystemAssistantAgent	pc2	ZMQ Client	ZMQ REQ	To UnifiedUtilsAgent	7118
RemoteConnectorAgent	pc2	ZMQ Server	ZMQ REP	Remote connections	7124
RemoteConnectorAgent	pc2	HTTP Client	HTTP POST	Ollama API	11434
RemoteConnectorAgent	pc2	ZMQ Client	ZMQ REQ	To AdvancedRouter	7129
UnifiedWebAgent	pc2	ZMQ Server	ZMQ REP	Web operations	7126
UnifiedWebAgent	pc2	HTTP Client	HTTP GET/POST	Web scraping	External
UnifiedWebAgent	pc2	DB Reader/Writer	SQLite	Web cache	-
DreamingModeAgent	pc2	ZMQ Server	ZMQ REP	Dream mode control	7127
DreamingModeAgent	pc2	ZMQ Client	ZMQ REQ	To DreamWorldAgent	7104
AdvancedRouter	pc2	ZMQ Server	ZMQ REP	Request routing	7129
AdvancedRouter	pc2	ZMQ Client	ZMQ REQ	To TaskScheduler	7115
ObservabilityHub	pc2	API Server	FastAPI + HTTP	/health, /metrics	9100
ObservabilityHub	pc2	HTTP Client	HTTP POST	MainPC sync	9000
ObservabilityHub	pc2	NATS Subscriber	NATS	Cross-machine events	nats:4222
TutoringServiceAgent	pc2	ZMQ Server	ZMQ REP	Tutoring services	7108
TutoringServiceAgent	pc2	ZMQ Client	ZMQ REQ	To MemoryOrchestratorService	7140
SelfHealingSupervisor	pc2	API Server	FastAPI + HTTP	/restart, /status	7009
SelfHealingSupervisor	pc2	HTTP Client	HTTP GET	To ObservabilityHub	9100
SpeechRelayService	pc2	API Server	FastAPI + WebSocket	/ws/speech	7130
SpeechRelayService	pc2	ZMQ Client	ZMQ REQ	To VisionProcessingAgent	7150
Communication Architecture Summary:
Primary Patterns:
ZMQ REQ/REP: Synchronous service-to-service communication (most common)
ZMQ PUB/SUB: Asynchronous broadcasting (audio streams, emotions, errors)
FastAPI/HTTP: External interfaces and dashboards
Redis: Caching and session storage
SQLite: Persistent data storage
WebSockets: Real-time browser communication
NATS: Modern streaming and cross-machine sync
Cross-Machine Communication:
ObservabilityHub instances sync via HTTP/NATS
GPU scheduling via HTTP REST APIs
Error bus via NATS streaming
Translation proxy via WebSocket relay
This analysis provides complete visibility into how all 77 agents communicate within and across the MainPC/PC2 architecture. Each agent has clearly defined communication roles and protocols for reliable, distributed operation.
