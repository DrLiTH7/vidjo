import os
import sys
import shutil

try:
    import imageio_ffmpeg
except ImportError:
    print("Erro: O pacote imageio-ffmpeg não está instalado.")
    print("Execute 'uv sync' ou 'pip install imageio-ffmpeg' primeiro.")
    sys.exit(1)

def main():
    # Caminho do executável FFmpeg empacotado no imageio-ffmpeg
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    
    # Caminho de destino (a pasta onde está o python.exe, ou seja, venv/Scripts)
    scripts_dir = os.path.dirname(sys.executable)
    dest = os.path.join(scripts_dir, "ffmpeg.exe")
    
    print(f"Encontrado FFmpeg em: {ffmpeg_exe}")
    
    if os.path.abspath(ffmpeg_exe) == os.path.abspath(dest):
        print("FFmpeg já está no destino correto.")
        return

    print(f"Copiando FFmpeg para: {dest}")
    shutil.copy2(ffmpeg_exe, dest)
    print("FFmpeg configurado com sucesso!")

if __name__ == "__main__":
    main()
