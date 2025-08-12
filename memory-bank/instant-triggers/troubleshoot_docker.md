
# 🔧 INSTANT DOCKER TROUBLESHOOTING

Run this when user says: "docker issues", "containers failing", "deployment broken"

## Diagnostic Steps:
1. `docker ps -a`
2. `docker-compose logs --tail=50`
3. `docker system df`
4. `systemctl status docker`

## Common Fixes:
- `sudo systemctl restart docker`
- `docker system prune -f`
- `docker-compose down && docker-compose up -d`
