"""Tunel Clientes: navegador dedicado que abre aparelhos da rede do cliente por um tunel SSH."""
import logging
import logging.handlers
import os
import sys

import config
import tunel


def _iniciar_log():
    h = logging.handlers.RotatingFileHandler(
        os.path.join(config.dados_dir(), "app.log"), maxBytes=512 * 1024, backupCount=3, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[h])
    logging.getLogger("paramiko").setLevel(logging.WARNING)


def _recurso(nome):
    return os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), nome)


def main():
    _iniciar_log()
    gerente = tunel.Gerente()  # sobe o SOCKS antes do motor web, que le o proxy so na partida
    try:
        excluir = config.carregar()[0]["excluir"]
    except config.Erro:
        excluir = config.DEFAULTS_PADRAO["excluir"]
    # tudo que o app abre vai pelo SOCKS, menos a faixa da VPN (direto). Sem servicos em segundo plano.
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join([
        f"--proxy-server=socks5://127.0.0.1:{gerente.socks.porta}",
        "--proxy-bypass-list=" + ";".join(excluir),
        "--disable-background-networking",
        "--no-pings",
    ])

    from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from janela import Janela

    app = QApplication(sys.argv)
    # botoes padrao do Qt (Salvar, Cancelar, Sim, Nao...) em portugues
    traducao = QTranslator(app)
    if traducao.load(QLocale("pt_BR"), "qtbase", "_", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(traducao)
    app.setApplicationName("Tunel Clientes")
    app.setDesktopFileName("tunel-clientes")  # Linux: liga a janela ao atalho (icone certo na barra)
    app.setWindowIcon(QIcon(_recurso("icone.png")))
    janela = Janela(gerente)
    janela.show()
    if not config.usuario_padrao() or not config.tem_senha():
        janela.configuracoes("Bem-vindo. Cadastre seu login SSH (usuário e senha) para conectar aos clientes. "
                             "A senha fica só no cofre de senhas do sistema.")
    codigo = app.exec()
    gerente.desconectar()
    sys.exit(codigo)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.getLogger("app").exception("falha fatal")
        raise
