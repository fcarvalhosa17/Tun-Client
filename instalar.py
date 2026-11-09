#!/usr/bin/env python3
"""Instala o Tunel Clientes no Linux (Debian/Ubuntu) ou no macOS, so para o usuario atual.

Uso, dentro da pasta descompactada:
    python3 instalar.py            instala ou atualiza
    python3 instalar.py --remover  remove o app (mantem clientes, historico e senhas)

So usa a biblioteca padrao. Cria um ambiente Python proprio (venv) com o PySide6, o paramiko e o keyring,
e o atalho do sistema: menu de aplicativos no Linux, "Tunel Clientes.app" em ~/Applications no Mac.
"""
import os
import shutil
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
MAC = sys.platform == "darwin"
CASA = os.path.expanduser("~")
if MAC:
    BASE = os.path.join(CASA, "Library", "Application Support", "tunel-clientes-app")
    BUNDLE = os.path.join(CASA, "Applications", "Tunel Clientes.app")
else:
    BASE = os.path.join(CASA, ".local", "share", "tunel-clientes-app")
    ATALHO = os.path.join(CASA, ".local", "share", "applications", "tunel-clientes.desktop")
    COMANDO = os.path.join(CASA, ".local", "bin", "tunel-clientes")
PYTHON = os.path.join(BASE, "venv", "bin", "python")

# bibliotecas do sistema que o Qt (xcb) e o Chromium do Qt WebEngine precisam no Debian/Ubuntu
LIBS_DEBIAN = [
    "libxcb-cursor0", "libxkbcommon-x11-0", "libxcb-icccm4", "libxcb-image0", "libxcb-keysyms1",
    "libxcb-randr0", "libxcb-render-util0", "libxcb-shape0", "libxcb-xkb1", "libnss3", "libxcomposite1",
    "libxdamage1", "libxrandr2", "libxtst6", "libxkbfile1", "libgbm1", "libegl1", "libfontconfig1",
    "libdbus-1-3", "gnome-keyring",
]


def falar(msg):
    print(f"\n==> {msg}", flush=True)


def sair(msg):
    print(f"\nERRO: {msg}", file=sys.stderr)
    sys.exit(1)


def rodar(*cmd):
    subprocess.run(cmd, check=True)


def perguntar(texto):
    try:
        return input(f"{texto} [S/n] ").strip().lower() in ("", "s", "sim", "y")
    except EOFError:
        return False


# ---------------------------------------------------------------- Linux: dependencias do sistema

def _instalado(pacote):
    r = subprocess.run(["dpkg-query", "-W", "-f=${Status}", pacote], capture_output=True, text=True)
    return r.returncode == 0 and "install ok installed" in r.stdout


def _existe_no_apt(pacote):
    return subprocess.run(["apt-cache", "show", pacote], capture_output=True).returncode == 0


def dependencias_linux():
    if not shutil.which("dpkg-query"):
        print("Sistema sem dpkg (não é Debian/Ubuntu): instale por conta própria as bibliotecas do Qt WebEngine.")
        return
    faltam = [p for p in LIBS_DEBIAN if not _instalado(p)]
    if not (_instalado("libasound2") or _instalado("libasound2t64")):  # Ubuntu 24.04 trocou o nome
        faltam.append("libasound2t64" if _existe_no_apt("libasound2t64") else "libasound2")
    try:
        import ensurepip  # noqa: F401  (sem ele o venv nao funciona: pacote python3-venv)
    except ImportError:
        faltam.append(f"python3.{sys.version_info.minor}-venv")
    if not faltam:
        return
    falar("Faltam pacotes do sistema: " + " ".join(faltam))
    if not perguntar("Instalar agora com 'sudo apt-get install'? (pede a sua senha do Linux)"):
        sair("Instale os pacotes acima e rode o instalador de novo.")
    rodar("sudo", "apt-get", "update")
    rodar("sudo", "apt-get", "install", "-y", *faltam)


# ---------------------------------------------------------------- app + ambiente Python

def copiar_app():
    falar(f"Copiando o app para {BASE}")
    os.makedirs(BASE, exist_ok=True)
    destino = os.path.join(BASE, "app")
    shutil.rmtree(destino, ignore_errors=True)
    shutil.copytree(os.path.join(AQUI, "app"), destino, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(os.path.join(AQUI, "requirements.txt"), BASE)


def ambiente():
    if not os.path.exists(PYTHON):
        falar("Criando o ambiente Python (venv)")
        try:
            rodar(sys.executable, "-m", "venv", os.path.join(BASE, "venv"))
        except subprocess.CalledProcessError:
            sair("Não foi possível criar o venv. No Debian/Ubuntu: sudo apt install python3-venv")
    falar("Instalando PySide6, paramiko e keyring (alguns minutos na primeira vez)")
    rodar(PYTHON, "-m", "pip", "install", "--upgrade", "--quiet", "pip")
    rodar(PYTHON, "-m", "pip", "install", "--upgrade", "-r", os.path.join(BASE, "requirements.txt"))


# ---------------------------------------------------------------- atalhos

def _gravar(caminho, conteudo, executavel=False):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="\n") as f:
        f.write(conteudo)
    if executavel:
        os.chmod(caminho, 0o755)


def atalho_linux():
    falar("Criando o atalho no menu de aplicativos e o comando tunel-clientes")
    main = os.path.join(BASE, "app", "main.py")
    _gravar(COMANDO, f"""#!/bin/sh
# Ubuntu 23.10+ bloqueia o sandbox do Chromium para apps sem perfil AppArmor proprio;
# nesse caso o motor web roda sem ele (o app so abre os aparelhos dos clientes).
if [ "$(cat /proc/sys/kernel/apparmor_restrict_unprivileged_userns 2>/dev/null)" = "1" ]; then
  export QTWEBENGINE_DISABLE_SANDBOX=1
fi
exec "{PYTHON}" "{main}" "$@"
""", executavel=True)
    _gravar(ATALHO, f"""[Desktop Entry]
Type=Application
Name=Tunel Clientes
Comment=Acesso aos aparelhos dos clientes por túnel SSH
Exec="{COMANDO}"
Icon={os.path.join(BASE, "app", "icone.png")}
Terminal=false
Categories=Network;
StartupWMClass=Tunel Clientes
""")
    if shutil.which("update-desktop-database"):
        subprocess.run(["update-desktop-database", os.path.dirname(ATALHO)], capture_output=True)


def atalho_mac():
    falar(f"Criando {BUNDLE}")
    shutil.rmtree(BUNDLE, ignore_errors=True)
    conteudo = os.path.join(BUNDLE, "Contents")
    _gravar(os.path.join(conteudo, "MacOS", "tunel-clientes"),
            f'#!/bin/sh\nexec "{PYTHON}" "{os.path.join(BASE, "app", "main.py")}" "$@"\n', executavel=True)
    _gravar(os.path.join(conteudo, "Info.plist"), """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Tunel Clientes</string>
  <key>CFBundleDisplayName</key><string>Tunel Clientes</string>
  <key>CFBundleIdentifier</key><string>br.com.cam.tunelclientes</string>
  <key>CFBundleExecutable</key><string>tunel-clientes</string>
  <key>CFBundleIconFile</key><string>icone</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>2.0.2</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
""")
    recursos = os.path.join(conteudo, "Resources")
    os.makedirs(recursos, exist_ok=True)
    # ponytail: icone 128 px convertido pelo sips (vem no macOS); sem ele o app fica com o icone padrao
    try:
        subprocess.run(["sips", "-s", "format", "icns", os.path.join(BASE, "app", "icone.png"),
                        "--out", os.path.join(recursos, "icone.icns")], capture_output=True)
    except OSError:
        pass


# ---------------------------------------------------------------- remover

def remover():
    alvos = [BASE, BUNDLE] if MAC else [BASE, ATALHO, COMANDO]
    for alvo in alvos:
        if os.path.isdir(alvo):
            shutil.rmtree(alvo)
        elif os.path.exists(alvo):
            os.remove(alvo)
    dados = "~/Library/Application Support/tunel-clientes" if MAC else "~/.config/tunel-clientes"
    print(f"Tunel Clientes removido. Clientes e histórico continuam em {dados}; "
          "as senhas continuam no cofre do sistema (apague por lá se quiser).")


def main():
    if sys.platform not in ("darwin", "linux"):
        sair("Este instalador é para Linux e macOS. No Windows use o setup .exe.")
    if sys.version_info < (3, 9):
        sair("Precisa do Python 3.9 ou mais novo. "
             + ("No Mac: instale pelo python.org." if MAC else "No Linux: sudo apt install python3"))
    if "--remover" in sys.argv:
        return remover()
    if not MAC:
        dependencias_linux()
    copiar_app()
    ambiente()
    atalho_mac() if MAC else atalho_linux()
    if MAC:
        falar("Pronto. Abra 'Tunel Clientes' em Aplicativos (pasta ~/Applications) ou pelo Spotlight.")
    else:
        falar("Pronto. Abra 'Tunel Clientes' no menu de aplicativos ou rode: tunel-clientes")
        if os.path.dirname(COMANDO) not in os.environ.get("PATH", "").split(os.pathsep):
            print("(o comando tunel-clientes funciona depois de sair e entrar de novo na sessão)")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        sair(f"o comando {' '.join(map(str, e.cmd))} falhou (código {e.returncode}).")
    except KeyboardInterrupt:
        sair("cancelado.")
