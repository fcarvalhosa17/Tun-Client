"""Tunel SSH (paramiko) + SOCKS5 local. Nunca loga senha nem conteudo de trafego.

O SOCKS vive o app inteiro em 127.0.0.1:<porta aleatoria> (o navegador do app aponta para ele
na inicializacao). Por tras dele fica no maximo UMA conexao SSH ativa, trocada ao conectar outro cliente.
"""
import ipaddress
import logging
import os
import socket
import struct
import threading
import time

import paramiko

import config
import hostkeys
from config import Erro

log = logging.getLogger("tunel")
TIMEOUT = 15
KEEPALIVE = 30
LOOPBACK = ipaddress.IPv4Network("127.0.0.0/8")


# ---------------------------------------------------------------- autenticacao SSH

def _carregar_chave(caminho):
    for nome in ("Ed25519Key", "ECDSAKey", "RSAKey"):
        cls = getattr(paramiko, nome, None)
        if cls is None:
            continue
        try:
            return cls.from_private_key_file(caminho)
        except paramiko.PasswordRequiredException:
            raise Erro("autenticacao_falhou",
                       f"A chave {caminho} é protegida por senha (não suportado). Use chave sem passphrase ou ssh-agent.")
        except paramiko.SSHException:
            continue  # tipo errado, tenta o proximo
        except OSError as e:
            raise Erro("autenticacao_falhou", f"Não foi possível ler a chave {caminho}: {e.strerror}")
    raise Erro("autenticacao_falhou", f"Formato de chave não reconhecido: {caminho}")


def _chaves(c):
    """-> (lista de chaves a tentar, agente a fechar depois)."""
    if c.get("identity_file"):
        return [_carregar_chave(os.path.expandvars(os.path.expanduser(c["identity_file"])))], None
    chaves, agente = [], None
    try:
        agente = paramiko.Agent()
        chaves += agente.get_keys()
    except Exception:
        log.info("ssh-agent indisponível")
    for nome in ("id_ed25519", "id_ecdsa", "id_rsa"):
        p = os.path.join(os.path.expanduser("~"), ".ssh", nome)
        if os.path.isfile(p):
            try:
                chaves.append(_carregar_chave(p))
            except Erro as e:
                log.info("chave padrão ignorada (%s): %s", nome, e.mensagem)
    return chaves, agente


def _autenticar(transport, c, senha):
    user = c["user"]
    if c["auth"] == "senha":
        transport.auth_password(user, senha)  # so password; keyboard-interactive nao suportado
        return
    chaves, agente = _chaves(c)
    try:
        for chave in chaves:
            try:
                transport.auth_publickey(user, chave)
                return
            except paramiko.AuthenticationException:
                continue
    finally:
        if agente is not None:
            agente.close()
    raise Erro("autenticacao_falhou", "Nenhuma chave SSH foi aceita pelo servidor (ou nenhuma foi encontrada).")


def _conectar_ssh(c, senha):
    host, port = c["host"], c["port"]
    t0 = time.monotonic()
    try:
        sock = socket.create_connection((host, port), timeout=TIMEOUT)
    except socket.timeout:
        raise Erro("timeout", f"Tempo esgotado ({TIMEOUT}s) ao conectar em {host}:{port}.")
    except OSError as e:
        raise Erro("host_inacessivel", f"Não foi possível alcançar {host}:{port} ({e.strerror or e}).")

    transport = paramiko.Transport(sock, default_window_size=2 ** 21)
    expirou = threading.Event()

    def estourou():
        expirou.set()
        transport.close()

    # prazo total de 15 s cobrindo handshake + autenticacao (auth_password nao tem timeout proprio)
    timer = threading.Timer(max(1.0, TIMEOUT - (time.monotonic() - t0)), estourou)
    timer.daemon = True
    timer.start()
    try:
        transport.start_client(timeout=TIMEOUT)
        # chave do servidor conferida ANTES de mandar a senha
        hostkeys.verificar_ou_gravar(host, port, transport.get_remote_server_key())
        _autenticar(transport, c, senha)
        if not transport.is_authenticated():
            raise paramiko.AuthenticationException("não autenticado")
    except Erro:
        transport.close()
        raise
    except Exception as e:
        transport.close()
        if expirou.is_set():
            raise Erro("timeout", f"Tempo esgotado ({TIMEOUT}s) ao negociar com {host}:{port}.")
        if isinstance(e, paramiko.AuthenticationException):
            raise Erro("autenticacao_falhou", f"Autenticação recusada por {host} para o usuário '{c['user']}'.")
        if isinstance(e, (paramiko.SSHException, EOFError, OSError)):
            raise Erro("host_inacessivel", f"Falha na negociação SSH com {host}:{port}: {e}")
        raise
    finally:
        timer.cancel()
    if expirou.is_set():  # timer disparou colado no sucesso
        transport.close()
        raise Erro("timeout", f"Tempo esgotado ({TIMEOUT}s) ao negociar com {host}:{port}.")
    transport.set_keepalive(KEEPALIVE)
    return transport


def _redes(lista, cid):
    redes = []
    for s in lista:
        try:
            redes.append(ipaddress.IPv4Network(s, strict=False))
        except ValueError:
            log.warning("rede inválida ignorada id=%s rede=%s", cid, s)
    return redes


# ---------------------------------------------------------------- conexao SSH de um cliente

class Conexao:
    def __init__(self, cliente, transport, ao_encerrar):
        self.id = cliente["id"]
        self.nome = cliente["nome"]
        self._redes = _redes(cliente["subnets"], self.id)
        self._fora = _redes(cliente["excluir"], self.id) + [LOOPBACK]
        self._idle = cliente["idle_minutes"] * 60
        self._transport, self._ao_encerrar = transport, ao_encerrar
        self._atividade = time.monotonic()
        self._fechado = threading.Event()
        self._lock = threading.Lock()
        self._sockets = set()
        threading.Thread(target=self._vigiar, daemon=True).start()
        log.info("túnel ativo id=%s", self.id)

    def permitido(self, ip):
        ip = ipaddress.IPv4Address(ip)
        return any(ip in r for r in self._redes) and not any(ip in r for r in self._fora)

    def abrir_canal(self, host, porta, cs=None):
        """Registra o socket local (se houver) e abre o canal direct-tcpip. None se a conexao ja fechou."""
        with self._lock:
            if self._fechado.is_set():
                return None
            if cs is not None:
                self._sockets.add(cs)
        self._atividade = time.monotonic()
        canal = self._transport.open_channel("direct-tcpip", (host, porta), ("127.0.0.1", 0), timeout=TIMEOUT)
        with self._lock:
            self._sockets.add(canal)
        return canal

    def soltar(self, *objs):
        with self._lock:
            self._sockets.difference_update(objs)

    def tocar(self):
        self._atividade = time.monotonic()

    def fechar(self, motivo=None):
        """Idempotente. Com motivo (queda/ociosidade) avisa quem abriu; fechar manual nao avisa."""
        with self._lock:
            if self._fechado.is_set():
                return
            self._fechado.set()
            abertos = list(self._sockets)
        for obj in (self._transport, *abertos):
            try:
                obj.close()
            except Exception:
                pass
        log.info("túnel encerrado id=%s motivo=%s", self.id, motivo or "manual")
        if motivo:
            self._ao_encerrar(self, motivo)

    def _vigiar(self):
        while not self._fechado.wait(2):
            if not self._transport.is_active():
                self.fechar("queda")
            elif self._idle > 0 and time.monotonic() - self._atividade > self._idle:
                self.fechar("ociosidade")


# ---------------------------------------------------------------- SOCKS5 (vida inteira do app)

def _ler(sock, n):
    buf = b""
    while len(buf) < n:
        d = sock.recv(n - len(buf))
        if not d:
            raise ConnectionError("conexão encerrada")
        buf += d
    return buf


def _resp(codigo):
    return b"\x05" + bytes([codigo]) + b"\x00\x01\x00\x00\x00\x00\x00\x00"


def _codigo_socks(e):
    if isinstance(e, paramiko.ChannelException):
        # 1 proibido, 2 connect failed, 3 tipo desconhecido, 4 falta de recurso
        return {1: 0x02, 2: 0x05, 3: 0x03, 4: 0x01}.get(e.code, 0x01)
    return 0x04  # timeout/SSHException: host inalcancavel


class Socks:
    def __init__(self):
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.bind(("127.0.0.1", 0))  # porta aleatoria: nunca "porta ocupada"
        self._srv.listen(64)
        self.porta = self._srv.getsockname()[1]
        self.ativa = None  # Conexao
        threading.Thread(target=self._aceitar, daemon=True).start()

    def _aceitar(self):
        while True:
            try:
                cs, _ = self._srv.accept()
            except OSError:
                break
            threading.Thread(target=self._atender, args=(cs,), daemon=True).start()

    def _atender(self, cs):
        con, canal = self.ativa, None
        try:
            cs.settimeout(TIMEOUT)
            ver, nmet = _ler(cs, 2)
            metodos = _ler(cs, nmet)
            if ver != 5 or 0 not in metodos:
                cs.sendall(b"\x05\xff")
                return
            cs.sendall(b"\x05\x00")
            ver, cmd, _, atyp = _ler(cs, 4)
            if atyp == 1:
                host = socket.inet_ntoa(_ler(cs, 4))
            elif atyp == 3:
                # o Chromium manda ate o IP digitado como "dominio"; nome de verdade e recusado
                # (nao da para checar a rede de um nome resolvido no servidor)
                host = _ler(cs, _ler(cs, 1)[0]).decode("ascii", "replace")
                try:
                    host = str(ipaddress.IPv4Address(host))
                except ValueError:
                    _ler(cs, 2)
                    log.info("SOCKS recusado: nome em vez de IP (%s)", host)
                    cs.sendall(_resp(0x02))
                    return
            else:  # IPv6 e demais: nao suportado
                if atyp == 4:
                    _ler(cs, 18)
                cs.sendall(_resp(0x08))
                return
            porta = struct.unpack(">H", _ler(cs, 2))[0]
            if cmd != 1:
                cs.sendall(_resp(0x07))
                return
            if con is None:
                cs.sendall(_resp(0x01))  # nenhum cliente conectado
                return
            if not con.permitido(host):
                log.info("SOCKS recusado fora das redes do cliente destino=%s:%s", host, porta)
                cs.sendall(_resp(0x02))  # 0x02 = proibido pelas regras
                return
            try:
                canal = con.abrir_canal(host, porta, cs)
            except Exception as e:
                log.info("SOCKS falhou destino=%s:%s erro=%s", host, porta, type(e).__name__)
                cs.sendall(_resp(_codigo_socks(e)))
                return
            if canal is None:
                cs.sendall(_resp(0x01))
                return
            cs.sendall(_resp(0x00))
            cs.settimeout(None)
            _retransmitir(cs, canal, con.tocar)
        except Exception:
            try:
                cs.sendall(_resp(0x01))
            except Exception:
                pass
        finally:
            if con:
                con.soltar(cs, *([canal] if canal else []))
            for obj in (cs, canal):
                try:
                    obj and obj.close()
                except Exception:
                    pass


def _retransmitir(cs, canal, tocar):
    def cliente_para_canal():
        try:
            while True:
                d = cs.recv(32768)
                if not d:
                    break
                tocar()
                canal.sendall(d)
        except Exception:
            pass
        try:
            canal.shutdown_write()
        except Exception:
            pass

    t = threading.Thread(target=cliente_para_canal, daemon=True)
    t.start()
    try:
        while True:
            d = canal.recv(32768)
            if not d:
                break
            cs.sendall(d)
    except Exception:
        pass
    try:
        cs.shutdown(socket.SHUT_WR)
    except Exception:
        pass
    t.join()


# ---------------------------------------------------------------- um cliente ativo por vez

class Gerente:
    def __init__(self):
        self.socks = Socks()
        self.ao_encerrar = lambda cid, motivo: None  # trocado pela interface; chamado de outra thread
        self._lock = threading.Lock()

    @property
    def ativa(self):
        return self.socks.ativa

    def conectar(self, cid):
        """Bloqueia ate 15 s: chamar fora da thread da interface."""
        cliente = config.obter_cliente(cid)
        if not cliente["user"]:
            raise Erro("usuario_nao_definido", "Defina o usuário SSH nas Configurações.")
        senha = None
        if cliente["auth"] == "senha":
            senha = config.senha_do_cliente(cliente)
            if not senha:
                raise Erro("senha_nao_cadastrada", "Senha não cadastrada para este cliente.", id=cid)
        with self._lock:
            self.desconectar()
            transport = _conectar_ssh(cliente, senha)
            self.socks.ativa = Conexao(cliente, transport, self._encerrou)
        return self.socks.ativa

    def desconectar(self):
        con, self.socks.ativa = self.socks.ativa, None
        if con:
            con.fechar()

    def _encerrou(self, con, motivo):
        if self.socks.ativa is con:
            self.socks.ativa = None
            self.ao_encerrar(con.id, motivo)
