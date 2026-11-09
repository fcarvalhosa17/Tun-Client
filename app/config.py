"""clientes.json, pasta de dados e credenciais (cofre do sistema via keyring).
Nenhuma senha e gravada em arquivo, logada ou devolvida daqui."""
import csv
import ipaddress
import json
import os
import re
import sys

import keyring
import keyring.errors

APP = "tunel-clientes"
SERVICE_PADRAO = f"{APP}:padrao"

DEFAULTS_PADRAO = {
    "user": None,  # login SSH padrao: definido pelo usuario na primeira abertura
    "port": 22, "auth": "senha", "identity_file": None, "idle_minutes": 30,
    # com o cliente conectado, qualquer IP vai pelo tunel, menos a faixa da VPN
    "subnets": ["0.0.0.0/0"], "excluir": ["10.255.0.0/16"],
}
# campos que o formulario de cliente controla; os demais sao preservados na edicao
GERENCIADOS = ("id", "nome", "host", "port", "user", "auth", "identity_file", "subnets", "tags", "senha_propria")
ID_OK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class Erro(Exception):
    def __init__(self, codigo, mensagem, **extras):
        super().__init__(mensagem)
        self.codigo, self.mensagem, self.extras = codigo, mensagem, extras


def _invalido(msg):
    return Erro("clientes_json_invalido", f"clientes.json inválido: {msg}")


# ---------------------------------------------------------------- pasta de dados (unico ponto por sistema)

def dados_dir():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser(r"~\AppData\Roaming")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    pasta = os.path.join(base, APP)
    os.makedirs(pasta, exist_ok=True)
    return pasta


def caminho_clientes():
    return os.path.join(dados_dir(), "clientes.json")


# ---------------------------------------------------------------- leitura

def _ler_bruto():
    try:
        with open(caminho_clientes(), encoding="utf-8-sig") as f:
            bruto = json.load(f)
    except FileNotFoundError:
        return {"defaults": {}, "clientes": []}
    except (OSError, ValueError) as e:
        raise _invalido(str(e))
    if not isinstance(bruto, dict) or not isinstance(bruto.get("clientes"), list):
        raise _invalido("esperado objeto com a lista 'clientes'.")
    if not isinstance(bruto.setdefault("defaults", {}), dict):
        raise _invalido("'defaults' deve ser objeto.")
    return bruto


def _gravar(bruto):
    """Grava atomico: temporario na mesma pasta + replace."""
    caminho = caminho_clientes()
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(bruto, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, caminho)


def _normalizar(d, ctx):
    for k in ("port", "idle_minutes"):
        try:
            d[k] = int(d[k])
        except (TypeError, ValueError):
            raise _invalido(f"{ctx}: campo '{k}' deve ser número.")
    if not 1 <= d["port"] <= 65535:
        raise _invalido(f"{ctx}: 'port' fora de 1-65535.")
    if d["auth"] not in ("senha", "chave"):
        raise _invalido(f"{ctx}: 'auth' deve ser 'senha' ou 'chave'.")
    for k in ("subnets", "excluir"):
        if not isinstance(d[k], list):
            raise _invalido(f"{ctx}: '{k}' deve ser lista.")
        d[k] = [str(x) for x in d[k]]


def carregar():
    """-> (defaults efetivos, {id: cliente efetivo}). Relê o arquivo a cada chamada."""
    bruto = _ler_bruto()
    defaults = {**DEFAULTS_PADRAO, **bruto["defaults"]}
    _normalizar(defaults, "defaults")
    clientes = {}
    for c in bruto["clientes"]:
        if not isinstance(c, dict) or not c.get("id") or not c.get("host"):
            raise _invalido("todo cliente precisa de 'id' e 'host'.")
        cid = str(c["id"])
        if cid in clientes:
            raise _invalido(f"id duplicado: {cid}.")
        ef = {**defaults, **c, "id": cid}
        ef["nome"] = c.get("nome") or cid
        ef["user"] = c.get("user") or defaults["user"]
        ef["tags"] = [str(t) for t in c.get("tags") or []]
        ef["senha_propria"] = c.get("senha_propria") is True
        _normalizar(ef, f"cliente {cid}")
        clientes[cid] = ef
    return defaults, clientes


def obter_cliente(cid):
    cliente = carregar()[1].get(cid)
    if cliente is None:
        raise Erro("cliente_nao_encontrado", f"Cliente '{cid}' não existe.")
    return cliente


def ler_cliente(cid):
    """Cliente como esta no arquivo (sem herdar defaults), para o formulario."""
    lista = _ler_bruto()["clientes"]
    i = _indice(lista, cid)
    if i is None:
        raise Erro("cliente_nao_encontrado", f"Cliente '{cid}' não existe.")
    return lista[i]


# ---------------------------------------------------------------- login SSH padrao

def usuario_padrao():
    return carregar()[0]["user"]


def definir_usuario_padrao(usuario):
    usuario = (usuario or "").strip()
    if not usuario or any(ch.isspace() for ch in usuario):
        raise Erro("usuario_invalido", "Informe o usuário SSH, sem espaços.")
    bruto = _ler_bruto()
    bruto["defaults"]["user"] = usuario
    _gravar(bruto)


# ---------------------------------------------------------------- edicao de clientes

def _indice(lista, cid):
    return next((i for i, c in enumerate(lista) if isinstance(c, dict) and str(c.get("id")) == cid), None)


def _cliente_valido(d):
    def erro(m):
        return Erro("cliente_invalido", m)

    txt = lambda k: str(d.get(k) or "").strip()
    c = {"id": txt("id")}
    if not ID_OK.match(c["id"]):
        raise erro("Id inválido: use letras, números, ponto, hífen ou sublinhado (até 64, sem espaço).")
    if txt("nome"):
        c["nome"] = txt("nome")
    c["host"] = txt("host")
    if not c["host"] or any(ch.isspace() for ch in c["host"]):
        raise erro("Informe o endereço do servidor (IP ou nome), sem espaços.")
    if txt("port"):
        try:
            c["port"] = int(txt("port"))
        except ValueError:
            raise erro("Porta deve ser número.")
        if not 1 <= c["port"] <= 65535:
            raise erro("Porta fora de 1-65535.")
    for k in ("user", "identity_file"):
        if txt(k):
            c[k] = txt(k)
    if "user" in c and any(ch.isspace() for ch in c["user"]):
        raise erro("Usuário não pode ter espaços.")
    if txt("auth"):
        if txt("auth") not in ("senha", "chave"):
            raise erro("Autenticação deve ser 'senha' ou 'chave'.")
        c["auth"] = txt("auth")
    redes = []
    for s in d.get("subnets") or []:
        try:
            redes.append(str(ipaddress.IPv4Network(str(s).strip(), strict=False)))
        except ValueError:
            raise erro(f"Rede inválida: {s}. Use o formato 192.168.0.0/24.")
    if redes:  # vazio = herda defaults (qualquer IP)
        c["subnets"] = redes
    tags = [str(t).strip() for t in d.get("tags") or [] if str(t).strip()]
    if tags:
        c["tags"] = tags
    if d.get("senha_propria") is True:
        c["senha_propria"] = True
    return c


def _upsert(lista, novo, id_original=None):
    i = None
    if id_original:
        i = _indice(lista, id_original)
        if i is None:
            raise Erro("cliente_nao_encontrado", f"Cliente '{id_original}' não existe mais.")
    j = _indice(lista, novo["id"])
    if j is not None and j != i:
        if id_original:
            raise Erro("cliente_invalido", f"Já existe um cliente com o id '{novo['id']}'.")
        i = j  # importacao: mesmo id atualiza
    if i is None:
        lista.append(novo)
        return True
    extras = {k: v for k, v in lista[i].items() if k not in GERENCIADOS}
    lista[i] = {**novo, **extras}
    return False


def salvar_cliente(dados, id_original=None):
    """Cria (sem id_original) ou edita. Devolve o id salvo."""
    bruto = _ler_bruto()
    novo = _cliente_valido(dados if isinstance(dados, dict) else {})
    if not id_original and _indice(bruto["clientes"], novo["id"]) is not None:
        raise Erro("cliente_invalido", f"Já existe um cliente com o id '{novo['id']}'.")
    _upsert(bruto["clientes"], novo, id_original)
    _gravar(bruto)
    return novo["id"]


def remover_cliente(cid):
    bruto = _ler_bruto()
    i = _indice(bruto["clientes"], cid)
    if i is None:
        raise Erro("cliente_nao_encontrado", f"Cliente '{cid}' não existe.")
    del bruto["clientes"][i]
    _gravar(bruto)


def importar_csv(caminho):
    """CSV com cabecalho id,nome,host,port,user,auth,identity_file,subnets,tags (subnets/tags separadas por ';').
    Mesmo id atualiza; id novo e acrescentado. -> (novos, atualizados)."""
    bruto = _ler_bruto()
    novos = atualizados = 0
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        # Excel em PT-BR exporta com ';'; decide pelo cabecalho
        cabecalho = f.readline()
        f.seek(0)
        sep = ";" if "host" in [x.strip().lower() for x in cabecalho.split(";")] else ","
        for n, linha in enumerate(csv.DictReader(f, delimiter=sep), start=2):
            l = {(k or "").strip().lower(): (v or "").strip() for k, v in linha.items()}
            dados = {**l, "subnets": l.get("subnets", "").split(";"), "tags": l.get("tags", "").split(";")}
            try:
                novo = _cliente_valido(dados)
            except Erro as e:
                raise Erro("csv_invalido", f"Linha {n}: {e.mensagem}")
            if _upsert(bruto["clientes"], novo):
                novos += 1
            else:
                atualizados += 1
    _gravar(bruto)
    return novos, atualizados


# ---------------------------------------------------------------- credenciais: um unico par (service, usuario)

def _par(cliente):
    if not cliente["user"]:
        raise Erro("usuario_nao_definido", "Defina o usuário SSH nas Configurações.")
    service = f"{APP}:{cliente['id']}" if cliente["senha_propria"] else SERVICE_PADRAO
    return service, cliente["user"]


def par_credencial(cid=None):
    if cid is None:
        usuario = usuario_padrao()
        if not usuario:
            raise Erro("usuario_nao_definido", "Defina o usuário SSH nas Configurações.")
        return SERVICE_PADRAO, usuario
    return _par(obter_cliente(cid))


def senha_do_cliente(cliente):
    return keyring.get_password(*_par(cliente))


def salvar_senha(cid, senha):
    if not senha:
        raise Erro("senha_vazia", "Digite a senha.")
    keyring.set_password(*par_credencial(cid), senha)


def tem_senha(cid=None):
    try:
        return keyring.get_password(*par_credencial(cid)) is not None
    except Erro:
        return False


def apagar_senha(cid=None):
    try:
        keyring.delete_password(*par_credencial(cid))
    except (keyring.errors.PasswordDeleteError, Erro):
        pass  # ja nao existia: idempotente
