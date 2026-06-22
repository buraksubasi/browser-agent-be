# Browser Agent

Doğal dil komutlarıyla web tarayıcısını otomatik olarak kontrol eden, adımları canlı olarak akıtan bir AI agent sistemi.

---

## Genel Mimari

```
Kullanıcı (Next.js UI)
        │  WebSocket /agent/stream
        ▼
  FastAPI Backend
        │
        ├── Gemini 2.5 Flash (LLM — görev planlama)
        │
        └── MCP Client
                │  stdio subprocess
                ▼
          MCP Server (Playwright)
                │
                ▼
          Chromium Browser
```

---

## Backend — `browser-agent-be`

### Stack

| Katman | Teknoloji |
|---|---|
| Web framework | **FastAPI** + **Uvicorn** (WebSocket desteği ile) |
| AI / LLM | **Google Gemini 2.5 Flash** (`google-generativeai`) |
| Browser otomasyon | **Playwright** (Chromium) |
| Tool protokolü | **MCP** (Model Context Protocol) — stdio subprocess |
| Görüntü işleme | **Pillow** (screenshot → Gemini'ye görsel gönderme) |
| Ortam değişkenleri | **python-dotenv** |
| Konteynerizasyon | **Docker** + **Docker Compose** |

### Proje Yapısı

```
browser-agent-be/
├── main.py          # FastAPI app, HTTP ve WebSocket endpoint'leri
├── agent.py         # Gemini agent döngüsü, tool çağrıları, adım yönetimi
├── mcp_client.py    # MCP subprocess bağlantısı (stdio)
├── mcp_server.py    # Playwright tool'ları (navigate, click, type, screenshot, pdf…)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env
```

### API Endpoint'leri

| Endpoint | Tip | Açıklama |
|---|---|---|
| `GET /health` | HTTP | Servis sağlık kontrolü |
| `POST /agent/run` | HTTP | Görevi çalıştır, tamamlanınca tüm adımları döndür |
| `WS /agent/stream` | WebSocket | Görevi çalıştır, adımları canlı akıt |

#### WebSocket Mesaj Formatı

Gönder:
```json
{ "task": "google.com'da Python ara ve ilk sonucu özetle" }
```

Al (her adımda):
```json
{
  "type": "tool_call",
  "tool": "navigate",
  "args": { "url": "https://google.com" },
  "result": "✅ Gidildi: https://google.com | Başlık: Google"
}
```

Özel adım tipleri:
- `screenshot` adımı → `step.screenshot` (base64 PNG)
- `pdf` adımı → `step.pdf = { filename, data }` (base64 PDF, indirilebilir)
- Son mesaj → `{ "type": "done", "result": "..." }`

### MCP Tool'ları

| Tool | Açıklama |
|---|---|
| `navigate` | URL'e git |
| `screenshot` | Sayfa görüntüsü al (base64 PNG) |
| `click` | CSS selector ile tıkla (JS fallback dahil) |
| `click_text` | Görünen metin ile tıkla |
| `type` | Input'a metin yaz |
| `set_value` | Date picker / custom input'a JS ile değer zorla |
| `select_option` | Dropdown seçeneği seç (native + custom) |
| `get_options` | Dropdown seçeneklerini listele |
| `get_text` | Sayfa metnini al |
| `get_html` | Sayfa HTML'ini al |
| `press_key` | Klavye tuşuna bas |
| `scroll` | Sayfayı kaydır |
| `wait_for` | Element görünene kadar bekle |
| `get_url` | Mevcut URL'i döndür |
| `go_back` | Geri git |
| `pdf` | Sayfayı PDF olarak al (base64 döndürür, dosyaya yazmaz) |

### Ortam Değişkenleri (`.env`)

```env
GOOGLE_API_KEY=...          # Gemini API anahtarı
FRONTEND_URL=http://localhost:3000
IS_DOCKER=false             # Docker içinde çalışıyorsa true
```

### Kurulum ve Çalıştırma

**Lokal:**
```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
playwright install chromium
uvicorn main:app --reload --port 8000
```

**Docker:**
```bash
docker compose up --build
```

---

## Frontend — `browser-agent-fe`

### Stack

| Katman | Teknoloji |
|---|---|
| Framework | **Next.js 16** (App Router) |
| UI | **React 19** + **Tailwind CSS v4** |
| Dil | **TypeScript** |
| Gerçek zamanlı | Native **WebSocket** API |

### Proje Yapısı

```
browser-agent-fe/
├── app/
│   ├── layout.tsx       # Root layout, metadata
│   └── page.tsx         # Ana sayfa (görev input + canlı akış)
├── components/
│   ├── StepCard.tsx     # Her agent adımını gösteren kart
│   └── StatusBadge.tsx  # Bağlantı durumu göstergesi
├── hooks/
│   └── useAgentStream.ts  # WebSocket bağlantı hook'u
└── .env.local
```

### Ortam Değişkenleri (`.env.local`)

```env
NEXT_PUBLIC_WS_URL=ws://localhost:8000/agent/stream
```

### Kurulum ve Çalıştırma

```bash
npm install
npm run dev     # http://localhost:3000
```

### `useAgentStream` Hook

```ts
const { steps, status, finalResult, run, stop } = useAgentStream(wsUrl)
```

| Değer | Tip | Açıklama |
|---|---|---|
| `steps` | `StepType[]` | Gerçek zamanlı adım listesi |
| `status` | `idle \| connecting \| running \| done \| error` | Bağlantı durumu |
| `finalResult` | `string \| null` | Görevin sonuç metni |
| `run(task)` | `fn` | Görevi başlat |
| `stop()` | `fn` | Bağlantıyı kes |

### Özellikler

- Görev girdi kutusu + örnek görevler
- Canlı adım akışı (her tool çağrısı ayrı kart)
- Screenshot adımlarında inline görüntü önizleme
- PDF adımlarında tek tıkla indirme butonu
- Durdur butonu (çalışırken iptal)
- Hata / tamamlanma sonuç kartı

---

## Deployment

| Servis | Platform |
|---|---|
| Backend | [Render.com](https://render.com) (Docker container) |
| Frontend | [Vercel](https://vercel.com) |

> Render'da PDF dosya sisteme yazılmaz; base64 olarak memory'de tutulup frontend'e aktarılır.
