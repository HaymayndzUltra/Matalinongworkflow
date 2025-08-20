import base64, json, requests
from pathlib import Path
def b64(p): return "data:image/jpeg;base64,"+base64.b64encode(Path(p).read_bytes()).decode()
img_dir = Path("/home/haymayndz/MatalinongWorkflow/photo-id")
candidates = [p for p in img_dir.glob("*") if p.suffix.lower() in {".jpg",".jpeg",".png"}]
latest = max(candidates, key=lambda p: p.stat().st_mtime)
payload = {"image_base64": b64(latest), "document_type": "DRIVERS_LICENSE", "session_id": "sess_local_latest"}
r = requests.post("http://localhost:8010/complete", json=payload, timeout=120)
print(json.dumps(r.json(), indent=2))
