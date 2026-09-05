import sys
import asyncio
from config import BlobUrls
from core import BlobDownloader

async def main_config():
    print("Iniciando download a partir do config.py...")
    downloader = BlobDownloader(clean_tmp=True)
    results = await downloader.run_batch(BlobUrls)

    successful = [r for r in results if not isinstance(r, Exception) and r is not None]
    print(f"Successfully downloaded {len(successful)}/{len(BlobUrls)} videos!")

if __name__ == "__main__":
    # If explicitly called with --config, or if BlobUrls is updated from default
    if "--config" in sys.argv:
        asyncio.run(main_config())
    else:
        # Default mode is now server mode
        print("=========================================================")
        print(" Modo Automático ativado! (Servidor Local)")
        print(" O Downblob aguardará links diretamente da Extensão Firefox.")
        print(" Para rodar via config.py, use: python main.py --config")
        print("=========================================================\n")
        import server
        server.main()
