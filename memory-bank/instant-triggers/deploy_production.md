
# 🚀 INSTANT PRODUCTION DEPLOYMENT

Run this when user says: "deploy production", "setup production", "go live"

## Immediate Actions:
1. `git reset --hard origin/cursor/reorganize-agent-groups-for-docker-production-deployment-8f25`
2. `scripts/security-hardening.sh`
3. `scripts/setup-gpu-partitioning.sh`
4. `docker-compose -f main_pc_code/config/docker-compose.yml up -d`
5. `docker-compose -f docker-compose.observability.yml up -d`

## Verification:
- `docker ps -a`
- `nvidia-smi`
- `curl http://localhost:3000`
