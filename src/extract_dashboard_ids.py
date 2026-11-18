import re

with open("dashboard/app.js", "r", encoding="utf-8") as f:
    text = f.read()

elem_ids = sorted(list(set(re.findall(r"getElementById\(['\"]([a-zA-Z0-9_\-]+)['\"]\)", text))))
print("Element IDs in app.js:")
for eid in elem_ids:
    print(f"  - {eid}")

classes = sorted(list(set(re.findall(r"querySelector(All)?\(['\"]\.([a-zA-Z0-9_\-]+)['\"]\)", text))))
print("\nClass queries in app.js:")
for c in classes:
    print(f"  - {c[1]}")
