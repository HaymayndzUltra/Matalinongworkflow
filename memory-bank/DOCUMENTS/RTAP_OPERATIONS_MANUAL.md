# RTAP Operations Manual

**Version**: 1.0  
**Date**: January 8, 2025  
**Audience**: Operations Teams, DevOps Engineers, Site Reliability Engineers  

---

## Quick Start

### Deployment Commands

```bash
# Clone and setup
git clone <rtap-repo>
cd real_time_audio_pipeline

# Deploy production instances
./deploy.sh

# Check status
docker-compose ps
docker-compose logs rtap-main
```

### Health Check

```bash
# Primary instance
curl http://localhost:8080/health

# Standby instance  
curl http://localhost:8081/health

# Monitoring dashboard
open http://localhost:3000
```

---

## Service Management

### Starting Services

```bash
# Start all services
docker-compose up -d

# Start specific service
docker-compose up -d rtap-main

# Start with logs
docker-compose up rtap-main
```

### Stopping Services

```bash
# Stop all services
docker-compose down

# Stop specific service
docker-compose stop rtap-main

# Force stop and remove
docker-compose down --volumes --remove-orphans
```

### Service Status

```bash
# Check running containers
docker-compose ps

# View resource usage
docker stats

# Check health status
docker-compose ps | grep healthy
```

---

## Configuration Management

### Environment Selection

```bash
# Main PC (GPU-optimized)
export RTAP_ENVIRONMENT=main_pc
docker-compose up -d rtap-main

# PC2 (CPU-optimized)
export RTAP_ENVIRONMENT=pc2
docker-compose up -d rtap-standby

# Default configuration
unset RTAP_ENVIRONMENT
docker-compose up -d
```

### Configuration Files

```bash
# Configuration hierarchy
config/
├── default.yaml      # Base configuration
├── main_pc.yaml      # Primary deployment
├── pc2.yaml          # Standby deployment
└── loader.py         # Configuration logic

# Validate configuration
docker run --rm -v $(pwd)/config:/app/config rtap:latest \
  python3 -c "from config.loader import UnifiedConfigLoader; \
               UnifiedConfigLoader().load_config()"
```

### Runtime Configuration

```bash
# Environment variables
RTAP_ENVIRONMENT=main_pc    # Configuration profile
RTAP_LOG_LEVEL=INFO        # Logging level
AUDIO_DEVICE=default       # Audio device
RTAP_AUDIO_MOCK=false      # Mock mode for testing
```

---

## Monitoring and Alerting

### Key Dashboards

```bash
# Grafana Dashboards
http://localhost:3000
- Username: admin
- Password: rtap-admin

# Prometheus Metrics
http://localhost:9090

# Log Aggregation
http://localhost:3100
```

### Critical Metrics to Monitor

```yaml
Performance Metrics:
- rtap_pipeline_latency_seconds (target: <0.15)
- rtap_frames_processed_total (rate indicator)
- rtap_buffer_utilization_ratio (target: <0.8)

System Metrics:
- rtap_memory_usage_bytes (growth monitoring)
- rtap_cpu_usage_percent (target: <20% per core)
- rtap_errors_total (error rate tracking)

Health Metrics:
- container_health_status (up/down)
- rtap_state_transitions_total (state monitoring)
```

### Alert Thresholds

```yaml
Critical Alerts:
- Latency >200ms p95: Immediate investigation
- Service down >30s: Page on-call engineer
- Error rate >1%: Check logs and restart if needed

Warning Alerts:
- Memory growth >10%/hour: Monitor for leaks
- CPU usage >50%: Check for performance issues
- Buffer utilization >80%: Risk of overflow

Info Alerts:
- High throughput: Normal operational notice
- Configuration changes: Audit trail
```

### Alerting Setup

```bash
# Configure Prometheus alerts
# File: monitoring/alerts.yml
groups:
  - name: rtap-alerts
    rules:
      - alert: RTAPHighLatency
        expr: histogram_quantile(0.95, rtap_pipeline_latency_seconds_bucket) > 0.2
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "RTAP latency too high"
```

---

## Log Management

### Log Locations

```bash
# Container logs
docker-compose logs rtap-main
docker-compose logs rtap-standby

# Application logs
docker exec rtap-main cat /app/logs/rtap-$(date +%Y%m%d).log

# System logs
journalctl -u docker
```

### Log Analysis

```bash
# Search for errors
docker-compose logs rtap-main | grep ERROR

# Filter by component
docker-compose logs rtap-main | grep "pipeline"

# Real-time monitoring
docker-compose logs -f rtap-main

# Export logs
docker-compose logs rtap-main > rtap-main.log
```

### Log Rotation

```bash
# Configure log rotation
# File: /etc/logrotate.d/rtap
/app/logs/*.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
    create 644 rtap rtap
}
```

---

## Performance Monitoring

### Real-time Performance

```bash
# Resource usage
docker stats rtap-main rtap-standby

# Network usage
docker exec rtap-main ss -tuln

# Process monitoring
docker exec rtap-main ps aux

# Memory analysis
docker exec rtap-main cat /proc/meminfo
```

### Performance Benchmarks

```bash
# Run latency tests
docker exec rtap-main python3 tests/test_latency.py

# Performance profiling
docker exec rtap-main py-spy record -o profile.svg -d 60 -p 1

# Stress testing
docker exec rtap-main python3 tests/test_profiling.py
```

### Performance Optimization

```yaml
# Tuning Parameters
audio.ring_buffer_size_ms: 4000    # Increase for higher latency tolerance
stt.beam_size: 5                   # Reduce for lower latency
stt.compute_dtype: "float16"       # Use for GPU optimization
resilience.bulkhead.max_concurrent: 8  # Adjust for throughput
```

---

## Troubleshooting

### Common Issues

#### 1. High Latency

```bash
# Symptoms
- Latency >150ms p95
- Slow response times

# Diagnosis
docker-compose logs rtap-main | grep latency
docker exec rtap-main python3 tests/test_latency.py

# Solutions
- Check CPU/GPU utilization
- Verify model loading
- Adjust buffer sizes
- Scale resources if needed
```

#### 2. Audio Device Issues

```bash
# Symptoms
- "PortAudio library not found"
- No audio input detected

# Diagnosis
docker exec rtap-main ls -la /dev/snd/
docker exec rtap-main aplay -l

# Solutions
- Verify audio device mounting: --device /dev/snd
- Enable mock mode: RTAP_AUDIO_MOCK=true
- Check audio permissions: usermod -a -G audio rtap
```

#### 3. Memory Issues

```bash
# Symptoms
- High memory usage
- Out of memory errors

# Diagnosis
docker stats --no-stream
docker exec rtap-main python3 -c "import psutil; print(psutil.virtual_memory())"

# Solutions
- Restart service: docker-compose restart rtap-main
- Increase memory limits: resources.limits.memory: 4G
- Check for memory leaks: py-spy profile
```

#### 4. Network Issues

```bash
# Symptoms
- Connection failures
- Port binding errors

# Diagnosis
netstat -tuln | grep -E "(6552|6553|5802|8080)"
docker exec rtap-main nc -z localhost 6553

# Solutions
- Check port availability
- Verify Docker network configuration
- Restart networking: docker network prune
```

#### 5. Model Loading Failures

```bash
# Symptoms
- Slow startup
- Model loading errors

# Diagnosis
docker-compose logs rtap-main | grep -i "model\|warmup"
docker exec rtap-main ls -la /app/models/

# Solutions
- Pre-download models
- Verify model paths in configuration
- Check disk space: df -h
- Use CPU fallback if GPU issues
```

### Debug Mode

```bash
# Enable debug logging
export RTAP_LOG_LEVEL=DEBUG
docker-compose up rtap-main

# Interactive debugging
docker exec -it rtap-main /bin/bash
python3 -c "from app import RTAPApplication; app = RTAPApplication()"

# Health check debugging
docker exec rtap-main /app/healthcheck.sh
```

### Performance Debugging

```bash
# CPU profiling
docker exec rtap-main py-spy top -p $(pgrep python3)

# Memory profiling
docker exec rtap-main python3 -m memory_profiler app.py

# Network debugging
docker exec rtap-main tcpdump -i any port 6553

# System monitoring
docker exec rtap-main iostat -x 1
```

---

## Backup and Recovery

### Configuration Backup

```bash
# Backup configuration
tar -czf rtap-config-$(date +%Y%m%d).tar.gz config/

# Backup Docker images
docker save rtap:latest | gzip > rtap-image-$(date +%Y%m%d).tar.gz

# Backup monitoring data
docker exec rtap-monitoring tar -czf /tmp/prometheus-backup.tar.gz /prometheus
docker cp rtap-monitoring:/tmp/prometheus-backup.tar.gz .
```

### Service Recovery

```bash
# Quick recovery
docker-compose down
docker-compose up -d

# Full recovery with rebuild
docker-compose down --volumes
docker-compose build --no-cache
docker-compose up -d

# Rollback to previous version
docker tag rtap:backup rtap:latest
docker-compose up -d
```

### Disaster Recovery

```bash
# Failover to standby
docker-compose stop rtap-main
# Update load balancer to point to rtap-standby ports

# Emergency shutdown
docker-compose down --remove-orphans
pkill -f "python.*app.py"

# Recovery validation
./deploy.sh
docker exec rtap-main python3 tests/test_final_verification.py
```

---

## Maintenance Procedures

### Regular Maintenance

```bash
# Daily Tasks
- Check service health: docker-compose ps
- Monitor resource usage: docker stats
- Review error logs: docker-compose logs | grep ERROR

# Weekly Tasks
- Clean up old logs: find /app/logs -name "*.log" -mtime +7 -delete
- Update monitoring dashboards
- Review performance metrics

# Monthly Tasks
- Update Docker images: docker-compose pull
- Security updates: apt update && apt upgrade
- Performance review and optimization
```

### Update Procedures

```bash
# Rolling update
1. Update standby instance first
2. Test standby functionality
3. Switch traffic to standby
4. Update primary instance
5. Switch traffic back to primary

# Update commands
docker-compose pull
docker-compose up -d rtap-standby
# Test and validate
docker-compose up -d rtap-main
```

### Security Maintenance

```bash
# Security scanning
docker scan rtap:latest

# Update security patches
docker-compose build --no-cache
docker-compose up -d

# Access audit
docker exec rtap-main cat /var/log/auth.log
```

---

## Integration with Downstream Systems

### ZMQ Integration

```bash
# Test ZMQ connectivity
python3 -c "
import zmq
context = zmq.Context()
socket = context.socket(zmq.SUB)
socket.connect('tcp://localhost:6553')
socket.setsockopt(zmq.SUBSCRIBE, b'transcript')
print('Connected to ZMQ transcript feed')
"
```

### WebSocket Integration

```bash
# Test WebSocket connectivity
curl --include \
     --no-buffer \
     --header "Connection: Upgrade" \
     --header "Upgrade: websocket" \
     --header "Sec-WebSocket-Key: SGVsbG8sIHdvcmxkIQ==" \
     --header "Sec-WebSocket-Version: 13" \
     http://localhost:5802/stream
```

### API Documentation

```bash
# Access API documentation
open http://localhost:5802/docs  # FastAPI docs
open http://localhost:5802/redoc # ReDoc documentation
```

---

## Support and Escalation

### Contact Information

```yaml
Primary Support:
- Team: RTAP Operations
- Email: rtap-ops@company.com
- Slack: #rtap-support

Escalation:
- L2 Support: RTAP Development Team
- L3 Support: Senior Engineering
- Emergency: On-call engineer via PagerDuty
```

### Issue Reporting

```bash
# Gather diagnostic information
./gather-diagnostics.sh > rtap-diagnostics.txt

# Include in issue report:
1. Service logs (last 1 hour)
2. Resource usage statistics
3. Configuration dump
4. Error messages and stack traces
5. Steps to reproduce
```

### Emergency Procedures

```yaml
Severity 1 (Production Down):
1. Immediate failover to standby
2. Page on-call engineer
3. Collect diagnostics
4. Escalate to development team

Severity 2 (Performance Degraded):
1. Monitor and gather metrics
2. Apply immediate fixes if known
3. Schedule maintenance window
4. Notify stakeholders

Severity 3 (Minor Issues):
1. Document issue
2. Plan fix during next maintenance
3. Monitor for escalation
```

---

This operations manual provides comprehensive guidance for managing RTAP in production. Keep this document updated as the system evolves and new operational patterns emerge.

---

**Document Version**: 1.0  
**Last Updated**: January 8, 2025  
**Review Cycle**: Monthly  
**Owner**: RTAP Operations Team  
