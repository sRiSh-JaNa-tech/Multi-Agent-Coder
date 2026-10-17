import zipfile
import json
import sys
import os
from collections import defaultdict
from logger import log

def zip_to_tree(zip_path):
    tree = defaultdict(dict)

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for file in zip_ref.namelist():
            parts = file.rstrip("/").split("/")
            current = tree
            for part in parts:
                current = current.setdefault(part, {})

    def build_json(node):
        children = []
        for name, sub in node.items():
            if sub:
                children.append({
                    "name": name,
                    "type": "folder",
                    "children": build_json(sub)
                })
            else:
                children.append({
                    "name": name,
                    "type": "file"
                })
        return sorted(children, key=lambda x: (x["type"], x["name"]))

    return build_json(tree)

if __name__ == "__main__":
    try:
        zip_path = sys.argv[1]

        base = os.path.basename(zip_path)
        name = os.path.splitext(base)[0]

        json_path = os.path.join(
            os.path.dirname(zip_path),
            f"{name}.json"
        )

        result = zip_to_tree(zip_path)

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        # 🚨 VERY IMPORTANT: print ONLY the JSON path
        print(json_path)

    except Exception as e:
        log(f"ZIP processing failed: {e}", level="ERROR", module_name="read_zip")
        print("")
