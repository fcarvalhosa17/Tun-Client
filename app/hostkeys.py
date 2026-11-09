"""known_hosts proprio: '<[host]:porta> <tipo> <base64>' por linha. Aceita na 1a vez, recusa se mudar."""
import base64
import hashlib
import os

from config import Erro, dados_dir


def _arquivo():
    return os.path.join(dados_dir(), "known_hosts")


def _nome(host, port):
    return f"[{host}]:{port}"


def fingerprint(blob):
    return "SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip("=")


def _ler():
    try:
        with open(_arquivo(), encoding="utf-8") as f:
            return [p for p in (l.split() for l in f) if len(p) == 3]
    except FileNotFoundError:
        return []


def verificar_ou_gravar(host, port, chave):
    nome, tipo, b64 = _nome(host, port), chave.get_name(), chave.get_base64()
    entradas = [e for e in _ler() if e[0] == nome]
    if not entradas:
        with open(_arquivo(), "a", encoding="utf-8") as f:
            f.write(f"{nome} {tipo} {b64}\n")
        return
    if any(e[1] == tipo and e[2] == b64 for e in entradas):
        return
    antiga = next((e for e in entradas if e[1] == tipo), entradas[0])
    antigo = fingerprint(base64.b64decode(antiga[2]))
    novo = fingerprint(chave.asbytes())
    raise Erro(
        "hostkey_mudou",
        f"A chave do servidor {host}:{port} mudou (possível ataque ou reinstalação). "
        f"Antiga: {antigo}. Nova: {novo}. Se for legítimo, use 'esquecer chave' e conecte de novo.",
        fingerprint_antigo=antigo, fingerprint_novo=novo)


def esquecer(host, port):
    nome = _nome(host, port)
    restantes = [e for e in _ler() if e[0] != nome]
    with open(_arquivo(), "w", encoding="utf-8") as f:
        f.writelines(" ".join(e) + "\n" for e in restantes)
