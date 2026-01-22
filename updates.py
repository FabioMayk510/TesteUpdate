
import sys
import os
import shutil
import time
import signal
import platform
from pathlib import Path


def kill_process(pid: int):
    try:
        if platform.system() == "Windows":
            os.system(f"taskkill /PID {pid} /F >nul 2>&1")
        else:
            os.kill(pid, signal.SIGTERM)
    except Exception:
        pass


def wait_process_end(pid: int, timeout=10):
    start = time.time()
    while time.time() - start < timeout:
        try:
            os.kill(pid, 0)
            time.sleep(0.5)
        except OSError:
            return
    kill_process(pid)


def copy_update(extract_dir: Path, destino: Path):
    """
    Copia os arquivos EXTRAÍDOS para o diretório de instalação
    """
    for item in extract_dir.iterdir():
        dest_item = destino / item.name

        if dest_item.exists():
            if dest_item.is_file():
                dest_item.unlink()
            else:
                shutil.rmtree(dest_item, ignore_errors=True)

        if item.is_file():
            shutil.copy2(item, dest_item)
        else:
            shutil.copytree(item, dest_item)


def main():
    if len(sys.argv) < 4:
        print("Uso: updater.exe <PID> <DESTINO> <EXTRACT_DIR>")
        sys.exit(1)

    pid = int(sys.argv[1])
    destino = Path(sys.argv[2]).resolve()
    extract_dir = Path(sys.argv[3]).resolve()

    print("🔄 Iniciando atualização...")
    time.sleep(2)

    # 1️⃣ Encerra processo antigo
    kill_process(pid)
    wait_process_end(pid)

    # 2️⃣ Valida diretório extraído
    if not extract_dir.exists():
        print("❌ Pasta extract_dir não encontrada.")
        sys.exit(1)

    # 3️⃣ Aplica atualização
    try:
        copy_update(extract_dir, destino)
    except Exception as e:
        print(f"❌ Erro ao aplicar atualização: {e}")
        sys.exit(1)

    # 4️⃣ Limpa pasta temporária
    shutil.rmtree(extract_dir, ignore_errors=True)

    print("✅ Atualização concluída com sucesso.")
    sys.exit(0)


if __name__ == "__main__":
    main()
