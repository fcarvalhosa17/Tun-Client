# Tunel Clientes

Navegador dedicado para abrir aparelhos da rede dos clientes. Você escolhe o cliente, o app abre um túnel SSH até o servidor dele (alcançado pela VPN, faixa `10.255.x.x`) e tudo o que você digitar como IP abre de dentro da rede do cliente.

- Roda em Windows, macOS e Linux, com o mesmo código (Python + Qt WebEngine).
- **Limpo:** sem conta, sincronização, extensões, telemetria, corretor ou pré-carregamento. Nada de histórico, cookie ou cache vai para o disco, e cada conexão começa com uma sessão nova, então nada de um cliente vaza para o outro.
- **Um cliente por vez:** os IPs internos se repetem entre clientes. Conectar outro fecha o túnel atual e as abas.
- **Login SSH de quem usa:** na primeira abertura o app pede o usuário e a senha SSH. Cada pessoa usa o próprio login. A senha fica só no cofre do sistema: Gerenciador de Credenciais (Windows), Chaves (macOS) ou Secret Service/GNOME Keyring/KWallet (Linux).

## Instalar

### Windows

Rode `tunel-clientes-<versão>-windows-setup.exe`. Não pede administrador. Sem assinatura de código, o SmartScreen pode mostrar "Editor desconhecido": clique em **Mais informações** e depois em **Executar assim mesmo**.

### Linux (Debian 12+, Ubuntu 22.04+) e macOS

Use o `tunel-clientes-<versão>-linux-macos.zip`. Ele traz o app e um instalador em Python que monta tudo na própria máquina, só para o seu usuário:

```
unzip tunel-clientes-<versão>-linux-macos.zip
cd tunel-clientes-<versão>
python3 instalar.py
```

- **Linux:**
  - O instalador confere as bibliotecas do sistema que o motor web precisa. Se faltar alguma, ele pergunta antes de instalar com `sudo apt-get`, e para isso pede a sua senha do Linux.
  - O app aparece no menu de aplicativos e também abre pelo comando `tunel-clientes`.
  - Precisa de um cofre de senhas ativo, como GNOME Keyring ou KWallet.
- **macOS:**
  - Precisa do Python 3.9 ou mais novo. Se o `python3` não existir, instale pelo [python.org](https://www.python.org/downloads/macos/).
  - O app é criado em `~/Applications/Tunel Clientes.app` e abre pelo Spotlight.
  - Como é montado na própria máquina, não passa pelo bloqueio do Gatekeeper.
  - Na primeira vez que salvar uma senha, o macOS pergunta se o Python pode usar as Chaves: clique em **Sempre permitir**.
- **Os dois:**
  - A primeira instalação baixa o PySide6 (cerca de 200 MB) e leva alguns minutos.
  - Para atualizar, rode `python3 instalar.py` de novo com o zip novo.
  - Para remover, use `python3 instalar.py --remover`. Clientes, histórico e senhas são mantidos.
- **Ubuntu 23.10 ou mais novo:** o sistema bloqueia o isolamento (sandbox) do Chromium para apps sem perfil próprio de segurança. Nesse caso o app roda o motor web sem esse isolamento. O app só abre os aparelhos dos clientes.

## Usar

1. Na primeira abertura, cadastre o login SSH em **Configurações**.
2. Cadastre os clientes em **Novo cliente**, ou importe a planilha em **Configurações, Importar planilha (CSV)**.
3. Selecione o cliente e clique em **Conectar** (ou dê dois cliques).
4. Digite o IP do aparelho na barra de endereço, por exemplo `192.168.0.10` ou `https://192.168.0.10:8443`.

Com o botão direito num cliente: **Conectar**, **Editar**, **Senha própria**, **Esquecer chave do servidor** e **Remover**.

- **Cores:** cliente conectado em verde (● e negrito), com erro em vermelho (✖), os demais em preto. O rodapé repete o estado da conexão.
- **Histórico:** cada cliente guarda os últimos 30 endereços abertos. Eles aparecem como sugestão ao digitar e no botão **Histórico**, que também limpa a lista do cliente.

### O que vai pelo túnel

- Qualquer IP digitado vai pelo túnel do cliente conectado.
- A faixa da VPN (`10.255.0.0/16`) vai direto, sem túnel.
- Nomes (DNS) não passam pelo túnel: use o IP do aparelho.
- Para limitar um cliente a certas redes, preencha **Redes pelo túnel** no cadastro dele.

### Telnet

- Digite `telnet://192.168.0.20` na barra de endereço, ou use o botão **Telnet…**. A porta padrão é 23; para outra, use `telnet://192.168.0.20:2323`.
- Abre uma aba de terminal (xterm.js, empacotado no app, sem internet) ligada ao aparelho pelo túnel do cliente conectado. Ela aceita cores e menus de tela cheia dos equipamentos, e copiar e colar pelo botão direito.
- O app avisa ao aparelho o tamanho da janela e se apresenta como terminal XTERM.
- Os endereços telnet entram no histórico do cliente, junto com os de web.
- ⟳ reconecta. Fechar a aba, trocar de cliente ou desconectar encerra a sessão.
- Endereços da faixa da VPN (`10.255.x.x`) conectam direto, sem túnel.

### Aparelhos com HTTPS próprio e login

- **Certificado não confiável:** o app pergunta uma vez por aparelho se você quer continuar.
- **Login do próprio aparelho** (janela de usuário e senha do navegador): abre um diálogo. Essa senha não é guardada.
- **Downloads** (backup de configuração, por exemplo): o app pergunta onde salvar.

## Lista de clientes

O arquivo fica na pasta de dados (o caminho aparece em **Configurações**):

| Sistema | Pasta de dados |
|---|---|
| Windows | `%APPDATA%\tunel-clientes` |
| macOS | `~/Library/Application Support/tunel-clientes` |
| Linux | `~/.config/tunel-clientes` |

```json
{
  "defaults": { "user": "seu_usuario", "port": 22, "auth": "senha", "idle_minutes": 30,
                "subnets": ["0.0.0.0/0"], "excluir": ["10.255.0.0/16"] },
  "clientes": [
    { "id": "ufabc", "nome": "UFABC", "host": "10.255.0.1", "tags": ["fone-rnp"] }
  ]
}
```

- Campos ausentes num cliente herdam de `defaults`.
- `excluir` é o que nunca vai pelo túnel. O valor de `defaults.excluir` vale para o navegador a partir da próxima abertura do app.
- `idle_minutes`: o túnel fecha sozinho depois desse tempo sem tráfego. Use 0 para nunca.

### Planilha (CSV)

Colunas: `id,nome,host,port,user,auth,identity_file,subnets,tags`. O separador pode ser `,` ou `;` (o do Excel em português). Dentro de `subnets` e `tags`, separe os valores com `;`. Colunas vazias herdam o padrão. Um id que já existe é atualizado; um id novo é acrescentado.

```
id,nome,host,port,user,auth,identity_file,subnets,tags
ufabc,UFABC,10.255.0.1,,,,,,fone-rnp
```

### Login por cliente

- **Usuário próprio:** preencha **Usuário SSH** no cadastro do cliente.
- **Senha própria:** botão direito no cliente, **Senha própria**, ou no cadastro, marcando **Este cliente usa senha própria**. A senha padrão continua valendo para os outros clientes. **Voltar à senha padrão** apaga a senha própria. Ela fica no cofre como `tunel-clientes:<id>`. Se você trocar o id, cadastre a senha de novo.
- **Chave SSH:** escolha **Chave SSH** em Autenticação e informe o arquivo. Sem arquivo, o app tenta o ssh-agent e as chaves padrão em `~/.ssh`. Chave com passphrase não é suportada.

## Segurança

- A chave do servidor é gravada na primeira conexão (`known_hosts` na pasta de dados) e conferida antes de a senha ser enviada. Se ela mudar, o app recusa e mostra os dois fingerprints.
- O túnel aceita conexões só do próprio computador (127.0.0.1), numa porta aleatória a cada abertura, e só para IPs dentro das redes do cliente conectado.
- O log (`app.log` na pasta de dados) não guarda senha nem conteúdo de tráfego.

## Problemas comuns

- **Autenticação recusada:** o usuário ou a senha está errado. Corrija em **Configurações**, ou no cliente, se ele tiver login próprio.
- **Chave do servidor mudou:** confirme com o cliente que o servidor foi trocado. Se foi, use **Esquecer chave do servidor** e conecte de novo. Se não foi, não conecte.
- **Página não abre:** confira se o cliente está conectado (aparece em negrito com ●) e se você digitou um IP, não um nome.
- **Linux sem cofre de senhas:** instale ou ative o GNOME Keyring ou o KWallet.

## Gerar os instaladores

```
python build.py
```

- **No Windows**, gera os dois arquivos. Precisa do Inno Setup 6 (`winget install --id JRSoftware.InnoSetup -e --scope user`).
  - `dist/tunel-clientes-<versão>-windows-setup.exe`
  - `dist/tunel-clientes-<versão>-linux-macos.zip`
- **Em qualquer sistema**, `python build.py --so-zip` gera só o zip de Linux e macOS.

A versão fica em `build.py` e em `instalar.py`.

## Estrutura

```
app/
  main.py        partida: SOCKS local + motor web apontado para ele
  janela.py      lista de clientes, abas e barra de endereço
  navegador.py   perfil limpo, certificado, login dos aparelhos, downloads
  terminal.py    aba de terminal telnet (xterm.js via QWebChannel)
  telnet.py      negociação telnet (python telnet.py roda a verificação)
  xterm/         xterm.js 5.5 (licença MIT) e a página do terminal
  dialogos.py    Configurações (login SSH, importar CSV) e cadastro de cliente
  tunel.py       túnel SSH (paramiko) e SOCKS5 local
  hostkeys.py    known_hosts próprio
  config.py      clientes.json, pasta de dados por sistema, cofre de senhas
build.py         setup do Windows (PyInstaller + Inno) e zip de Linux/macOS
instalar.py      instalador de Linux e macOS (só biblioteca padrão)
installer/windows.iss
```
