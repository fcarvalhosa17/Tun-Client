#!/bin/sh
# Instala (ou atualiza) o Tunel Clientes no Linux (Debian/Ubuntu) ou no macOS com um comando:
#   Linux: wget -qO- https://raw.githubusercontent.com/fcarvalhosa17/Tun-Client/main/instalar.sh | sh
#   Mac:   curl -fsSL https://raw.githubusercontent.com/fcarvalhosa17/Tun-Client/main/instalar.sh | sh
# Para remover, acrescente:  | sh -s -- --remover
set -e
VERSAO=2.0.1
URL="https://github.com/fcarvalhosa17/Tun-Client/releases/download/v$VERSAO/tunel-clientes-$VERSAO-linux-macos.zip"

if ! command -v python3 >/dev/null 2>&1; then
  if [ "$(uname)" = Darwin ]; then
    echo "Falta o Python 3. Instale em https://www.python.org/downloads/macos/ e rode este comando de novo."
  else
    echo "Falta o Python 3. Rode: sudo apt install python3   e depois este comando de novo."
  fi
  exit 1
fi

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
echo "Baixando o Tunel Clientes $VERSAO..."
if command -v curl >/dev/null 2>&1; then
  curl -fsSL "$URL" -o "$TMP/app.zip"
else
  wget -q "$URL" -O "$TMP/app.zip"
fi
python3 -m zipfile -e "$TMP/app.zip" "$TMP"
cd "$TMP/tunel-clientes-$VERSAO"
# o script chega pelo pipe: as perguntas do instalador leem do teclado (se houver um terminal)
if ( : < /dev/tty ) 2>/dev/null; then
  python3 instalar.py "$@" < /dev/tty
else
  python3 instalar.py "$@"
fi
