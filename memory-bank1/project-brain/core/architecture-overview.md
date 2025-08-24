# Architecture Overview - AI System Monorepo

## High-Level System Design

### System Architecture Layers

```
┌─────────────────────────────────────────────────────────────────────┐
│                     CLI INTERFACE LAYER                            │
│                   memory_system/cli.py                             │
│  Commands: tcc | run | migrate | monitor | arch-mode               │
└─────────────────┬───────────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   WORKFLOW ORCHESTRATION                           │
├─────────────────┬───────────────────┬───────────────────────────────┤
│ Architecture    │ Task Command      │ Async Task Engine             │
│ Mode Engine     │ Center (TCC)      │ (Concurrent Execution)        │
└─────────────────┼───────────────────┼───────────────────────────────┘
                  │                   │
                  ▼                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                INTELLIGENCE & PROCESSING CORE                      │
│              workflow_memory_intelligence_fixed.py                 │
│  • Task Complexity Analysis • Hybrid Parsing • Smart Chunking     │
└─────────────────┬───────────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                MEMORY & STATE MANAGEMENT                           │
├───────────────┬─────────────────┬─────────────────┬─────────────────┤
│ Project Brain │ TODO Manager    │ Task State Mgr  │ Memory Provider │
│ (Knowledge)   │ (CRUD Tasks)    │ (Persistence)   │ (Data Storage)  │
└───────────────┼─────────────────┼─────────────────┼─────────────────┘
                │                 │                 │
                ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   INTEGRATION & SERVICES                           │
├─────────────────┬───────────────────┬───────────────────────────────┤
│ Auto Sync       │ Telemetry         │ Health Monitoring             │
│ (State Sync)    │ (Metrics)         │ (System Status)               │
└─────────────────┴───────────────────┴───────────────────────────────┘
```

## Core Components

### 1. CLI Interface Layer
**Primary Entry Point**: `memory_system/cli.py`
- **Responsibility**: Command parsing, routing, and user interaction
- **Commands**: 
  - `run`: Execute tasks with intelligent processing
  - `tcc`: Launch Task Command Center UI
  - `arch-mode`: Architecture-first planning workflow
  - `migrate`: Memory system migration
  - `monitor`: Real-time system monitoring

### 2. Workflow Orchestration Layer

#### Architecture Mode Engine
- **Purpose**: Plan-first development workflow
- **Components**: Plan generation, validation, approval pipeline
- **Integration**: Project Brain Manager, Context Loader

#### Task Command Center (TCC)
- **Purpose**: Interactive task management interface
- **Features**: Task creation, monitoring, completion tracking
- **Technology**: Terminal-based UI

#### Async Task Engine
- **Purpose**: Concurrent task execution with intelligent coordination
- **Features**: Semaphore-based concurrency, telemetry integration
- **Scalability**: Configurable worker limits, automatic load balancing

### 3. Intelligence & Processing Core

#### Workflow Memory Intelligence
**File**: `workflow_memory_intelligence_fixed.py`
- **Task Complexity Analyzer**: Determines execution strategy (Simple/Medium/Complex)
- **Action Item Extractor**: Decomposes tasks into actionable steps
- **Smart Task Executor**: Routes tasks through appropriate processing pipeline
- **Hybrid Parsing**: Rule-based parser for simple tasks, LLM-based for complex

#### Processing Strategies
- **Simple Tasks**: Direct execution with minimal overhead
- **Complex Tasks**: Multi-step chunking with TODO generation
- **Conditional Logic**: Dynamic routing based on task characteristics

### 4. Memory & State Management

#### Project Brain System
- **Structure**: Hierarchical knowledge organization (core/modules/workflows/progress)
- **Context Loading**: Targeted and full context loading capabilities
- **Consistency Validation**: Automatic integrity checking
- **Search**: Content-based knowledge retrieval

#### TODO Manager
- **Data Model**: JSON-based task storage with hierarchical TODOs
- **Operations**: Full CRUD with automatic cleanup and deduplication
- **Integration**: Auto-sync with all state management systems

#### State Management
- **Single Source of Truth**: `todo-tasks.json` as authoritative task database
- **State Files**: 
  - `cursor_state.json`: Current session context
  - `task-state.json`: Task execution state
  - `task_interruption_state.json`: Recovery and resume logic

### 5. Integration & Services Layer

#### Auto Sync Manager
- **Purpose**: Maintain consistency across all state files
- **Triggers**: Task changes, session start/end, manual force sync
- **Safety**: Backup creation before all modifications

#### Telemetry System
- **Metrics Collection**: Performance, usage, and error tracking
- **Event Emission**: JSON-line format for external processing
- **Span Tracking**: Execution timing and context preservation

#### Health Monitoring
- **Components**: System health checks, status reporting
- **Tools**: `cli_health_check.py`, `system_status_reporter.py`
- **Coverage**: File integrity, integration status, performance metrics

## Data Flow Architecture

### Task Execution Flow
```
User Input → CLI Parser → Architecture Mode (optional) → 
Task Intelligence → Complexity Analysis → Execution Strategy → 
State Management → Telemetry → Results
```

### Memory Management Flow
```
Context Request → Project Brain → Targeted Loading → 
Context Cache → AI Processing → Context Updates → 
Brain Persistence → State Sync
```

### State Synchronization Flow
```
Data Change → Auto Sync Trigger → State Validation → 
Backup Creation → State Updates → Consistency Check → 
Notification
```

## Design Principles

### 1. Architecture-First Development
- **Planning Phase**: All features start with architecture planning
- **Validation**: Plans must be validated before implementation
- **Approval**: Explicit approval step before coding begins
- **Documentation**: All architectural decisions captured in Project Brain

### 2. Memory-Driven Intelligence
- **Context Preservation**: All system knowledge persisted across sessions
- **Learning**: System improves based on historical data and patterns
- **Consistency**: Unified memory model across all components
- **Searchability**: All knowledge accessible through structured queries

### 3. Graceful Degradation
- **Fallback Mechanisms**: System continues working when optional components fail
- **Error Recovery**: Automatic recovery from common failure scenarios
- **Safe Defaults**: Conservative behavior when uncertain
- **Rollback Capability**: All changes reversible through backup systems

### 4. Modular Extensibility
- **Plugin Architecture**: New features added through well-defined interfaces
- **Clean Interfaces**: Clear separation of concerns between components
- **Dependency Injection**: Configurable component relationships
- **Testing Isolation**: Each component testable independently

## Scalability Considerations

### Horizontal Scaling
- **Concurrent Processing**: Multiple tasks executed simultaneously
- **Worker Pools**: Configurable concurrency limits
- **Load Distribution**: Intelligent task routing and balancing

### Vertical Scaling
- **Memory Management**: Efficient context loading and caching
- **Storage Optimization**: Automated cleanup and compression
- **Performance Monitoring**: Continuous performance analysis and optimization

## Security Model

### Data Protection
- **Local Storage**: All data stored locally, no external transmission
- **Backup Integrity**: Cryptographic verification of backup files
- **Access Control**: File system permissions for data protection

### Code Security
- **Input Validation**: All user inputs validated and sanitized
- **Safe Execution**: Sandboxed execution for user-provided code
- **Error Handling**: Secure error messages without information leakage

## Integration Points

### External Systems
- **MCP (Model Context Protocol)**: Memory provider integration
- **Ollama**: LLM integration for complex task processing
- **File System**: Direct file system integration for data persistence

### Internal Systems
- **CLI Commands**: Unified command interface across all components
- **State Management**: Automatic synchronization between all state stores
- **Event System**: Pub/sub pattern for component communication

---

*Architecture Version: 2.0*
*Last Updated: 2025-07-30*
*Next Review: After Architecture Mode implementation*
