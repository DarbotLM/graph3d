<p align="center">
  <a href="https://graph3dlabs.ai"><img src="https://raw.githubusercontent.com/DarbotLM/graph3d/v4/docs/logo-text.svg" width="260" height="64" alt="Graph3d"/></a>
</p>

<p align="center">
  <a href="../../README.md">English</a> | <a href="README.zh-CN.md">简体中文</a> | <a href="README.ja-JP.md">日本語</a> | <a href="README.ko-KR.md">한국어</a> | <a href="README.de-DE.md">Deutsch</a> | <a href="README.fr-FR.md">Français</a> | <a href="README.es-ES.md">Español</a> | <a href="README.hi-IN.md">हिन्दी</a> | <a href="README.pt-BR.md">Português</a> | <a href="README.ru-RU.md">Русский</a> | <a href="README.ar-SA.md">العربية</a> | <a href="README.it-IT.md">Italiano</a> | <a href="README.pl-PL.md">Polski</a> | <a href="README.nl-NL.md">Nederlands</a> | <a href="README.tr-TR.md">Türkçe</a> | <a href="README.uk-UA.md">Українська</a> | <a href="README.vi-VN.md">Tiếng Việt</a> | <a href="README.id-ID.md">Bahasa Indonesia</a> | <a href="README.sv-SE.md">Svenska</a> | <a href="README.el-GR.md">Ελληνικά</a> | <a href="README.ro-RO.md">Română</a> | <a href="README.cs-CZ.md">Čeština</a> | <a href="README.fi-FI.md">Suomi</a> | <a href="README.da-DK.md">Dansk</a> | <a href="README.no-NO.md">Norsk</a> | <a href="README.hu-HU.md">Magyar</a> | <a href="README.th-TH.md">ภาษาไทย</a> | <a href="README.uz-UZ.md">Oʻzbekcha</a> | <a href="README.zh-TW.md">繁體中文</a>
</p>

<p align="center">
  <a href="https://www.ycombinator.com/companies/graph3d"><img src="https://img.shields.io/badge/Y%20Combinator-S26-F0652F?style=flat&logo=ycombinator&logoColor=white" alt="YC S26"/></a>
  <a href="https://safishamsi.gumroad.com/l/qetvlo"><img src="https://img.shields.io/badge/Book-The%20Memory%20Layer-2ea44f?style=flat&logo=gitbook&logoColor=white" alt="The Memory Layer"/></a>
  <a href="https://github.com/DarbotLM/graph3d/actions/workflows/ci.yml"><img src="https://github.com/DarbotLM/graph3d/actions/workflows/ci.yml/badge.svg?branch=v8" alt="CI"/></a>
  <a href="https://pypi.org/project/graph3d/"><img src="https://img.shields.io/pypi/v/graph3d" alt="PyPI"/></a>
  <a href="https://clickpy.clickhouse.com/dashboard/graph3d"><img src="https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fsql-clickhouse.clickhouse.com%2F%3Fquery%3DSELECT%2520concat%2528toString%2528round%2528sum%2528count%2529%2F1000%2529%2529%2C%2520%2527k%2527%2529%2520AS%2520c%2520FROM%2520pypi.pypi_downloads%2520WHERE%2520project%253D%2527graph3d%2527%2520FORMAT%2520JSON%26user%3Ddemo&query=%24.data%5B0%5D.c&label=downloads&color=blue" alt="Downloads"/></a>
  <a href="https://github.com/sponsors/safishamsi"><img src="https://img.shields.io/badge/sponsor-safishamsi-ea4aaa?logo=github-sponsors" alt="Sponsor"/></a>
  <a href="https://www.linkedin.com/in/safi-shamsi"><img src="https://img.shields.io/badge/LinkedIn-Safi%20Shamsi-0077B5?logo=linkedin" alt="LinkedIn"/></a>
  <a href="https://x.com/graph3d"><img src="https://img.shields.io/badge/X-graph3d-000000?logo=x&logoColor=white" alt="X"/></a>
</p>

<p align="center">
  <a href="https://star-history.com/#DarbotLM/graph3d&Date">
    <img src="https://api.star-history.com/svg?repos=DarbotLM/graph3d&type=Date" alt="Star History Chart" width="370"/>
  </a>
</p>

Введіть `/graph3d` у своєму ШІ-асистенті для кодингу, і він нанесе весь ваш проект — код, документи, PDF, зображення, відео — на граф знань, який можна запитувати замість того, щоб шукати по файлах.

Працює в Claude Code, Codex, OpenCode, Cursor, Gemini CLI, GitHub Copilot CLI, VS Code Copilot Chat, Aider, OpenClaw, Factory Droid, Trae, Hermes, Kimi Code, Kiro, Pi та Google Antigravity.

```
/graph3d .
```

Це все. Ви отримуєте три файли:

```
graph3d-out/
├── graph.html       відкрийте в будь-якому браузері — клікайте по вузлах, фільтруйте, шукайте
├── GRAPH_REPORT.md  основне: ключові концепції, неочікувані зв’язки, запропоновані запитання
└── graph.json       повний граф — запитуйте його будь-коли без повторного перечитування ваших файлів
```

Для читабельної сторінки архітектури з діаграмами викликів Mermaid виконайте:

```bash
graph3d export callflow-html
```

---

## Вимоги

| Вимога | Мінімум | Перевірка | Встановлення |
|---|---|---|---|
| Python | 3.10+ | `python --version` | [python.org](https://www.python.org/downloads/) |
| uv *(рекомендовано)* | будь-яка | `uv --version` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| pipx *(альтернатива)* | будь-яка | `pipx --version` | `pip install pipx` |

**Швидке встановлення на macOS (Homebrew):**
```bash
brew install python@3.12 uv
```

**Швидке встановлення на Windows:**
```powershell
winget install astral-sh.uv
```

**Ubuntu/Debian:**
```bash
sudo apt install python3.12 python3-pip pipx
# або встановити uv:
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## Встановлення

> **Офіційний пакет:** Пакет PyPI — `graph3d` (подвійна y). Інші пакети `graph3d*` на PyPI не є афілійованими. Команда CLI залишається `graph3d`.

**Крок 1 — встановити пакет:**

```bash
# Рекомендовано (uv автоматично додає graph3d до PATH):
uv tool install graph3d

# Альтернативи:
pipx install graph3d
pip install graph3d
```

**Крок 2 — зареєструвати навичку у вашому ШІ-асистенті:**

```bash
graph3d install
```

Це все. Відкрийте асистента і введіть `/graph3d .`

Щоб встановити навичку в поточний репозиторій замість профілю користувача, додайте `--project`:

```bash
graph3d install --project
graph3d install --project --platform codex
```

Встановлення на рівні проєкту записуються в поточну директорію, наприклад .claude/skills/graph3d/SKILL.md або .agents/skills/graph3d/SKILL.md, і виводять підказку git add для файлів, які можна закомітити. Команди для окремих платформ, що підтримують інсталяції на рівні проєкту, приймають той самий прапорець, наприклад graph3d claude install --project або graph3d codex install --project.

> **Примітка для PowerShell:** Використовуйте `graph3d .` замість `/graph3d .` — ведучий слеш є роздільником шляху в PowerShell.

> **`graph3d: command not found`?** Використовуйте `uv tool install graph3d` або `pipx install graph3d` — обидва автоматично додають CLI до PATH. При використанні звичайного `pip` додайте `~/.local/bin` (Linux) або `~/Library/Python/3.x/bin` (Mac) до вашого PATH, або запустіть `python -m graph3d`.

### Оберіть платформу

| Платформа | Команда встановлення |
|----------|----------------|
| Claude Code (Linux/Mac) | `graph3d install` |
| Claude Code (Windows) | `graph3d install --platform windows` |
| Codex | `graph3d install --platform codex` |
| OpenCode | `graph3d install --platform opencode` |
| GitHub Copilot CLI | `graph3d install --platform copilot` |
| VS Code Copilot Chat | `graph3d vscode install` |
| Aider | `graph3d install --platform aider` |
| OpenClaw | `graph3d install --platform claw` |
| Factory Droid | `graph3d install --platform droid` |
| Trae | `graph3d install --platform trae` |
| Trae CN | `graph3d install --platform trae-cn` |
| Gemini CLI | `graph3d install --platform gemini` |
| Hermes | `graph3d install --platform hermes` |
| Kimi Code | `graph3d install --platform kimi` |
| Kiro IDE/CLI | `graph3d kiro install` |
| Pi coding agent | `graph3d install --platform pi` |
| Cursor | `graph3d cursor install` |
| Google Antigravity | `graph3d antigravity install` |

> Користувачам Codex: також додайте `multi_agent = true` під `[features]` у `~/.codex/config.toml`.
> Codex використовує `$graph3d` замість `/graph3d`.

### Додаткові пакети (опціонально)

Встановіть лише те, що потрібно:

| Пакет | Що додає | Встановлення |
|---|---|---|
| `pdf` | Вилучення PDF | `pip install "graph3d[pdf]"` |
| `office` | Підтримка `.docx` та `.xlsx` | `pip install "graph3d[office]"` |
| `google` | Рендеринг Google Sheets | `pip install "graph3d[google]"` |
| `video` | Транскрипція відео/аудіо (faster-whisper + yt-dlp) | `pip install "graph3d[video]"` |
| `mcp` | MCP stdio-сервер | `pip install "graph3d[mcp]"` |
| `neo4j` | Підтримка надсилання до Neo4j | `pip install "graph3d[neo4j]"` |
| `svg` | Експорт графу в SVG | `pip install "graph3d[svg]"` |
| `leiden` | Виявлення спільнот Leiden (лише Python < 3.13) | `pip install "graph3d[leiden]"` |
| `ollama` | Локальний вивід Ollama | `pip install "graph3d[ollama]"` |
| `openai` | OpenAI / OpenAI-сумісні API | `pip install "graph3d[openai]"` |
| `gemini` | Google Gemini API | `pip install "graph3d[gemini]"` |
| `bedrock` | AWS Bedrock (використовує IAM, без API-ключа) | `pip install "graph3d[bedrock]"` |
| `sql` | Вилучення SQL схем | `pip install "graph3d[sql]"` |
| `all` | Все вищезазначене | `pip install "graph3d[all]"` |

---

## Змусьте асистента завжди використовувати граф

Виконайте один раз у своєму проекті після побудови графу:

| Платформа | Команда |
|----------|---------|
| Claude Code | `graph3d claude install` |
| Codex | `graph3d codex install` |
| OpenCode | `graph3d opencode install` |
| GitHub Copilot CLI | `graph3d copilot install` |
| VS Code Copilot Chat | `graph3d vscode install` |
| Aider | `graph3d aider install` |
| OpenClaw | `graph3d claw install` |
| Factory Droid | `graph3d droid install` |
| Trae | `graph3d trae install` |
| Trae CN | `graph3d trae-cn install` |
| Cursor | `graph3d cursor install` |
| Gemini CLI | `graph3d gemini install` |
| Hermes | `graph3d hermes install` |
| Kimi Code | `graph3d install --platform kimi` |
| Kiro IDE/CLI | `graph3d kiro install` |
| Pi coding agent | `graph3d pi install` |
| Google Antigravity | `graph3d antigravity install` |

Це записує невеликий конфігураційний файл, який каже асистенту звертатися до графу знань для питань про кодову базу — надаючи перевагу локалізованим запитам на кшталт `graph3d query "<питання>"` замість читання повного звіту або пошуку по сирих файлах. На платформах, що підтримують хуки з корисним навантаженням (Claude Code, Gemini CLI), хук спрацьовує автоматично перед пошуковими викликами інструментів і спрямовує асистента до графу. На інших (Codex, OpenCode, Cursor тощо) постійні файли інструкцій (`AGENTS.md`, `.cursor/rules/` тощо) забезпечують таке саме керівництво. `GRAPH_REPORT.md` все ще доступний для загального огляду архітектури.

Щоб видалити graph3d з усіх платформ одразу: `graph3d uninstall` (додайте `--purge`, щоб також видалити `graph3d-out/`). Або скористайтеся командою для конкретної платформи (напр. `graph3d claude uninstall`).

---

## Що є у звіті

- **Вузли-боги** — найбільш пов'язані концепції у вашому проекті. Через них проходить все.
- **Несподівані зв'язки** — зв'язки між речами з різних файлів або модулів. Відсортовані за ступенем несподіваності.
- **«Чому»** — рядкові коментарі (`# NOTE:`, `# WHY:`, `# HACK:`), рядки документації та обґрунтування дизайну з документів витягуються як окремі вузли, пов'язані з кодом, який вони пояснюють.
- **Запропоновані питання** — 4–5 питань, на які граф унікально здатний відповісти.
- **Теги впевненості** — кожен виведений зв'язок позначений як `EXTRACTED`, `INFERRED` або `AMBIGUOUS`. Ви завжди знаєте, що знайдено, а що виведено.

---

## Які файли підтримуються

| Тип | Розширення |
|------|-----------|
| Код (31 мова) | `.py .ts .js .jsx .tsx .mjs .go .rs .java .c .cpp .h .hpp .rb .cs .kt .scala .php .swift .lua .luau .zig .ps1 .ex .exs .m .mm .jl .vue .svelte .astro .groovy .gradle .dart .v .sv .sql .f .f90 .f95 .f03 .f08 .pas .pp .dpr .dpk .lpr .inc .dfm .lfm .lpk .sh .bash .json` |
| Документи | `.md .mdx .qmd .html .txt .rst .yaml .yml` |
| Office | `.docx .xlsx` (потрібен `pip install graph3d[office]`) |
| Google Workspace | `.gdoc .gsheet .gslides` (опціонально; потрібна автентифікація `gws` та `--google-workspace`; Sheets потребує `pip install graph3d[google]`) |
| PDF | `.pdf` |
| Зображення | `.png .jpg .webp .gif` |
| Відео / Аудіо | `.mp4 .mov .mp3 .wav` та інші (потрібен `pip install graph3d[video]`) |
| YouTube / URL | будь-який URL відео (потрібен `pip install graph3d[video]`) |

Код витягується локально без API-викликів (AST через tree-sitter). Все інше обробляється через API моделі вашого ШІ-асистента.

Файли `.gdoc`, `.gsheet` та `.gslides` з Google Drive for desktop — це ярлики-посилання, а не вміст документів. Щоб включити нативні Google Docs, Sheets та Slides у безголове витягування, встановіть та автентифікуйте [`gws` CLI](https://github.com/googleworkspace/cli), потім запустіть:

```bash
pip install "graph3d[google]"  # потрібен для рендерингу таблиць Google Sheets
gws auth login -s drive
graph3d extract ./docs --google-workspace
```

Також можна встановити `GRAPH3D_GOOGLE_WORKSPACE=1`. Graph3d експортує ярлики в `graph3d-out/converted/` як Markdown-сайдкари, а потім витягує ці файли.

---

## Часті команди

```bash
/graph3d .                        # побудувати граф для поточної папки
/graph3d ./docs --update          # повторно витягнути лише змінені файли
/graph3d . --cluster-only         # перезапустити кластеризацію без повторного витягування
/graph3d . --cluster-only --resolution 1.5      # більш дрібні спільноти
/graph3d . --cluster-only --exclude-hubs 99     # виключити утилітарні суперхаби з рейтингів “god-node” вузлів-богів
/graph3d . --no-viz               # пропустити HTML, лише звіт + JSON
/graph3d . --wiki                 # побудувати markdown-вікі з графу
graph3d export callflow-html      # Mermaid архітектура/flow-викликів HTML (автоматично регенерується на кожен git-коміт, якщо встановлений hook)

/graph3d query "що пов'язує auth з базою даних?"
/graph3d path "UserService" "DatabasePool"
/graph3d explain "RateLimiter"

/graph3d add https://arxiv.org/abs/1706.03762   # завантажити статтю і додати її
/graph3d add <youtube-url>                       # транскрибувати і додати відео

graph3d hook install              # автоматичне перебудування при git-коміті
graph3d merge-graphs a.json b.json              # об'єднати два графи

graph3d prs                       # дашборд PR: стан CI, статус рев’ю, мапінг worktree
graph3d prs 42                    # детальний огляд PR #42 з впливом на граф
graph3d prs --triage              # ШІ оцінює вашу чергу рев’ю (використовує будь-який налаштований бекенд)
graph3d prs --conflicts           # PR-и, що ділять спільні графові спільноти — ризик порядку злиття
```

Дивіться [повний довідник команд](#повний-довідник-команд) нижче.

---

## Ігнорування файлів

Створіть `.graph3dignore` у кореневій директорії проекту — той самий синтаксис, що й `.gitignore`, включно з запереченням `!`:

```
# .graph3dignore
node_modules/
dist/
*.generated.py

# індексувати лише src/, ігнорувати все інше
*
!src/
!src/**
```

---

## Налаштування для команди

`graph3d-out/` призначений для коміту в git, щоб кожен у команді починав із картою.

**Рекомендовані доповнення до `.gitignore`:**
```
graph3d-out/manifest.json    # базується на mtime, ламається після git clone
graph3d-out/cost.json        # лише локальний
# graph3d-out/cache/         # опціонально: комітьте для швидкості, пропустіть для меншого репо
```

**Робочий процес:**
1. Одна людина запускає `/graph3d .` і комітить `graph3d-out/`.
2. Усі виконують pull — їхній асистент одразу читає граф.
3. Запустіть `graph3d hook install` для автоматичного перебудування після кожного коміту (лише AST, без витрат API). Щоб також уникнути маркерів конфліктів у `graph.json`, налаштуйте merge driver окремо: додайте `graph3d-out/graph.json merge=graph3d` до `.gitattributes` і зареєструйте driver командою `git config merge.graph3d.driver "graph3d merge-driver %O %A %B"`.
4. Коли документи або статті змінюються, запустіть `/graph3d --update`, щоб оновити ці вузли.

---

## Використання графу напряму

```bash
# запит до графу з терміналу
graph3d query "покажи потік автентифікації"
graph3d query "що пов'язує DigestAuth з Response?" --graph graph3d-out/graph.json

# відкрити граф як MCP-сервер (для повторного доступу через інструменти)
python -m graph3d.serve graph3d-out/graph.json

# зареєструвати в Kimi Code:
kimi mcp add --transport stdio graph3d -- python -m graph3d.serve graph3d-out/graph.json
```

MCP-сервер надає асистенту структурований доступ: `query_graph`, `get_node`, `get_neighbors`, `shortest_path`, `list_prs`, `get_pr_impact`, `triage_prs`.

> **Примітка для WSL / Linux:** Ubuntu постачає `python3`, а не `python`. Використовуйте venv, щоб уникнути конфліктів:
> ```bash
> python3 -m venv .venv && .venv/bin/pip install "graph3d[mcp]"
> ```

---

## Змінні середовища

Потрібні лише для **headless / CI витягування** (`graph3d extract`). При запуску через навичку `/graph3d` у вашому IDE API моделі надається сесією IDE — додаткових ключів не потрібно.

| Змінна | Використання | Коли потрібна |
|---|---|---|
| `ANTHROPIC_API_KEY` | Backend Claude (Anthropic) | `--backend claude` |
| `GEMINI_API_KEY` або `GOOGLE_API_KEY` | Backend Google Gemini | `--backend gemini` |
| `OPENAI_API_KEY` | OpenAI або OpenAI-сумісні API | `--backend openai` |
| `DEEPSEEK_API_KEY` | Backend DeepSeek | `--backend deepseek` |
| `MOONSHOT_API_KEY` | Backend Kimi Code | `--backend kimi` |
| `OLLAMA_BASE_URL` | URL локального виводу Ollama | `--backend ollama` (типово: `http://localhost:11434`) |
| `OLLAMA_MODEL` | Назва моделі Ollama | `--backend ollama` (типово: автовизначення) |
| `GRAPH3D_OLLAMA_NUM_CTX` | Перевизначити розмір KV-кеш вікна Ollama | опціонально — автоматично за замовчуванням |
| `GRAPH3D_OLLAMA_KEEP_ALIVE` | Хвилини утримання моделі Ollama завантаженою | опціонально — встановіть `0` для вивантаження після кожного шматка |
| `AWS_*` / `~/.aws/credentials` | AWS Bedrock — стандартний ланцюг облікових даних | `--backend bedrock` (без API-ключа, використовує IAM) |
| `GRAPH3D_MAX_WORKERS` | Кількість потоків паралелізму AST | опціонально — також прапор `--max-workers` |
| `GRAPH3D_MAX_OUTPUT_TOKENS` | Підвищити ліміт виводу для щільних корпусів | опціонально — напр. `32768` для великих файлів |
| `GRAPH3D_API_TIMEOUT` | HTTP тайм-аут у секундах (типово: 600) | опціонально — також прапор `--api-timeout` |
| `GRAPH3D_FORCE` | Примусове перебудування графу навіть із меншою кількістю вузлів | опціонально — також прапор `--force` |
| `GRAPH3D_GOOGLE_WORKSPACE` | Автоввімкнення експорту Google Workspace | опціонально — встановіть в `1` |
| `GRAPH3D_TRIAGE_BACKEND` | Backend для `graph3d prs --triage` | опціонально — автовизначення з наявних ключів |
| `GRAPH3D_TRIAGE_MODEL` | Перевизначення моделі для triage | опціонально — напр. `claude-opus-4-7` |

---

## Конфіденційність

- **Файли коду** — обробляються локально через tree-sitter. Нічого не покидає ваш комп'ютер.
- **Відео / аудіо** — транскрибуються локально за допомогою faster-whisper. Нічого не покидає ваш комп'ютер.
- **Документи, PDF, зображення** — надсилаються до вашого ШІ-асистента для семантичного витягування (через навичку `/graph3d`, використовуючи модель, що запущена у вашому IDE). Безголове `graph3d extract` потребує `GEMINI_API_KEY` / `GOOGLE_API_KEY` (Gemini), `MOONSHOT_API_KEY` (Kimi), `ANTHROPIC_API_KEY` (Claude), `OPENAI_API_KEY` (OpenAI), `DEEPSEEK_API_KEY` (DeepSeek), запущеного екземпляра Ollama (`OLLAMA_BASE_URL`), AWS-облікових даних через стандартний ланцюг провайдерів (Bedrock — без API-ключа, використовує IAM) або бінарного файлу `claude` CLI (Claude Code — без API-ключа, використовує вашу підписку Claude). Прапор `--dedup-llm` використовує той самий ключ.
- Без телеметрії, без відстеження використання, без аналітики.

---

## Вирішення проблем

**`graph3d: command not found` після `pip install graph3d`**
pip встановлює скрипти в директорію bin для користувача, яка може не бути в PATH. Виправлення:
- macOS: додайте `~/Library/Python/3.x/bin` до PATH у `~/.zshrc`
- Linux: додайте `~/.local/bin` до PATH у `~/.bashrc`
- Або використовуйте `uv tool install graph3d` / `pipx install graph3d` — обидва автоматично керують PATH.

**`python -m graph3d` працює, але команда `graph3d` — ні**
PATH вашої оболонки не включає директорію скриптів Python. Використовуйте `uv` або `pipx` замість звичайного `pip`.

**`/graph3d .` викликає "path not recognized" в PowerShell**
PowerShell трактує ведучий `/` як роздільник шляху. Використовуйте `graph3d .` (без слеша) на Windows.

**Граф має менше вузлів після `--update` або перебудови**
Якщо рефакторинг видалив файли, старі вузли залишаються. Передайте `--force` (або встановіть `GRAPH3D_FORCE=1`), щоб перезаписати навіть якщо перебудова має менше вузлів.

**Граф має дублікати вузлів для однієї сутності (фантомні дублікати)**
Це трапляється, коли семантичне та AST-витягування не погодилось щодо формату ID вузла. Запустіть повне повторне витягування для очищення:
```bash
graph3d extract . --force
```

**Ollama вичерпує VRAM / перевищено вікно контексту**
KV-кеш вікно автоматично розраховується, але може бути завеликим для вашого GPU. Зменшіть його:
```bash
GRAPH3D_OLLAMA_NUM_CTX=8192 graph3d extract ./docs --backend ollama --token-budget 4000
```

**HTML графу занадто великий для відкриття в браузері (>5000 вузлів)**
Пропустіть генерацію HTML і використовуйте JSON напряму:
```bash
graph3d cluster-only ./my-project --no-viz
graph3d query "..."
```

**`graph.json` має маркери конфліктів після одночасного коміту двох розробників**
`graph3d hook install` встановлює хуки post-commit і post-checkout, але не налаштовує merge driver автоматично. Щоб запобігти маркерам конфліктів, додайте `graph3d-out/graph.json merge=graph3d` до `.gitattributes`, а потім виконайте `git config merge.graph3d.driver "graph3d merge-driver %O %A %B"`.

**Вилучення повертає порожні вузли/ребра для документів або PDF**
Документи та PDF потребують LLM-виклику. Перевірте, що API-ключ встановлено і backend правильний:
```bash
ANTHROPIC_API_KEY=sk-... graph3d extract ./docs --backend claude
```

**Попередження про невідповідність версій навички у вашому IDE**
Встановлена версія graph3d відрізняється від файлу навички. Оновіть:
```bash
uv tool upgrade graph3d
graph3d install  # перезаписує файл навички
```

---

## Повний довідник команд

```
/graph3d                          # запустити в поточному каталозі
/graph3d ./raw                    # запустити у конкретній папці
/graph3d ./raw --mode deep        # більш агресивне витягування зв'язків
/graph3d ./raw --update           # повторно витягнути лише змінені файли
/graph3d ./raw --directed         # зберегти напрямок ребер
/graph3d ./raw --cluster-only     # повторна кластеризація існуючого графу
/graph3d ./raw --no-viz           # пропустити HTML-візуалізацію
/graph3d ./raw --obsidian         # згенерувати сховище Obsidian
/graph3d ./raw --wiki             # побудувати markdown-вікі для обходу агентами
/graph3d ./raw --svg              # експортувати graph.svg
/graph3d ./raw --graphml          # експортувати для Gephi / yEd
/graph3d ./raw --neo4j            # згенерувати cypher.txt для Neo4j
/graph3d ./raw --neo4j-push bolt://localhost:7687
/graph3d ./raw --watch            # автосинхронізація при зміні файлів
/graph3d ./raw --mcp              # запустити MCP stdio-сервер

/graph3d add https://arxiv.org/abs/1706.03762
/graph3d add <video-url>
/graph3d add https://... --author "Name" --contributor "Name"

/graph3d query "що пов'язує attention з optimizer?"
/graph3d query "..." --dfs --budget 1500
/graph3d path "DigestAuth" "Response"
/graph3d explain "SwinTransformer"

graph3d uninstall                 # видалити з усіх платформ одразу
graph3d uninstall --purge         # також видалити graph3d-out/
graph3d uninstall --project --platform codex  # видалити лише файли проектного встановлення

graph3d hook install              # хуки post-commit + post-checkout
graph3d hook uninstall
graph3d hook status

graph3d claude install / uninstall
graph3d codex install / uninstall
graph3d opencode install
graph3d cursor install / uninstall
graph3d gemini install / uninstall
graph3d copilot install / uninstall
graph3d aider install / uninstall
graph3d claw install / uninstall
graph3d droid install / uninstall
graph3d trae install / uninstall
graph3d trae-cn install / uninstall
graph3d hermes install / uninstall
graph3d kiro install / uninstall
graph3d antigravity install / uninstall

graph3d extract ./docs                        # headless LLM-витягування для CI (без IDE)
graph3d extract ./docs --backend gemini       # явний backend: gemini, kimi, claude, openai, deepseek, ollama, bedrock або claude-cli
graph3d extract ./docs --backend gemini --model gemini-3.1-pro-preview
graph3d extract ./docs --backend ollama       # локальний Ollama (встановіть OLLAMA_BASE_URL / OLLAMA_MODEL) — без API-ключа для loopback
GRAPH3D_OLLAMA_NUM_CTX=32768 graph3d extract ./docs --backend ollama   # перевизначити KV-кеш вікно (автоматично за замовчуванням)
GRAPH3D_OLLAMA_KEEP_ALIVE=0 graph3d extract ./docs --backend ollama    # вивантажити модель після кожного шматка (економить VRAM на малих GPU)
graph3d extract ./docs --backend bedrock      # AWS Bedrock через IAM — без API-ключа, використовує ланцюг облікових даних AWS
graph3d extract ./docs --backend claude-cli   # маршрутизація через Claude Code CLI — без API-ключа, використовує вашу підписку Claude
graph3d extract ./docs --max-workers 16       # паралелізм AST (також GRAPH3D_MAX_WORKERS)
graph3d extract ./docs --token-budget 30000   # менші семантичні шматки для локальних/малих моделей
graph3d extract ./docs --max-concurrency 2    # менше паралельних LLM-викликів (корисно для локального виводу)
graph3d extract ./docs --api-timeout 900      # довший HTTP тайм-аут для повільних локальних моделей (типово 600с)
graph3d extract ./docs --google-workspace     # експортувати .gdoc/.gsheet/.gslides через gws перед витягуванням
graph3d extract ./docs --no-cluster           # лише сире витягування, пропустити кластеризацію
graph3d extract ./docs --force                # перезаписати graph.json навіть якщо новий граф має менше вузлів (використовуйте після рефакторингу або для очищення фантомних дублікатів)
graph3d extract ./docs --dedup-llm            # LLM-арбітр для неоднозначних пар сутностей (використовує той самий API-ключ)
graph3d extract ./docs --global --as myrepo   # витягнути і зареєструвати в крос-проектний глобальний граф
GRAPH3D_MAX_OUTPUT_TOKENS=32768 graph3d extract ./docs --backend claude  # підвищити ліміт виводу для щільних корпусів

graph3d export callflow-html                       # graph3d-out/<project>-callflow.html
graph3d export callflow-html --max-sections 8      # обмежити кількість згенерованих секцій архітектури
graph3d export callflow-html --output docs/arch.html
graph3d export callflow-html ./some-repo/graph3d-out

graph3d global add graph3d-out/graph.json myrepo   # зареєструвати граф проекту в ~/.graph3d/global.json
graph3d global remove myrepo                         # видалити проект з глобального графу
graph3d global list                                  # показати всі зареєстровані репо + кількість вузлів/ребер
graph3d global path                                  # вивести шлях до файлу глобального графу

graph3d prs                              # дашборд PR: CI, рев’ю, worktree, вплив на граф
graph3d prs 42                           # детальний огляд PR #42
graph3d prs --triage                     # AI ранжування пріоритизації (автоматично визначає бекенд з середовища)
graph3d prs --worktrees                  # worktree → гілка → PR зіставлення
graph3d prs --conflicts                  # PR-и, що ділять спільні графові спільноти (ризик порядку злиття)
graph3d prs --base main                  # фільтр PR-ів за цільовою базовою гілкою
graph3d prs --repo owner/repo            # запустити для іншого GitHub-репо
GRAPH3D_TRIAGE_BACKEND=kimi graph3d prs --triage   # використовувати конкретний backend для triage

graph3d clone https://github.com/karpathy/nanoGPT
graph3d merge-graphs a.json b.json --out merged.json
graph3d --version                                    # вивести встановлену версію
graph3d watch ./src
graph3d check-update ./src
graph3d update ./src
graph3d update ./src --no-cluster  # пропустити рекластеризацію, записати лише сирий AST граф
graph3d update ./src --force       # перезаписати навіть якщо новий граф має менше вузлів
graph3d cluster-only ./my-project
graph3d cluster-only ./my-project --graph path/to/graph.json  # власне розташування графу
graph3d cluster-only ./my-project --resolution 1.5            # більше, менших спільнот
graph3d cluster-only ./my-project --exclude-hubs 99           # виключити вузли p99 ступеня з розбиття
```

---

## Дізнатися більше

- [Як це працює](../how-it-works.md) — пайплайн витягування, виявлення спільнот, оцінка впевненості, бенчмарки
- [ARCHITECTURE.md](../../ARCHITECTURE.md) — опис модулів, як додати мову
- [Опціональні інтеграції](../docker-mcp-sqlite.md) — Docker MCP Toolkit + SQLite

---

## Побудовано на graph3d — Penpax

[**Penpax**](https://graph3dlabs.ai) — це завжди активний шар поверх graph3d, він застосовує той самий графовий підхід до всього робочого життя: зустрічей, історії браузера, email-ів, файлів і коду, постійно оновлюючись у фоновому режимі.

Створений для людей, чия робота розкидана по сотнях розмов і документів, які неможливо повністю відтворити. Без хмари, повністю на пристрої.

**Безкоштовна пробна версія незабаром.** [Приєднайтесь до списку очікування →](https://graph3dlabs.ai)

---

<details>
<summary>Участь у розробці</summary>

### Налаштування розробки

Клонуйте репо і встановіть у редагованому режимі:

```bash
git clone https://github.com/DarbotLM/graph3d.git
cd graph3d
git checkout v8                        # гілка активної розробки

# Створіть віртуальне середовище (потрібен Python 3.10+):
python3 -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate

# Встановіть у редагованому режимі з усіма опціональними пакетами:
pip install -e ".[all]"
```

Перевірте редаговане встановлення:
```bash
graph3d --version
python -c "import graph3d; print(graph3d.__file__)"
```

### Запуск тестів

```bash
pip install pytest
pytest tests/ -q                       # запустити весь набір тестів
pytest tests/test_extract.py -q        # один модуль
pytest tests/ -q -k "python"           # фільтрація за назвою
```

> Примітка для macOS: набір тестів включає обидва файли `sample.f90` та `sample.F90`. Вони конфліктують на файлових системах HFS+ / APFS без урахування регістру. Запускайте на Linux або в Docker-контейнері, якщо потрібно тестувати обидва варіанти Fortran одночасно.

### Робочий процес з git

- Активна розробка відбувається в гілці `v8`.
- Стиль комітів: `fix: <опис>` / `feat: <опис>` / `docs: <опис>`
- Перед відкриттям PR запустіть `pytest tests/ -q` і переконайтесь, що він проходить.
- Додайте файл-фікстуру до `tests/fixtures/` і тести до `tests/test_languages.py` для будь-якого нового екстрактора мови.

### Що варто додати

Найкорисніший внесок — це **опрацьовані приклади**. Запустіть `/graph3d` на реальному корпусі, збережіть результат у `worked/{slug}/`, напишіть чесний `review.md` про те, що граф зробив правильно і неправильно, і відкрийте PR.

**Помилки витягування** — відкрийте issue з вхідним файлом, записом кешу (`graph3d-out/cache/`) і тим, що було пропущено або неправильно.

Дивіться [ARCHITECTURE.md](../../ARCHITECTURE.md) щодо відповідальностей модулів і того, як додати мову.

</details>
