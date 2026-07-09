#!/usr/bin/env python3
"""
Ferramenta de bastidor pra buscar e baixar modelos 3D do Sketchfab, salvar
em assets/models/ e publicar sozinha (git add/commit/push) — o modelo já
aparece pronto pra escolher no app (campo "Modelo 3D self-hosted") sem
precisar ir conferir nada manualmente no GitHub.

Roda só no seu PC (linha de comando) — não faz parte do app publicado, e não
precisa de nada além do Python padrão (sem pip install). Push automático
usa o "git" já instalado no seu PC — se a autenticação do git não estiver
configurada, o script avisa e te deixa fazer o push na mão.

------------------------------------------------------------------------
TOKEN DA API (grátis, mas NÃO cole no código — exporte como variável de
ambiente antes de rodar, senão corre o risco de subir pro git sem querer):

  1. Crie/entre numa conta em sketchfab.com
  2. Vá em Settings > Password e copie o campo "API Token"
  3. No terminal, antes de usar o script:
       export SKETCHFAB_API_TOKEN="seu_token_aqui"
------------------------------------------------------------------------

Uso:
  python3 tools/fetch_sketchfab_model.py search "katana"
  python3 tools/fetch_sketchfab_model.py get <link ou UID do Sketchfab> [--name espada-zangetsu] [--no-push]

"get" só funciona se o autor do modelo original marcou ele como
"Downloadable" no Sketchfab — nem todo modelo permite isso.
"""
import argparse
import io
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile

API_BASE = "https://api.sketchfab.com/v3"
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(REPO_ROOT, "assets", "models")
INDEX_PATH = os.path.join(MODELS_DIR, "index.json")


def get_token():
    token = os.environ.get("SKETCHFAB_API_TOKEN")
    if not token:
        print("Erro: defina a variável de ambiente SKETCHFAB_API_TOKEN antes de rodar.", file=sys.stderr)
        print('Ex: export SKETCHFAB_API_TOKEN="seu_token"', file=sys.stderr)
        sys.exit(1)
    return token


def extract_uid(text):
    text = text.strip()
    m = re.search(r'sketchfab\.com/(?:3d-models|models)/[\w-]*?-?([0-9a-f]{32})', text, re.I)
    if m:
        return m.group(1)
    if re.fullmatch(r'[0-9a-f]{32}', text, re.I):
        return text
    print(f"Não entendi \"{text}\" como link ou UID do Sketchfab.", file=sys.stderr)
    sys.exit(1)


def api_get(path, token=None, params=None):
    url = f"{API_BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    if token:
        req.add_header("Authorization", f"Token {token}")
    try:
        with urllib.request.urlopen(req) as res:
            return json.loads(res.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"Erro HTTP {e.code} em {url}:\n{body}", file=sys.stderr)
        sys.exit(1)


def slugify(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def prettify(slug):
    return re.sub(r'[-_]+', ' ', slug).strip().title()


def cmd_search(args):
    data = api_get("/search", params={"type": "models", "q": args.query, "downloadable": "true", "count": args.limit})
    results = data.get("results", [])
    if not results:
        print("Nada encontrado com download habilitado pra esse termo.")
        return
    for r in results:
        user = r.get("user", {}).get("username", "?")
        print(f"{r['uid']}  \"{r['name']}\"  por {user}  ->  https://sketchfab.com/3d-models/{r['uid']}")


def rebuild_index():
    """Varre assets/models/ e monta a lista de modelos disponíveis pro app escolher."""
    entries = []
    if not os.path.isdir(MODELS_DIR):
        return entries
    for entry in sorted(os.listdir(MODELS_DIR)):
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


def run_git(args):
    try:
        return subprocess.run(["git", "-C", REPO_ROOT] + args, capture_output=True, text=True)
    except FileNotFoundError:
        print("Git não encontrado no PATH — instale o Git ou faça commit/push manualmente.", file=sys.stderr)
        return None


def git_commit_and_push(message):
    add = run_git(["add", "assets/models"])
    if add is None or add.returncode != 0:
        if add is not None:
            print("Aviso: git add falhou:", add.stderr.strip(), file=sys.stderr)
        print("Não consegui publicar sozinho — faça 'git add assets/models && git commit && git push' na mão.", file=sys.stderr)
        return False

    status = run_git(["status", "--porcelain", "--", "assets/models"])
    if status is not None and not status.stdout.strip():
        print("Nada novo pra publicar (os arquivos já estavam salvos).")
        return True

    commit = run_git(["commit", "-m", message])
    if commit is None or commit.returncode != 0:
        print("Aviso: git commit falhou:", (commit.stderr.strip() if commit else ""), file=sys.stderr)
        return False
    print(commit.stdout.strip())

    push = run_git(["push"])
    if push is None or push.returncode != 0:
        print("\nAviso: git push falhou — provavelmente falta configurar autenticação do git nesse PC", file=sys.stderr)
        print("(git credential manager, token de acesso pessoal, ou chave SSH). O commit já foi feito", file=sys.stderr)
        print("localmente; rode 'git push' na mão pra ver o erro completo e resolver.", file=sys.stderr)
        if push is not None:
            print(push.stderr.strip(), file=sys.stderr)
        return False

    print("\n✓ Publicado! Em ~1 minuto o modelo já deve estar disponível no site (deploy automático).")
    return True


def cmd_get(args):
    token = get_token()
    uid = extract_uid(args.model)

    meta = api_get(f"/models/{uid}", token=token)
    name = args.name or slugify(meta.get("name", uid)) or uid

    print(f"Baixando \"{meta.get('name')}\" ({uid})...")
    dl = api_get(f"/models/{uid}/download", token=token)
    gltf_info = dl.get("gltf")
    if not gltf_info:
        print("Este modelo não tem uma versão glTF disponível pra download", file=sys.stderr)
        print("(o autor pode não ter habilitado download, ou você não tem permissão).", file=sys.stderr)
        sys.exit(1)

    with urllib.request.urlopen(gltf_info["url"]) as res:
        zip_bytes = res.read()

    dest_dir = os.path.join(MODELS_DIR, name)
    os.makedirs(dest_dir, exist_ok=True)
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            zf.extractall(dest_dir)
    except zipfile.BadZipFile:
        print("O download não veio como um .zip válido — tente de novo.", file=sys.stderr)
        sys.exit(1)

    entry_rel = "scene.gltf"
    for root, _, files in os.walk(dest_dir):
        for f in files:
            if f.endswith(".gltf"):
                entry_rel = os.path.relpath(os.path.join(root, f), dest_dir).replace(os.sep, "/")
                break
        else:
            continue
        break

    with open(os.path.join(dest_dir, "_meta.json"), "w", encoding="utf-8") as f:
        json.dump({
            "label": meta.get("name"),
            "uid": uid,
            "source": "sketchfab",
            "author": meta.get("user", {}).get("username"),
        }, f, ensure_ascii=False, indent=2)

    model3d_path = f"assets/models/{name}/{entry_rel}"
    print(f"\nPronto! Salvo em: {model3d_path}")

    write_index()
    print("Índice assets/models/index.json atualizado — o modelo já aparece na lista do app.")

    if args.no_push:
        print("\n(--no-push usado: lembre de fazer git add/commit/push manualmente quando quiser publicar)")
    else:
        git_commit_and_push(f"Adiciona modelo 3D: {meta.get('name')}")


def cmd_reindex(args):
    entries = write_index()
    print(f"Índice atualizado com {len(entries)} modelo(s).")
    for e in entries:
        print(f"  {e['label']}  ->  {e['path']}")


def main():
    p = argparse.ArgumentParser(description="Busca e baixa modelos 3D do Sketchfab pro ibasho.")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("search", help="busca modelos com download habilitado")
    sp.add_argument("query")
    sp.add_argument("--limit", type=int, default=10)
    sp.set_defaults(func=cmd_search)

    gp = sub.add_parser("get", help="baixa um modelo específico (link ou UID) e publica sozinho")
    gp.add_argument("model")
    gp.add_argument("--name", help="nome da pasta em assets/models/ (padrão: nome do modelo)")
    gp.add_argument("--no-push", action="store_true", help="não faz commit/push automático, só baixa")
    gp.set_defaults(func=cmd_get)

    rp = sub.add_parser("reindex", help="reconstrói assets/models/index.json (sem baixar nada novo)")
    rp.set_defaults(func=cmd_reindex)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
