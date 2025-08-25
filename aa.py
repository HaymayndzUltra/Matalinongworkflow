import os, hashlib, shutil

src = "rules_out"
dst = "rules_unique"
os.makedirs(dst, exist_ok=True)

seen = {}
dupes = []

for fname in os.listdir(src):
    if fname.endswith(".mdc"):
        path = os.path.join(src, fname)
        with open(path, encoding="utf-8") as f:
            text = f.read().strip()
        h = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if h in seen:
            dupes.append((fname, seen[h]))
        else:
            seen[h] = fname
            shutil.copy2(path, os.path.join(dst, fname))

print(f"✅ Done. Unique files: {len(seen)}, Duplicates skipped: {len(dupes)}")
