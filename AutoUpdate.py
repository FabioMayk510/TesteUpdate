
"""
App com auto-atualização via Tufup
"""

from __future__ import annotations
import sys
import os
import shutil
import time
import urllib.request
from dotenv import load_dotenv
from pathlib import Path
from tufup.client import Client

# =========================
# Helpers de caminho/ambiente
# =========================
def get_runtime_paths(app_name):
    """
    Retorna:
      install_dir: diretório de instalação do app (onde fica o .exe/.py)
      user_base  : diretório base gravável do usuário para cache/update/metadata
    """
    if getattr(sys, "frozen", False):
        # Executando como .exe (PyInstaller)
        executable_path = Path(sys.executable).resolve()
        install_dir = executable_path.parent
    else:
        executable_path = Path(__file__).resolve()
        install_dir = executable_path.parent

    # Pastas graváveis do usuário
    if os.name == "nt":
        # Windows
        local_appdata = os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")
        user_base = Path(local_appdata) / app_name
    elif sys.platform == "darwin":
        # macOS
        user_base = Path.home() / "Library" / "Application Support" / app_name
    else:
        # Linux/Unix
        user_base = Path.home() / ".local" / "share" / app_name

    user_base.mkdir(parents=True, exist_ok=True)
    return install_dir, user_base


def ensure_dirs(user_base: Path):
    """
    Cria as pastas necessárias:
      metadata_dir: cache de metadados TUF
      target_dir  : downloads dos targets (.tar.gz/.patch)
      extract_dir : pasta de extração temporária
    """
    metadata_dir = user_base / "metadata"
    target_dir = user_base / "downloads"
    extract_dir = user_base / "extracted"
    for d in (metadata_dir, target_dir, extract_dir):
        d.mkdir(parents=True, exist_ok=True)
    return metadata_dir, target_dir, extract_dir


def copy_bundled_root_if_available(metadata_dir: Path):
    """
    Se o root.json vier embutido no bundle (recomendado),
    copia para o cache na primeira execução.
    (O exemplo oficial embute root.json no bundle do app.)
    """
    # Tentativa 1: se estiver congelado, procurar no _MEIPASS
    bundled_root = None
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        maybe = Path(getattr(sys, "_MEIPASS")) / "root.json"
        if maybe.exists():
            bundled_root = maybe

    # Tentativa 2: procurar ao lado do executável/script
    if bundled_root is None:
        here = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
        maybe = here / "root.json"
        if maybe.exists():
            bundled_root = maybe

    if bundled_root:
        dst = metadata_dir / "root.json"
        if not dst.exists():
            shutil.copy2(bundled_root, dst)
            # Opcional: se você quiser também versionado "1.root.json" na primeira vez:
            vdst = metadata_dir / "1.root.json"
            if not vdst.exists():
                shutil.copy2(bundled_root, vdst)
        return True
    return False


# =========================
# Updater
# =========================
class AppUpdater:
    def __init__(
            self, 
            app_name, 
            current_version,
            metadata_target,
            target_base
            ):
        install_dir, user_base = get_runtime_paths(app_name)
        self.install_dir = install_dir
        self.user_base = user_base

        self.metadata_dir, self.target_dir, self.extract_dir = ensure_dirs(user_base)

        # Inicializa metadados root (bootstrap) se necessário
        self._initialize_metadata(metadata_target)

        # Cria cliente Tufup
        self.client = Client(
            app_name=app_name,
            app_install_dir=self.install_dir,
            current_version=current_version,
            metadata_dir=self.metadata_dir,
            metadata_base_url=metadata_target,
            target_dir=self.target_dir,
            target_base_url=target_base,
            extract_dir=self.extract_dir,
        )
        

    def _initialize_metadata(self, metadata_target):
        """
        Bootstrap do TUF:
          1) Tenta usar root.json embutido no app (preferível).
          2) Se não houver, baixa 1.root.json e root.json do repositório (RAW) apenas 1ª vez.
        Sempre limpa metadados MUTÁVEIS antes de verificar update.
        """
        print("  🧹 Limpando cache de metadados mutáveis...")
        for fname in ("timestamp.json", "snapshot.json", "targets.json"):
            f = self.metadata_dir / fname
            if f.exists():
                f.unlink()

        root_file = self.metadata_dir / "root.json"
        versioned_root = self.metadata_dir / "1.root.json"

        if root_file.exists() and versioned_root.exists():
            print("  ℹ️  Metadados root já inicializados")
            return

        # Tenta root.json embutido
        if copy_bundled_root_if_available(self.metadata_dir):
            print("  ✓ root.json copiado do bundle")
            # Se ainda faltar o versionado, baixamos só o 1.root.json
            if not versioned_root.exists():
                self._download_metadata_file("1.root.json", metadata_target)
            return

        # Fallback: baixa 1.root.json e root.json do GitHub RAW (bootstrap TOFU)
        print("🔧 Inicializando metadados TUF (bootstrap remoto)...")
        for fname in ("1.root.json", "root.json"):
            self._download_metadata_file(fname, metadata_target)
        print("  ✓ Metadados root inicializados")

    def _download_metadata_file(self, filename: str, metadata_target: str):
        url = f"{metadata_target}{filename}"
        print(f"  📥 Baixando: {filename}\n     URL: {url}")
        content = urllib.request.urlopen(url).read()
        (self.metadata_dir / filename).write_bytes(content)
        print(f"  ✓ Salvo: {(self.metadata_dir / filename)}")

    def _progress(self, *, bytes_downloaded: int, bytes_expected: int):
        pct = (bytes_downloaded / max(bytes_expected, 1)) * 100.0
        print(f"    ⇣ {bytes_downloaded}/{bytes_expected} bytes ({pct:.1f}%)", end="\r")

    def check_for_updates(self, app_name, current_version):
        """Verifica se há atualizações disponíveis."""
        print(f"Verificando atualizações para {app_name} v{current_version}...")
        try:
            # Limpa novamente os mutáveis (garante estado limpo)
            for fname in ("timestamp.json", "snapshot.json", "targets.json"):
                f = self.metadata_dir / fname
                if f.exists():
                    f.unlink()

            print("  Buscando atualizações...")
            # check_for_updates chama refresh() conforme necessário
            latest_meta = self.client.check_for_updates()
            if latest_meta:
                print(f"✓ Nova versão disponível: {latest_meta.filename}")
                self.client._target_base_url = self.client._target_base_url + f"v{latest_meta.version.base_version}/"
                # guarde para usar no download
                self._latest_meta = latest_meta
                return latest_meta
            else:
                self._latest_meta = None
                print("✓ Você está na versão mais recente!")
                return None

        except Exception as e:
            import traceback
            print(f"✗ Erro ao verificar atualizações: {e}")
            print("\n📋 Detalhes do erro:")
            traceback.print_exc()
            return None

    
    def download_and_apply_update(self):
        try:
            print("\n📥 Baixando atualização...")

            self.client.download_and_apply_update(
                skip_confirmation=True,
                purge_old_archives=True,
                install=custom_install
            )

            print("\n✓ Atualização aplicada com sucesso!")
            print("⚠️  Reinicie o aplicativo para usar a nova versão.")
            return True

        except SystemExit:
            raise
        except Exception as e:
            import traceback
            print(f"✗ Erro ao aplicar atualização: {e}")
            print("\n📋 Detalhes do erro:")
            traceback.print_exc()
            return False


# =========================
# App principal
# =========================


def custom_install(src_dir, dst_dir, **kwargs):
    """
    src_dir: já contém os arquivos EXTRAÍDOS do novo app
    """
    import subprocess, os, sys

    updater = dst_dir / "updater.exe"
    if not updater.exists():
        raise FileNotFoundError("updater.exe não encontrado")

    subprocess.Popen([
        str(updater),
        str(os.getpid()),
        str(dst_dir),
        str(src_dir),      # ✅ repassa o conteúdo pronto
    ])

    sys.exit(0)

class AutoUpdate:
    def __init__(
            self, 
            app_name: str = "AppTeste", 
            current_version: str = "0.0.0",
            metadata_target: str = "https://raw.githubusercontent.com/FabioMayk510/TesteUpdate/main/tufup-repo/metadata/",
            target_base: str = "https://github.com/fabiomayk510/TesteUpdate/releases/download"
            ):
        self.update(app_name, current_version, metadata_target, target_base)


    def show_version(self, app_name, current_version):
        print("=" * 50)
        print(f"  {app_name}")
        print(f"  Versão: {current_version}")
        print("=" * 50)


    def update(self, app_name, current_version, metadata_target, target_base):
        try:
            self.show_version(app_name, current_version)
            updater = AppUpdater(app_name, current_version, metadata_target, target_base)
            new_version = updater.check_for_updates(app_name, current_version)

            if new_version:
                # print("\nDeseja atualizar agora? (s/n): ", end="")

                choice = "s"
                # print(choice)

                if choice.lower().strip() == "s":
                    if updater.download_and_apply_update():
                        print(f"\n🔄 Reinicie o aplicativo para usar a versão {new_version.version}")
                        input("\nPressione ENTER para sair...")
                        sys.exit(0)
                else:
                    print("Atualização cancelada.")

        except Exception as e:
            print(f"\n⚠️  Erro no sistema de atualização: {e}")
            print("O aplicativo continuará rodando normalmente.")
        
        except KeyboardInterrupt:
            print("\n\nAplicativo encerrado.")