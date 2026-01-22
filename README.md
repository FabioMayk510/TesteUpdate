# 🚀 AutoUpdate – Gerenciador de Atualizações Automáticas 

Este projeto fornece uma estrutura completa de atualização automática para aplicações Python empacotadas em .exe, utilizando TUF (The Update Framework), tufup e um gerenciador de releases (update_manager.exe). 

O sistema garante: 

✅ Atualizações seguras (hash + assinatura) 

✅ Distribuição via repositório remoto (ex: GitHub) 

✅ Aplicação automática da nova versão no cliente 

✅ Separação clara entre cliente, metadados e artefatos 

 

## 📁 Estrutura do projeto (exemplo) 
```
1     AutoUpdate/ 

2     ├── AutoUpdate.py            # Módulo que inicializa e executa a verificação de updates 

3     ├── update_manager.exe       # Gerenciador de repositório (init / full / add) 

4     ├── tufup-repo/ 

5     │   ├── metadata/            # Metadados TUF gerados automaticamente 

6     │   └── targets/             # Artefatos .tar.gz por versão 

7     ├── dist/ 

8     │   └── AppTeste.exe         # Executável gerado via PyInstaller 

9     ├── .env                     # Variáveis de ambiente (configuração) 

10    └── README.md 
```
 

## ⚙️ 1. Configuração inicial (.env) 

Antes de qualquer comando, é obrigatório configurar o arquivo .env com as informações do seu repositório e ambiente. 

### Exemplo de .env 
```
1     # Nome da aplicação 
2     APP_NAME=AppTeste
3     CURRENT_VERSION=1.0.0 
4      
5     # Bases de atualização
6     METADATA_BASE_URL=https://raw.githubusercontent.com/USUARIO/REPOSITORIO/main/tufup-repo/metadata/
7
8     TARGET_BASE_URL=https://github.com/USUARIO/REPOSITORIO/releases/download 
```
### ⚠️ Nunca versione o .env 
Adicione obrigatoriamente ao .gitignore: 

1     .env 

 

## 🧱 2. Inicialização do repositório TUF 

Após configurar o .env, execute o comando de inicialização. 

> update_manager.exe init 

Esse comando irá: 

✅ Criar o repositório TUF local (tufup-repo) 

✅ Gerar chaves criptográficas (root, targets, snapshot, timestamp) 

✅ Criar a estrutura inicial de metadados 

✅ Preparar o projeto para receber versões 

Esse passo é feito apenas uma vez. 

 

## 🧩 3. Integração no seu aplicativo (cliente) 

No arquivo principal do seu aplicativo, importe o módulo de atualização logo no início do script. 

Exemplo: 

> import AutoUpdate 

### 📌 Essa importação garante que: 

o cliente carregue as configurações do .env 

o sistema de auto‑update seja inicializado corretamente 

a verificação de novas versões possa ocorrer 

 

## 📦 4. Criar uma nova versão da aplicação 

Sempre que houver uma nova versão do aplicativo: 

### Passo 1️⃣ Compile o executável 

> pyinstaller --onefile --name AppTeste app.py 

O executável será gerado na pasta dist/. 

 

### Passo 2️⃣ Gerar update completo 

Execute o comando abaixo, informando a nova versão: 

> update_manager.exe full <new_version> 

Exemplo: 

> update_manager.exe full 1.0.18 

Esse comando realiza automaticamente: 

✅ Montagem do bundle da aplicação 

✅ Geração do arquivo AppTeste-<versão>.tar.gz 

✅ Atualização do targets.json 

✅ Assinatura e versionamento dos metadados 

✅ Preparação dos arquivos para publicação 

 

## ☁️ 5. Publicação dos arquivos 

Após rodar o comando full, dois uploads são obrigatórios. 

 

### 📤 5.1 Upload dos metadados 

Faça o upload de todos os arquivos da pasta: 

> tufup-repo/metadata/ 

Para a base definida em: 

> METADATA_UPLOAD_BASE 

### 📌 Exemplo (GitHub): 
```
git add tufup-repo/metadata 
git commit -m "Release v1.0.18" 
git push 
```
 

### 📤 5.2 Upload do arquivo .tar.gz 

Faça o upload do arquivo gerado: 

> tufup-repo/targets/AppTeste-1.0.18.tar.gz 

Para o target definido no .env: 

> TARGET_UPLOAD_BASE 

### 📌 Exemplo: 

- GitHub Releases 
- S3 
- Servidor HTTP 
- SharePoint (via script) 

⚠️ O nome do arquivo deve ser idêntico ao registrado nos metadados. 

 

## 🔄 6. Funcionamento no cliente final 

Quando o usuário abrir o aplicativo: 

✅ O cliente carrega o AutoUpdate.py 

✅ Verifica os metadados remotos 

✅ Detecta nova versão (se existir) 

✅ Baixa o .tar.gz 

✅ Executa o instalador (updater.exe) 

✅ Atualiza os arquivos 

✅ Solicita reinício do app 

Tudo isso ocorre de forma segura e automática. 

 

## ✅ Boas práticas 

🔒 Nunca altere arquivos dentro de tufup-repo/metadata manualmente 

🔁 Sempre gere novas versões com full <versão> 

🧪 Teste cada release antes de publicar em produção 

📦 Use versionamento semântico (MAJOR.MINOR.PATCH) 

🗂️ Mantenha .env separado por ambiente (dev / prod) 