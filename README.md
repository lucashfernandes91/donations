# Gestão de Doações

Aplicação web para registrar doadores e doações, emitir comprovantes em PDF e acompanhar os resultados financeiros. Inclui controle de acesso por perfil, histórico de auditoria e exportação de dados para Excel.

## Funcionalidades

- Cadastro e consulta de doadores, com CPF, contato, observações e validação do CPF.
- Cadastro de doações com data, forma de recebimento e valores separados entre doação e contribuição.
- Registro de responsáveis e emissão de comprovantes em PDF para doações e contribuições.
- Dashboard com totais do dia e do mês, média mensal e histórico dos últimos 12 meses.
- Busca, filtros, ordenação e paginação de doações e doadores.
- Exportação das doações filtradas para XLSX, incluindo todos os resultados, não apenas a página aberta.
- Cancelamento de doações com motivo, preservando o registro e o número do comprovante.
- Auditoria de inclusões, alterações e cancelamentos realizados pelas telas da aplicação.
- Backup consistente e verificado do banco SQLite.

## Tecnologias

- Python 3.14 ou superior
- Django 6.1
- SQLite por padrão; PostgreSQL opcional
- `uv` para gerenciamento de ambiente e dependências
- ReportLab para comprovantes PDF e OpenPyXL para planilhas XLSX

## Executar localmente

É necessário ter [Python](https://www.python.org/) e [uv](https://docs.astral.sh/uv/) instalados.

1. Instale as dependências do projeto:

   ```powershell
   uv sync
   ```

2. Crie o arquivo de configuração local:

   ```powershell
   Copy-Item .env.example .env
   ```

   O projeto usa SQLite por padrão. Para desenvolvimento, os valores de `.env.example` são suficientes. Antes de publicar a aplicação, defina uma `DJANGO_SECRET_KEY` segura e configure os parâmetros de produção descritos abaixo.

3. Crie as tabelas do banco e os perfis de acesso:

   ```powershell
   uv run python manage.py migrate
   uv run python manage.py setup_roles
   ```

4. Crie o primeiro usuário administrador:

   ```powershell
   uv run python manage.py createsuperuser
   ```

5. Inicie o servidor de desenvolvimento:

   ```powershell
   uv run python manage.py runserver
   ```

   Acesse <http://127.0.0.1:8000/>. A tela de login fica em <http://127.0.0.1:8000/conta/entrar/>.

### Dados de demonstração (opcional)

Para popular uma base de desenvolvimento com dados fictícios:

```powershell
uv run python manage.py seed_demo
```

O comando cria 25 doadores e 100 doações identificadas como demonstração, além dos respectivos registros de auditoria. A carga é transacional e não deve ser usada para inserir dados reais.

## Páginas principais

| Página | Endereço |
| --- | --- |
| Dashboard | `/` |
| Doadores | `/doadores/` |
| Responsáveis | `/doadores/responsaveis/` |
| Doações | `/doacoes/` |
| Auditoria | `/auditoria/` |
| Administração de usuários e grupos | `/admin/` |

## Perfis de acesso

Após executar `setup_roles`, atribua os grupos aos usuários pela administração Django em `/admin/auth/user/`. O comando configura os grupos, mas não atribui usuários automaticamente. As permissões de vários grupos são combinadas.

| Perfil | Permissões |
| --- | --- |
| Consulta | Visualizar dashboard, doadores e doações; consultar, exportar e emitir comprovantes. |
| Operador | Consulta, além de cadastrar e editar doadores e doações ativas. |
| Administrador | Operador, além de cancelar doações e consultar a auditoria. |

O superusuário gerencia usuários e grupos. Não há exclusão física de doações pelos perfis da aplicação; o cancelamento mantém o registro para consulta e auditoria. Usuários sem grupo ou permissão recebem acesso restrito.

## Auditoria e cancelamento

Inclusões e alterações feitas pelas telas são registradas com usuário, horário e valores anteriores e posteriores. O registro da alteração e a própria alteração são atômicos: se a auditoria falhar, a operação é desfeita. O histórico em `/auditoria/` é somente leitura.

A auditoria registra operações a partir da ativação desta versão; ela não reconstrói alterações anteriores. Operações feitas diretamente no banco, pelo shell ou por integrações que não usem as telas não são capturadas por esse mecanismo.

O cancelamento exige motivo e confirmação por POST. A doação cancelada mantém seus dados e o número do comprovante, mas não pode ser editada nem gerar novos PDFs. Ela permanece nas listagens e no histórico, porém não entra nos indicadores, consultas financeiras, totais do doador ou exportações. PDFs já baixados ou impressos não podem ser recolhidos automaticamente.

## Configuração

A aplicação carrega variáveis de ambiente e, se existir, o arquivo `.env` na raiz do projeto. `.env.example` lista as opções disponíveis.

| Variável | Uso |
| --- | --- |
| `DJANGO_SECRET_KEY` | Chave secreta do Django. Use uma chave forte e privada fora do desenvolvimento local. |
| `DJANGO_DEBUG` | Ativa ou desativa o modo de depuração. Desative em produção. |
| `DJANGO_ALLOWED_HOSTS` | Hosts permitidos, separados por vírgula. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Origens confiáveis para CSRF, separadas por vírgula e incluindo esquema quando necessário. |
| `DJANGO_DATABASE_ENGINE` | `sqlite` (padrão) ou `postgres`/`postgresql`. |
| `DJANGO_DATABASE_PATH` | Caminho do arquivo SQLite; padrão `db.sqlite3`. |
| `DJANGO_DATABASE_NAME`, `DJANGO_DATABASE_USER`, `DJANGO_DATABASE_PASSWORD` | Nome, usuário e senha obrigatórios ao usar PostgreSQL. |
| `DJANGO_DATABASE_HOST`, `DJANGO_DATABASE_PORT` | Endereço e porta do PostgreSQL; padrões `127.0.0.1` e `5432`. |
| `DJANGO_DATABASE_CONN_MAX_AGE` | Duração, em segundos, das conexões persistentes do PostgreSQL. |
| `DJANGO_STATIC_URL`, `DJANGO_STATIC_ROOT` | URL e diretório de destino dos arquivos estáticos. |
| `DJANGO_FORCE_SCRIPT_NAME` | Prefixo opcional para implantação sob um subcaminho. |
| `DJANGO_SECURE_SSL_REDIRECT` | Redireciona requisições HTTP para HTTPS. |
| `DJANGO_SESSION_COOKIE_SECURE`, `DJANGO_CSRF_COOKIE_SECURE` | Restringe cookies de sessão e CSRF a conexões HTTPS. |
| `DJANGO_SECURE_HSTS_SECONDS` | Duração da política HSTS, em segundos. |
| `DJANGO_EMAIL_BACKEND` | Backend de e-mail do Django; o padrão imprime mensagens no console. |
| `RECEIPT_ORGANIZATION_NAME` | Nome da organização usado nos comprovantes. |

Para PostgreSQL, configure `DJANGO_DATABASE_ENGINE=postgres` e informe `DJANGO_DATABASE_NAME`, `DJANGO_DATABASE_USER` e `DJANGO_DATABASE_PASSWORD`. O driver PostgreSQL está incluído nas dependências do projeto.

## Backup do SQLite

Execute o comando abaixo para criar uma cópia consistente e verificada em `backups/`:

```powershell
uv run python manage.py backup_database
```

É possível informar outro destino:

```powershell
uv run python manage.py backup_database --directory "C:\Backups\Donations"
```

Cada execução cria um novo arquivo, sem substituir ou remover backups existentes. O comando usa a API de backup do SQLite e verifica a integridade e as referências do arquivo gerado. Ele requer um banco SQLite em arquivo, não possui endpoint web e não copia `.env`, código ou arquivos de mídia.

Proteja a pasta de destino: o backup contém dados pessoais, usuários e auditoria. Agendamento, armazenamento externo, retenção e restauração precisam ser configurados operacionalmente. Antes de restaurar, teste a cópia em ambiente isolado; substituir o banco em uso requer interromper a aplicação.

## Testes e verificações

```powershell
uv run python manage.py test apps
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
```

## Implantação

Este repositório fornece a aplicação e suas migrations; a implantação precisa preparar o ambiente e o banco. Antes de expor o serviço, configure chave secreta, `DJANGO_DEBUG=false`, hosts permitidos, HTTPS e cookies seguros, aplique as migrations, crie o superusuário e execute `setup_roles`. Configure também a entrega dos arquivos estáticos e os backups conforme a operação do ambiente.

A emissão de comprovantes usa o modelo em `static/pdf/comprovante-modelo.png`. Confirme o resultado físico e o alinhamento desse modelo no ambiente de implantação antes do uso oficial.
