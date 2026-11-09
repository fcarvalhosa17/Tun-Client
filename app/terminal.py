"""Aba de terminal telnet: xterm.js (empacotado, sem internet) <-> QWebChannel <-> canal pelo tunel."""
import codecs
import logging
import os
import sys
import threading

from PySide6.QtCore import QObject, Qt, QUrl, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWebEngineWidgets import QWebEngineView

from telnet import Protocolo

log = logging.getLogger("terminal")
PASTA = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), "xterm")


class Ponte(QObject):
    """Objeto que o JS enxerga. A leitura do canal roda em thread; o texto chega ao JS pela thread da interface."""
    chegou = Signal(str)        # -> xterm
    conectou = Signal()         # -> janela (historico), sempre na thread da interface
    _da_thread = Signal(str)
    _conectou_thread = Signal()

    def __init__(self, destino, abrir):
        """abrir() -> (canal, tocar): canal com recv/sendall/close; tocar() marca atividade do tunel."""
        super().__init__()
        self.destino, self._abrir = destino, abrir
        self._canal = None
        self._proto = None
        self._lock = threading.Lock()
        self._tamanho = (80, 24)
        self._da_thread.connect(self.chegou, Qt.ConnectionType.QueuedConnection)
        self._conectou_thread.connect(self.conectou, Qt.ConnectionType.QueuedConnection)

    @Slot()
    def pronto(self):
        """O xterm terminou de carregar: agora conecta (nada se perde antes)."""
        threading.Thread(target=self._rodar, daemon=True).start()

    def _rodar(self):
        self._da_thread.emit(f"\x1b[90mConectando a {self.destino}…\x1b[0m\r\n")
        try:
            canal, tocar = self._abrir()
        except Exception as e:
            msg = getattr(e, "mensagem", None) or str(e) or type(e).__name__
            self._da_thread.emit(f"\x1b[31mNão foi possível conectar: {msg}\x1b[0m\r\n")
            return
        self.fechar()
        proto = Protocolo(self._mandar)
        proto.redimensionar(*self._tamanho)
        self._canal, self._proto = canal, proto
        self._conectou_thread.emit()
        texto = codecs.getincrementaldecoder("utf-8")("replace")
        try:
            while True:
                dados = canal.recv(4096)
                if not dados:
                    break
                tocar()
                visivel = proto.receber(dados)
                if visivel:
                    self._da_thread.emit(texto.decode(visivel))
        except Exception as e:
            log.info("telnet %s encerrado: %s", self.destino, type(e).__name__)
        if self._canal is canal:
            self._da_thread.emit("\r\n\x1b[90m[conexão encerrada — ⟳ para reconectar]\x1b[0m\r\n")

    def _mandar(self, dados):
        with self._lock:
            if self._canal:
                self._canal.sendall(dados)

    @Slot(str)
    def enviar(self, texto):
        try:
            self._mandar(Protocolo.preparar(texto))
        except Exception:
            pass  # conexao caiu: o leitor avisa

    @Slot(int, int)
    def redimensionar(self, colunas, linhas):
        self._tamanho = (colunas, linhas)
        if self._proto:
            try:
                self._proto.redimensionar(colunas, linhas)
            except Exception:
                pass

    def fechar(self):
        canal, self._canal, self._proto = self._canal, None, None
        if canal:
            try:
                canal.close()
            except Exception:
                pass


class AbaTerminal(QWebEngineView):
    def __init__(self, perfil, destino, abrir):
        """destino: texto 'telnet://ip:porta'; abrir(): bloqueante, devolve (canal, tocar)."""
        super().__init__()
        self.endereco = destino
        self.setPage(QWebEnginePage(perfil, self))
        self.ponte = Ponte(destino, abrir)
        self._web = QWebChannel(self.page())
        self._web.registerObject("ponte", self.ponte)
        self.page().setWebChannel(self._web)
        self.load(QUrl.fromLocalFile(os.path.join(PASTA, "terminal.html")))

    def encerrar(self):
        self.ponte.fechar()

    def reload(self):  # ⟳ = reconectar
        self.ponte.fechar()
        super().reload()

    def back(self):
        pass

    def forward(self):
        pass
