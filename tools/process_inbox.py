#!/usr/bin/env python3
"""
Processa assets/models/_inbox/ — roda dentro do GitHub Actions (não precisa
rodar isso na sua máquina). Pra usar: sobe um arquivo .glb ou .zip (baixado
do Sketchfab, por exemplo) direto pela interface do GitHub em
assets/models/_inbox/ (celular ou PC, sem precisar de terminal) — esse
script organiza o arquivo no lugar certo, atualiza o índice, e o workflow
que o chama já commita e publica sozinho.

Formatos aceitos na caixa de entrada:
  - .glb                 -> vira assets/models/<nome>.glb
  - .zip (export gltf)   -> extraído pra assets/models/<nome>/
  - .gltf avulso         -> movido pra assets/models/<nome>/ (sem .bin/texturas
                             associadas ele pode não carregar — prefira .glb ou .zip)
"""
import json
import os
import re
import shutil
import sys
import zipfile

from model_index import MODELS_DIR, INBOX_DIR, slugify, write_index


def unique_dest(path_no_ext, ext=""):
    """Evita sobrescrever algo que já existe, tipo nome-2, nome-3..."""
    candidate = path_no_ext + ext
    n = 2
    while os.path.exists(candidate):
        candidate = f"{path_no_ext}-{n}{ext}"
        n += 1
    return candidate


def process_glb(src_path, slug):
    dest = unique_dest(os.path.join(MODELS_DIR, slug), ".glb")
    shutil.move(src_path, dest)
    print(f"  -> assets/models/{os.path.basename(dest)}")
    return True


def process_zip(src_path, slug):
    dest_dir = unique_dest(os.path.join(MODELS_DIR, slug))
    os.makedirs(dest_dir, exist_ok=True)
    try:
        with zipfile.ZipFile(src_path) as zf:
            zf.extractall(dest_dir)
    except zipfile.BadZipFile:
        print(f"  ERRO: {os.path.basename(src_path)} não é um .zip válido, pulando.", file=sys.stderr)
        shutil.rmtree(dest_dir, ignore_errors=True)
        return False

    has_model = any(f.endswith((".glb", ".gltf")) for _, _, files in os.walk(dest_dir) for f in files)
    if not has_model:
        print(f"  ERRO: {os.path.basename(src_path)} não continha nenhum .glb/.gltf, pulando.", file=sys.stderr)
        shutil.rmtree(dest_dir, ignore_errors=True)
        return False

    with open(os.path.join(dest_dir, "_meta.json"), "w", encoding="utf-8") as f:
        json.dump({"label": None, "source": "inbox"}, f, ensure_ascii=False, indent=2)
    os.remove(src_path)
    print(f"  -> assets/models/{os.path.basename(dest_dir)}/")
    return True


def process_gltf(src_path, slug):
    dest_dir = unique_dest(os.path.join(MODELS_DIR, slug))
    os.makedirs(dest_dir, exist_ok=True)
    shutil.move(src_path, os.path.join(dest_dir, os.path.basename(src_path)))
    print(f"  -> assets/models/{os.path.basename(dest_dir)}/  (aviso: .gltf sozinho, sem .bin/texturas pode não carregar)")
    return True


def main():
    if not os.path.isdir(INBOX_DIR):
        print("Pasta _inbox não existe, nada a fazer.")
        return

    files = [f for f in sorted(os.listdir(INBOX_DIR)) if not f.startswith(".")]
    if not files:
        print("Caixa de entrada vazia, nada a processar.")
        return

    processed_any = False
    for filename in files:
        src_path = os.path.join(INBOX_DIR, filename)
        if os.path.isdir(src_path):
            continue
        name, ext = os.path.splitext(filename)
        slug = slugify(name) or "modelo"
        ext = ext.lower()
        print(f"Processando \"{filename}\"...")

        if ext == ".glb":
            ok = process_glb(src_path, slug)
        elif ext == ".zip":
            ok = process_zip(src_path, slug)
        elif ext == ".gltf":
            ok = process_gltf(src_path, slug)
        else:
            print(f"  ERRO: tipo de arquivo não reconhecido ({ext}), pulando.", file=sys.stderr)
            ok = False

        processed_any = processed_any or ok

    if processed_any:
        entries = write_index()
        print(f"\nÍndice atualizado: {len(entries)} modelo(s) disponíveis.")
    else:
        print("\nNenhum arquivo novo processado com sucesso.")


if __name__ == "__main__":
    main()
