<p align="center">
  <img src="https://raw.githubusercontent.com/DarbotLM/graph3d/v4/docs/logo-text.svg" width="260" height="64" alt="Graph3d"/>
</p>

<p align="center">
  <a href="../../README.md">English</a> | <a href="README.zh-CN.md">简体中文</a> | <a href="README.ja-JP.md">日本語</a> | <a href="README.ko-KR.md">한국어</a> | <a href="README.de-DE.md">Deutsch</a> | <a href="README.fr-FR.md">Français</a> | <a href="README.es-ES.md">Español</a> | <a href="README.hi-IN.md">हिन्दी</a> | <a href="README.pt-BR.md">Português</a> | <a href="README.ru-RU.md">Русский</a> | <a href="README.ar-SA.md">العربية</a> | <a href="README.it-IT.md">Italiano</a> | <a href="README.pl-PL.md">Polski</a> | <a href="README.nl-NL.md">Nederlands</a> | <a href="README.tr-TR.md">Türkçe</a> | <a href="README.uk-UA.md">Українська</a> | <a href="README.vi-VN.md">Tiếng Việt</a> | <a href="README.id-ID.md">Bahasa Indonesia</a> | <a href="README.sv-SE.md">Svenska</a> | <a href="README.el-GR.md">Ελληνικά</a> | <a href="README.ro-RO.md">Română</a> | <a href="README.cs-CZ.md">Čeština</a> | <a href="README.fi-FI.md">Suomi</a> | <a href="README.da-DK.md">Dansk</a> | <a href="README.no-NO.md">Norsk</a> | <a href="README.hu-HU.md">Magyar</a> | <a href="README.th-TH.md">ภาษาไทย</a> | <a href="README.uz-UZ.md">Oʻzbekcha</a> | <a href="README.zh-TW.md">繁體中文</a>
</p>

<p align="center">
  <a href="https://github.com/DarbotLM/graph3d/actions/workflows/ci.yml"><img src="https://github.com/DarbotLM/graph3d/actions/workflows/ci.yml/badge.svg?branch=v4" alt="CI"/></a>
  <a href="https://pypi.org/project/graph3d/"><img src="https://img.shields.io/pypi/v/graph3d" alt="PyPI"/></a>
  <a href="https://pepy.tech/project/graph3d"><img src="https://static.pepy.tech/badge/graph3d" alt="Downloads"/></a>
  <a href="https://github.com/sponsors/safishamsi"><img src="https://img.shields.io/badge/sponsor-safishamsi-ea4aaa?logo=github-sponsors" alt="Sponsor"/></a>
  <a href="https://www.linkedin.com/in/safi-shamsi"><img src="https://img.shields.io/badge/LinkedIn-Safi%20Shamsi-0077B5?logo=linkedin" alt="LinkedIn"/></a>
</p>

**Uma habilidade para assistentes de código IA.** Digite `/graph3d` no Claude Code, Codex, OpenCode, Cursor, Gemini CLI, GitHub Copilot CLI, VS Code Copilot Chat, Aider, OpenClaw, Factory Droid, Trae, Hermes, Kiro ou Google Antigravity — ele lê seus arquivos, constrói um grafo de conhecimento e devolve a você estrutura que você não sabia que existia. Entenda uma base de código mais rapidamente. Encontre o "porquê" por trás das decisões arquiteturais.

Totalmente multimodal. Adicione código, PDFs, markdown, capturas de tela, diagramas, fotos de quadros brancos, imagens em outros idiomas, ou arquivos de vídeo e áudio — graph3d extrai conceitos e relações de tudo isso e os conecta em um único grafo. Vídeos são transcritos localmente com Whisper usando um prompt adaptado ao domínio derivado do seu corpus. 30+ linguagens de programação suportadas via tree-sitter AST (Python, JS, TS, Go, Rust, Java, C, C++, Ruby, C#, Kotlin, Scala, PHP, Swift, Lua, Zig, PowerShell, Elixir, Objective-C, Julia, Verilog, SystemVerilog, Vue, Svelte, Dart).

> Andrej Karpathy mantém uma pasta `/raw` onde deposita papers, tweets, capturas de tela e notas. graph3d é a resposta para esse problema — 71,5x menos tokens por consulta versus ler os arquivos brutos, persistente entre sessões, honesto sobre o que foi encontrado versus inferido.

```
/graph3d .                        # funciona em qualquer pasta — seu código, notas, papers, tudo
```

```
graph3d-out/
├── graph.html       grafo interativo — abrir em qualquer navegador, clicar em nós, pesquisar
├── GRAPH_REPORT.md  nós deus, conexões surpreendentes, perguntas sugeridas
├── graph.json       grafo persistente — consultar semanas depois sem reler
└── cache/           cache SHA256 — re-execuções processam apenas arquivos modificados
```

Adicione um arquivo `.graph3dignore` para excluir pastas:

```
# .graph3dignore
vendor/
node_modules/
dist/
*.generated.py
```

Mesma sintaxe do `.gitignore`.

## Como funciona

graph3d executa em três passes. Primeiro, uma passagem AST determinística extrai estrutura de arquivos de código (classes, funções, importações, grafos de chamadas, docstrings, comentários de justificativa) sem LLM. Segundo, arquivos de vídeo e áudio são transcritos localmente com faster-whisper. Terceiro, subagentes Claude executam em paralelo sobre documentos, papers, imagens e transcrições para extrair conceitos, relações e justificativas de design. Os resultados são mesclados em um grafo NetworkX, agrupados com detecção de comunidades Leiden, e exportados como HTML interativo, JSON consultável e um relatório de auditoria em linguagem natural.

**O clustering é baseado em topologia de grafo — sem embeddings.** Leiden encontra comunidades por densidade de arestas. As arestas de similaridade semântica que Claude extrai (`semantically_similar_to`, marcadas INFERRED) já estão no grafo. A estrutura do grafo é o sinal de similaridade — nenhum passo de embedding separado ou banco de dados vetorial é necessário.

Cada relação é marcada como `EXTRACTED` (encontrada diretamente na fonte), `INFERRED` (inferência razoável com pontuação de confiança) ou `AMBIGUOUS` (marcada para revisão).

## Instalação

**Requisitos:** Python 3.10+ e um de: [Claude Code](https://claude.ai/code), [Codex](https://openai.com/codex), [OpenCode](https://opencode.ai), [Cursor](https://cursor.com), [Gemini CLI](https://github.com/google-gemini/gemini-cli), [GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli), [VS Code Copilot Chat](https://code.visualstudio.com/docs/copilot/overview), [Aider](https://aider.chat), [OpenClaw](https://openclaw.ai), [Factory Droid](https://factory.ai), [Trae](https://trae.ai), [Kiro](https://kiro.dev), Hermes ou [Google Antigravity](https://antigravity.google)

```bash
# Recomendado — funciona no Mac e Linux sem configurar o PATH
uv tool install graph3d && graph3d install
# ou com pipx
pipx install graph3d && graph3d install
# ou pip simples
pip install graph3d && graph3d install
```

> **Pacote oficial:** O pacote PyPI chama-se `graph3d` (instalar com `pip install graph3d`). Outros pacotes chamados `graph3d*` no PyPI não são afiliados a este projeto. O único repositório oficial é [DarbotLM/graph3d](https://github.com/DarbotLM/graph3d).

### Suporte a plataformas

| Plataforma | Comando de instalação |
|------------|-----------------------|
| Claude Code (Linux/Mac) | `graph3d install` |
| Claude Code (Windows) | `graph3d install` (detecção automática) ou `graph3d install --platform windows` |
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
| Kiro IDE/CLI | `graph3d kiro install` |
| Cursor | `graph3d cursor install` |
| Google Antigravity | `graph3d antigravity install` |

Depois abra seu assistente de código IA e digite:

```
/graph3d .
```

Nota: Codex usa `$` em vez de `/` para habilidades, então digite `$graph3d .`.

### Fazer o assistente sempre usar o grafo (recomendado)

Após construir um grafo, execute isso uma vez no seu projeto:

| Plataforma | Comando |
|------------|---------|
| Claude Code | `graph3d claude install` |
| Codex | `graph3d codex install` |
| OpenCode | `graph3d opencode install` |
| Cursor | `graph3d cursor install` |
| Gemini CLI | `graph3d gemini install` |
| Kiro IDE/CLI | `graph3d kiro install` |
| Google Antigravity | `graph3d antigravity install` |

## Uso

```
/graph3d                          # diretório atual
/graph3d ./raw                    # pasta específica
/graph3d ./raw --mode deep        # extração de arestas INFERRED mais agressiva
/graph3d ./raw --update           # re-extrair apenas arquivos modificados
/graph3d ./raw --directed         # grafo dirigido
/graph3d ./raw --cluster-only     # re-executar clustering no grafo existente
/graph3d ./raw --no-viz           # sem HTML, apenas relatório + JSON
/graph3d ./raw --obsidian         # gerar vault do Obsidian (opt-in)

/graph3d add https://arxiv.org/abs/1706.03762   # buscar um paper
/graph3d add <video-url>                         # baixar áudio, transcrever, adicionar
/graph3d query "o que conecta Attention ao otimizador?"
/graph3d path "DigestAuth" "Response"
/graph3d explain "SwinTransformer"

graph3d hook install              # instalar hooks do Git
graph3d update ./src              # re-extrair arquivos de código, sem LLM
graph3d watch ./src               # atualização automática do grafo
```

## O que você obtém

**Nós deus** — conceitos com maior grau (por onde tudo passa)

**Conexões surpreendentes** — classificadas por pontuação composta. Arestas código-paper pontuam mais alto. Cada resultado inclui um porquê em linguagem natural.

**Perguntas sugeridas** — 4-5 perguntas que o grafo está em posição única de responder

**O "porquê"** — docstrings, comentários inline (`# NOTE:`, `# IMPORTANT:`, `# HACK:`, `# WHY:`), e justificativas de design extraídas como nós `rationale_for`.

**Pontuações de confiança** — cada aresta INFERRED tem um `confidence_score` (0,0-1,0).

**Benchmark de tokens** — impresso automaticamente após cada execução. Em um corpus misto: **71,5x** menos tokens por consulta vs arquivos brutos.

**Sincronização automática** (`--watch`) — atualiza o grafo automaticamente quando o código muda.

**Hooks do Git** (`graph3d hook install`) — instala hooks post-commit e post-checkout.

## Privacidade

graph3d envia conteúdo de arquivos para a API do modelo do seu assistente IA para extração semântica de documentos, papers e imagens. Arquivos de código são processados localmente via tree-sitter AST. Arquivos de vídeo e áudio são transcritos localmente com faster-whisper. Sem telemetria, sem rastreamento de uso.

## Stack técnico

NetworkX + Leiden (graspologic) + tree-sitter + vis.js. Extração semântica via Claude, GPT-4 ou o modelo da sua plataforma. Transcrição de vídeo via faster-whisper + yt-dlp (opcional).

## Construído sobre graph3d — Penpax

[**Penpax**](https://safishamsi.github.io/penpax.ai) é a camada enterprise sobre o graph3d. Onde o graph3d transforma uma pasta de arquivos em um grafo de conhecimento, o Penpax aplica o mesmo grafo a toda a sua vida profissional — continuamente.

**Teste gratuito em breve.** [Entrar na lista de espera →](https://safishamsi.github.io/penpax.ai)

## Histórico de estrelas

[![Star History Chart](https://api.star-history.com/svg?repos=DarbotLM/graph3d&type=Date)](https://star-history.com/#DarbotLM/graph3d&Date)
