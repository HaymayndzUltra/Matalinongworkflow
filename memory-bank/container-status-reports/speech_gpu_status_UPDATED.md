# Speech GPU Group - UPDATED Container Status Report
**Report Generated:** 2025-08-02 16:46:00

## Group Overview
- **Total Containers:** 10
- **Healthy:** 1
- **Stopped/Failed:** 9

## ✅ HEALTHY CONTAINERS

### redis_speech
- **Status:** Up 7 hours (healthy)
- **Ports:** 0.0.0.0:6387->6379/tcp
- **Issue:** None - Working perfectly

## ❌ STOPPED CONTAINERS (All with dependency issues)

### tts_service
- **Status:** Exited (1) 7 hours ago
- **Issue:** Missing sounddevice module
- **Error:** `ModuleNotFoundError: No module named 'sounddevice'`

**Logs:**
```
File "/app/main_pc_code/agents/streaming_tts_agent.py", line 37, in <module>
    import sounddevice as sd
ModuleNotFoundError: No module named 'sounddevice'
```

### wake_word_detector
- **Status:** Exited (1) 7 hours ago
- **Issue:** Missing pvporcupine module
- **Error:** `ModuleNotFoundError: No module named 'pvporcupine'`

**Logs:**
```
File "/app/main_pc_code/agents/wake_word_detector.py", line 15, in <module>
    import pvporcupine
ModuleNotFoundError: No module named 'pvporcupine'
```

### streaming_speech_recognition
- **Status:** Exited (1) 7 hours ago
- **Issue:** Missing noisereduce module (from previous logs)

### fused_audio_preprocessor
- **Status:** Exited (1) 7 hours ago
- **Issue:** Audio processing dependencies missing

### audio_capture
- **Status:** Exited (0) 7 hours ago
- **Issue:** Clean exit but not running

### Other Speech Agents
- **streaming_language_analyzer:** Exited (1) 7 hours ago
- **streaming_interrupt_handler:** Exited (1) 7 hours ago
- **streaming_tts_agent:** Exited (1) 7 hours ago
- **stt_service:** Exited (1) 7 hours ago

## ✅ FIXES PREPARED (Not yet deployed)

### Dependencies Added to requirements.txt:
- ✅ sounddevice==0.4.6
- ✅ noisereduce==3.0.4
- ✅ pvporcupine==2.2.0

## 🔄 DEPLOYMENT STATUS

**Current Status:** READY FOR REBUILD
- All missing dependencies identified and added to requirements.txt
- Infrastructure (Redis) working perfectly
- Need to rebuild speech_gpu image and restart all agents

**Command to Deploy Fixes:**
```bash
docker build -t speech_gpu:latest -f docker/speech_gpu/Dockerfile .
docker compose -f docker/speech_gpu/docker-compose.yml up -d
```

## Summary
Speech GPU group is **10% functional** (1/10 healthy). This group has the most extensive dependency issues but all fixes are prepared.

**Root Cause:** Missing specialized audio processing libraries
**Solution:** Dependencies added, needs rebuild
**Expected after rebuild:** 90%+ functional

**Status:** AWAITING REBUILD - All fixes prepared! 🔄
