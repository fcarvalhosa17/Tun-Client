# Manual de instalação do Tunel Clientes

Este manual mostra, passo a passo, como instalar o Tunel Clientes e usá-lo pela primeira vez. Vá direto ao seu sistema:

- [Windows](#windows) (5 passos)
- [Ubuntu e Debian](#ubuntu-e-debian) (1 comando)
- [macOS](#macos) (2 comandos)
- [Primeiro uso](#primeiro-uso) (vale para todos)
- [Atualizar e remover](#atualizar-e-remover)
- [Problemas comuns](#problemas-comuns)

## Antes de começar

Você precisa de:

1. **Seu login SSH**, ou seja, o usuário e a senha que a equipe usa para entrar nos servidores dos clientes.
2. **A VPN conectada**, para o computador alcançar os servidores dos clientes (endereços `10.255.x.x`).
3. Um destes sistemas:
   - Windows 10 ou 11
   - Ubuntu 22.04 ou mais novo, ou Debian 12 ou mais novo
   - macOS 12 (Monterey) ou mais novo, em Mac Intel ou Apple Silicon (M1, M2, M3...)

Não é preciso ser administrador do computador: o app é instalado só para o seu usuário.

---

## Windows

### Passo 1: baixar

Clique para baixar: **[instalador do Windows](https://github.com/fcarvalhosa17/Tun-Client/releases/latest)**. Na página que abre, clique em `tunel-clientes-<versão>-windows-setup.exe`, em **Assets**.

> O navegador pode avisar que o arquivo "não é baixado com frequência". Clique nos **três pontinhos** (ou na seta) ao lado do aviso e escolha **Manter** e depois **Manter mesmo assim**. O aviso aparece porque o instalador ainda não tem assinatura digital paga, e não porque haja algum problema.

### Passo 2: abrir o instalador

Abra a pasta **Downloads** e dê dois cliques em `tunel-clientes-<versão>-windows-setup.exe`.

> Se aparecer a tela azul **"O Windows protegeu o computador"**:
> 1. Clique em **Mais informações**.
> 2. Clique em **Executar assim mesmo**.

### Passo 3: instalar

1. Na tela **Selecionar tarefas adicionais**, marque **Criar atalho na área de trabalho** se quiser, e clique em **Avançar**.
2. Clique em **Instalar**.
3. Na última tela, deixe marcado **Abrir o Tunel Clientes** e clique em **Concluir**.

### Passo 4: cadastrar o login

Na primeira abertura aparece a janela **Configurações**, com a mensagem de boas-vindas:

1. Em **Usuário**, digite seu usuário SSH.
2. Em **Senha**, digite sua senha SSH.
3. Clique em **Salvar login**. Abaixo dos campos deve aparecer *"Senha cadastrada para seu_usuario: sim"*.
4. Clique em **Fechar**.

A senha fica guardada no **Gerenciador de Credenciais do Windows**. Ela não fica em nenhum arquivo do app.

### Passo 5: pronto

Siga para o [Primeiro uso](#primeiro-uso). Depois, o app abre pelo **menu Iniciar**: digite **Tunel Clientes**.

---

## Ubuntu e Debian

### Forma rápida (recomendada): 1 comando

1. Abra o **Terminal**: aperte **Ctrl + Alt + T**, ou procure "Terminal" no menu.
2. Copie o comando abaixo, cole no Terminal (botão direito e **Colar**, ou **Ctrl + Shift + V**) e aperte **Enter**:

   ```
   wget -qO- https://raw.githubusercontent.com/fcarvalhosa17/Tun-Client/main/instalar.sh | sh
   ```

3. Se faltar algum componente do sistema, o instalador mostra a lista e pergunta:
   *"Instalar agora com 'sudo apt-get install'? [S/n]"*.
   - Aperte **Enter** para aceitar.
   - Digite a **sua senha do Linux** e aperte **Enter**. Nada aparece na tela enquanto você digita; isso é normal.
4. Espere terminar. Na primeira vez, ele baixa cerca de 200 MB e leva alguns minutos. No fim aparece *"Pronto. Abra 'Tunel Clientes' no menu de aplicativos"*.
5. Abra o **Tunel Clientes** pelo menu de aplicativos.
6. Na janela **Configurações**, cadastre seu login SSH como no [passo 4 do Windows](#passo-4-cadastrar-o-login) e siga para o [Primeiro uso](#primeiro-uso).

> **KDE e outros ambientes sem cofre de senhas:** o app guarda a senha no cofre do sistema, que é o GNOME Keyring no Ubuntu e no Debian com GNOME, ou o KWallet no KDE. Se ao salvar o login aparecer um erro de cofre, instale o GNOME Keyring com `sudo apt install gnome-keyring`, saia e entre de novo na sessão.

### Forma manual (se preferir não usar o comando)

1. Baixe `tunel-clientes-<versão>-linux-macos.zip` na [página da última versão](https://github.com/fcarvalhosa17/Tun-Client/releases/latest).
2. Na pasta **Downloads**, clique com o botão direito no zip e escolha **Extrair aqui**.
3. Abra a pasta extraída, clique com o botão direito num espaço vazio e escolha **Abrir no Terminal**.
4. Digite `python3 instalar.py` e aperte **Enter**.
5. Continue do passo 3 da forma rápida.

---

## macOS

### Passo 1: conferir o Python

1. Abra o **Terminal**: aperte **Cmd + Espaço**, digite **Terminal** e aperte **Enter**.
2. Digite `python3 --version` e aperte **Enter**.
   - Se aparecer `Python 3.9` ou um número maior, vá para o passo 2.
   - Se aparecer uma janela pedindo para instalar as **ferramentas de linha de comando**, clique em **Instalar**, espere terminar e repita este passo.
   - Se nada disso funcionar, instale o Python pelo [python.org](https://www.python.org/downloads/macos/): baixe o instalador para macOS, abra o arquivo e clique em **Continuar** até o fim.

### Passo 2: instalar

Copie o comando abaixo, cole no Terminal (**Cmd + V**) e aperte **Enter**:

```
curl -fsSL https://raw.githubusercontent.com/fcarvalhosa17/Tun-Client/main/instalar.sh | sh
```

Espere terminar. Na primeira vez, ele baixa cerca de 200 MB e leva alguns minutos. No fim aparece *"Pronto. Abra 'Tunel Clientes' em Aplicativos"*.

### Passo 3: abrir

- Aperte **Cmd + Espaço**, digite **Tunel Clientes** e aperte **Enter**.
- O app fica em **Finder → Ir → Início → Aplicativos**. É a pasta Aplicativos do seu usuário, não a do sistema. Para deixá-lo no Dock, arraste o ícone para lá.

### Passo 4: cadastrar o login

Faça como no [passo 4 do Windows](#passo-4-cadastrar-o-login). Ao clicar em **Salvar login**, o macOS pergunta se o app pode usar as **Chaves** (o cofre de senhas do Mac):

1. Digite a **senha do seu Mac**.
2. Clique em **Sempre permitir**.

O aviso pode mostrar o nome "Python" em vez de "Tunel Clientes", porque o app roda sobre o Python. É esperado.

---

## Primeiro uso

### 1. Cadastrar os clientes

Escolha um dos jeitos:

- **Um por um:** clique em **Novo cliente** e preencha:
  - **Id:** nome curto e sem espaços, por exemplo `ufcspa`.
  - **Nome:** como aparece na lista, por exemplo `UFCSPA`.
  - **Endereço do servidor:** o IP do servidor do cliente na VPN, por exemplo `10.255.51.12`.
  - O resto pode ficar em branco, e aí vale o padrão: porta 22 e o seu login SSH.
  - Clique em **Salvar**.
- **Planilha:**
  1. Clique em **Configurações** e depois em **Importar planilha (CSV)…**.
  2. A planilha precisa das colunas `id`, `nome` e `host`. As outras são opcionais (veja o [README](README.md#planilha-csv)). No Excel, use **Arquivo → Salvar como → CSV (separado por vírgulas)**.

### 2. Conectar

1. Clique no cliente na lista.
2. Clique em **Conectar**, ou dê dois cliques no cliente.
3. Quando conectar, o cliente fica **verde**, com um **●**, e o rodapé mostra *"● Conectado a NOME"*.
   - Se der erro, ele fica **vermelho**, com um **✖**, e aparece uma mensagem explicando o motivo (veja [Problemas comuns](#problemas-comuns)).

### 3. Abrir um aparelho

1. Na barra de endereço, no alto, digite o IP do aparelho, por exemplo `192.168.0.10`, e aperte **Enter**.
2. O app tenta `http` e, se não houver resposta, `https`, sozinho.
3. Se aparecer **"Certificado não confiável"**, clique em **Sim**. Isso é comum em equipamentos. O app só pergunta uma vez por aparelho.
4. Se o aparelho pedir usuário e senha numa janela, digite o login **do aparelho**. Esse login não é guardado.

Para abrir mais de um aparelho ao mesmo tempo, use **+ Aba**.

### 4. Telnet

- Digite `telnet://192.168.0.20` na barra de endereço, ou clique em **Telnet…** e informe o IP.
- Abre uma aba de terminal ligada ao aparelho. Para outra porta: `telnet://192.168.0.20:2323`.

### 5. Histórico

O botão **Histórico** mostra os endereços já abertos no cliente conectado. Eles também aparecem como sugestão enquanto você digita.

### 6. Trocar de cliente

Basta conectar outro cliente. O app fecha o túnel atual e as abas abertas antes de conectar o novo, porque os IPs internos se repetem entre clientes.

---

## Atualizar e remover

| | Windows | Ubuntu e Debian | macOS |
|---|---|---|---|
| **Atualizar** | Feche o app, baixe o instalador novo e rode-o. | Rode de novo o comando da instalação. | Rode de novo o comando da instalação. |
| **Remover** | **Configurações → Aplicativos → Tunel Clientes → Desinstalar** | `wget -qO- https://raw.githubusercontent.com/fcarvalhosa17/Tun-Client/main/instalar.sh \| sh -s -- --remover` | `curl -fsSL https://raw.githubusercontent.com/fcarvalhosa17/Tun-Client/main/instalar.sh \| sh -s -- --remover` |

Atualizar mantém a lista de clientes, o histórico e as senhas. Remover também mantém esses dados, para o caso de você instalar de novo.

---

## Problemas comuns

| O que aparece | O que fazer |
|---|---|
| **"Autenticação recusada"** | O usuário ou a senha SSH está errado. Corrija em **Configurações** e clique em **Salvar login**. Se o cliente usa outra senha, clique nele com o botão direito e escolha **Senha própria (diferente da padrão)…**. |
| **"Não foi possível alcançar 10.255..."** ou **"Tempo esgotado"** | A VPN está desconectada ou o servidor do cliente está fora do ar. Confira a VPN e tente de novo. |
| **"A chave do servidor mudou"** | Pode ser troca do servidor ou tentativa de ataque. Confirme com o cliente. Se o servidor foi trocado, clique no cliente com o botão direito, escolha **Esquecer chave do servidor** e conecte de novo. Se ninguém trocou o servidor, **não conecte**. |
| A página do aparelho não abre | Confira se o cliente está verde (conectado) e se você digitou o **IP**, não um nome. |
| **"Digite o IP do aparelho. Nomes não passam pelo túnel."** | Use o número do IP, por exemplo `192.168.0.10`, em vez do nome do aparelho. |
| Windows: o instalador não abre | Veja o [passo 2 do Windows](#passo-2-abrir-o-instalador) (Mais informações → Executar assim mesmo). |
| Linux: erro de cofre de senhas ao salvar o login | Instale com `sudo apt install gnome-keyring`, saia e entre de novo na sessão. |
| Linux: o comando parou com erro do `apt-get` | Rode `sudo apt-get update` e depois o comando da instalação de novo. |
| Mac: `python3: command not found` | Faça o [passo 1 do macOS](#passo-1-conferir-o-python). |
| O túnel caiu sozinho | Depois de 30 minutos sem uso, o túnel fecha para economizar recursos. É só conectar de novo. |

Se o problema continuar, envie à equipe o arquivo de registro `app.log`. Ele não guarda senhas. Fica em:

- Windows: `%APPDATA%\tunel-clientes\app.log`. Cole esse caminho na barra de endereço do Explorador de Arquivos.
- Linux: `~/.config/tunel-clientes/app.log`
- macOS: `~/Library/Application Support/tunel-clientes/app.log`
