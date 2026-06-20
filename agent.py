from dotenv import load_dotenv
load_dotenv()

import os
import base64
import google.generativeai as genai
from PIL import Image
import io
from mcp_client import MCPClient

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel("gemini-2.5-flash")

TOOLS = [
    {"name": "navigate",   "description": "URL'e git",                 "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
    {"name": "screenshot", "description": "Sayfanın screenshot'ını al", "parameters": {"type": "object", "properties": {}}},
    {"name": "click",      "description": "CSS selector ile tıkla. Selector bulunamazsa JS fallback dener.", "parameters": {"type": "object", "properties": {"selector": {"type": "string"}}, "required": ["selector"]}},
    {"name": "click_text",   "description": "Görünen metne göre tıkla. CSS selector işe yaramadığında kullan.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "exact": {"type": "boolean"}}, "required": ["text"]}},
    {"name": "set_value",    "description": "Date picker veya custom input'a JS ile değer zorla. type çalışmadığında kullan. Tarih: YYYY-MM-DD", "parameters": {"type": "object", "properties": {"selector": {"type": "string"}, "value": {"type": "string"}}, "required": ["selector", "value"]}},
    {"name": "get_options",  "description": "Dropdown seçeneklerini listele. select_option'dan ÖNCE çağır.", "parameters": {"type": "object", "properties": {"selector": {"type": "string"}}, "required": ["selector"]}},
    {"name": "select_option","description": "Dropdown'dan seçenek seç. ÖNCE get_options ile seçenekleri öğren.", "parameters": {"type": "object", "properties": {"selector": {"type": "string"}, "value": {"type": "string"}, "label": {"type": "string"}}, "required": ["selector"]}},
    {"name": "type",       "description": "Input'a metin yaz",         "parameters": {"type": "object", "properties": {"selector": {"type": "string"}, "text": {"type": "string"}}, "required": ["selector", "text"]}},
    {"name": "press_key",  "description": "Klavye tuşuna bas",         "parameters": {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]}},
    {"name": "get_text",   "description": "Sayfa metnini al",          "parameters": {"type": "object", "properties": {}}},
    {"name": "scroll",     "description": "Sayfayı kaydır",            "parameters": {"type": "object", "properties": {"direction": {"type": "string", "enum": ["down", "up"]}}, "required": ["direction"]}},
    {"name": "get_url",    "description": "Mevcut URL'i döndür",       "parameters": {"type": "object", "properties": {}}},
    {"name": "go_back",    "description": "Bir sayfa geri git",        "parameters": {"type": "object", "properties": {}}},
    {"name": "pdf",        "description": "PDF kaydet",                "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
]

SYSTEM = """Sen bir browser automation agent'ısın.
Kullanıcının istediği görevi tarayıcıda gerçekleştirmek için araçları kullan.
Her adımda önce screenshot al, sayfayı gör, sonra hareket et.
Görev tamamlandığında Türkçe özet ver.

Form Doldurma Stratejisi:
KURAL: Bir formu ASLA eksik alanla gönderme. Submit butonuna basmadan önce aşağıdaki adımları sırayla uygula:

ADIM 1 — Formu tara:
  get_html ile sayfanın HTML'ini al. <input>, <select>, <textarea> elementlerini bul.
  Her elementin name, id, type ve placeholder değerini not et.

ADIM 2 — Her alanı doldur:
  - text/email/tel/number input    → type({selector: "input[name=...]", text: "..."})
    type hata verirse              → set_value({selector, value}) ile dene
  - Tarih input (type="date")      → set_value({selector: "input[type='date']", value: "YYYY-MM-DD"})
    Tarih formatı MUTLAKA YYYY-MM-DD olmalı (örn: "2025-06-25")
    Kullanıcı tarih belirtmemişse bugünden 3 gün sonrasını kullan.
  - Dropdown (<select> veya "Seçiniz..." gibi custom):
      1. ÖNCE get_options({selector}) çağır — mevcut seçeneklerin label ve value değerlerini gör
      2. Kullanıcının isteğine uygun ya da ilk anlamlı seçeneği belirle ("Seçiniz" / "Seç" hariç)
      3. select_option({selector, label: "seçenek metni"}) ile seç
  - <textarea>                     → type({selector: "textarea[name=...]", text: "..."})
    type hata verirse              → set_value({selector, value}) ile dene
  - checkbox/radio                 → click({selector})

ADIM 3 — Doğrula:
  screenshot al. Tüm alanların dolu göründüğünü gözle kontrol et.
  Boş veya placeholder gösteren alan varsa tekrar doldur.

ADIM 4 — Gönder:
  Ancak tüm alanlar dolduktan sonra submit/gönder butonuna tıkla.

ADIM 5 — GÖNDERİMİ DOĞRULA (ZORUNLU):
  Submit'e bastıktan sonra ASLA hemen "tamamlandı" deme.
  Şunları kontrol et:
  a) screenshot al — sayfanın nasıl göründüğüne bak
  b) get_text ile sayfanın metnini oku
  c) Başarı durumu: "teşekkür", "başarıyla", "gönderildi", "alındı", "onaylandı",
     "thank you", "success" gibi ifadeler veya farklı bir sayfaya yönlendirme varsa → BAŞARILI
  d) Hata durumu: "zorunlu alan", "gerekli", "lütfen doldurun", "hata", "error",
     kırmızı border'lı input veya form hâlâ aynı sayfada duruyorsa → BAŞARISIZ
  e) BAŞARISIZ ise: get_text ile hata mesajını oku, eksik/hatalı alanı bul ve düzelt, tekrar gönder.
  f) Birden fazla denemeye rağmen form gönderilemiyorsa kullanıcıya nedenini açıkça belirt.

Tıklama Stratejisi:
- Önce basit CSS selector dene: 'button', 'a', '#id', '.class' gibi.
- href içeren karmaşık selectorlar yerine click_text kullan: click_text({text: "Bağlantı metni"}).
- click hata verirse hemen click_text ile aynı elementi metniyle bul.
- Input/form elementleri için daima 'input[name=...]' veya '#id' gibi basit selectorlar kullan.

CAPTCHA / Bot Algılama Kuralları:
- Sayfada "Ben robot değilim" veya reCAPTCHA checkbox'ı görürsen hemen click aracıyla tıklamayı dene.
  Önce '#recaptcha-anchor', sonra 'iframe[src*="recaptcha"] .recaptcha-checkbox', sonra 'div.recaptcha-checkbox-border' selector'larını dene.
- "Bu sayfa hakkında" / "About this page" gibi Google güvenlik sayfası çıkarsa sayfayı yenile (navigate ile aynı URL'e git) ve tekrar dene.
- Google bot engeline takılırsan alternatif olarak Bing (https://www.bing.com/search?q=...) veya DuckDuckGo (https://duckduckgo.com/?q=...) kullan.
- CAPTCHA görünce pes etme; önce tıklamayı dene, olmazsa alternatif arama motoruna geç.

Sayfa scroll işlemleri:
- Sayfayı kaydırma işlemleri için scroll aracını kullan.
- gerekli bilgiyi buluncaya kadar sayfayı en aşağı kadar kaydır."""


async def run_agent(task: str, on_step=None):
    mcp = MCPClient()
    await mcp.connect()

    messages = [
        {"role": "user", "parts": [f"{SYSTEM}\n\nGörev: {task}"]}
    ]
    steps = []

    try:
        for _ in range(50):
            response = model.generate_content(
                messages,
                tools=[{"function_declarations": TOOLS}],
                tool_config={"function_calling_config": {"mode": "AUTO"}}
            )

            candidate = response.candidates[0]
            parts = candidate.content.parts

            # Sadece geçerli function_call'ları al (name boş olmayanlar)
            fc_parts = [
                p for p in parts
                if hasattr(p, "function_call")
                and p.function_call.name
                and p.function_call.name.strip()
            ]

            # Tool call yoksa bitti
            if not fc_parts:
                text_parts = [p for p in parts if hasattr(p, "text") and p.text]
                final = text_parts[0].text if text_parts else "Görev tamamlandı."
                steps.append({"type": "final", "text": final})
                return {"steps": steps, "result": final}

            # Model mesajını history'e ekle
            messages.append({"role": "model", "parts": parts})

            # Her tool call'ı sırayla çalıştır
            tool_response_parts = []
            last_pil_image = None

            for part in fc_parts:
                fc = part.function_call
                tool_name = fc.name.strip()
                tool_args = dict(fc.args) if fc.args else {}

                step = {"type": "tool_call", "tool": tool_name, "args": tool_args}

                # MCP server'da çalıştır
                result = await mcp.call_tool(tool_name, tool_args)
                step["result"] = result

                # Screenshot ise base64'ü sakla, PIL image'ı yerel değişkende tut
                if tool_name == "screenshot":
                    step["screenshot"] = result
                    try:
                        img_bytes = base64.b64decode(result)
                        last_pil_image = Image.open(io.BytesIO(img_bytes))
                    except Exception:
                        pass

                # PDF ise base64 payload'ı step'e ekle
                if tool_name == "pdf":
                    try:
                        import json as _json
                        pdf_payload = _json.loads(result)
                        step["pdf"] = pdf_payload  # {"filename": "...", "data": "<base64>"}
                        gemini_result = f"✅ PDF oluşturuldu: {pdf_payload.get('filename', 'document.pdf')}"
                    except Exception:
                        gemini_result = result
                else:
                    gemini_result = result

                steps.append(step)
                if on_step:
                    await on_step(step)

                # Tool response part oluştur — Gemini'ye PDF base64 gönderme
                tool_response_parts.append(
                    genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=tool_name,
                            response={"result": "Screenshot alındı." if tool_name == "screenshot" else gemini_result[:3000]}
                        )
                    )
                )

            # Tool response'ları history'e ekle
            user_parts = tool_response_parts

            # Son screenshot varsa görseli de Gemini'ye ekle
            if last_pil_image is not None:
                user_parts = tool_response_parts + [last_pil_image]

            messages.append({"role": "user", "parts": user_parts})

    finally:
        await mcp.disconnect()

    return {"steps": steps, "result": "Maksimum adım sayısına ulaşıldı."}