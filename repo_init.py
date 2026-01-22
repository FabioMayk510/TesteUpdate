
"""
Script para criar e gerenciar repositório Tufup
Gera o archive (.tar.gz) via Tufup a partir de um diretório de bundle
e grava url_path_segments para uso com GitHub Releases.
"""

from pathlib import Path
from tufup.repo import Repository
from dotenv import load_dotenv
import shutil
import sys
import os

# Configurações
REPO_DIR = Path("tufup-repo")
KEYS_DIR = Path("keystore")
APP_NAME: str | None = None

def criar_repositorio():
    """Cria o repositório Tufup inicial (gera/usa chaves e metadados)."""
    from securesystemslib.keys import generate_ed25519_key
    import json

    # Criar diretórios
    REPO_DIR.mkdir(exist_ok=True)
    KEYS_DIR.mkdir(exist_ok=True)

    print("Criando repositório Tufup...")

    # Gerar chaves manualmente para cada role (mantido do seu script)
    print("\n🔐 Gerando chaves criptográficas...")
    roles = ['root', 'targets', 'snapshot', 'timestamp']

    for role in roles:
        key_path = KEYS_DIR / role

        if not key_path.exists():
            print(f"  Gerando chave para: {role}")

            key = generate_ed25519_key()

            with open(key_path, 'w') as f:
                json.dump(key, f, indent=2)

            print(f"  ✓ Chave criada: {key_path}")

    print("\n📦 Inicializando repositório...")
    repo = Repository(
        app_name=APP_NAME,
        repo_dir=REPO_DIR,
        keys_dir=KEYS_DIR,
        expiration_days={
            'root': 365,
            'targets': 365,
            'snapshot': 7,
            'timestamp': 1,
        }
    )

    # Inicializa diretórios/roles/keys/metadata conforme API
    repo.save_config()
    repo.initialize()

    print("\n✓ Repositório criado com sucesso!")
    print(f"✓ Chaves salvas em: {KEYS_DIR}/")
    print(f"✓ Metadados salvos em: {REPO_DIR}/metadata/")
    print("\n⚠️  IMPORTANTE: Guarde as chaves em local seguro!")
    print("\n📋 Adicione ao .gitignore:")
    print("   keystore/")
    print("   *.tar.gz")
    print("   build/")
    print("   dist/")

    return repo


def empacotar_app(versao, dist_dir="dist"):
    """
    Monta um diretório de bundle (sem criar .tar.gz).
    O .tar.gz será gerado pelo Tufup (repo.add_bundle).

    Args:
        versao: Versão do app (ex: "1.0.1")
        dist_dir: Diretório onde está o executável (padrão: "dist")

    Retorna:
        Path do diretório de bundle pronto para o add_bundle()
        ou None em caso de falha.
    """
    print(f"\n📦 Montando bundle da versão {versao}...")

    dist_path = Path(dist_dir)
    if not dist_path.exists():
        print(f"✗ Diretório não encontrado: {dist_dir}")
        print("\n💡 Dica: Compile antes com PyInstaller.")
        print(f"   Ex.: pyinstaller --onefile --name {APP_NAME} app.py")
        return None

    bundle_dir = Path(f"temp_bundle_{versao}")
    try:
        if bundle_dir.exists():
            shutil.rmtree(bundle_dir)
        bundle_dir.mkdir()

        # Opção 1: --onefile (um único .exe)
        exe_file = dist_path / f"{APP_NAME}.exe"
        if exe_file.exists():
            shutil.copy2(exe_file, bundle_dir / f"{APP_NAME}.exe")
            print(f"  ✓ {APP_NAME}.exe")

        # Opção 2: --onedir (pasta com vários arquivos)
        app_folder = dist_path / APP_NAME
        if app_folder.exists() and app_folder.is_dir():
            shutil.copytree(app_folder, bundle_dir / APP_NAME)
            print(f"  ✓ Pasta {APP_NAME}/ completa")

        # Copiar arquivos adicionais necessários (opcionais)
        extras = [
            "config.ini",
            "README.txt",
            "assets/",
            "data/",
        ]
        for extra in extras:
            p = Path(extra)
            if p.exists():
                if p.is_file():
                    shutil.copy2(p, bundle_dir / p.name)
                elif p.is_dir():
                    shutil.copytree(p, bundle_dir / p.name)
                print(f"  ✓ {extra}")

        # Verificar conteúdo
        if not any(bundle_dir.iterdir()):
            print("✗ Nenhum arquivo encontrado no bundle!")
            return None

        print(f"✓ Bundle pronto: {bundle_dir}")
        return bundle_dir

    except Exception as e:
        print(f"✗ Erro ao montar bundle: {e}")
        if bundle_dir.exists():
            shutil.rmtree(bundle_dir)
        return None
    



def _pos_publicacao_ajustar_url(repo: Repository, versao: str, tag_release: str | None = None):
    """
    ✅ CORRETO:
    - Move o arquivo fisicamente para targets/vX.Y.Z/
    - NÃO registra o target novamente
    - O target já foi registrado corretamente por repo.add_bundle()
    """

    if not tag_release:
        return

    latest = repo.roles.get_latest_archive()
    if latest is None:
        return

    target_filename = f"{APP_NAME}-{versao}.tar.gz"

    # Caminho criado pelo tufup
    tar_original = repo.targets_dir / target_filename
    if not tar_original.exists():
        return

    # Mover fisicamente
    tag_dir = repo.targets_dir / tag_release
    tag_dir.mkdir(parents=True, exist_ok=True)
    tar_final = tag_dir / target_filename

    if tar_final.exists():
        tar_final.unlink()

    shutil.move(str(tar_original), str(tar_final))

    print(f"✓ Artefato movido para: {tar_final}")



def adicionar_primeira_versao(versao, bundle_dir, tag_release=None):
    """Adiciona a primeira versão (inicial) ao repositório."""
    print(f"\n🎯 Adicionando PRIMEIRA versão {versao} ao repositório...")

    bundle_path = Path(bundle_dir)
    if not bundle_path.exists():
        print(f"✗ Bundle não encontrado: {bundle_dir}")
        return False

    try:
        repo = Repository.from_config()

        # Deixa o Tufup gerar o .tar.gz e atualizar metadados (sem patch)
        repo.add_bundle(
            new_version=versao,
            new_bundle_dir=bundle_path,
            skip_patch=True,
        )

        # Grava a tag do Release como segmento de URL do target
        _pos_publicacao_ajustar_url(repo, versao, tag_release)

        # Assina e persiste metadata
        repo.publish_changes(private_key_dirs=[KEYS_DIR])

        # Limpa bundle temporário
        shutil.rmtree(bundle_path, ignore_errors=True)

        tar_path = repo.targets_dir / f"{APP_NAME}-{versao}.tar.gz"
        size = os.path.getsize(tar_path) if tar_path.exists() else 0

        print(f"\n✓ Primeira versão {versao} adicionada e assinada!")
        print(f"✓ Metadados: {REPO_DIR}/metadata/")
        print(f"✓ Artefato gerado (suba este no Release): {tar_path} ({size} bytes)")
        return True

    except Exception as e:
        import traceback
        print(f"✗ Erro: {e}")
        traceback.print_exc()
        return False


def adicionar_versao(versao, bundle_dir, tag_release=None):
    """Adiciona uma nova versão ao repositório."""
    print(f"\n➕ Adicionando versão {versao} ao repositório...")

    bundle_path = Path(bundle_dir)
    if not bundle_path.exists():
        print(f"✗ Bundle não encontrado: {bundle_dir}")
        return False

    try:
        repo = Repository.from_config()

        # Se não existir nenhuma versão anterior, adicionar como primeira
        if not repo.targets_dir.exists() or not any(repo.targets_dir.glob(f"{APP_NAME}-*.tar.gz")):
            print("  ℹ️  Nenhuma versão anterior encontrada. Adicionando como versão inicial...")
            return adicionar_primeira_versao(versao, bundle_dir, tag_release)

        # Gera o archive e (caso aplicável) patch
        repo.add_bundle(
            new_version=versao,
            new_bundle_dir=bundle_path,
        )

        # Grava a tag do Release como segmento de URL
        _pos_publicacao_ajustar_url(repo, versao, tag_release)

        # Assina e salva metadados
        repo.publish_changes(private_key_dirs=[KEYS_DIR])

        # Limpa bundle temporário
        shutil.rmtree(bundle_path, ignore_errors=True)

        tar_path = repo.targets_dir / f"{APP_NAME}-{versao}.tar.gz"
        size = os.path.getsize(tar_path) if tar_path.exists() else 0

        print(f"\n✓ Versão {versao} adicionada com sucesso!")
        print(f"✓ Metadados: {REPO_DIR}/metadata/")
        print(f"✓ Artefato gerado (suba este no Release): {tar_path} ({size} bytes)")
        return True

    except Exception as e:
        import traceback
        print(f"✗ Erro ao adicionar versão: {e}")
        print(f"\n📋 Detalhes do erro:")
        traceback.print_exc()
        return False


def mostrar_instrucoes(versao):
    """Mostra instruções para publicar no GitHub Releases + metadata no repo."""
    print("\n" + "="*60)
    print("📤 PRÓXIMOS PASSOS PARA PUBLICAR NO GITHUB")
    print("="*60)

    print("\n1️⃣  ATUALIZAR METADADOS (branch main):")
    print("   git add tufup-repo/metadata/")
    print(f"   git commit -m 'Atualização para v{versao}'")
    print("   git push")

    print("\n2️⃣  CRIAR RELEASE NO GITHUB:")
    print(f"   • Acesse: https://github.com/fabiomayk510/AutoUpdate/releases/new")
    print(f"   • Tag: v{versao}")
    print(f"   • Title: Versão {versao}")
    print("   • Faça upload do arquivo GERADO PELO TUFUP:")
    print(f"       tufup-repo/targets/{APP_NAME}-{versao}.tar.gz")
    print("   • Clique em 'Publish release'")

    print("\n3️⃣  URL DO ASSET NO RELEASE (para conferência):")
    print(f"   https://github.com/fabiomayk510/AutoUpdate/releases/download/v{versao}/{APP_NAME}-{versao}.tar.gz")

    print("\n" + "="*60)


def compilar_exe():
    """Instrução para compilar o executável com PyInstaller."""
    print("\n🔨 COMPILAR EXECUTÁVEL")
    print("="*60)
    print("\nAntes de empacotar, compile seu app com PyInstaller:")
    print("\n📦 Opção 1 - Arquivo único (recomendado):")
    print(f"   pyinstaller --onefile --name {APP_NAME} --icon=icone.ico app.py")
    print("\n📁 Opção 2 - Pasta com dependências:")
    print(f"   pyinstaller --onedir --name {APP_NAME} --icon=icone.ico app.py")
    print("\n💡 Opções úteis:")
    print("   --noconsole          # Esconde o console (para GUI)")
    print("   --add-data 'src;dst' # Adiciona arquivos extras")
    print("   --hidden-import pkg  # Importa pacotes não detectados")
    print("\nApós compilar, o executável estará em: dist/")
    print("="*60)


def require_app_name():
    if not APP_NAME:
        print("✗ APP_NAME não informado.")
        print("Uso:")
        print("  update_manager <comando> <versão> <APP_NAME>")
        print("Exemplo:")
        print("  update_manager full 2.0.0 test")
        sys.exit(1)



def main():
    global APP_NAME
    
    if len(sys.argv) < 2:
        print("="*60)
        print(f"  GERENCIADOR DE REPOSITÓRIO TUFUP - {APP_NAME}")
        print("="*60)
        print("\n📋 COMANDOS DISPONÍVEIS:\n")
        print("  init <APP_NAME>             - Criar repositório inicial")
        print("  compile <APP_NAME>          - Mostrar como compilar o .exe")
        print("  pack <versão> <APP_NAME>    - Montar bundle (sem .tar.gz)")
        print("  add <versão> <APP_NAME>     - Adicionar versão ao repositório (gera tar)")
        print("  full <versão> <APP_NAME>    - pack + add + instruções")
        print("\n📖 EXEMPLOS:\n")
        print("  update_manager init test")
        print("  update_manager compile test")
        print("  update_manager full 1.0.5 test")
        print("="*60)
        sys.exit(1)

    comando = sys.argv[1].lower()

    
    # comandos que NÃO precisam de versão
    if comando in {"init", "compile"}:
        if len(sys.argv) < 3:
            print("✗ É necessário informar o APP_NAME.")
            print(f"Ex.: update_manager {comando} test")
            sys.exit(1)

        APP_NAME = sys.argv[2]

    else:
        # comandos que precisam de versão
        if len(sys.argv) < 4:
            print("✗ É necessário informar versão e APP_NAME.")
            print(f"Ex.: update_manager {comando} 2.0.0 test")
            sys.exit(1)

        APP_NAME = sys.argv[3]


    if comando == "init":
        criar_repositorio()

    elif comando == "compile":
        compilar_exe()

    elif comando == "pack":
        if len(sys.argv) < 3:
            print("✗ Especifique a versão: python criar_repositorio.py pack 1.0.5")
            sys.exit(1)
        versao = sys.argv[2]
        bundle_dir = empacotar_app(versao)
        if bundle_dir:
            print(f"\n✓ Bundle pronto: {bundle_dir}")

    elif comando == "add":
        if len(sys.argv) < 3:
            print("✗ Especifique a versão: python criar_repositorio.py add 1.0.5")
            sys.exit(1)

        versao = sys.argv[2]
        tag = f"v{versao}"  # ajuste se usar outro padrão de tag
        bundle_dir = empacotar_app(versao)
        if not bundle_dir:
            sys.exit(1)

        if adicionar_versao(versao, bundle_dir, tag_release=tag):
            mostrar_instrucoes(versao)

    elif comando == "full":
        if len(sys.argv) < 3:
            print("✗ Especifique a versão: python criar_repositorio.py full 1.0.5")
            sys.exit(1)

        versao = sys.argv[2]
        tag = f"v{versao}"

        # 1. Montar bundle
        bundle_dir = empacotar_app(versao)
        if not bundle_dir:
            sys.exit(1)

        # 2. Adicionar (gera tar + metadados + url_path_segments)
        if not adicionar_versao(versao, bundle_dir, tag_release=tag):
            sys.exit(1)

        # 3. Mostrar instruções de publicação
        mostrar_instrucoes(versao)

    else:
        print(f"✗ Comando desconhecido: {comando}")
        print("Use: python criar_repositorio.py (sem argumentos) para ver a ajuda")


if __name__ == "__main__":
    main()
