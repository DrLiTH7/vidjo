# VIDJO

Ferramenta avançada para baixar vídeos HLS e streaming. Composta por uma extensão de navegador (**Here is Video**) que intercepta os links e headers de autenticação da página, e um backend Python (**IDIFY**) que realiza o download dos segmentos, contorna proteções e os monta em um único arquivo MP4.

---

## Capacidades e Funcionalidades

- **Captura de Headers Autenticados:** A extensão monitora o tráfego da aba e captura cookies e tokens de acesso reais que o navegador usa, permitindo baixar vídeos bloqueados ou exclusivos para assinantes (vídeos protegidos por DRM e outros sistemas de proteção mais robustos não são suportados).
- **Interface de Gerenciamento (UI):** Acompanhe o progresso de download, cancele tarefas, exclua o histórico ou abra a pasta do vídeo diretamente pelo painel de *Downloads* na própria extensão.
- **Alta Velocidade:** Baixa múltiplos segmentos `.ts` simultaneamente, garantindo alta velocidade no download.
- **Fallback Automático (yt-dlp):** Se o motor de download nativo do HLS falhar ou encontrar encriptações complexas, o sistema repassa a tarefa automaticamente para o `yt-dlp`.

---

## Pré-requisitos

1. **Python 3.12+** instalado
2. **Navegador Chrome, Edge ou Firefox**.

---

## Instalação

### 1. Configurando o Backend (IDIFY)

Não é necessário instalar ferramentas extras globalmente, o script de automação cuidará de baixar tudo que é necessário (incluindo dependências, FFmpeg e yt-dlp) de forma isolada.

1. Navegue até a pasta `IDIFY` no seu computador.
2. Dê um duplo clique no arquivo `setup.bat`.
3. Um terminal se abrirá instalando e configurando tudo automaticamente e depois registrará a integração com o navegador (Host Nativo). Siga as instruções que aparecerem na tela.

### 2. Instalando a Extensão (Here is Video)

**No Google Chrome / Edge:**
1. Acesse `chrome://extensions/` (ou `edge://extensions/`).
2. Ative o **Modo do desenvolvedor** no canto superior direito.
3. Clique em **Carregar sem compactação** (Load unpacked).
4. Selecione a pasta `Here is Video`.

**No Firefox:**
1. Acesse `about:debugging`.
2. Clique em **Este Firefox** → **Carregar extensão temporária**.
3. Selecione o arquivo `manifest.json` dentro da pasta `Here is Video`.

---

## Como Usar

1. Acesse a página onde está o player de vídeo e dê play.
2. O ícone da extensão **Here is Video** na barra superior mudará de cor indicando que interceptou streams.
3. Clique no ícone da extensão. Aparecerá a lista de resoluções/qualidades de vídeo encontradas.
4. Clique em **Baixar** ao lado do stream desejado.
5. Clique no botão de **Downloads** na extensão para acompanhar o progresso. Quando terminar, você pode clicar no ícone de pasta para abrir o local onde o `.mp4` foi salvo (essa pasta é personalizada nas configurações da extensão, mas o padrão é a pasta `downloads` do usuário).

### Modo Servidor Independente (Alternativo)

Caso você não tenha instalado o `install_host.bat` ou prefira ver o terminal processando:
1. Inicie o servidor localmente:
   ```bash
   cd IDIFY
   venv\Scripts\python.exe main.py
   ```
2. O servidor HTTP abrirá na porta `8000`.
3. A extensão reconhecerá automaticamente que o servidor está rodando e enviará os comandos por lá.

---

## Configurações

Na aba superior da extensão, há um botão de **Engrenagem (Configurações)** onde você pode ajustar:
- **Pasta de Downloads:** Caminho absoluto do Windows (ex: `C:\Users\Downloads`). Se deixado em branco, salva por padrão na pasta `downloads` do usuário.
- **Threads FFmpeg / Download Concorrente:** Ajustes para controle de velocidade e carga no CPU.

---