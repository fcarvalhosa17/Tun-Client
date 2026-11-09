"""Janela principal: lista de clientes a esquerda, abas de navegacao a direita."""
import ipaddress
import json
import logging
import socket
import threading

from PySide6.QtCore import QObject, QSettings, QStringListModel, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QFont, QKeySequence
from PySide6.QtWidgets import (QCompleter, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMenu,
                               QMessageBox, QPushButton, QSplitter, QTabWidget, QToolBar, QToolButton, QVBoxLayout, QWidget)

import config
import dialogos
import hostkeys
from config import Erro
from navegador import Aba, novo_perfil, url_do_texto
from terminal import AbaTerminal

log = logging.getLogger("janela")
CORES = {"ok": "#15803d", "neutro": "#111111", "erro": "#b91c1c"}
MOTIVOS = {"ociosidade": "encerrado por ociosidade", "queda": "a conexão com o cliente caiu"}


class Sinais(QObject):
    """Ponte das threads do tunel para a interface."""
    conectado = Signal(str)
    falhou = Signal(object, str)
    encerrado = Signal(str, str)


class Janela(QMainWindow):
    def __init__(self, gerente):
        super().__init__()
        self.gerente = gerente
        self.sinais = Sinais()
        self.sinais.conectado.connect(self._conectado)
        self.sinais.falhou.connect(self._falhou)
        self.sinais.encerrado.connect(self._encerrado)
        gerente.ao_encerrar = self.sinais.encerrado.emit
        self.prefs = QSettings("tunel-clientes", "app")
        self.clientes = {}
        self.ocupado = False
        self.perfil = None

        self.setWindowTitle("Tunel Clientes")
        self.resize(1280, 800)

        # --- painel de clientes
        lateral = QWidget()
        col = QVBoxLayout(lateral)
        self.busca = QLineEdit()
        self.busca.setPlaceholderText("Buscar por nome, id, endereço ou tag")
        self.busca.setClearButtonEnabled(True)
        self.busca.textChanged.connect(self._render)
        self.lista = QListWidget()
        self.lista.itemDoubleClicked.connect(lambda it: self.conectar(it.data(Qt.ItemDataRole.UserRole)))
        self.lista.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.lista.customContextMenuRequested.connect(self._menu_cliente)
        self.lista.currentItemChanged.connect(lambda *_: self._botoes())
        self.bt_conectar = QPushButton("Conectar")
        self.bt_conectar.clicked.connect(self._alternar)
        bt_novo, bt_config = QPushButton("Novo cliente"), QPushButton("Configurações")
        bt_novo.clicked.connect(self._novo_cliente)
        bt_config.clicked.connect(lambda: self.configuracoes())
        linha = QHBoxLayout()
        linha.addWidget(self.bt_conectar)
        linha.addWidget(bt_novo)
        col.addWidget(self.busca)
        col.addWidget(self.lista)
        col.addLayout(linha)
        col.addWidget(bt_config)

        # --- navegador
        direita = QWidget()
        col2 = QVBoxLayout(direita)
        col2.setContentsMargins(0, 0, 0, 0)
        barra = QToolBar()
        self.endereco = QLineEdit()
        self.endereco.setPlaceholderText("IP do aparelho, ex.: 192.168.0.10 ou https://192.168.0.10:8443")
        self.endereco.returnPressed.connect(self.navegar)
        for texto, atalho, acao in (
            ("◀", QKeySequence.StandardKey.Back, lambda: self._aba() and self._aba().back()),
            ("▶", QKeySequence.StandardKey.Forward, lambda: self._aba() and self._aba().forward()),
            ("⟳", QKeySequence.StandardKey.Refresh, lambda: self._aba() and self._aba().reload()),
        ):
            a = QAction(texto, self)
            a.setShortcut(atalho)
            a.triggered.connect(acao)
            barra.addAction(a)
        barra.addWidget(self.endereco)
        # historico de enderecos do cliente conectado: sugestoes ao digitar + menu
        self.modelo_hist = QStringListModel(self)
        sugestoes = QCompleter(self.modelo_hist, self)
        sugestoes.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        sugestoes.setFilterMode(Qt.MatchFlag.MatchContains)
        self.endereco.setCompleter(sugestoes)
        bt_hist = QToolButton()
        bt_hist.setText("Histórico")
        bt_hist.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu_hist = QMenu(bt_hist)
        menu_hist.aboutToShow.connect(lambda: self._menu_historico(menu_hist))
        bt_hist.setMenu(menu_hist)
        barra.addWidget(bt_hist)
        telnet = QAction("Telnet…", self)
        telnet.triggered.connect(self._pedir_telnet)
        barra.addAction(telnet)
        nova = QAction("+ Aba", self)
        nova.setShortcut(QKeySequence.StandardKey.AddTab)
        nova.triggered.connect(lambda: self.abrir_aba() and self.endereco.setFocus())
        barra.addAction(nova)
        self.abas = QTabWidget()
        self.abas.setTabsClosable(True)
        self.abas.setDocumentMode(True)
        self.abas.tabCloseRequested.connect(self._fechar_aba)
        self.abas.currentChanged.connect(lambda *_: self._sincronizar_endereco())
        col2.addWidget(barra)
        col2.addWidget(self.abas)

        divisor = QSplitter()
        divisor.addWidget(lateral)
        divisor.addWidget(direita)
        divisor.setSizes([300, 980])
        self.setCentralWidget(divisor)
        # estado da conexao no rodape (verde conectado, preto desconectado, vermelho erro);
        # o mesmo esquema de cor vale para o cliente na lista
        self.estado = QLabel()
        self.statusBar().addPermanentWidget(self.estado)
        self.erro_id = self.conectando_id = None
        self._estado("● Desconectado", "neutro")
        if self.prefs.value("geometria"):
            self.restoreGeometry(self.prefs.value("geometria"))

        self._sessao_limpa()
        self.carregar_lista()

    # ------------------------------------------------------------ lista de clientes
    def carregar_lista(self):
        try:
            self.clientes = config.carregar()[1]
        except Erro as e:
            self.clientes = {}
            self.statusBar().showMessage(e.mensagem)
        self._render()

    # QSettings devolve texto (nao lista) quando ha um item so: guarda listas como JSON
    def _lista(self, chave):
        try:
            return [str(x) for x in json.loads(self.prefs.value(chave) or "[]")]
        except (TypeError, ValueError):
            return []

    def _guardar_lista(self, chave, lista):
        self.prefs.setValue(chave, json.dumps(lista))

    def _recentes(self):
        return self._lista("recentes")

    def _render(self):
        q = self.busca.text().strip().lower()
        ativa = self.gerente.ativa.id if self.gerente.ativa else None
        recentes = self._recentes()
        ordem = lambda c: (recentes.index(c["id"]) if c["id"] in recentes else 99, c["nome"].lower())
        atual = self.lista.currentItem().data(Qt.ItemDataRole.UserRole) if self.lista.currentItem() else None
        self.lista.clear()
        for c in sorted(self.clientes.values(), key=ordem):
            if q and q not in " ".join([c["nome"], c["id"], c["host"], *c["tags"]]).lower():
                continue
            marca = {ativa: "● ", self.conectando_id: "◌ ", self.erro_id: "✖ "}.get(c["id"], "")
            it = QListWidgetItem(marca + f"{c['nome']}   ({c['host']})")
            it.setData(Qt.ItemDataRole.UserRole, c["id"])
            it.setToolTip(f"id: {c['id']}\nusuário: {c['user'] or '(padrão não definido)'}")
            cor = CORES["ok"] if c["id"] == ativa else CORES["erro"] if c["id"] == self.erro_id else None
            if cor:
                f = QFont(it.font())
                f.setBold(True)
                it.setFont(f)
                it.setForeground(QColor(cor))
            self.lista.addItem(it)
            if c["id"] in (atual, ativa):
                self.lista.setCurrentItem(it)
        self._botoes()

    def _selecionado(self):
        it = self.lista.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def _botoes(self):
        ativa = self.gerente.ativa
        sel = self._selecionado()
        if ativa and (sel is None or sel == ativa.id):
            self.bt_conectar.setText("Desconectar")
            self.bt_conectar.setEnabled(not self.ocupado)
        else:
            self.bt_conectar.setText("Conectar")
            self.bt_conectar.setEnabled(not self.ocupado and sel is not None)

    def _alternar(self):
        ativa, sel = self.gerente.ativa, self._selecionado()
        if ativa and (sel is None or sel == ativa.id):
            self.desconectar()
        elif sel:
            self.conectar(sel)

    def _menu_cliente(self, pos):
        it = self.lista.itemAt(pos)
        if not it:
            return
        cid = it.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        menu.addAction("Conectar", lambda: self.conectar(cid))
        menu.addAction("Editar…", lambda: self._editar_cliente(cid))
        if self.clientes.get(cid, {}).get("senha_propria"):
            menu.addAction("Trocar senha própria…", lambda: self._senha_propria(cid))
            menu.addAction("Voltar à senha padrão", lambda: self._senha_padrao(cid))
        else:
            menu.addAction("Senha própria (diferente da padrão)…", lambda: self._senha_propria(cid))
        menu.addAction("Esquecer chave do servidor", lambda: self._esquecer_chave(cid))
        menu.addSeparator()
        menu.addAction("Remover", lambda: self._remover_cliente(cid))
        menu.exec(self.lista.mapToGlobal(pos))

    def _novo_cliente(self):
        dlg = dialogos.Cliente(self)
        if dlg.exec():
            self.carregar_lista()

    def _editar_cliente(self, cid):
        try:
            dlg = dialogos.Cliente(self, cid)
        except Erro as e:
            return QMessageBox.warning(self, "Editar cliente", e.mensagem)
        if dlg.exec():
            self.carregar_lista()
            if self.gerente.ativa and self.gerente.ativa.id == cid:
                self.statusBar().showMessage("Alterações valem a partir da próxima conexão.", 8000)

    def _remover_cliente(self, cid):
        nome = self.clientes.get(cid, {}).get("nome", cid)
        if QMessageBox.question(self, "Remover cliente", f"Remover {nome} ({cid})?") != QMessageBox.StandardButton.Yes:
            return
        if self.gerente.ativa and self.gerente.ativa.id == cid:
            self.desconectar()
        try:
            if self.clientes.get(cid, {}).get("senha_propria"):
                config.apagar_senha(cid)  # antes de remover: a credencial depende do cliente existir
            config.remover_cliente(cid)
        except Erro as e:
            QMessageBox.warning(self, "Remover cliente", e.mensagem)
        self.carregar_lista()

    def _marcar_propria(self, cid, propria):
        dados = dict(config.ler_cliente(cid), senha_propria=propria)
        config.salvar_cliente(dados, cid)

    def _senha_propria(self, cid):
        """Senha so deste cliente, no cofre como tunel-clientes:<id>; a padrao continua valendo para os outros."""
        nome = self.clientes.get(cid, {}).get("nome", cid)
        try:
            ja_era = self.clientes.get(cid, {}).get("senha_propria")
            if not ja_era:
                self._marcar_propria(cid, True)
            if not dialogos.pedir_senha_cliente(self, cid, nome) and not ja_era:
                self._marcar_propria(cid, False)  # cancelou: continua na padrao
                return
        except Erro as e:
            return QMessageBox.warning(self, "Senha própria", e.mensagem)
        self.carregar_lista()
        self.statusBar().showMessage(f"{nome} agora usa senha própria (vale na próxima conexão).", 8000)

    def _senha_padrao(self, cid):
        nome = self.clientes.get(cid, {}).get("nome", cid)
        try:
            config.apagar_senha(cid)  # antes de desmarcar: a credencial depende do flag
            self._marcar_propria(cid, False)
        except Erro as e:
            return QMessageBox.warning(self, "Senha padrão", e.mensagem)
        self.carregar_lista()
        self.statusBar().showMessage(f"{nome} voltou a usar a senha padrão.", 8000)

    def _esquecer_chave(self, cid):
        c = self.clientes.get(cid)
        if not c:
            return
        aviso = (f"Esquecer a chave gravada do servidor {c['host']}:{c['port']}?\n\n"
                 "Faça isso só se o servidor do cliente foi trocado ou reinstalado. "
                 "Na próxima conexão a chave nova será aceita e gravada.")
        if QMessageBox.question(self, "Esquecer chave do servidor", aviso) == QMessageBox.StandardButton.Yes:
            hostkeys.esquecer(c["host"], c["port"])
            self.statusBar().showMessage(f"Chave do servidor de {c['nome']} esquecida.", 8000)

    def configuracoes(self, aviso=None):
        dlg = dialogos.Configuracoes(self, aviso)
        dlg.exec()
        self.carregar_lista()

    # ------------------------------------------------------------ conexao
    def conectar(self, cid):
        if self.ocupado or not cid:
            return
        nome = self.clientes.get(cid, {}).get("nome", cid)
        self.ocupado = True
        self._botoes()
        self.lista.setEnabled(False)
        self.erro_id, self.conectando_id = None, cid
        self._render()
        self._estado(f"◌ Conectando a {nome}…", "neutro")

        def trabalhar():
            try:
                self.gerente.conectar(cid)
                self.sinais.conectado.emit(cid)
            except Erro as e:
                self.sinais.falhou.emit(e, cid)
            except Exception as e:
                log.exception("falha inesperada ao conectar")
                self.sinais.falhou.emit(Erro("erro_interno", f"Erro inesperado: {e}"), cid)

        threading.Thread(target=trabalhar, daemon=True).start()

    def _fim_tentativa(self):
        self.ocupado = False
        self.conectando_id = None
        self.lista.setEnabled(True)
        self._render()

    def _conectado(self, cid):
        c = self.clientes.get(cid, {"nome": cid})
        recentes = [cid, *[x for x in self._recentes() if x != cid]][:5]
        self._guardar_lista("recentes", recentes)
        self.modelo_hist.setStringList(self._lista(f"historico/{cid}"))
        self._sessao_limpa()
        self.setWindowTitle(f"Tunel Clientes — {c['nome']}")
        self._estado(f"● Conectado a {c['nome']} ({c.get('host', '')})", "ok")
        self._fim_tentativa()
        self.endereco.setFocus()

    def _falhou(self, e, cid):
        self.erro_id = cid
        self._fim_tentativa()
        self.setWindowTitle("Tunel Clientes")
        c = self.clientes.get(cid, {"nome": cid, "senha_propria": False})
        self._estado(f"✖ Erro ao conectar a {c['nome']}: {e.mensagem}", "erro")
        if e.codigo == "usuario_nao_definido" or (e.codigo == "senha_nao_cadastrada" and not c.get("senha_propria")):
            self.configuracoes("Cadastre seu login SSH para conectar.")
            if config.tem_senha():
                self.conectar(cid)
        elif e.codigo == "senha_nao_cadastrada":
            if dialogos.pedir_senha_cliente(self, cid, c["nome"]):
                self.conectar(cid)
        elif e.codigo == "hostkey_mudou":
            QMessageBox.critical(
                self, "Chave do servidor mudou",
                f"{e.mensagem}\n\nSe o servidor foi trocado de verdade, use o botão direito no cliente, "
                "Esquecer chave do servidor, e conecte de novo. Se não foi, não conecte.")
        else:
            QMessageBox.warning(self, f"Não foi possível conectar a {c['nome']}", e.mensagem)

    def desconectar(self):
        self.gerente.desconectar()
        self._sessao_limpa()
        self.setWindowTitle("Tunel Clientes")
        self._estado("● Desconectado", "neutro")
        self.modelo_hist.setStringList([])
        self._render()

    def _encerrado(self, cid, motivo):
        nome = self.clientes.get(cid, {}).get("nome", cid)
        self.erro_id = cid
        self._sessao_limpa()
        self.setWindowTitle("Tunel Clientes")
        self._estado(f"✖ Túnel de {nome} {MOTIVOS.get(motivo, 'encerrado')}. Desconectado.", "erro")
        self.modelo_hist.setStringList([])
        self._render()

    def _estado(self, texto, tipo):
        self.estado.setText(texto)
        self.estado.setStyleSheet(f"color: {CORES[tipo]}; font-weight: bold; padding: 0 6px;")

    # ------------------------------------------------------------ abas
    def _sessao_limpa(self):
        """Fecha as abas e troca o perfil: nada de um cliente sobra para o outro."""
        while self.abas.count():
            w = self.abas.widget(0)
            self.abas.removeTab(0)
            getattr(w, "encerrar", lambda: None)()
            w.deleteLater()
        antigo, self.perfil = self.perfil, novo_perfil(self)
        if antigo:
            QTimer.singleShot(3000, antigo.deleteLater)  # depois das paginas
        self.abrir_aba()

    def abrir_aba(self):
        aba = Aba(self.perfil, self.abrir_aba)
        i = self.abas.addTab(aba, "Nova aba")
        aba.titleChanged.connect(lambda t, a=aba: self._titulo(a, t))
        aba.urlChanged.connect(lambda *_: self._sincronizar_endereco())
        aba.loadFinished.connect(lambda ok, a=aba: self._carregou(a, ok))
        aba.alternativa = None  # https a tentar se o http falhar
        self.abas.setCurrentIndex(i)
        return aba

    def _carregou(self, aba, ok):
        if ok:
            self._lembrar_endereco(aba.url())
        alternativa, aba.alternativa = aba.alternativa, None
        if not ok and alternativa:
            self.statusBar().showMessage(f"Sem resposta em http; tentando {alternativa.toString()}", 8000)
            aba.load(alternativa)

    # ------------------------------------------------------------ historico de enderecos por cliente
    def _lembrar_endereco(self, url):
        con = self.gerente.ativa
        try:
            ipaddress.IPv4Address(url.host())
        except ValueError:
            return
        if not con:
            return
        porta = f":{url.port()}" if url.port() != -1 else ""
        self._lembrar(con.id, f"{url.scheme()}://{url.host()}{porta}")

    def _lembrar(self, cid, item):
        chave = f"historico/{cid}"
        hist = [item, *[x for x in self._lista(chave) if x != item]][:30]  # ponytail: 30 por cliente
        self._guardar_lista(chave, hist)
        self.modelo_hist.setStringList(hist)

    def _menu_historico(self, menu):
        menu.clear()
        con = self.gerente.ativa
        if not con:
            menu.addAction("Conecte um cliente para ver o histórico dele").setEnabled(False)
            return
        hist = self._lista(f"historico/{con.id}")
        if not hist:
            menu.addAction(f"Nenhum endereço aberto em {con.nome} ainda").setEnabled(False)
            return
        for h in hist:
            menu.addAction(h, lambda h=h: (self.endereco.setText(h), self.navegar()))
        menu.addSeparator()
        menu.addAction(f"Limpar histórico de {con.nome}", lambda: self._limpar_historico(con.id))

    def _limpar_historico(self, cid):
        self.prefs.remove(f"historico/{cid}")
        self.modelo_hist.setStringList([])

    def _titulo(self, aba, titulo):
        i = self.abas.indexOf(aba)
        if i >= 0:
            self.abas.setTabText(i, (titulo or "Nova aba")[:30])

    def _fechar_aba(self, i):
        w = self.abas.widget(i)
        self.abas.removeTab(i)
        getattr(w, "encerrar", lambda: None)()
        w.deleteLater()
        if not self.abas.count():
            self.abrir_aba()

    def _aba(self):
        return self.abas.currentWidget()

    def _sincronizar_endereco(self):
        aba = self._aba()
        url = getattr(aba, "endereco", None) or (aba.url().toString() if aba else "")
        self.endereco.setText("" if url in ("", "about:blank") else url)

    def navegar(self):
        texto = self.endereco.text().strip()
        if texto.lower().startswith("telnet://"):
            return self.abrir_telnet(texto)
        url = url_do_texto(texto)
        host = url.host()
        try:
            ip = ipaddress.IPv4Address(host)
        except ValueError:
            ip = None
        if ip is None:
            self.statusBar().showMessage("Digite o IP do aparelho. Nomes não passam pelo túnel.", 8000)
        elif not self.gerente.ativa and not self._fora_do_tunel(ip):
            self.statusBar().showMessage("Conecte um cliente antes de abrir um aparelho.", 8000)
            return
        aba = self._aba()
        if not isinstance(aba, Aba):  # aba de terminal: o site abre numa aba nova
            aba = self.abrir_aba()
        # sem http:// ou https:// digitado: tenta http e, se nao responder, https
        aba.alternativa = None
        if "://" not in texto:
            alternativa = url_do_texto(texto)
            alternativa.setScheme("https")
            aba.alternativa = alternativa
        aba.load(url)

    # ------------------------------------------------------------ telnet
    def _pedir_telnet(self):
        texto, ok = QInputDialog.getText(self, "Telnet", "IP do aparelho (porta opcional, padrão 23):",
                                         text="192.168.0.")
        if ok and texto.strip():
            self.abrir_telnet("telnet://" + texto.strip().removeprefix("telnet://"))

    def abrir_telnet(self, texto):
        url = url_do_texto(texto)
        host, porta = url.host(), url.port(23)
        try:
            ip = ipaddress.IPv4Address(host)
        except ValueError:
            return self.statusBar().showMessage("Telnet: digite o IP do aparelho, ex.: telnet://192.168.0.20", 8000)
        direto = self._fora_do_tunel(ip)
        con = self.gerente.ativa
        if not con and not direto:
            return self.statusBar().showMessage("Conecte um cliente antes de abrir um aparelho.", 8000)
        destino = f"telnet://{host}" + (f":{porta}" if porta != 23 else "")

        def abrir():  # roda na thread do terminal
            if direto:  # faixa da VPN: sem tunel
                s = socket.create_connection((host, porta), timeout=15)
                s.settimeout(None)
                return s, lambda: None
            if not con.permitido(host):
                raise Erro("fora_da_rede", "IP fora das redes do cliente conectado.")
            canal = con.abrir_canal(host, porta)
            if canal is None:
                raise Erro("desconectado", "O túnel deste cliente foi fechado.")
            return canal, con.tocar

        aba = AbaTerminal(self.perfil, destino, abrir)
        if con and not direto:
            aba.ponte.conectou.connect(lambda cid=con.id: self._lembrar(cid, destino))
        i = self.abas.addTab(aba, f"Telnet {host}")
        self.abas.setCurrentIndex(i)
        aba.setFocus()

    @staticmethod
    def _fora_do_tunel(ip):
        try:
            excluir = config.carregar()[0]["excluir"]
        except Erro:
            return False
        return any(ip in ipaddress.IPv4Network(r, strict=False) for r in excluir)

    def closeEvent(self, ev):
        self.prefs.setValue("geometria", self.saveGeometry())
        self.gerente.desconectar()
        super().closeEvent(ev)
