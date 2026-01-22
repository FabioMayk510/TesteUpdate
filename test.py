from AutoUpdate import AutoUpdate

APP_VERSION = "2.0.4"

update = AutoUpdate(
        app_name="test", 
        current_version=APP_VERSION, 
        metadata_target="https://raw.githubusercontent.com/FabioMayk510/TesteUpdate/main/tufup-repo/metadata/", 
        target_base="https://github.com/fabiomayk510/TesteUpdate/releases/download"
    )

input(f"testando versão {APP_VERSION}")