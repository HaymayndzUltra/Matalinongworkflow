
# 🎮 INSTANT GPU DIAGNOSTICS

Run this when user says: "gpu issues", "nvidia problems", "gpu not working"

## GPU Checks:
1. `nvidia-smi`
2. `docker run --gpus all nvidia/cuda:11.0-base nvidia-smi`
3. `ls -la /dev/nvidia*`
4. `nvidia-container-cli info`

## GPU Fixes:
- `sudo systemctl restart nvidia-persistenced`
- `scripts/setup-gpu-partitioning.sh`
