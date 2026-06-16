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
</p>

**En færdighed til AI-kodeassistenter.** Skriv `/graph3d` i Claude Code, Codex, OpenCode, Cursor, Gemini CLI, GitHub Copilot CLI, VS Code Copilot Chat, Aider, OpenClaw, Factory Droid, Trae, Hermes, Kiro eller Google Antigravity — den læser dine filer, bygger en vidensgraf og giver dig den struktur tilbage, du ikke vidste eksisterede. Forstå en kodebase hurtigere. Find "hvorfor" bag arkitektoniske beslutninger.

Fuldt multimodal. Tilføj kode, PDF'er, markdown, skærmbilleder, diagrammer, whiteboardfotos, billeder på andre sprog eller video- og lydfiler — graph3d udtrækker begreber og relationer fra alt og forbinder dem i én graf. Videoer transskriberes lokalt med Whisper. Understøtter 30+ programmeringssprog via tree-sitter AST.

> Andrej Karpathy opretholder en `/raw`-mappe, hvor han lægger artikler, tweets, skærmbilleder og noter. graph3d er svaret på det problem — **71,5x** færre tokens pr. forespørgsel sammenlignet med at læse rå filer, vedvarende mellem sessioner.

```
/graph3d .
```

```
graph3d-out/
├── graph.html       interaktiv graf — åbn i enhver browser
├── GRAPH_REPORT.md  gudknuder, overraskende forbindelser, foreslåede spørgsmål
├── graph.json       vedvarende graf — forespørgselsbar uger senere
└── cache/           SHA256-cache — gentagne kørsler behandler kun ændrede filer
```

## Sådan fungerer det

graph3d arbejder i tre gennemløb. Først udtrækker et deterministisk AST-gennemløb struktur fra kodefiler uden LLM. Derefter transskriberes video- og lydfiler lokalt med faster-whisper. Endelig kører Claude-underagenter parallelt på dokumenter, artikler, billeder og transskriptioner. Resultaterne flettes ind i en NetworkX-graf, klynges med Leiden og eksporteres som interaktiv HTML, forespørgselsbar JSON og revisionsrapport.

Hver relation er mærket `EXTRACTED`, `INFERRED` (med konfidensscore) eller `AMBIGUOUS`.

## Installation

**Krav:** Python 3.10+ og én af: [Claude Code](https://claude.ai/code), [Codex](https://openai.com/codex), [OpenCode](https://opencode.ai), [Cursor](https://cursor.com) og andre.

```bash
uv tool install graph3d && graph3d install
# eller med pipx
pipx install graph3d && graph3d install
# eller pip
pip install graph3d && graph3d install
```

> **Officiel pakke:** PyPI-pakken hedder `graph3d`. Det eneste officielle lager er [DarbotLM/graph3d](https://github.com/DarbotLM/graph3d).

## Brug

```
/graph3d .
/graph3d ./raw --update
/graph3d query "hvad forbinder Attention med optimizeren?"
/graph3d path "DigestAuth" "Response"
graph3d hook install
graph3d update ./src
```

## Hvad du får

**Gudknuder** — begreber med den højeste grad · **Overraskende forbindelser** — rangeret efter score · **Foreslåede spørgsmål** · **"Hvorfor"** — docstrings og designbegrundelse udtrukket som knuder · **Token-benchmark** — **71,5x** færre tokens på blandet korpus.

## Privatliv

Kodefiler behandles lokalt via tree-sitter AST. Videoer transskriberes lokalt med faster-whisper. Ingen telemetri.

## Bygget på graph3d — Penpax

[**Penpax**](https://safishamsi.github.io/penpax.ai) er enterprise-laget oven på graph3d. **Gratis prøveperiode kommer snart.** [Tilmeld dig ventelisten →](https://safishamsi.github.io/penpax.ai)

[![Star History Chart](https://api.star-history.com/svg?repos=DarbotLM/graph3d&type=Date)](https://star-history.com/#DarbotLM/graph3d&Date)
