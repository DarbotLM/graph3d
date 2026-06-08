<p align="center">
  <img src="https://raw.githubusercontent.com/DarbotLM/graph3d/v4/docs/logo-text.svg" width="260" height="64" alt="Graph3d"/>
</p>

<p align="center">
  🇺🇸 <a href="../../README.md">English</a> | 🇨🇳 <a href="README.zh-CN.md">简体中文</a> | 🇯🇵 <a href="README.ja-JP.md">日本語</a> | 🇰🇷 <a href="README.ko-KR.md">한국어</a> | 🇩🇪 <a href="README.de-DE.md">Deutsch</a> | 🇫🇷 <a href="README.fr-FR.md">Français</a> | 🇪🇸 <a href="README.es-ES.md">Español</a> | 🇮🇳 <a href="README.hi-IN.md">हिन्दी</a> | 🇧🇷 <a href="README.pt-BR.md">Português</a> | 🇷🇺 <a href="README.ru-RU.md">Русский</a> | 🇸🇦 <a href="README.ar-SA.md">العربية</a> | 🇮🇹 <a href="README.it-IT.md">Italiano</a> | 🇵🇱 <a href="README.pl-PL.md">Polski</a> | 🇳🇱 <a href="README.nl-NL.md">Nederlands</a> | 🇹🇷 <a href="README.tr-TR.md">Türkçe</a> | 🇺🇦 <a href="README.uk-UA.md">Українська</a> | 🇻🇳 <a href="README.vi-VN.md">Tiếng Việt</a> | 🇮🇩 <a href="README.id-ID.md">Bahasa Indonesia</a> | 🇸🇪 <a href="README.sv-SE.md">Svenska</a> | 🇬🇷 <a href="README.el-GR.md">Ελληνικά</a> | 🇷🇴 <a href="README.ro-RO.md">Română</a> | 🇨🇿 <a href="README.cs-CZ.md">Čeština</a> | 🇫🇮 <a href="README.fi-FI.md">Suomi</a> | 🇩🇰 <a href="README.da-DK.md">Dansk</a> | 🇳🇴 <a href="README.no-NO.md">Norsk</a> | 🇭🇺 <a href="README.hu-HU.md">Magyar</a> | 🇹🇭 <a href="README.th-TH.md">ภาษาไทย</a> | 🇺🇿 <a href="README.uz-UZ.md">Oʻzbekcha</a> | 🇹🇼 <a href="README.zh-TW.md">繁體中文</a>
</p>

<p align="center">
  <a href="https://github.com/DarbotLM/graph3d/actions/workflows/ci.yml"><img src="https://github.com/DarbotLM/graph3d/actions/workflows/ci.yml/badge.svg?branch=v4" alt="CI"/></a>
  <a href="https://pypi.org/project/graph3d/"><img src="https://img.shields.io/pypi/v/graph3d" alt="PyPI"/></a>
  <a href="https://pepy.tech/project/graph3d"><img src="https://static.pepy.tech/badge/graph3d" alt="Downloads"/></a>
  <a href="https://github.com/sponsors/safishamsi"><img src="https://img.shields.io/badge/sponsor-safishamsi-ea4aaa?logo=github-sponsors" alt="Sponsor"/></a>
  <a href="https://www.linkedin.com/in/safi-shamsi"><img src="https://img.shields.io/badge/LinkedIn-Safi%20Shamsi-0077B5?logo=linkedin" alt="LinkedIn"/></a>
</p>

**Sun'iy intellektga asoslangan kod yordamchilari uchun ko'nikma.** Claude Code, Codex, OpenCode, Cursor, Gemini CLI, GitHub Copilot CLI, VS Code Copilot Chat, Aider, OpenClaw, Factory Droid, Trae, Hermes, Kiro yoki Google Antigravity da `/graph3d` deb yozing — u sizning fayllaringizni o'qiydi, bilim grafini quradi va siz bilmagan tuzilmani sizga qaytaradi. Kod bazasini tezroq tushuning. Arxitektura qarorlari ortidagi "nima uchun" savoliga javob toping.

To'liq multimodal. Kod, PDF, markdown, ekran tasvirlari, diagrammalar, doska suratlari, boshqa tillardagi tasvirlar, video va audio fayllarni qo'shing — graph3d ularning barchasidan tushuncha va aloqalarni chiqarib, bitta grafga birlashtiradi. Videolar Whisper yordamida mahalliy ravishda transkripsiya qilinadi, sizning korpusingizdan olingan domen-maxsus so'rov bilan. tree-sitter AST orqali 25 ta dasturlash tilini qo'llab-quvvatlaydi (Python, JS, TS, Go, Rust, Java, C, C++, Ruby, C#, Kotlin, Scala, PHP, Swift, Lua, Zig, PowerShell, Elixir, Objective-C, Julia, Verilog, SystemVerilog, Vue, Svelte, Dart).

> Andrej Karpati maqolalar, tvitlar, ekran tasvirlari va eslatmalarni saqlaydigan `/raw` papkasini yuritadi. graph3d ushbu muammoga javob — xom fayllarni o'qishga nisbatan har bir so'rov uchun **71,5 marta** kamroq token, sessiyalar orasida saqlanadi, topilgan va xulosa qilinganlar haqida halol.

```
/graph3d .                        # istalgan papka bilan ishlaydi — kod, eslatmalar, maqolalar, hammasi
```

```
graph3d-out/
├── graph.html       interaktiv graf — brauzerda oching, tugunlarni bosing, qidiring, filtrlang
├── GRAPH_REPORT.md  god-tugunlar, kutilmagan aloqalar, taklif qilingan savollar
├── graph.json       doimiy graf — haftalardan keyin qayta o'qimasdan so'rov qiling
└── cache/           SHA256-kesh — qayta ishga tushirish faqat o'zgargan fayllarni qayta ishlaydi
```

Papkalarni istisno qilish uchun `.graph3dignore` faylini qo'shing:

```
# .graph3dignore
vendor/
node_modules/
dist/
*.generated.py
```

Sintaksisi `.gitignore` ga o'xshash.

## Qanday ishlaydi

graph3d uch bosqichda ishlaydi. Birinchi navbatda, deterministik AST bosqichi kod fayllaridan tuzilmani chiqaradi (klasslar, funksiyalar, importlar, chaqiruv graflari, docstring lar, sabab izohlari) — LLM ishtirokisiz. Keyin video va audio fayllar faster-whisper yordamida mahalliy ravishda transkripsiya qilinadi. Nihoyat, Claude subagentlari hujjatlar, maqolalar, tasvirlar va transkriptlar ustida parallel ishlab, tushunchalar, aloqalar va dizayn asoslarini chiqarib oladi. Natijalar NetworkX grafiga birlashtiriladi, Leiden hamjamiyat aniqlash algoritmi bilan klasterlanadi va interaktiv HTML, so'rov qilinadigan JSON hamda tabiiy tildagi audit hisoboti sifatida eksport qilinadi.

**Klasterlash graf topologiyasiga asoslangan — embedding ishlatilmaydi.** Leiden hamjamiyatlarni qirralar zichligi bo'yicha topadi. Claude tomonidan chiqarilgan semantik o'xshashlik qirralari (`semantically_similar_to`, INFERRED deb belgilangan) allaqachon grafda. Graf tuzilmasining o'zi o'xshashlik signali. Alohida embedding bosqichi yoki vektor ma'lumotlar bazasi shart emas.

Har bir aloqa `EXTRACTED` (manbada to'g'ridan-to'g'ri topilgan), `INFERRED` (ishonch bahosi bilan asoslangan xulosa) yoki `AMBIGUOUS` (tekshirish uchun belgilangan) deb teglanadi.

## O'rnatish

**Talablar:** Python 3.10+ va quyidagilardan biri: [Claude Code](https://claude.ai/code), [Codex](https://openai.com/codex), [OpenCode](https://opencode.ai), [Cursor](https://cursor.com), [Gemini CLI](https://github.com/google-gemini/gemini-cli), [GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli), [VS Code Copilot Chat](https://code.visualstudio.com/docs/copilot/overview), [Aider](https://aider.chat), [OpenClaw](https://openclaw.ai), [Factory Droid](https://factory.ai), [Trae](https://trae.ai), [Kiro](https://kiro.dev), Hermes yoki [Google Antigravity](https://antigravity.google)

```bash
# Tavsiya etiladi — Mac va Linux da PATH ni sozlashsiz ishlaydi
uv tool install graph3d && graph3d install
# yoki pipx bilan
pipx install graph3d && graph3d install
# yoki oddiy pip
pip install graph3d && graph3d install
```

> **Rasmiy paket:** PyPI dagi paket nomi `graph3d` (`pip install graph3d` orqali o'rnatiladi). PyPI dagi boshqa `graph3d*` nomli paketlar bu loyiha bilan bog'liq emas. Yagona rasmiy repozitoriy — [DarbotLM/graph3d](https://github.com/DarbotLM/graph3d).

### Platforma qo'llab-quvvatlash

| Platforma | O'rnatish buyrug'i |
|-----------|--------------------|
| Claude Code (Linux/Mac) | `graph3d install` |
| Claude Code (Windows) | `graph3d install` (avto-aniqlash) yoki `graph3d install --platform windows` |
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

Keyin AI yordamchingizni oching va kiriting:

```
/graph3d .
```

Eslatma: Codex ko'nikmalar uchun `/` o'rniga `$` ishlatadi, shuning uchun `$graph3d .` deb kiriting.

### Yordamchini har doim grafdan foydalanishga majbur qilish (tavsiya etiladi)

Graf qurilgandan so'ng, loyihangizda buni bir marta bajaring:

| Platforma | Buyruq |
|-----------|--------|
| Claude Code | `graph3d claude install` |
| Codex | `graph3d codex install` |
| OpenCode | `graph3d opencode install` |
| Cursor | `graph3d cursor install` |
| Gemini CLI | `graph3d gemini install` |
| Kiro IDE/CLI | `graph3d kiro install` |
| Google Antigravity | `graph3d antigravity install` |

## Foydalanish

```
/graph3d                          # joriy katalog
/graph3d ./raw                    # ma'lum bir papka
/graph3d ./raw --mode deep        # INFERRED qirralarini agressivroq chiqarish
/graph3d ./raw --update           # faqat o'zgargan fayllarni qayta chiqarish
/graph3d ./raw --directed         # yo'naltirilgan graf
/graph3d ./raw --cluster-only     # mavjud grafda klasterlashni qayta ishga tushirish
/graph3d ./raw --no-viz           # HTML siz, faqat hisobot + JSON
/graph3d ./raw --obsidian         # Obsidian vault yaratish (opsional)

/graph3d add https://arxiv.org/abs/1706.03762   # maqolani olish
/graph3d add <video-url>                         # audio yuklab olish, transkripsiya qilish va qo'shish
/graph3d query "Attention ni optimallashtiruvchi bilan nima bog'laydi?"
/graph3d path "DigestAuth" "Response"
/graph3d explain "SwinTransformer"

graph3d hook install              # Git ilgaklarini o'rnatish
graph3d update ./src              # kod fayllarini qayta chiqarish, LLM siz
graph3d watch ./src               # grafni avtomatik yangilash
```

## Nima olasiz

**God-tugunlar** — eng yuqori darajadagi tushunchalar (hamma narsa ular orqali o'tadi)

**Kutilmagan aloqalar** — qo'shma ball bo'yicha tartiblangan. Kod-maqola qirralari yuqoriroq baholanadi. Har bir natijada tabiiy tildagi "nima uchun" tushuntirishi bor.

**Taklif qilingan savollar** — graf alohida javob bera oladigan 4-5 ta savol

**"Nima uchun"** — docstring lar, ichki izohlar (`# NOTE:`, `# IMPORTANT:`, `# HACK:`, `# WHY:`) va hujjatlardagi dizayn asoslari `rationale_for` tugunlari sifatida chiqariladi.

**Ishonch ballari** — har bir INFERRED qirrasida `confidence_score` (0,0-1,0) mavjud.

**Token benchmark** — har bir ishga tushirishdan keyin avtomatik chiqariladi. Aralash korpusda: so'rov uchun **71,5 marta** kamroq token, xom fayllarga nisbatan.

**Avto-sinxronlash** (`--watch`) — kod o'zgarganida grafni avtomatik yangilaydi.

**Git ilgaklari** (`graph3d hook install`) — post-commit va post-checkout ilgaklarini o'rnatadi.

## Maxfiylik

graph3d hujjatlar, maqolalar va tasvirlardan semantik chiqarish uchun fayl mazmunini AI yordamchingizning model API siga yuboradi. Kod fayllari tree-sitter AST orqali mahalliy ravishda qayta ishlanadi. Video va audio fayllar faster-whisper bilan mahalliy ravishda transkripsiya qilinadi. Hech qanday telemetriya, foydalanishni kuzatish yo'q.

## Texnologiyalar to'plami

NetworkX + Leiden (graspologic) + tree-sitter + vis.js. Semantik chiqarish Claude, GPT-4 yoki sizning platformangiz modeli orqali. Video transkripsiyasi faster-whisper + yt-dlp orqali (opsional).

## graph3d ustida qurilgan — Penpax

[**Penpax**](https://safishamsi.github.io/penpax.ai) — graph3d ustidagi korporativ qatlam. graph3d fayllar papkasini bilim grafiga aylantirganidek, Penpax o'sha yondashuvni butun ish hayotingizga uzluksiz qo'llaydi.

**Tez orada bepul sinov muddati.** [Kutish ro'yxatiga qo'shiling →](https://safishamsi.github.io/penpax.ai)

## Yulduzlar tarixi

[![Star History Chart](https://api.star-history.com/svg?repos=DarbotLM/graph3d&type=Date)](https://star-history.com/#DarbotLM/graph3d&Date)
