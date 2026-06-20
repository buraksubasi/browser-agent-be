import asyncio
import base64
import os
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from playwright.async_api import async_playwright

server = Server("playwright-server")

# Global browser state
_playwright = None
_browser = None
_page = None

# IS_DOCKER env varı ya da DISPLAY yoksa (Docker/CI ortamı) headless çalış
IS_DOCKER = os.getenv("IS_DOCKER", "false").lower() == "true"
HEADLESS = IS_DOCKER or (os.getenv("DISPLAY", "") == "")


STEALTH_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
    "--disable-dev-shm-usage",
    "--disable-extensions",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-default-apps",
    "--disable-gpu",
    "--single-process",
    "--disable-software-rasterizer",
]

STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
Object.defineProperty(navigator, 'languages', { get: () => ['tr-TR', 'tr', 'en-US', 'en'] });
window.chrome = { runtime: {} };
"""

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


async def get_page():
    global _playwright, _browser, _page
    if _page is None:
        _playwright = await async_playwright().start()
        _browser = await _playwright.chromium.launch(
            headless=HEADLESS,
            args=STEALTH_ARGS,
        )
        context = await _browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=USER_AGENT,
            locale="tr-TR",
            timezone_id="Europe/Istanbul",
        )
        await context.add_init_script(STEALTH_SCRIPT)
        _page = await context.new_page()
    return _page


@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="navigate",
            description="Belirtilen URL'e git ve sayfanın yüklenmesini bekle",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Gidilecek URL"}
                },
                "required": ["url"]
            }
        ),
        Tool(
            name="screenshot",
            description="Mevcut sayfanın screenshot'ını base64 formatında al",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="click",
            description="CSS selector ile belirtilen elemente tıkla. Selector bulunamazsa JS ile tıklamayı dener.",
            inputSchema={
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector"}
                },
                "required": ["selector"]
            }
        ),
        Tool(
            name="click_text",
            description="Sayfada görünen metne göre elemente tıkla. CSS selector yetersiz kaldığında kullan.",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Tıklanacak elementin içerdiği metin"},
                    "exact": {"type": "boolean", "description": "True ise tam eşleşme, False ise içerme (varsayılan false)"}
                },
                "required": ["text"]
            }
        ),
        Tool(
            name="type",
            description="Belirtilen input alanına metin yaz. Çalışmazsa set_value kullan.",
            inputSchema={
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector"},
                    "text": {"type": "string", "description": "Yazılacak metin"}
                },
                "required": ["selector", "text"]
            }
        ),
        Tool(
            name="set_value",
            description="Date picker veya custom input'a JavaScript ile değer zorla. type çalışmadığında kullan. Tarih formatı: YYYY-MM-DD",
            inputSchema={
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector"},
                    "value": {"type": "string", "description": "Set edilecek değer (tarih için YYYY-MM-DD)"}
                },
                "required": ["selector", "value"]
            }
        ),
        Tool(
            name="get_options",
            description="Bir dropdown/select elementinin mevcut seçeneklerini listele. select_option'dan ÖNCE çağır.",
            inputSchema={
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector (<select> veya custom dropdown)"}
                },
                "required": ["selector"]
            }
        ),
        Tool(
            name="select_option",
            description="Dropdown'dan seçenek seç. Native <select> ve custom dropdown'ları destekler. ÖNCE get_options ile seçenekleri öğren.",
            inputSchema={
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector"},
                    "value": {"type": "string", "description": "Option value değeri"},
                    "label": {"type": "string", "description": "Option görünen metni"}
                },
                "required": ["selector"]
            }
        ),
        Tool(
            name="press_key",
            description="Klavye tuşuna bas (örn: Enter, Tab, Escape)",
            inputSchema={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Tuş adı (Enter, Tab, Escape, ArrowDown vb.)"}
                },
                "required": ["key"]
            }
        ),
        Tool(
            name="get_text",
            description="Sayfanın görünür metnini al",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="get_html",
            description="Sayfanın HTML içeriğini al",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="wait_for",
            description="Belirtilen CSS selector görünene kadar bekle",
            inputSchema={
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "Beklenen CSS selector"},
                    "timeout": {"type": "number", "description": "Maksimum bekleme süresi (ms), varsayılan 5000"}
                },
                "required": ["selector"]
            }
        ),
        Tool(
            name="scroll",
            description="Sayfayı yukarı veya aşağı kaydır",
            inputSchema={
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "enum": ["down", "up"],
                        "description": "Kaydırma yönü"
                    },
                    "amount": {"type": "number", "description": "Kaydırma miktarı (px), varsayılan 500"}
                },
                "required": ["direction"]
            }
        ),
        Tool(
            name="pdf",
            description="Mevcut sayfayı PDF olarak kaydet",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "PDF kayıt yolu (örn: /app/pdfs/rapor.pdf)"}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="get_url",
            description="Mevcut sayfanın URL'ini döndür",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="go_back",
            description="Tarayıcıda bir sayfa geri git",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    page = await get_page()

    try:
        if name == "navigate":
            await page.goto(arguments["url"], wait_until="networkidle", timeout=30000)
            title = await page.title()
            return [TextContent(type="text", text=f"✅ Gidildi: {arguments['url']} | Başlık: {title}")]

        elif name == "screenshot":
            await asyncio.sleep(0.8)
            await page.wait_for_load_state("domcontentloaded")
            buf = await page.screenshot(type="png", full_page=False)
            b64 = base64.b64encode(buf).decode("utf-8")
            return [TextContent(type="text", text=b64)]

        elif name == "click":
            selector = arguments["selector"]
            try:
                await page.wait_for_selector(selector, timeout=10000)
                await page.click(selector)
            except Exception:
                # JS click fallback
                await page.evaluate(f"document.querySelector(`{selector}`)?.click()")
            try:
                await page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                await asyncio.sleep(1)
            return [TextContent(type="text", text=f"✅ Tıklandı: {selector}")]

        elif name == "click_text":
            text = arguments["text"]
            exact = arguments.get("exact", False)
            locator = page.get_by_text(text, exact=exact)
            try:
                await locator.first.wait_for(timeout=10000)
                await locator.first.click()
            except Exception:
                await page.evaluate(
                    f"[...document.querySelectorAll('*')].find(el => el.innerText?.includes(`{text}`))?.click()"
                )
            try:
                await page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                await asyncio.sleep(1)
            return [TextContent(type="text", text=f"✅ Metin ile tıklandı: '{text}'")]

        elif name == "type":
            selector = arguments["selector"]
            text = arguments["text"]
            await page.wait_for_selector(selector, timeout=10000)
            try:
                await page.fill(selector, text)
            except Exception:
                try:
                    await page.click(selector)
                    await asyncio.sleep(0.2)
                    await page.keyboard.type(text, delay=30)
                except Exception:
                    # Son çare: JS ile yaz
                    await page.evaluate(
                        """([selector, value]) => {
                            const el = document.querySelector(selector);
                            if (!el) return;
                            el.focus();
                            el.value = value;
                            el.dispatchEvent(new Event('input', { bubbles: true }));
                            el.dispatchEvent(new Event('change', { bubbles: true }));
                            el.blur();
                        }""",
                        [selector, text]
                    )
            return [TextContent(type="text", text=f"✅ Yazıldı: '{text}'")]

        elif name == "set_value":
            selector = arguments["selector"]
            value = arguments["value"]
            await page.wait_for_selector(selector, timeout=10000)
            await page.evaluate(
                """([selector, value]) => {
                    const el = document.querySelector(selector);
                    if (!el) return;
                    // input ve textarea için doğru prototype seç
                    const proto = el.tagName === 'TEXTAREA'
                        ? window.HTMLTextAreaElement.prototype
                        : window.HTMLInputElement.prototype;
                    const descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
                    if (descriptor && descriptor.set) {
                        descriptor.set.call(el, value);
                    } else {
                        el.value = value;
                    }
                    el.dispatchEvent(new Event('focus',  { bubbles: true }));
                    el.dispatchEvent(new Event('input',  { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    el.dispatchEvent(new Event('blur',   { bubbles: true }));
                }""",
                [selector, value]
            )
            return [TextContent(type="text", text=f"✅ Değer set edildi: '{value}' → {selector}")]

        elif name == "select_option":
            selector = arguments["selector"]
            value = arguments.get("value", "")
            label = arguments.get("label", "")
            await page.wait_for_selector(selector, timeout=10000)
            tag = await page.evaluate(f"document.querySelector(`{selector}`)?.tagName")
            if tag and tag.upper() == "SELECT":
                # Native <select> elementi
                if value:
                    await page.select_option(selector, value=value)
                elif label:
                    await page.select_option(selector, label=label)
            else:
                # Custom dropdown: tıkla → seçeneğe tıkla
                await page.click(selector)
                await asyncio.sleep(0.4)
                if label:
                    await page.get_by_text(label, exact=True).first.click()
                elif value:
                    await page.get_by_text(value, exact=False).first.click()
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                await asyncio.sleep(0.5)
            return [TextContent(type="text", text=f"✅ Seçenek seçildi: {value or label}")]

        elif name == "get_options":
            # <select> elementinin tüm seçeneklerini listele
            selector = arguments["selector"]
            await page.wait_for_selector(selector, timeout=10000)
            options = await page.evaluate(
                """selector => {
                    const el = document.querySelector(selector);
                    if (!el) return [];
                    if (el.tagName === 'SELECT') {
                        return [...el.options].map(o => ({ value: o.value, label: o.text.trim() }));
                    }
                    // Custom dropdown: li/div içindeki seçenekleri dene
                    return [...el.querySelectorAll('li, [role="option"], .option')]
                        .map(o => ({ value: o.dataset.value || '', label: o.innerText.trim() }));
                }""",
                selector
            )
            import json
            return [TextContent(type="text", text=json.dumps(options, ensure_ascii=False))]

        elif name == "press_key":
            await page.keyboard.press(arguments["key"])
            await asyncio.sleep(0.5)
            return [TextContent(type="text", text=f"✅ Tuş basıldı: {arguments['key']}")]

        elif name == "get_text":
            text = await page.inner_text("body")
            return [TextContent(type="text", text=text[:8000])]

        elif name == "get_html":
            html = await page.content()
            return [TextContent(type="text", text=html[:8000])]

        elif name == "wait_for":
            timeout = arguments.get("timeout", 5000)
            await page.wait_for_selector(arguments["selector"], timeout=timeout)
            return [TextContent(type="text", text=f"✅ Element beklendi: {arguments['selector']}")]

        elif name == "scroll":
            amount = arguments.get("amount", 500)
            delta = amount if arguments["direction"] == "down" else -amount
            await page.evaluate(f"window.scrollBy(0, {delta})")
            await asyncio.sleep(0.3)
            return [TextContent(type="text", text=f"✅ Kaydırıldı: {arguments['direction']} {amount}px")]

        elif name == "pdf":
            import tempfile, json as _json
            filename = arguments["path"]
            # Sadece dosya adını al, dizini yok say — geçici dosyaya yaz
            filename = os.path.basename(filename) or "document.pdf"
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp_path = tmp.name
            await page.pdf(path=tmp_path, format="A4", print_background=True)
            with open(tmp_path, "rb") as f:
                pdf_b64 = base64.b64encode(f.read()).decode("utf-8")
            os.unlink(tmp_path)
            payload = _json.dumps({"filename": filename, "data": pdf_b64})
            return [TextContent(type="text", text=payload)]

        elif name == "get_url":
            return [TextContent(type="text", text=page.url)]

        elif name == "go_back":
            await page.go_back(wait_until="networkidle")
            return [TextContent(type="text", text=f"✅ Geri gidildi: {page.url}")]

        else:
            return [TextContent(type="text", text=f"❌ Bilinmeyen araç: {name}")]

    except Exception as e:
        return [TextContent(type="text", text=f"❌ Hata ({name}): {str(e)}")]


async def main():
    from mcp.server.models import InitializationOptions
    from mcp.types import ServerCapabilities, ToolsCapability

    async with stdio_server() as (read, write):
        await server.run(
            read,
            write,
            InitializationOptions(
                server_name="playwright-server",
                server_version="1.0.0",
                capabilities=ServerCapabilities(
                    tools=ToolsCapability(listChanged=False)
                )
            )
        )

if __name__ == "__main__":
    asyncio.run(main())

