"""Configuracoes (login SSH padrao, importar planilha) e cadastro de cliente.
Senhas: so passam do campo para o cofre do sistema; o campo e limpo em seguida."""
import re

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
                               QPushButton, QVBoxLayout)

import config
from config import Erro


def _senha():
    campo = QLineEdit()
    campo.setEchoMode(QLineEdit.EchoMode.Password)
    return campo


def _erro(pai, e):
    QMessageBox.warning(pai, "Tunel Clientes", e.mensagem if isinstance(e, Erro) else str(e))


class Configuracoes(QDialog):
    def __init__(self, pai, aviso=None):
        super().__init__(pai)
        self.setWindowTitle("Configurações")
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        if aviso:
            rotulo = QLabel(aviso)
            rotulo.setWordWrap(True)
            layout.addWidget(rotulo)

        grupo = QGroupBox("Login SSH padrão (usado por todos os clientes sem login próprio)")
        form = QFormLayout(grupo)
        self.usuario = QLineEdit(config.usuario_padrao() or "")
        self.usuario.setPlaceholderText("seu usuário SSH")
        self.senha = _senha()
        self.senha.setPlaceholderText("deixe vazio para manter a atual")
        self.estado = QLabel()
        form.addRow("Usuário", self.usuario)
        form.addRow("Senha", self.senha)
        form.addRow("", self.estado)
        linha = QHBoxLayout()
        salvar, apagar = QPushButton("Salvar login"), QPushButton("Apagar senha")
        salvar.setDefault(True)
        salvar.clicked.connect(self._salvar)
        apagar.clicked.connect(self._apagar)
        linha.addStretch()
        linha.addWidget(apagar)
        linha.addWidget(salvar)
        form.addRow(linha)
        layout.addWidget(grupo)

        grupo = QGroupBox("Clientes")
        caixa = QVBoxLayout(grupo)
        dica = QLabel("Importe uma planilha CSV com as colunas id, nome, host, port, user, auth, "
                      "identity_file, subnets, tags (subnets e tags separadas por ;). Mesmo id atualiza.")
        dica.setWordWrap(True)
        importar = QPushButton("Importar planilha (CSV)…")
        importar.clicked.connect(self._importar)
        caixa.addWidget(dica)
        caixa.addWidget(importar)
        caixa.addWidget(QLabel(f"Pasta de dados: {config.dados_dir()}"))
        layout.addWidget(grupo)

        fechar = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        fechar.rejected.connect(self.accept)
        layout.addWidget(fechar)
        self.importou = False
        self._atualizar()

    def _atualizar(self):
        u = config.usuario_padrao()
        if not u:
            self.estado.setText("Nenhum usuário definido.")
        else:
            self.estado.setText(f"Senha cadastrada para {u}: {'sim' if config.tem_senha() else 'não'}")

    def _salvar(self):
        try:
            novo = self.usuario.text().strip()
            mudou = novo != (config.usuario_padrao() or "")
            if mudou and not self.senha.text():
                raise Erro("senha_vazia", "Usuário novo: digite também a senha dele.")
            config.definir_usuario_padrao(novo)
            if self.senha.text():
                config.salvar_senha(None, self.senha.text())
        except Exception as e:
            _erro(self, e)
        finally:
            self.senha.clear()
            self._atualizar()

    def _apagar(self):
        config.apagar_senha(None)
        self._atualizar()

    def _importar(self):
        caminho, _ = QFileDialog.getOpenFileName(self, "Importar planilha", "", "CSV (*.csv);;Todos (*)")
        if not caminho:
            return
        try:
            novos, atualizados = config.importar_csv(caminho)
        except Exception as e:
            return _erro(self, e)
        self.importou = True
        QMessageBox.information(self, "Importar planilha", f"{novos} cliente(s) novo(s), {atualizados} atualizado(s).")


class Cliente(QDialog):
    """Novo (cid=None) ou edicao. Campo vazio herda o padrao."""

    def __init__(self, pai, cid=None):
        super().__init__(pai)
        self.cid_original = cid
        self.setWindowTitle("Editar cliente" if cid else "Novo cliente")
        self.setMinimumWidth(480)
        d = config.ler_cliente(cid) if cid else {}
        form = QFormLayout(self)
        self.campos = {}
        for chave, rotulo, dica in (
            ("id", "Id", "curto, sem espaços, ex.: ufabc"),
            ("nome", "Nome", ""),
            ("host", "Endereço do servidor", "10.255.0.1"),
            ("port", "Porta SSH", "padrão: 22"),
            ("user", "Usuário SSH", f"padrão: {config.usuario_padrao() or '(não definido)'}"),
            ("identity_file", "Arquivo da chave", "opcional, só para autenticação por chave"),
        ):
            campo = QLineEdit(str(d.get(chave) or ""))
            campo.setPlaceholderText(dica)
            form.addRow(rotulo, campo)
            self.campos[chave] = campo
        self.auth = QComboBox()
        for texto, valor in (("Padrão (senha)", ""), ("Senha", "senha"), ("Chave SSH", "chave")):
            self.auth.addItem(texto, valor)
        self.auth.setCurrentIndex(max(0, self.auth.findData(d.get("auth") or "")))
        form.insertRow(5, "Autenticação", self.auth)
        self.subnets = QPlainTextEdit("\n".join(d.get("subnets") or []))
        self.subnets.setPlaceholderText("Vazio = qualquer IP. Uma rede por linha, ex.: 192.168.10.0/24")
        self.subnets.setFixedHeight(60)
        form.addRow("Redes pelo túnel", self.subnets)
        self.tags = QLineEdit(", ".join(d.get("tags") or []))
        self.tags.setPlaceholderText("separadas por vírgula")
        form.addRow("Tags", self.tags)
        self.propria = QCheckBox("Este cliente usa senha própria (não a padrão)")
        self.propria.setChecked(d.get("senha_propria") is True)
        form.addRow("", self.propria)
        self.senha = _senha()
        self.senha.setPlaceholderText("senha deste cliente (vazio = manter)")
        self.senha.setEnabled(self.propria.isChecked())
        self.propria.toggled.connect(self.senha.setEnabled)
        form.addRow("Senha própria", self.senha)
        botoes = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        botoes.accepted.connect(self._salvar)
        botoes.rejected.connect(self.reject)
        form.addRow(botoes)
        self.cid = None

    def _salvar(self):
        lista = lambda s: [x.strip() for x in re.split(r"[\n;,]+", s) if x.strip()]
        dados = {k: c.text() for k, c in self.campos.items()}
        dados.update(auth=self.auth.currentData(), senha_propria=self.propria.isChecked(),
                     subnets=lista(self.subnets.toPlainText()), tags=lista(self.tags.text()))
        try:
            self.cid = config.salvar_cliente(dados, self.cid_original)
            if self.propria.isChecked() and self.senha.text():
                config.salvar_senha(self.cid, self.senha.text())
        except Exception as e:
            return _erro(self, e)
        finally:
            self.senha.clear()
        self.accept()


def pedir_senha_cliente(pai, cid, nome):
    """Para cliente com senha propria que ainda nao tem senha cadastrada. -> True se salvou."""
    dlg = QDialog(pai)
    dlg.setWindowTitle(f"Senha de {nome}")
    form = QFormLayout(dlg)
    campo = _senha()
    form.addRow(QLabel(f"{nome} usa senha própria. Digite a senha SSH deste cliente."))
    form.addRow("Senha", campo)
    botoes = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
    botoes.accepted.connect(dlg.accept)
    botoes.rejected.connect(dlg.reject)
    form.addRow(botoes)
    ok = dlg.exec() == QDialog.DialogCode.Accepted and campo.text()
    try:
        if ok:
            config.salvar_senha(cid, campo.text())
    except Exception as e:
        _erro(pai, e)
        ok = False
    finally:
        campo.clear()
    return bool(ok)
