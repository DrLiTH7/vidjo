#!/usr/bin/env bash
# Instala o IDIFY como serviço de usuário no systemd (Linux).
# Execute a partir da pasta raiz do projeto:
#   bash launchers/linux_install_service.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
IDIFY_PATH="$PROJECT_ROOT/IDIFY"
SERVICE_NAME="idify"
SERVICE_FILE="$SCRIPT_DIR/linux_idify.service"
SYSTEMD_DIR="$HOME/.config/systemd/user"

# Validações
if [ ! -f "$IDIFY_PATH/main.py" ]; then
    echo "Erro: pasta IDIFY não encontrada em $IDIFY_PATH"
    exit 1
fi

# Detecta o Python a usar
if [ -f "$IDIFY_PATH/venv/bin/python" ]; then
    PYTHON_BIN="$IDIFY_PATH/venv/bin/python"
else
    PYTHON_BIN="$(which python3 || which python)"
fi

echo "Instalando serviço '$SERVICE_NAME'..."
echo "  Projeto : $IDIFY_PATH"
echo "  Python  : $PYTHON_BIN"

# Cria diretório do systemd do usuário se não existir
mkdir -p "$SYSTEMD_DIR"

# Gera o .service com os caminhos reais
sed \
    -e "s|YOUR_USER|$(whoami)|g" \
    -e "s|/home/YOUR_USER/downblob/IDIFY|$IDIFY_PATH|g" \
    -e "s|venv/bin/python main.py|$PYTHON_BIN main.py|g" \
    "$SERVICE_FILE" > "$SYSTEMD_DIR/$SERVICE_NAME.service"

# Recarrega e habilita
systemctl --user daemon-reload
systemctl --user enable "$SERVICE_NAME"
systemctl --user start "$SERVICE_NAME"

echo ""
echo "Serviço instalado e iniciado!"
echo ""
echo "Comandos úteis:"
echo "  Status  : systemctl --user status $SERVICE_NAME"
echo "  Logs    : journalctl --user -u $SERVICE_NAME -f"
echo "  Parar   : systemctl --user stop $SERVICE_NAME"
echo "  Remover : systemctl --user disable $SERVICE_NAME"
echo "            rm $SYSTEMD_DIR/$SERVICE_NAME.service"
