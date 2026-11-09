"""Gera o app e o pacote do sistema em que roda (rode em cada sistema). Uso: python build.py

Windows       -> dist/tunel-clientes-<versao>-windows-setup.exe  (rodando no Windows; precisa do Inno Setup 6)
Linux e macOS -> dist/tunel-clientes-<versao>-linux-macos.zip    (em qualquer sistema; dentro, o instalar.py
                 instala o app na propria maquina). So o zip: python build.py --so-zip
"""
import os
import shutil
import subprocess
import sys

VERSAO = "2.0.1"
NOME = "Tunel Clientes"
RAIZ = os.path.dirname(os.path.abspath(__file__))
APP, DIST, BUILD = (os.path.join(RAIZ, p) for p in ("app", "dist", "build"))


def rodar(*cmd):
    print(">", " ".join(cmd))
    subprocess.run(cmd, check=True)


def pyinstaller():
    rodar(sys.executable, "-m", "pip", "install", "-r", os.path.join(RAIZ, "requirements.txt"), "pyinstaller", "pillow")
    args = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--name", NOME,
        "--distpath", DIST, "--workpath", BUILD, "--specpath", BUILD, "--paths", APP,
        "--icon", os.path.join(APP, "icone.png"),  # pillow converte para .ico/.icns
        "--add-data", f"{os.path.join(APP, 'icone.png')}{os.pathsep}.",
        "--add-data", f"{os.path.join(APP, 'xterm')}{os.pathsep}xterm",  # terminal telnet, sem internet
        "--collect-submodules", "keyring.backends", "--copy-metadata", "keyring",
    ]
    rodar(*args, os.path.join(APP, "main.py"))


def enxugar():
    """Tira do pacote o que o app nao usa: simbolos de depuracao, QML e idiomas alem de pt-BR/en-US."""
    for pasta, dirs, arquivos in os.walk(DIST):
        if os.path.basename(pasta) == "PySide6" and "qml" in dirs:
            shutil.rmtree(os.path.join(pasta, "qml"))
            dirs.remove("qml")
        nome_pasta = os.path.basename(pasta)
        for a in arquivos:
            apagar = (
                ".debug." in a
                or (nome_pasta == "qtwebengine_locales" and a not in ("pt-BR.pak", "en-US.pak"))
                or (nome_pasta == "translations" and a.endswith(".qm") and "pt_BR" not in a)
            )
            if apagar:
                os.remove(os.path.join(pasta, a))


def pacote_windows():
    iscc = next((p for p in (
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"),
        os.path.expandvars(r"%ProgramFiles%\Inno Setup 6\ISCC.exe"),
    ) if os.path.isfile(p)), None)
    if not iscc:
        sys.exit("Inno Setup 6 não encontrado. Instale: winget install --id JRSoftware.InnoSetup -e --scope user")
    rodar(iscc, f"/DVersao={VERSAO}", os.path.join(RAIZ, "installer", "windows.iss"))


def pacote_linux_mac():
    """Zip com o codigo e o instalar.py: instala no proprio Linux (Debian/Ubuntu) ou Mac, sem compilar."""
    import zipfile
    destino = os.path.join(DIST, f"tunel-clientes-{VERSAO}-linux-macos.zip")
    os.makedirs(DIST, exist_ok=True)
    pasta = f"tunel-clientes-{VERSAO}"
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for nome in ("instalar.py", "requirements.txt", "README.md"):
            z.write(os.path.join(RAIZ, nome), f"{pasta}/{nome}")
        for raiz, dirs, arquivos in os.walk(APP):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for a in arquivos:
                caminho = os.path.join(raiz, a)
                z.write(caminho, f"{pasta}/{os.path.relpath(caminho, RAIZ)}".replace(os.sep, "/"))
    print("Gerado:", destino)


if __name__ == "__main__":
    if sys.platform == "win32" and "--so-zip" not in sys.argv:
        pyinstaller()
        enxugar()
        pacote_windows()
    pacote_linux_mac()
    print("Pronto. Veja a pasta dist/.")
