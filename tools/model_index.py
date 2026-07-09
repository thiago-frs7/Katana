"""
Lógica compartilhada de indexação de assets/models/ — usada tanto pelo
fetch_sketchfab_model.py (roda no seu PC) quanto pelo process_inbox.py
(roda dentro do GitHub Actions quando você sobe um arquivo pelo celular).
"""
import json
import os
import re

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(REPO_ROOT, "assets", "models")
INDEX_PATH = os.path.join(MODELS_DIR, "index.json")
INBOX_DIR = os.path.join(MODELS_DIR, "_inbox")


def slugify(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def prettify(slug):
    return re.sub(r'[-_]+', ' ', slug).strip().title()


def rebuild_index():
    """Varre assets/models/ (menos _inbox) e monta a lista de modelos disponíveis."""
    entries = []
    if not os.path.isdir(MODELS_DIR):
        return entries
    for entry in sorted(os.listdir(MODELS_DIR)):
        if entry == "_inbox":
            continue
        full = os.path.join(MODELS_DIR, entry)
        if os.path.isdir(full):
            label = None
            meta_path = os.path.join(full, "_meta.json")
            if os.path.isfile(meta_path):
                try:
                    with open(meta_path, encoding="utf-8") as f:
                        label = json.load(f).get("label")
                except (OSError, json.JSONDecodeError):
                    pass
            model_file = None
            for root, _, files in os.walk(full):
                for f in files:
                    if f.endswith((".glb", ".gltf")):
                        model_file = os.path.relpath(os.path.join(root, f), MODELS_DIR).replace(os.sep, "/")
                        break
                if model_file:
                    break
            if model_file:
                entries.append({"name": entry, "label": label or prettify(entry), "path": f"assets/models/{model_file}"})
        elif entry.endswith((".glb", ".gltf")):
            name = os.path.splitext(entry)[0]
            entries.append({"name": name, "label": prettify(name), "path": f"assets/models/{entry}"})
    return entries


def write_index():
    entries = rebuild_index()
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    return entries
