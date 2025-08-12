============================================================
🎮 TASK COMMAND & CONTROL CENTER
============================================================

📋 ALL OPEN TASKS:
========================================

1. 🗒️  docker_arch_impl_20250810
   Description: A phased implementation plan to build, migrate, and manage the entire service fl...
   Status: in_progress
   Created: 2025-08-10T08:01:15Z
   TODO Items (7):
      [✔] 0. PHASE 0: SETUP & PROTOCOL (READ FIRST)

**Core Behavioral Mandates:**
*   **Execute Sequentially:** Phases are designed to be completed in order, as they build upon each other. Do not skip phases.
*   **Verify Each Step:** After completing a technical task within a phase, verify its success before proceeding.
*   **Consult Source Document:** This plan is a derivative of the "FINAL Docker Architecture Blueprint". Refer back to it for granular details, rationale, and original context.

**How-To/Workflow Protocol:**
This plan is managed by a command-line tool (`todo_manager.py`).
1.  To view the current status of all phases, run: `python3 todo_manager.py show docker_arch_impl_20250810`
2.  When all tasks within a phase are complete, mark the phase as done using the `done` command specified at the end of that phase's instructions. This is a crucial step for tracking progress.

**Concluding Step: Phase Completion Protocol**
To formally conclude this phase, update the plan's state, and prepare for the next, execute the following protocol:
1.  **Run Command (Mark Complete):** `python3 todo_manager.py done docker_arch_impl_20250810 0`
2.  **Analyze Next Phase:** Before proceeding, read and understand the 'Explanations' and 'Tasks' for Phase 1.

──────────────────────────────────
IMPORTANT NOTE: This phase contains the operating manual for this entire plan. Completing it signifies you understand the workflow required to execute the following technical phases successfully.
      [✔] 1. PHASE 1: BUILD FOUNDATIONAL BASE IMAGES

**Explanations:**
This phase creates the core, shared layers of the entire Docker ecosystem as defined in §B of the blueprint. Getting these right is critical, as all ~50 services will be derived from them. The build order must follow the dependency hierarchy.

**Technical Artifacts / Tasks:**
1.  **Review Risk Register:** Before starting, review the "Risk Register & Rollback" (section G) from the blueprint to be aware of potential issues like driver mismatches or cache quotas.
2.  **Create Base Images:** Build and push the following base images to GHCR in the specified order. Use the tagging convention `ghcr.io/<org>/<family>:YYYYMMDD-<git_sha>`.
    *   `base-python:3.11-slim`
    *   `base-utils` (derived from `base-python`)
    *   `base-cpu-pydeps` (derived from `base-utils`)
    *   `family-web` (derived from `base-cpu-pydeps`)
    *   `base-gpu-cu121` (derived from `nvidia/cuda:12.1.1-runtime-ubuntu22.04`)
    *   `family-torch-cu121` (derived from `base-gpu-cu121`)
    *   `family-llm-cu121` (derived from `family-torch-cu121`)
    *   `family-vision-cu121` (derived from `base-gpu-cu121`)
3.  **Create Legacy Base Image:** Build and push the `legacy-py310-cpu` image for services pending migration.
4.  **Verify Images on GHCR:** Confirm all images are present in the GitHub Container Registry (`ghcr.io/<org>`) with the correct tags.

**Concluding Step: Phase Completion Protocol**
To formally conclude this phase, update the plan's state, and prepare for the next, execute the following protocol:
1.  **Run Command (Review State):** `python3 todo_manager.py show docker_arch_impl_20250810`
2.  **Run Command (Mark Complete):** `python3 todo_manager.py done docker_arch_impl_20250810 1`
3.  **Analyze Next Phase:** Before proceeding, read and understand the 'Explanations' and 'Tasks' for Phase 2.

──────────────────────────────────
IMPORTANT NOTE: The stability of the entire system depends on these foundational images. Any errors here will propagate to all services. Double-check CUDA versions and Python dependencies before proceeding.
      [✗] 2. PHASE 2: DEPENDENCY AUDIT & SPECIALIZED IMAGE REFINEMENT

**Explanations:**
As per blueprint §H.2, we must ensure that specialized GPU images (`family-torch` and `family-vision`) contain all necessary system-level libraries (e.g., for audio/video processing) without bloating the more common CPU images.

**Technical Artifacts / Tasks:**
1.  **Perform Static Analysis:** For services in the `family-torch-cu121` and `family-vision-cu121` groups (see Fleet Table §F), perform a dependency audit.
    *   Use static code scanning to identify Python library imports.
    *   Use `ldd` on compiled binaries or `.so` files within those libraries to find system library dependencies (e.g., `ffmpeg`, `libpulse`, `libgl1`).
2.  **Update Base Images (If Necessary):** If the audit reveals missing system libraries, update the Dockerfiles for `family-torch-cu121` and/or `family-vision-cu121` to include them via `apt-get install`.
3.  **Rebuild and Push:** If any changes were made, rebuild and push the affected images, incrementing the date tag.

**Concluding Step: Phase Completion Protocol**
To formally conclude this phase, update the plan's state, and prepare for the next, execute the following protocol:
1.  **Run Command (Review State):** `python3 todo_manager.py show docker_arch_impl_20250810`
2.  **Run Command (Mark Complete):** `python3 todo_manager.py done docker_arch_impl_20250810 2`
3.  **Analyze Next Phase:** Before proceeding, read and understand the 'Explanations' and 'Tasks' for Phase 3.

──────────────────────────────────
IMPORTANT NOTE: This phase is a precision task. The goal is to add *only* the required libraries to the specialized images to maintain the principle of minimal layers.
      [✗] 3. PHASE 3: IMPLEMENT CI/CD AUTOMATION PIPELINE

**Explanations:**
This phase automates the build, test, and deployment process using GitHub Actions, as outlined in blueprint sections A.6 and C. This pipeline will enforce quality gates and ensure reproducibility.

**Technical Artifacts / Tasks:**
1.  **Configure GHA Matrix Build:** Create a GitHub Actions workflow that uses a build matrix for `family` × `machine` combinations.
2.  **Implement Registry Caching:** Configure `docker buildx` within the GHA workflow to use the registry for caching, as specified in the blueprint:
    ```
    --cache-to type=registry,ref=ghcr.io/<org>/cache
    --cache-from type=registry,ref=ghcr.io/<org>/cache
    ```
3.  **Integrate Vulnerability Scanning:** Add a Trivy scan step to the pipeline. The step MUST be configured to `fail on HIGH/CRITICAL` severities.
4.  **Implement SBOM Generation:** Add a step to the workflow that generates a Software Bill of Materials (SBOM) for each built image and uploads it as a build artifact.

**Concluding Step: Phase Completion Protocol**
To formally conclude this phase, update the plan's state, and prepare for the next, execute the following protocol:
1.  **Run Command (Review State):** `python3 todo_manager.py show docker_arch_impl_20250810`
2.  **Run Command (Mark Complete):** `python3 todo_manager.py done docker_arch_impl_20250810 3`
3.  **Analyze Next Phase:** Before proceeding, read and understand the 'Explanations' and 'Tasks' for Phase 4.

──────────────────────────────────
IMPORTANT NOTE: The CI pipeline is the factory floor for all services. Ensure it is robust and that failure conditions (like Trivy scans) are properly enforced before migrating services.
      [✗] 4. PHASE 4: PHASED SERVICE MIGRATION

**Explanations:**
This is the largest phase, involving the migration of all ~50 services to the new Docker architecture. The migration is broken into sub-phases to manage complexity and risk, as per blueprint §H.4. For each service, you must create a new Dockerfile following the canonical patterns in §E, implement the health check from §C, and use the hardware profiles from §D.

**Technical Artifacts / Tasks:**
1.  **Sub-Phase 4.1 (Core Infrastructure):** Migrate the following services.
    *   `ServiceRegistry`
    *   `SystemDigitalTwin`
    *   `UnifiedSystemAgent`
    *   `SelfHealingSupervisor`
    *   `UnifiedObservabilityCenter` & `(pc2)`
    *   `CentralErrorBus`
2.  **Sub-Phase 4.2 (MainPC 4090 GPU Services):** Migrate the GPU-heavy services on the main machine.
    *   `ModelOpsCoordinator`
    *   `AffectiveProcessingCenter`
    *   `RealTimeAudioPipeline`
    *   `TinyLlamaServiceEnhanced`
    *   `ChainOfThoughtAgent`, `CognitiveModelAgent`, `LearningOpportunityDetector`, `LearningManager`, `DynamicIdentityAgent`, `ProactiveAgent`
    *   `FaceRecognitionAgent`
    *   `Responder`, `EmotionSynthesisAgent`, `STTService`, `TTSService`, `StreamingSpeechRecognition`, `StreamingTTSAgent`, `EmpathyAgent`
3.  **Sub-Phase 4.3 (PC2 3060 Services):** Migrate all services designated for the second machine.
    *   `RealTimeAudioPipelinePC2`
    *   `VisionProcessingAgent`, `DreamWorldAgent`, `DreamingModeAgent`
    *   `SpeechRelayService`
    *   All other CPU services listed for PC2 (e.g., `TieredResponder`, `ResourceManager`, `TaskScheduler`, etc.)
4.  **Sub-Phase 4.4 (Legacy & Remaining CPU Services):** Migrate the remaining services, including those on the legacy Python 3.10 base.
    *   `IntentionValidatorAgent`, `NLUAgent`, `AdvancedCommandHandler`, `ChitchatAgent`
    *   All other CPU services on the 4090 machine (e.g., `MemoryFusionHub`, `CodeGenerator`, `Executor`, etc.)

**Concluding Step: Phase Completion Protocol**
To formally conclude this phase, update the plan's state, and prepare for the next, execute the following protocol:
1.  **Run Command (Review State):** `python3 todo_manager.py show docker_arch_impl_20250810`
2.  **Run Command (Mark Complete):** `python3 todo_manager.py done docker_arch_impl_20250810 4`
3.  **Analyze Next Phase:** Before proceeding, read and understand the 'Explanations' and 'Tasks' for Phase 5.

──────────────────────────────────
IMPORTANT NOTE: This phase involves modifying the runtime of every service. Coordinate deployments carefully, especially for core infrastructure, to minimize downtime. Use the `FORCE_IMAGE_TAG` environment variable for targeted testing.
      [✗] 5. PHASE 5: OBSERVABILITY & TRACEABILITY INTEGRATION

**Explanations:**
To achieve full system awareness, each service must report its identity and build information to the `UnifiedObservabilityCenter` upon startup, as per blueprint §H.5.

**Technical Artifacts / Tasks:**
1.  **Modify Service Entrypoints:** For every service migrated in Phase 4, modify its startup script (e.g., `entrypoint.sh`).
2.  **Implement Reporting Logic:** The script should read the image's SBOM and the Git SHA (passed as an environment variable from the CI pipeline) and emit this data to the `UnifiedObservabilityCenter`'s API endpoint.
3.  **Verify Integration:** After deploying a service, check the `UnifiedObservabilityCenter` logs or dashboard to confirm it has received the startup report.

**Concluding Step: Phase Completion Protocol**
To formally conclude this phase, update the plan's state, and prepare for the next, execute the following protocol:
1.  **Run Command (Review State):** `python3 todo_manager.py show docker_arch_impl_20250810`
2.  **Run Command (Mark Complete):** `python3 todo_manager.py done docker_arch_impl_20250810 5`
3.  **Analyze Next Phase:** Before proceeding, read and understand the 'Explanations' and 'Tasks' for Phase 6.

───────────────────
IMPORTANT NOTE: This step is crucial for runtime security and debugging. Knowing exactly which version of code is running in every container is non-negotiable for a production-grade system.
      [✗] 6. PHASE 6: FINALIZE ROLLBACK PROCEDURES & DOCUMENTATION

**Explanations:**
The final phase is to formalize the safety net. This involves documenting the rollback process and ensuring the previous stable images are preserved correctly, as outlined in blueprint §H.6.

**Technical Artifacts / Tasks:**
1.  **Tag Previous Images:** Identify the last-known-good production images for all services (before this project began) and tag them with a `-prev` suffix in the container registry. This provides a definitive fallback point.
2.  **Create Rollback Runbook:** Create a markdown document (`ROLLBACK_PROCEDURE.md`) in the main repository.
3.  **Document Procedure:** The runbook must detail the exact steps to roll a service back to its `-prev` version, primarily by setting the `FORCE_IMAGE_TAG` environment variable in the deployment supervisor.
4.  **Final System Review:** Conduct a full system health check. Ensure all services are running, reporting to the observability center, and communicating correctly.

**Concluding Step: Plan Completion Protocol**
To formally conclude the entire plan and mark it as complete, execute the following protocol:
1.  **Run Command (Review State):** `python3 todo_manager.py show docker_arch_impl_20250810`
2.  **Run Command (Mark Complete):** `python3 todo_manager.py done docker_arch_impl_20250810 6`

──────────────────────────────────
IMPORTANT NOTE: This final phase ensures the project is not only complete but also maintainable and resilient. A well-documented rollback plan is a critical piece of operational readiness.
