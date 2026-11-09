"""Negociacao telnet minima (RFC 854/855): separa os dados dos comandos IAC e responde as opcoes.
Aceita do servidor ECHO e SUPPRESS-GO-AHEAD; oferece tamanho da janela (NAWS) e tipo de terminal
(XTERM); recusa o resto. Sem Qt aqui: so bytes."""

IAC, DONT, DO, WONT, WILL, SB, SE = 255, 254, 253, 252, 251, 250, 240
ECHO, SGA, TTYPE, NAWS = 1, 3, 24, 31
MAX_PENDENTE = 4096  # subnegociacao sem fim nao cresce para sempre


class Protocolo:
    def __init__(self, enviar):
        """enviar(bytes): manda as respostas da negociacao ao servidor."""
        self._enviar = enviar
        self._resto = b""
        self._naws = False
        self.tamanho = (80, 24)

    def receber(self, dados):
        """Bytes do servidor -> bytes para mostrar (comandos removidos e respondidos)."""
        buf, self._resto = self._resto + dados, b""
        saida = bytearray()
        i = 0
        while i < len(buf):
            b = buf[i]
            if b != IAC:
                saida.append(b)
                i += 1
                continue
            if i + 1 >= len(buf):
                break
            cmd = buf[i + 1]
            if cmd == IAC:
                saida.append(IAC)
                i += 2
            elif cmd in (DO, DONT, WILL, WONT):
                if i + 2 >= len(buf):
                    break
                self._opcao(cmd, buf[i + 2])
                i += 3
            elif cmd == SB:
                fim = buf.find(bytes([IAC, SE]), i + 2)
                if fim < 0:
                    break
                self._sub(buf[i + 2:fim])
                i = fim + 2
            else:  # NOP, GA, AYT...: ignora
                i += 2
        self._resto = buf[i:] if len(buf) - i <= MAX_PENDENTE else b""
        return bytes(saida)

    def _opcao(self, cmd, opt):
        if cmd == DO:
            if opt == NAWS:
                self._enviar(bytes([IAC, WILL, NAWS]))
                self._naws = True
                self._mandar_tamanho()
            elif opt == TTYPE:
                self._enviar(bytes([IAC, WILL, TTYPE]))
            else:
                self._enviar(bytes([IAC, WONT, opt]))
        elif cmd == WILL:
            self._enviar(bytes([IAC, DO if opt in (ECHO, SGA) else DONT, opt]))
        # DONT/WONT: nada a fazer (ja nao usamos a opcao)

    def _sub(self, dados):
        if dados[:2] == bytes([TTYPE, 1]):  # SEND
            self._enviar(bytes([IAC, SB, TTYPE, 0]) + b"XTERM" + bytes([IAC, SE]))

    def redimensionar(self, colunas, linhas):
        self.tamanho = (colunas, linhas)
        if self._naws:
            self._mandar_tamanho()

    def _mandar_tamanho(self):
        c, l = self.tamanho
        corpo = bytes([c >> 8 & 255, c & 255, l >> 8 & 255, l & 255]).replace(b"\xff", b"\xff\xff")
        self._enviar(bytes([IAC, SB, NAWS]) + corpo + bytes([IAC, SE]))

    @staticmethod
    def preparar(texto):
        """Teclado -> bytes para o servidor: Enter vira CR LF (como o PuTTY) e 0xFF e escapado."""
        texto = texto.replace("\r\n", "\r").replace("\r", "\r\n")
        return texto.encode("utf-8").replace(b"\xff", b"\xff\xff")


if __name__ == "__main__":
    # verificacao rapida: python telnet.py
    enviados = []
    p = Protocolo(enviados.append)
    assert p.receber(b"login:" + bytes([IAC, DO, NAWS, IAC, WILL, ECHO, IAC])) == b"login:"
    assert bytes([IAC, WILL, NAWS]) in enviados and bytes([IAC, DO, ECHO]) in enviados
    assert p.receber(bytes([DO, 99]) + b"x") == b"x"  # IAC partido entre dois pacotes
    assert enviados[-1] == bytes([IAC, WONT, 99])
    assert p.receber(bytes([IAC, SB, TTYPE, 1, IAC, SE, IAC, IAC])) == b"\xff"
    assert enviados[-1].endswith(b"XTERM" + bytes([IAC, SE]))
    assert Protocolo.preparar("ls\r") == b"ls\r\n"
    print("ok")
