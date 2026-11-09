"""Navegador limpo: perfil sem gravacao em disco, sem corretor, sem pre-carregamento.
Um perfil novo a cada cliente conectado: cookies, cache, logins e certificados aceitos de um
cliente nunca vazam para outro (os IPs internos se repetem entre clientes)."""
import os

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QLabel, QLineEdit,
                               QMessageBox)


def novo_perfil(pai):
    perfil = QWebEngineProfile(pai)  # sem nome = fora do registro: nada vai para o disco
    perfil.setSpellCheckEnabled(False)
    perfil.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
    perfil.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
    s = perfil.settings()
    s.setAttribute(QWebEngineSettings.WebAttribute.DnsPrefetchEnabled, False)
    s.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, False)
    s.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
    perfil.aceitos = set()  # (host, porta) com certificado aceito pelo usuario nesta conexao
    perfil.downloadRequested.connect(_baixar)
    return perfil


def _baixar(download):
    destino, _ = QFileDialog.getSaveFileName(
        None, "Salvar arquivo", os.path.join(download.downloadDirectory(), download.downloadFileName()))
    if not destino:
        download.cancel()
        return
    download.setDownloadDirectory(os.path.dirname(destino))
    download.setDownloadFileName(os.path.basename(destino))
    download.accept()


class Pagina(QWebEnginePage):
    def __init__(self, perfil, aba):
        super().__init__(perfil, aba)
        self._aba = aba
        self.certificateError.connect(self._certificado)
        self.authenticationRequired.connect(self._login)

    # aparelhos costumam usar HTTPS com certificado proprio: pergunta uma vez por aparelho
    def _certificado(self, erro):
        url = erro.url()
        chave = (url.host(), url.port(443))
        if chave in self.profile().aceitos:
            erro.acceptCertificate()
            return
        if not erro.isOverridable():
            erro.rejectCertificate()
            return
        erro.defer()
        QTimer.singleShot(0, lambda e=erro, k=chave: self._perguntar_certificado(e, k))

    def _perguntar_certificado(self, erro, chave):
        r = QMessageBox.warning(
            self._aba, "Certificado não confiável",
            f"O aparelho {chave[0]}:{chave[1]} apresentou um certificado não confiável:\n\n"
            f"{erro.description()}\n\nIsso é comum em equipamentos com HTTPS próprio. "
            "Continuar mesmo assim?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if r == QMessageBox.StandardButton.Yes:
            self.profile().aceitos.add(chave)
            erro.acceptCertificate()
        else:
            erro.rejectCertificate()

    # janela de login do proprio aparelho (autenticacao basica/digest)
    def _login(self, url, autenticador):
        dlg = QDialog(self._aba)
        dlg.setWindowTitle("Login do aparelho")
        form = QFormLayout(dlg)
        form.addRow(QLabel(f"{url.host()} pede usuário e senha.\n{autenticador.realm()}"))
        usuario, senha = QLineEdit(), QLineEdit()
        senha.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Usuário", usuario)
        form.addRow("Senha", senha)
        botoes = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botoes.accepted.connect(dlg.accept)
        botoes.rejected.connect(dlg.reject)
        form.addRow(botoes)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            autenticador.setUser(usuario.text())
            autenticador.setPassword(senha.text())
        # sem preencher, o QtWebEngine cancela o pedido

    # link que abre janela nova vira aba nova
    def createWindow(self, _tipo):
        return self._aba.abrir_aba().page()


class Aba(QWebEngineView):
    def __init__(self, perfil, abrir_aba):
        super().__init__()
        self.abrir_aba = abrir_aba
        self.setPage(Pagina(perfil, self))


def url_do_texto(texto):
    """'192.168.0.10' -> http://192.168.0.10 ; aceita esquema, porta e caminho."""
    texto = texto.strip()
    if "://" not in texto:
        texto = "http://" + texto
    return QUrl(texto)
