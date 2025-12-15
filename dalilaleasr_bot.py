import requests
import feedparser
import json
import time
import base64
import sqlite3
import os
import re
import urllib.parse
import io
import urllib3
import random
import httpx
from openai import OpenAI
from datetime import datetime
from difflib import SequenceMatcher
from PIL import Image, ImageDraw, ImageFont

# ==========================================
# 0. إعدادات النظام - دليل العصر V1.5
# ==========================================
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# === نظام تناوب مفاتيح OpenRouter ===
OPENROUTER_KEYS = [
    os.getenv("OPENROUTER_KEY_1", ""),
    os.getenv("OPENROUTER_KEY_2", ""),
    os.getenv("OPENROUTER_KEY_3", ""),
    os.getenv("OPENROUTER_KEY_4", ""),
    os.getenv("OPENROUTER_KEY_5", ""),
    os.getenv("OPENROUTER_KEY_6", ""),
]
# تنظيف القائمة من القيم الفارغة وإضافة المفتاح القديم كاحتياط
OPENROUTER_KEYS = [k for k in OPENROUTER_KEYS if k]
if not OPENROUTER_KEYS:
    legacy_key = os.getenv("OPENROUTER_KEY", "")
    if legacy_key: OPENROUTER_KEYS.append(legacy_key)

def get_random_key():
    if not OPENROUTER_KEYS: return ""
    return random.choice(OPENROUTER_KEYS)

# === إعدادات WordPress ===
WP_DOMAIN = os.getenv("WP_DOMAIN", "https://dalilaleasr.com") 
WP_USER = os.getenv("WP_USER", "admin")
WP_APP_PASS = os.getenv("WP_APP_PASS", "")
WP_ENDPOINT = f"{WP_DOMAIN}/wp-json/wp/v2"

# === إعدادات العلامة المائية ===
WATERMARK_TEXT = os.getenv("WATERMARK_TEXT", "dalilaleasr.com")

# === تحميل الأقسام من Environment Variables ===
# القيمة الافتراضية
CATEGORY_MAP = {"News": 1} 
DEFAULT_CATEGORY_ID = 1

# قراءة JSON من Coolify
env_cats = os.getenv("CATEGORY_MAP_JSON", "")
if env_cats:
    try:
        # محاولة تنظيف النص في حال وجود أخطاء نسخ ولصق
        env_cats = env_cats.strip()
        if env_cats.startswith("CATEGORY_MAP_JSON="): 
            env_cats = env_cats.replace("CATEGORY_MAP_JSON=", "", 1)
        
        CATEGORY_MAP = json.loads(env_cats)
        print(f"   ✅ تم تحميل خريطة الأقسام: {len(CATEGORY_MAP)} تصنيف")
    except Exception as e:
        print(f"   ⚠️ خطأ في قراءة الأقسام من JSON: {e}")
        print("   -> تأكد من استخدام علامات تنصيص مزدوجة \" في Coolify")

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    "Referer": "https://google.com"
}

FREE_TEXT_MODELS = [
    "google/gemini-2.0-flash-exp:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "microsoft/phi-3-medium-128k-instruct:free"
]

FREE_VISION_MODELS = [
    "google/gemini-2.0-flash-exp:free",
    "meta-llama/llama-3.2-90b-vision-instruct:free",
]

BLACKLIST_KEYWORDS = [
    "فيلم", "مسلسل", "أغنية", "فنان", "ممثلة", "رقص", "حفل غنائي", 
    "سينما", "دراما", "طرب", "ألبوم", "كليب", "فضائيات", 
    "Movie", "Song", "Actress", "Cinema", "Music Video", "Concert"
]

DB_FILE = "/app/data/dalil_history.db" if os.path.exists("/app") else "dalil_history.db"
FONT_PATH = "/app/data/Roboto-Bold.ttf"

# ==========================================
# 1. دوال النظام
# ==========================================
def init_db():
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True) if "/" in DB_FILE else None
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (link TEXT PRIMARY KEY, title TEXT, published_at TEXT)''')
    conn.commit()
    conn.close()

def ensure_font():
    if not os.path.exists(FONT_PATH):
        try:
            url = "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Bold.ttf"
            r = requests.get(url, timeout=30)
            if r.status_code == 200:
                os.makedirs(os.path.dirname(FONT_PATH), exist_ok=True)
                with open(FONT_PATH, 'wb') as f: f.write(r.content)
        except: pass

def is_published_link(link):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT 1 FROM history WHERE link=?", (link,))
    exists = c.fetchone()
    conn.close()
    return exists is not None

def mark_published(link, title):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO history VALUES (?, ?, ?)", (link, title, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def is_duplicate_semantic(new_title):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT title FROM history ORDER BY published_at DESC LIMIT 50")
    rows = c.fetchall()
    conn.close()
    if not rows: return False
    
    recent_titles = [row[0] for row in rows if row[0]]
    for existing in recent_titles:
        if SequenceMatcher(None, new_title.lower(), existing.lower()).ratio() > 0.70:
            return True
    return False

# ==========================================
# 2. إدارة الأقسام
# ==========================================
def get_auth_header():
    creds = base64.b64encode(f"{WP_USER}:{WP_APP_PASS}".encode()).decode()
    return {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}

def get_or_create_tag_id(tag_name):
    try:
        h = get_auth_header()
        r = requests.get(f"{WP_ENDPOINT}/tags?search={urllib.parse.quote(tag_name)}", headers=h)
        if r.status_code == 200 and r.json(): return r.json()[0]['id']
        r = requests.post(f"{WP_ENDPOINT}/tags", headers=h, json={"name": tag_name})
        if r.status_code == 201: return r.json()['id']
    except: pass
    return None

# ==========================================
# 3. معالجة الصور
# ==========================================
def get_ai_image_url(title):
    clean = re.sub(r'[^\w\s]', '', title)
    words = clean.split()[:9]
    prompt = " ".join(words)
    enc_prompt = urllib.parse.quote(f"Editorial news photo of {prompt}, realistic, 4k, no text")
    return f"https://image.pollinations.ai/prompt/{enc_prompt}?width=1280&height=720&nologo=true&seed={int(time.time())}&model=flux"

def check_image_safety(image_url):
    print(f"   🔍 Checking watermark...")
    http_client = httpx.Client(verify=False, transport=httpx.HTTPTransport(local_address="0.0.0.0"))
    key = get_random_key()
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key, http_client=http_client)
    for i in range(3):
        try:
            res = client.chat.completions.create(
                model=random.choice(FREE_VISION_MODELS),
                messages=[{"role": "user", "content": [{"type": "text", "text": "Does this image contain ANY text or logos? Answer YES or NO."}, {"type": "image_url", "image_url": {"url": image_url}}]}]
            )
            return "NO" in res.choices[0].message.content.strip().upper()
        except: 
            client.api_key = get_random_key()
            time.sleep(1)
    return False

def apply_branding(image_bytes):
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        width, height = img.size
        bar_h = int(height * 0.13) 
        overlay = Image.new("RGBA", img.size, (0,0,0,0))
        draw = ImageDraw.Draw(overlay)
        draw.rectangle([(0, height - bar_h), (width, height)], fill=(0,0,0,120))
        ensure_font()
        font_size = int(bar_h * 0.85)
        try: font = ImageFont.truetype(FONT_PATH, font_size) if os.path.exists(FONT_PATH) else ImageFont.load_default()
        except: font = ImageFont.load_default()
        
        try:
            l, t, r, b = font.getbbox(WATERMARK_TEXT)
            w_txt, h_txt = r-l, b-t
        except: w_txt, h_txt = len(WATERMARK_TEXT)*font_size*0.5, font_size
        
        x = (width - w_txt) / 2
        y = height - (bar_h/2) - (h_txt/2) - (b*0.1 if 'b' in locals() else 0)
        draw.text((x, y), WATERMARK_TEXT, font=font, fill=(255,255,255,255))
        return io.BytesIO(Image.alpha_composite(img, overlay).convert("RGB").save(io.BytesIO(), "JPEG", quality=95) or io.BytesIO().getvalue()).getvalue()
    except: return image_bytes

def upload_final_image(img_url, alt_text):
    print(f"   ⬆️ Branding & Uploading...")
    try:
        r = requests.get(img_url, headers=BROWSER_HEADERS, timeout=30, verify=False)
        if r.status_code == 200:
            data = apply_branding(r.content)
            headers = get_auth_header()
            headers.update({"Content-Disposition": f"attachment; filename=dalil_{int(time.time())}.jpg", "Content-Type": "image/jpeg"})
            wp = requests.post(f"{WP_ENDPOINT}/media", headers=headers, data=data)
            if wp.status_code == 201:
                mid = wp.json()['id']
                requests.post(f"{WP_ENDPOINT}/media/{mid}", headers=get_auth_header(), json={"alt_text": alt_text, "title": alt_text})
                return mid
    except: pass
    return None

def extract_image(entry):
    if hasattr(entry, 'media_content'): return entry.media_content[0]['url']
    if hasattr(entry, 'links'):
        for l in entry.links: 
            if 'image' in getattr(l, 'type', ''): return getattr(l, 'href', None)
    if hasattr(entry, 'summary'):
        m = re.search(r'<img.*?src=["\']([^"\']+)["\']', entry.summary)
        if m: return m.group(1)
    return None

# ==========================================
# 4. الذكاء الاصطناعي
# ==========================================
def clean_text_output(text):
    text = text.replace("*", "").replace('"', "").replace("##", "")
    text = re.sub(r'<a [^>]*>([a-zA-Z0-9\s]+)</a>', r'\1', text) 
    return text

def is_english(text):
    return len(re.findall(r'[a-zA-Z]', text)) > len(re.findall(r'[\u0600-\u06FF]', text))

def generate_arabic_content_package(news_item):
    http = httpx.Client(verify=False, transport=httpx.HTTPTransport(local_address="0.0.0.0"))
    
    # تحضير قائمة الأقسام المتاحة لإخبار الذكاء الاصطناعي بها
    # نأخذ فقط المفاتيح العربية الفريدة لتقليل حجم البرومبت
    available_cats = list(set([k for k in CATEGORY_MAP.keys()]))
    available_cats_str = ", ".join(available_cats[:20]) # نرسل أول 20 قسم لتجنب الطول الزائد

    prompt = f"""
    أنت محرر "دليل العصر". أعد صياغة هذا الخبر لمقال عربي:
    "{news_item['title']}" - {news_item['summary']}
    
    القواعد:
    1. العنوان عربي فقط.
    2. اربط الكلمات العربية ببحث الموقع: <a href="{WP_DOMAIN}/?s=الكلمة">الكلمة</a>.
    3. اختر التصنيف الأنسب بدقة من هذه القائمة: [{available_cats_str}]

    الهيكلية:
    OUTPUT_TITLE: [عنوان عربي]
    OUTPUT_BODY:
    <div style="background-color:#f1f8e9;border-right:5px solid #66bb6a;padding:20px;margin-bottom:30px"><h3 style="margin:0;color:#2e7d32">🔥 خلاصة:</h3><ul><li>نقطة 1</li></ul></div>
    [المقال...]
    OUTPUT_META:
    CATEGORY: [اكتب اسم التصنيف هنا بدقة]
    TAGS: [Tags]
    META_DESC: [Desc]
    """
    for _ in range(5):
        try:
            key = get_random_key()
            client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key, http_client=http)
            print(f"   🤖 AI Gen with key ending {key[-4:]}...")
            res = client.chat.completions.create(model=random.choice(FREE_TEXT_MODELS), messages=[{"role":"user","content":prompt}], temperature=0.7)
            content = res.choices[0].message.content.replace("```html","").replace("```","").strip()
            
            title, body, cat_found = "", "", ""
            
            if "OUTPUT_TITLE:" in content:
                p = content.split("OUTPUT_BODY:")
                if len(p)>1:
                    title = clean_text_output(p[0].replace("OUTPUT_TITLE:","").strip())
                    
                    # فصل الجسم عن الميتا
                    if "OUTPUT_META:" in p[1]:
                        body_parts = p[1].split("OUTPUT_META:")
                        body = clean_text_output(body_parts[0].strip())
                        
                        # استخراج التصنيف
                        meta_part = body_parts[1]
                        if "CATEGORY:" in meta_part:
                            cat_line = meta_part.split("CATEGORY:")[1].split("\n")[0].strip()
                            cat_found = cat_line.replace("[", "").replace("]", "").strip()
                    else:
                        body = clean_text_output(p[1].strip())
            
            if not title or is_english(title): title = news_item['title']
            
            # إرجاع البيانات كـ Dictionary لسهولة التعامل
            return {
                "title": title,
                "body": body,
                "category": cat_found
            }
            
        except Exception as e:
            if "429" in str(e): time.sleep(2)
            else: time.sleep(3)
    return None

def publish_to_wp(data_package, fid):
    title = data_package['title']
    content = data_package['body']
    cat_name_from_ai = data_package.get('category', '')
    
    if is_english(title): return None
    
    cat_id = DEFAULT_CATEGORY_ID
    
    # 🔥 المنطق الجديد لمطابقة الأقسام
    if cat_name_from_ai:
        print(f"   ℹ️ الذكاء الاصطناعي اقترح قسم: {cat_name_from_ai}")
        # 1. تطابق تام
        if cat_name_from_ai in CATEGORY_MAP:
            cat_id = CATEGORY_MAP[cat_name_from_ai]
        else:
            # 2. بحث جزئي (مثلاً: "تكنولوجيا" يطابق "تكنولوجيا ومعلومات")
            for key, val in CATEGORY_MAP.items():
                if key in cat_name_from_ai or cat_name_from_ai in key:
                    cat_id = val
                    break
    
    # بيانات النشر
    post_data = {
        "title": title, "content": content, "status": "publish",
        "categories": [cat_id], "featured_media": fid,
        "rank_math_focus_keyword": title
    }
    
    r = requests.post(f"{WP_ENDPOINT}/posts", headers=get_auth_header(), json=post_data)
    if r.status_code == 201: return r.json()['link']
    return None

# ==========================================
# 5. Main
# ==========================================
def main():
    print(f"🚀 Dalil Al-Asr (V15 - JSON Categories) Started.")
    if not OPENROUTER_KEYS:
        print("❌ Error: No API Keys!")
        return

    init_db()
    ensure_font()
    
    # قائمة مصادر منوعة
    feeds = [
        "https://cointelegraph.com/rss", "https://decrypt.co/feed",
        "https://techcrunch.com/feed/", "https://www.theverge.com/rss/index.xml",
        "https://www.aljazeera.net/aljazeerarss/a7c186be-1baa-4bd4-9d80-a84db769f779/73d0e1b4-532f-45ef-b135-bfdff8b8cab9",
        "https://www.skynewsarabia.com/web/rss",
        "https://www.cnbc.com/id/100003114/device/rss/rss.html"
    ]
    
    while True:
        print(f"\n⏰ Cycle: {datetime.now().strftime('%H:%M')}")
        random.shuffle(feeds)
        for feed in feeds:
            try:
                d = feedparser.parse(feed)
                for entry in d.entries[:3]:
                    if is_published_link(entry.link): continue
                    if any(x in entry.title for x in BLACKLIST_KEYWORDS): continue
                    if is_duplicate_semantic(entry.title): continue
                    
                    print(f"   ⚡ Processing: {entry.title[:30]}...")
                    img = extract_image(entry)
                    final_img = img if img and check_image_safety(img) else get_ai_image_url(entry.title)
                    fid = upload_final_image(final_img, entry.title)
                    
                    if fid:
                        # توليد المحتوى
                        data_pkg = generate_arabic_content_package({'title':entry.title, 'summary':getattr(entry,'summary','')})
                        if data_pkg and data_pkg['title']:
                            l = publish_to_wp(data_pkg, fid)
                            if l: 
                                print(f"   ✅ Published: {l}")
                                mark_published(entry.link, entry.title)
                    time.sleep(10)
            except Exception as e: print(f"   ⚠️ Error: {str(e)[:50]}")
        print("💤 Sleeping 10m...")
        time.sleep(600)

if __name__ == "__main__":
    main()
