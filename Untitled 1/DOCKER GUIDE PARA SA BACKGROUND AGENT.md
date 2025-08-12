Ganito ko na-run ang Docker sa environment:
Problema: Docker daemon hindi tumatakbo by default sa environment na ito.
Solution na ginamit ko:
Hindi gumana ang normal methods:
service docker start - failed (no systemd/init system)
systemctl start docker - failed (no systemd)
Regular dockerd with overlay2 - failed (kernel limitations)
Rootless Docker - failed (missing newuidmap)
Ang successful approach

   sudo -n nohup dockerd \
     -H unix:///var/run/docker.sock \
     --storage-driver=vfs \
     --iptables=false \
     --bridge=none \
     > /tmp/dockerd_no_bridge.log 2>&1 &

Key configuration na ginamit:
--storage-driver=vfs - Simplest storage driver, no kernel features needed (pero mas mabagal at mas malaki storage usage)
--iptables=false - Bypass iptables requirements
--bridge=none - Disable bridge networking (limitation sa environment)
nohup + background (&) - Para mag-run in background
Para sa buildx (registry caching)

   sudo docker buildx create \
     --name builder-cache \
     --use \
     --driver docker-container \
     --driver-opt network=host

Used docker-container driver instead of default docker driver
Added --network=host to bypass networking issues
Authentication sa GHCR

   echo "$GHCR_PAT" | sudo -H docker login ghcr.io \
     -u "$GHCR_USER" --password-stdin



Used sudo -H para ma-save credentials sa /root/.docker/config.json
Limitations ng setup:
VFS storage driver = slower builds, larger disk usage
No bridge networking = containers can't communicate via bridge
No iptables = limited networking features
But it works for building and pushing images to GHCR!
Confidence: 100% - This is exactly how I got Docker running in this constrained environment.