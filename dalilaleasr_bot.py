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
import difflib
from PIL import Image, ImageDraw, ImageFont

# ==========================================
# 0. إعدادات النظام - دليل العصر V1.0
# ==========================================
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# === نظام تناوب مفاتيح OpenRouter (6 مفاتيح) ===
# يتم إضافتها في Coolify Environment Variables
OPENROUTER_KEYS = [
    os.getenv("OPENROUTER_KEY_1", ""),
    os.getenv("OPENROUTER_KEY_2", ""),
    os.getenv("OPENROUTER_KEY_3", ""),
    os.getenv("OPENROUTER_KEY_4", ""),
    os.getenv("OPENROUTER_KEY_5", ""),
    os.getenv("OPENROUTER_KEY_6", ""),
]
# تصفية المفاتيح الفارغة
OPENROUTER_KEYS = [k for k in OPENROUTER_KEYS if k]

# عداد لتتبع المفتاح الحالي
current_key_index = 0

def get_next_api_key():
    """الحصول على المفتاح التالي بنظام Round-Robin"""
    global current_key_index
    if not OPENROUTER_KEYS:
        raise ValueError("❌ لم يتم العثور على أي مفاتيح API! تأكد من إضافتها في Environment Variables")
    key = OPENROUTER_KEYS[current_key_index]
    current_key_index = (current_key_index + 1) % len(OPENROUTER_KEYS)
    return key

# === إعدادات WordPress ===
WP_DOMAIN = os.getenv("WP_DOMAIN", "https://dalilaleasr.com")
WP_USER = os.getenv("WP_USER", "admin")
WP_APP_PASS = os.getenv("WP_APP_PASS", "")

WP_ENDPOINT = f"{WP_DOMAIN}/wp-json/wp/v2"

# === إعدادات Bing Image Creator (اختياري - للضرورة فقط) ===
BING_COOKIE = os.getenv("BING_COOKIE", "")

# === العلامة المائية ===
WATERMARK_TEXT = os.getenv("WATERMARK_TEXT", "dalilaleasr.com")
SITE_NAME = "دليل العصر"

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    "Referer": "https://google.com"
}

# === قائمة النماذج المجانية ===
FREE_TEXT_MODELS = [
    "google/gemini-2.0-flash-exp:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "deepseek/deepseek-chat:free",
    "qwen/qwen-2.5-72b-instruct:free",
    "meta-llama/llama-3.1-405b-instruct:free",
    "huggingfaceh4/zephyr-7b-beta:free",
]

FREE_VISION_MODELS = [
    "google/gemini-2.0-flash-exp:free",
    "meta-llama/llama-3.2-90b-vision-instruct:free",
    "meta-llama/llama-3.2-11b-vision-instruct:free",
]

# === نماذج توليد الصور المجانية (للضرورة فقط) ===
FREE_IMAGE_MODELS = [
    "stabilityai/stable-diffusion-xl-base-1.0",
]

# ==========================================
# 1. مصادر RSS المتنوعة - كل المجالات
# ==========================================
RSS_FEEDS = {
    # === الكريبتو والعملات الرقمية ===
    "crypto": [
        "https://cointelegraph.com/rss",
        "https://decrypt.co/feed",
        "https://cryptoslate.com/feed/",
        "https://bitcoinmagazine.com/.rss/full/",
        "https://blockworks.co/feed/",
        "https://u.today/rss",
        "https://cryptonews.com/news/feed/",
        "https://beincrypto.com/feed/",
        "https://dailyhodl.com/feed/",
        "https://zycrypto.com/feed/",
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "https://cryptopotato.com/feed/",
        # مصادر عربية للكريبتو
        "https://ar.cointelegraph.com/rss",
        "https://arabmarketcap.com/feed/",
    ],
    
    # === الذكاء الاصطناعي والتقنية ===
    "ai_tech": [
        "https://techcrunch.com/category/artificial-intelligence/feed/",
        "https://www.wired.com/feed/category/ai/latest/rss",
        "https://venturebeat.com/category/ai/feed/",
        "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
        "https://openai.com/blog/rss/",
        "https://blog.google/technology/ai/rss/",
        "https://www.technologyreview.com/feed/",
        "https://news.mit.edu/topic/mitartificial-intelligence2-rss.xml",
        "https://ai.googleblog.com/feeds/posts/default",
        "https://machinelearningmastery.com/feed/",
        # مصادر عربية للتقنية
        "https://aitnews.com/feed/",
        "https://www.tech-wd.com/wd/feed/",
        "https://www.arageek.com/feed",
        "https://www.unlimit-tech.com/feed/",
    ],
    
    # === أخبار سياسية واقتصادية ===
    "politics_economy": [
        # مصادر عربية
        "https://www.aljazeera.net/aljazeerarss/a7c186be-1baa-4bd4-9d80-a84db769f779/73d0e1b4-532f-45ef-b135-bba5a9dd06a3",
        "https://www.alarabiya.net/.mrss/ar.xml",
        "https://www.skynewsarabia.com/web/rss",
        "https://arabic.rt.com/rss/",
        "https://www.france24.com/ar/rss",
        "https://www.bbc.com/arabic/index.xml",
        "https://www.independentarabia.com/rss",
        "https://www.aleqt.com/feed.rss",
        "https://makkahnewspaper.com/rss",
        # مصادر إنجليزية
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        "https://www.reuters.com/rssFeed/worldNews",
        "https://www.theguardian.com/world/rss",
    ],
    
    # === الاقتصاد والأعمال ===
    "business": [
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "https://www.bloomberg.com/feed/podcast/etf-iq.xml",
        "https://feeds.a]pnews.com/apnews/Business",
        "https://www.ft.com/rss/home",
        "https://www.economist.com/finance-and-economics/rss.xml",
        # عربي
        "https://www.argaam.com/ar/feeds/articles-rss",
        "https://www.mubasher.info/rss/news-sa",
        "https://www.aleqt.com/feed.rss",
        "https://arabic.investing.com/rss/news.rss",
    ],
    
    # === شروحات وتقنية البرامج ===
    "tutorials": [
        "https://www.howtogeek.com/feed/",
        "https://lifehacker.com/rss",
        "https://www.makeuseof.com/feed/",
        "https://www.digitaltrends.com/feed/",
        "https://www.tomsguide.com/feeds/all",
        "https://www.pcmag.com/feeds/all-articles",
        "https://www.zdnet.com/rss.xml",
        "https://www.cnet.com/rss/all/",
        # عربي
        "https://www.arageek.com/tech/feed",
        "https://www.tech-wd.com/wd/feed/",
        "https://www.unlimit-tech.com/feed/",
        "https://me.kaspersky.com/blog/feed/",
    ],
    
    # === أمن المعلومات ===
    "security": [
        "https://thehackernews.com/feeds/posts/default",
        "https://www.bleepingcomputer.com/feed/",
        "https://krebsonsecurity.com/feed/",
        "https://www.darkreading.com/rss.xml",
        "https://threatpost.com/feed/",
        "https://securityaffairs.co/wordpress/feed",
    ],
    
    # === العلوم والمستقبل ===
    "science": [
        "https://www.sciencedaily.com/rss/all.xml",
        "https://www.nature.com/nature.rss",
        "https://www.newscientist.com/feed/home/",
        "https://www.space.com/feeds/all",
        "https://phys.org/rss-feed/",
        # عربي
        "https://www.scientificamerican.com/arabic/rss/",
    ],
}

# === قائمة المصادر المسطحة للاستخدام ===
ALL_FEEDS = []
for category, feeds in RSS_FEEDS.items():
    ALL_FEEDS.extend(feeds)

# ==========================================
# 2. خريطة الأقسام الشاملة
# ==========================================
CATEGORY_MAP = {
    # كريبتو
    "News": 2, "Bitcoin": 2, "Ethereum": 2, "Web3": 2, "Regulation": 2, "Crypto": 2,
    "أخبار": 2, "بيتكوين": 2, "إيثريوم": 2, "عملات رقمية": 2,
    "Market": 3, "Analysis": 3, "Price": 3, "Trading": 3, "Chart": 3,
    "سوق": 3, "تحليل": 3, "تداول": 3,
    "DeFi": 4, "DEX": 4, "Swap": 4, "Lending": 4, "التمويل اللامركزي": 4,
    "Stablecoin": 6, "USDT": 6, "USDC": 6, "Tether": 6, "عملات مستقرة": 6,
    "DAO": 7, "Governance": 7, "حوكمة": 7,
    
    # تقنية وذكاء اصطناعي
    "AI": 8, "Artificial Intelligence": 8, "Machine Learning": 8, "ChatGPT": 8, "OpenAI": 8,
    "ذكاء اصطناعي": 8, "تعلم آلي": 8,
    "Technology": 9, "Tech": 9, "تقنية": 9, "تكنولوجيا": 9,
    "Software": 10, "Apps": 10, "برامج": 10, "تطبيقات": 10,
    "Security": 11, "Cybersecurity": 11, "Hacking": 11, "أمن المعلومات": 11, "اختراق": 11,
    
    # سياسة واقتصاد
    "Politics": 12, "سياسة": 12, "Government": 12, "حكومة": 12,
    "Economy": 13, "اقتصاد": 13, "Business": 13, "أعمال": 13,
    "Finance": 14, "مالية": 14, "Banking": 14, "بنوك": 14,
    
    # شروحات
    "Education": 5, "Guide": 5, "Tutorial": 5, "Learn": 5, "How": 5,
    "شروحات": 5, "دليل": 5, "تعلم": 5,
    
    # علوم
    "Science": 15, "علوم": 15, "Space": 15, "فضاء": 15,
    
    "Uncategorized": 1
}
DEFAULT_CATEGORY_ID = 2

# ==========================================
# 3. خريطة الصور الاحتياطية
# ==========================================
EMERGENCY_MAP = {
    "bitcoin": [
        "https://images.unsplash.com/photo-1621761191319-c6fb62004040?auto=format&fit=crop&w=1280&q=80",
        "https://images.unsplash.com/photo-1596239464385-2800555f68b4?auto=format&fit=crop&w=1280&q=80",
    ],
    "ethereum": [
        "https://images.unsplash.com/photo-1622630998477-20aa696fab05?auto=format&fit=crop&w=1280&q=80",
    ],
    "ai": [
        "https://images.unsplash.com/photo-1677442136019-21780ecad995?auto=format&fit=crop&w=1280&q=80",
        "https://images.unsplash.com/photo-1684391976641-39e8b13c2a81?auto=format&fit=crop&w=1280&q=80",
        "https://images.unsplash.com/photo-1676299081847-824916de030a?auto=format&fit=crop&w=1280&q=80",
    ],
    "tech": [
        "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1280&q=80",
        "https://images.unsplash.com/photo-1488590528505-98d2b5aba04b?auto=format&fit=crop&w=1280&q=80",
    ],
    "security": [
        "https://images.unsplash.com/photo-1563986768609-322da13575f3?auto=format&fit=crop&w=1280&q=80",
        "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?auto=format&fit=crop&w=1280&q=80",
    ],
    "economy": [
        "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=1280&q=80",
        "https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f?auto=format&fit=crop&w=1280&q=80",
    ],
    "politics": [
        "https://images.unsplash.com/photo-1529107386315-e1a2ed48a620?auto=format&fit=crop&w=1280&q=80",
        "https://images.unsplash.com/photo-1555848962-6e79363ec58f?auto=format&fit=crop&w=1280&q=80",
    ],
    "science": [
        "https://images.unsplash.com/photo-1507413245164-6160d8298b31?auto=format&fit=crop&w=1280&q=80",
        "https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=1280&q=80",
    ],
    "default": [
        "https://images.unsplash.com/photo-1639762681485-074b7f938ba0?auto=format&fit=crop&w=1280&q=80",
        "https://images.unsplash.com/photo-1620321023374-d1a68fddadb3?auto=format&fit=crop&w=1280&q=80",
    ]
}

DB_FILE = "/app/data/history.db" if os.path.exists("/app/data") else "history.db"

# ==========================================
# 4. دوال قاعدة البيانات
# ==========================================
def init_db():
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True) if "/" in DB_FILE else None
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (link TEXT PRIMARY KEY, title TEXT, published_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS api_usage 
                 (key_index INTEGER PRIMARY KEY, usage_count INTEGER, last_used TEXT)''')
    conn.commit()
    conn.close()

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
    c.execute("INSERT OR IGNORE INTO history VALUES (?, ?, ?)", 
              (link, title, datetime.now().isoformat()))
    conn.commit()
    conn.close()

# ==========================================
# 5. نظام منع التكرار
# ==========================================
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
            print(f"   ⚠️ عنوان مكرر: التشابه مع '{existing[:30]}...'")
            return True
    return False

# ==========================================
# 6. معالجة الصور المتقدمة
# ==========================================
def check_image_has_watermark(image_url):
    """فحص إذا كانت الصورة تحتوي على علامة مائية"""
    print(f"   🔍 فحص العلامة المائية: {image_url[:50]}...")
    
    api_key = get_next_api_key()
    http_client = httpx.Client(verify=False, transport=httpx.HTTPTransport(local_address="0.0.0.0"))
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key, http_client=http_client)
    
    for i in range(3):
        model = random.choice(FREE_VISION_MODELS)
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{
                    "role": "user", 
                    "content": [
                        {
                            "type": "text", 
                            "text": """Analyze this image carefully. Does it contain ANY of the following:
1. Watermarks (text overlay, logo overlay)
2. News channel logos (CNN, BBC, Reuters, etc)
3. Website URLs or domain names
4. Copyright text or symbols
5. Any identifying text overlay

Answer with EXACTLY one of these:
- "CLEAN" if the image has NO watermarks or logos
- "WATERMARK" if the image has ANY watermark, logo, or text overlay"""
                        }, 
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]
                }],
                max_tokens=50
            )
            result = response.choices[0].message.content.strip().upper()
            print(f"   📋 نتيجة الفحص: {result}")
            return "WATERMARK" in result
        except Exception as e:
            print(f"   ⚠️ خطأ في الفحص ({model}): {e}")
            api_key = get_next_api_key()  # جرب مفتاح آخر
            time.sleep(2)
    
    # في حالة الفشل، نفترض وجود علامة مائية للأمان
    return True

def apply_watermark_simple(image_bytes):
    """إضافة علامة مائية بسيطة للصورة النظيفة"""
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        width, height = img.size
        
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        # شريط شفاف في الأسفل
        bar_height = int(height * 0.06)
        draw.rectangle([(0, height - bar_height), (width, height)], fill=(0, 0, 0, 140))
        
        # محاولة تحميل خط عربي أو استخدام الافتراضي
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", int(bar_height * 0.6))
        except:
            try:
                font = ImageFont.truetype("arial.ttf", int(bar_height * 0.6))
            except:
                font = ImageFont.load_default()
        
        # كتابة العلامة المائية
        text = WATERMARK_TEXT
        
        # حساب موقع النص في المنتصف
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
        except:
            text_width = len(text) * 10
            text_height = bar_height * 0.5
        
        text_x = (width - text_width) / 2
        text_y = height - bar_height + (bar_height - text_height) / 2
        
        # ظل للنص
        draw.text((text_x + 2, text_y + 2), text, font=font, fill=(0, 0, 0, 200))
        # النص الأبيض
        draw.text((text_x, text_y), text, font=font, fill=(255, 255, 255, 255))
        
        combined = Image.alpha_composite(img, overlay)
        output = io.BytesIO()
        combined.convert("RGB").save(output, format="JPEG", quality=90)
        print(f"   ✅ تمت إضافة العلامة المائية: {WATERMARK_TEXT}")
        return output.getvalue()
        
    except Exception as e:
        print(f"   ⚠️ خطأ في إضافة العلامة: {e}")
        return image_bytes

def apply_watermark_cover(image_bytes):
    """إخفاء العلامة المائية الموجودة بشريط ووضع علامتنا فوقه"""
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        width, height = img.size
        
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        # شريط أكبر لتغطية العلامات المائية (عادة في الأسفل أو الزاوية)
        bar_height = int(height * 0.12)
        
        # شريط أسود غير شفاف لإخفاء العلامة المائية الأصلية
        draw.rectangle([(0, height - bar_height), (width, height)], fill=(20, 20, 30, 250))
        
        # إضافة خط زخرفي
        draw.rectangle([(0, height - bar_height), (width, height - bar_height + 3)], fill=(59, 130, 246, 255))
        
        try:
            font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(bar_height * 0.5))
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", int(bar_height * 0.3))
        except:
            try:
                font_large = ImageFont.truetype("arial.ttf", int(bar_height * 0.5))
                font_small = ImageFont.truetype("arial.ttf", int(bar_height * 0.3))
            except:
                font_large = ImageFont.load_default()
                font_small = font_large
        
        # العلامة المائية الرئيسية
        text = WATERMARK_TEXT
        try:
            bbox = draw.textbbox((0, 0), text, font=font_large)
            text_width = bbox[2] - bbox[0]
        except:
            text_width = len(text) * 15
        
        text_x = (width - text_width) / 2
        text_y = height - bar_height + int(bar_height * 0.15)
        
        # ظل ونص
        draw.text((text_x + 2, text_y + 2), text, font=font_large, fill=(0, 0, 0, 200))
        draw.text((text_x, text_y), text, font=font_large, fill=(255, 255, 255, 255))
        
        # نص "دليل العصر" تحته
        site_text = SITE_NAME
        try:
            bbox2 = draw.textbbox((0, 0), site_text, font=font_small)
            site_width = bbox2[2] - bbox2[0]
        except:
            site_width = len(site_text) * 8
        
        site_x = (width - site_width) / 2
        site_y = text_y + int(bar_height * 0.45)
        draw.text((site_x, site_y), site_text, font=font_small, fill=(200, 200, 200, 255))
        
        combined = Image.alpha_composite(img, overlay)
        output = io.BytesIO()
        combined.convert("RGB").save(output, format="JPEG", quality=90)
        print(f"   ✅ تم إخفاء العلامة المائية القديمة ووضع علامتنا: {WATERMARK_TEXT}")
        return output.getvalue()
        
    except Exception as e:
        print(f"   ⚠️ خطأ في تغطية العلامة: {e}")
        return image_bytes

def get_emergency_image_list(title):
    """الحصول على قائمة صور احتياطية حسب الموضوع"""
    t = title.lower()
    key = "default"
    
    if any(x in t for x in ["bitcoin", "btc", "بيتكوين"]): key = "bitcoin"
    elif any(x in t for x in ["ethereum", "eth", "إيثريوم"]): key = "ethereum"
    elif any(x in t for x in ["ai", "artificial", "gpt", "ذكاء اصطناعي", "chatgpt"]): key = "ai"
    elif any(x in t for x in ["hack", "security", "أمن", "اختراق", "cyber"]): key = "security"
    elif any(x in t for x in ["economy", "اقتصاد", "market", "سوق", "stock"]): key = "economy"
    elif any(x in t for x in ["politic", "سياس", "government", "حكوم"]): key = "politics"
    elif any(x in t for x in ["science", "علم", "space", "فضاء", "research"]): key = "science"
    elif any(x in t for x in ["tech", "تقن", "software", "برنامج", "app"]): key = "tech"
    
    images = EMERGENCY_MAP.get(key, EMERGENCY_MAP["default"]).copy()
    random.shuffle(images)
    return images

def get_generated_image_url(title):
    """توليد صورة بالذكاء الاصطناعي - للضرورة القصوى فقط"""
    print("   🎨 توليد صورة (للضرورة فقط)...")
    
    # استخدام Pollinations (مجاني)
    clean_title = re.sub(r'[^\w\s]', '', title)
    words = clean_title.split()[:6]
    prompt_text = " ".join(words)
    final_prompt = f"{prompt_text}, professional news style, clean, modern, 4k, no text, no watermark"
    encoded_prompt = urllib.parse.quote(final_prompt)
    seed = int(time.time())
    
    return f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1280&height=720&nologo=true&seed={seed}&model=flux"

# ==========================================
# 7. توليد المحتوى بالعربية
# ==========================================
def generate_arabic_content(news_item):
    """توليد محتوى عربي احترافي مع الحفاظ على الأرقام والمعلومات"""
    
    api_key = get_next_api_key()
    print(f"   🔑 استخدام مفتاح API: ...{api_key[-8:]}")
    
    http_client = httpx.Client(verify=False, transport=httpx.HTTPTransport(local_address="0.0.0.0"))
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key, http_client=http_client)
    
    prompt = f"""أنت كاتب محتوى محترف لموقع "دليل العصر".
اكتب مقالاً عربياً احترافياً اعتماداً على الخبر التالي فقط (بدون إضافة معلومات من خارج النص).

العنوان الأصلي: {news_item['title']}
ملخص الخبر: {news_item['summary']}

⚠️ قواعد صارمة جداً:
1) العربية الفصحى، أسلوب إخباري واضح ومباشر، بدون مبالغة أو "كليك بيت".
2) ممنوع اختراع تفاصيل. إذا لم توجد معلومة في الخبر اكتب: "بحسب ما ورد في التقرير" أو تجاهلها.
3) لا تغيّر أي رقم/نسبة/تاريخ/سعر/اسم علم. اتركها كما هي حرفياً.
4) أسماء العملات/الشركات/التقنيات المعروفة تبقى كما هي بالإنجليزية عند الحاجة (Bitcoin, Ethereum, AI, OpenAI...).
5) طول المقال: 450 إلى 650 كلمة تقريباً.
6) اكتب المحتوى بصيغة HTML فقط (بدون Markdown، بدون ```، بدون عناوين مثل: مقدمة/خاتمة ككلمات منفصلة).

✅ الهيكل المطلوب (HTML فقط):
A) صندوق "أبرز النقاط" (4 إلى 6 نقاط):
<div style="background:#111827;border-radius:12px;padding:18px;margin-bottom:22px;color:#fff;">
  <h4 style="margin:0 0 12px 0;font-size:1.2em;">🔥 أبرز النقاط</h4>
  <ul style="margin:0;padding-right:18px;line-height:1.8;">
    <li>...</li>
  </ul>
</div>

B) جسم المقال:
- ابدأ بمقدمة قصيرة (2-3 فقرات) داخل <p>.
- ثم 3 إلى 5 عناوين فرعية باستخدام <h2>، وتحت كل عنوان فقرات <p>.
- اختم بخلاصة قصيرة من فقرة واحدة.

🧾 في نهاية المقال (إلزامي جداً وبنفس الصيغة والحروف الكبيرة تماماً، وكل عنصر في سطر مستقل):
META_DESC: اكتب وصفاً ميتا بين 150 و160 حرفاً (بدون علامات اقتباس).
TAGS: اكتب 5 إلى 8 وسوم مفصولة بفواصل (مزيج عربي/إنجليزي عند الحاجة، بدون #).
CATEGORY: اختر اسماً واحداً فقط حرفياً من القائمة التالية (بدون أي شرح أو كلمات إضافية):
سياسة | صحة وطب | برامج | أجهزة | ذكاء اصطناعي | أمن المعلومات | عملات رقمية

مهم جداً:
- لا تكتب أي نص بعد سطر CATEGORY.
- لا تضع META_DESC أو TAGS أو CATEGORY داخل HTML. اكتبها كسطور نصية عادية في آخر المقال.
"""
    
    # محاولة 5 مرات مع نماذج مختلفة
    for attempt in range(5):
        model = random.choice(FREE_TEXT_MODELS)
        try:
            print(f"   🤖 محاولة {attempt + 1}/5 - النموذج: {model}")
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000
            )
            content = response.choices[0].message.content
            content = content.replace("```html", "").replace("```", "").strip()
            content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
            
            print(f"   ✅ تم توليد المحتوى بنجاح ({len(content)} حرف)")
            return content
            
        except Exception as e:
            print(f"   ⚠️ فشل النموذج ({model}): {e}")
            api_key = get_next_api_key()  # جرب مفتاح آخر
            client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key, http_client=http_client)
            time.sleep(3)
    
    return None

def generate_arabic_title(original_title):
    """توليد عنوان عربي جذاب"""
    
    api_key = get_next_api_key()
    http_client = httpx.Client(verify=False, transport=httpx.HTTPTransport(local_address="0.0.0.0"))
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key, http_client=http_client)
    
    prompt = f"""حوّل هذا العنوان إلى عنوان عربي صحفي موجز وواضح:

"{original_title}"

شروط صارمة:
1) احتفظ بالأرقام كما هي حرفياً.
2) لا تترجم أسماء العملات/الشركات/الأشخاص (Bitcoin, Ethereum, Apple...).
3) بدون مبالغة أو إثارة زائدة.
4) الطول 65 إلى 85 حرفاً تقريباً.
5) أعد العنوان فقط بدون أي شرح أو علامات اقتباس.
"""
    
    for attempt in range(3):
        model = random.choice(FREE_TEXT_MODELS)
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=100
            )
            title = response.choices[0].message.content.strip()
            title = title.replace('"', '').replace("'", "").strip()
            if title:
                return title
        except Exception as e:
            print(f"   ⚠️ خطأ في ترجمة العنوان: {e}")
            api_key = get_next_api_key()
            client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key, http_client=http_client)
            time.sleep(2)
    
    return original_title  # إرجاع العنوان الأصلي في حالة الفشل

# ==========================================
# 8. الرفع والنشر
# ==========================================
def get_auth_header():
    clean_pass = WP_APP_PASS.replace(' ', '')
    creds = base64.b64encode(f"{WP_USER}:{clean_pass}".encode()).decode()
    return {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}

def get_or_create_tag_id(tag_name):
    try:
        h = get_auth_header()
        r = requests.get(f"{WP_ENDPOINT}/tags?search={urllib.parse.quote(tag_name)}", headers=h, timeout=10)
        if r.status_code == 200 and r.json(): 
            return r.json()[0]['id']
        r = requests.post(f"{WP_ENDPOINT}/tags", headers=h, json={"name": tag_name}, timeout=10)
        if r.status_code == 201: 
            return r.json()['id']
    except Exception as e:
        print(f"   ⚠️ خطأ في الوسم '{tag_name}': {e}")
    return None

def upload_image_with_seo(img_url, alt_text, has_watermark=False):
    """رفع الصورة مع معالجة العلامة المائية"""
    print(f"   ⬆️ رفع الصورة: {alt_text[:30]}...")
    try:
        r_img = requests.get(img_url, headers=BROWSER_HEADERS, timeout=30, verify=False)
        if r_img.status_code == 200:
            # معالجة العلامة المائية
            if has_watermark:
                final_image_data = apply_watermark_cover(r_img.content)
            else:
                final_image_data = apply_watermark_simple(r_img.content)
            
            filename = f"dalilaleasr_{int(time.time())}.jpg"
            headers_wp = get_auth_header()
            headers_wp["Content-Disposition"] = f"attachment; filename={filename}"
            headers_wp["Content-Type"] = "image/jpeg"
            
            r_wp = requests.post(f"{WP_ENDPOINT}/media", headers=headers_wp, data=final_image_data, timeout=60)
            if r_wp.status_code == 201: 
                media_id = r_wp.json()['id']
                
                # تحديث SEO للصورة
                seo_data = {
                    "alt_text": alt_text, 
                    "title": alt_text, 
                    "caption": f"المصدر: دليل العصر - {alt_text}", 
                    "description": alt_text
                }
                requests.post(f"{WP_ENDPOINT}/media/{media_id}", headers=get_auth_header(), json=seo_data, timeout=10)
                print("   ✅ تم رفع الصورة بنجاح")
                return media_id
            else:
                print(f"   ❌ فشل الرفع: {r_wp.status_code}")
    except Exception as e:
        print(f"   ❌ خطأ في رفع الصورة: {e}")
    return None

def publish_to_wp(title, content, feat_img_id):
    """نشر المقال في WordPress"""
    meta_desc, tags, cat_id = "", [], DEFAULT_CATEGORY_ID
    def _pick_best_category_id(category_text: str) -> int:
        """اختر أقرب تصنيف معروف من CATEGORY_MAP بناءً على نص CATEGORY القادم من النموذج."""
        if not category_text:
            return DEFAULT_CATEGORY_ID

        # خذ أول سطر فقط (تجنب أي شرح إضافي)
        category_text = category_text.strip().splitlines()[0].strip()

        # إذا جاء بصيغة: "X | Y | Z" اختر أول عنصر معروف
        if "|" in category_text:
            parts = [p.strip() for p in category_text.split("|") if p.strip()]
            for p in parts:
                if p in CATEGORY_MAP:
                    return CATEGORY_MAP[p]
            category_text = parts[0] if parts else category_text

        # مطابقة مباشرة
        if category_text in CATEGORY_MAP:
            return CATEGORY_MAP[category_text]

        # مطابقة جزئية (contains)
        low = category_text.lower()
        for k, v in CATEGORY_MAP.items():
            if k.lower() in low or low in k.lower():
                return v

        # مطابقة تقريبية (fuzzy)
        best_k, best_ratio = None, 0.0
        for k in CATEGORY_MAP.keys():
            r = difflib.SequenceMatcher(None, low, k.lower()).ratio()
            if r > best_ratio:
                best_ratio, best_k = r, k

        if best_k and best_ratio >= 0.60:
            return CATEGORY_MAP[best_k]

        return DEFAULT_CATEGORY_ID

    
    # استخراج الميتا والوسوم والتصنيف
    if "META_DESC:" in content:
        try:
            parts = content.split("META_DESC:")
            content = parts[0]
            rest = parts[1]
            if "TAGS:" in rest:
                t_parts = rest.split("TAGS:")
                meta_desc = t_parts[0].strip()
                rest = t_parts[1]
                if "CATEGORY:" in rest:
                    c_parts = rest.split("CATEGORY:")
                    tags = [t.strip() for t in c_parts[0].split(',') if t.strip()]
                    
                    cat_id = _pick_best_category_id(c_parts[1])
        except Exception as e:
            print(f"   ⚠️ خطأ في تحليل الميتا: {e}")
    
    tag_ids = [tid for t in tags if t and (tid := get_or_create_tag_id(t))]
    focus_keyword = tags[0] if tags else "أخبار"
    
    data = {
        "title": title, 
        "content": content, 
        "status": "publish",
        "categories": [cat_id], 
        "tags": tag_ids, 
        "excerpt": meta_desc,
        "featured_media": feat_img_id,
        "meta": { 
            "rank_math_focus_keyword": focus_keyword,
            "rank_math_description": meta_desc
        }
    }
    
    try:
        r = requests.post(f"{WP_ENDPOINT}/posts", headers=get_auth_header(), json=data, timeout=30)
        if r.status_code == 201: 
            return r.json()['link']
        print(f"   ❌ فشل النشر: {r.status_code} - {r.text[:200]}")
    except Exception as e:
        print(f"   ❌ خطأ في النشر: {e}")
    return None

def extract_image_from_entry(entry):
    """استخراج الصورة من مدخل RSS"""
    # media_content
    if hasattr(entry, 'media_content') and entry.media_content:
        try:
            return entry.media_content[0].get('url') if isinstance(entry.media_content[0], dict) else entry.media_content[0]['url']
        except: pass
    
    # media_thumbnail
    if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        try:
            return entry.media_thumbnail[0].get('url')
        except: pass
    
    # enclosures
    if hasattr(entry, 'enclosures') and entry.enclosures:
        for enc in entry.enclosures:
            if 'image' in enc.get('type', ''):
                return enc.get('href') or enc.get('url')
    
    # links
    if hasattr(entry, 'links') and entry.links:
        for l in entry.links:
            link_type = getattr(l, 'type', '') or l.get('type', '')
            if 'image' in str(link_type): 
                return getattr(l, 'href', None) or l.get('href')
    
    # من الملخص
    if hasattr(entry, 'summary') and entry.summary:
        m = re.search(r'<img.*?src=["\']([^"\']+)["\']', entry.summary)
        if m: return m.group(1)
    
    # من المحتوى
    if hasattr(entry, 'content') and entry.content:
        for c in entry.content:
            content_value = getattr(c, 'value', '') or ''
            m = re.search(r'<img.*?src=["\']([^"\']+)["\']', content_value)
            if m: return m.group(1)
    
    return None

# ==========================================
# 9. المحرك الرئيسي
# ==========================================
def process_single_entry(entry):
    """معالجة خبر واحد"""
    print(f"\n   ⚡ معالجة: {entry.title[:60]}...")
    
    # 1. ترجمة العنوان للعربية
    arabic_title = generate_arabic_title(entry.title)
    print(f"   📝 العنوان العربي: {arabic_title[:50]}...")
    
    # 2. استخراج الصورة من المصدر
    original_img = extract_image_from_entry(entry)
    final_img_url = None
    has_watermark = False
    
    if original_img:
        print(f"   🖼️ صورة من المصدر: {original_img[:50]}...")
        has_watermark = check_image_has_watermark(original_img)
        final_img_url = original_img
    else:
        # لا توجد صورة - استخدام صورة احتياطية
        print("   ⚠️ لا توجد صورة - استخدام صورة احتياطية...")
        emergency_images = get_emergency_image_list(entry.title)
        if emergency_images:
            final_img_url = emergency_images[0]
            has_watermark = False
    
    # 3. رفع الصورة
    fid = None
    if final_img_url:
        fid = upload_image_with_seo(final_img_url, arabic_title, has_watermark)
    
    # إذا فشل الرفع، جرب الصور الاحتياطية
    if not fid:
        print("   🔄 محاولة صور احتياطية...")
        for backup_url in get_emergency_image_list(entry.title):
            fid = upload_image_with_seo(backup_url, arabic_title, False)
            if fid: break
    
    if not fid:
        print("   ❌ فشل رفع جميع الصور")
        return False
    
    # 4. توليد المحتوى العربي
    summary = getattr(entry, 'summary', '') or getattr(entry, 'description', '')
    content = generate_arabic_content({
        'title': entry.title, 
        'summary': summary
    })
    
    if not content:
        print("   ❌ فشل توليد المحتوى")
        return False
    
    # 5. النشر
    link = publish_to_wp(arabic_title, content, fid)
    if link:
        print(f"   ✅ تم النشر: {link}")
        mark_published(entry.link, arabic_title)
        return True
    
    return False

def main():
    print("=" * 60)
    print("🚀 دليل العصر - نظام النشر التلقائي V1.0")
    print("=" * 60)
    print(f"   🌐 الموقع: {WP_DOMAIN}")
    print(f"   👤 المستخدم: {WP_USER}")
    print(f"   🔑 عدد مفاتيح API: {len(OPENROUTER_KEYS)}")
    print(f"   📰 عدد مصادر RSS: {len(ALL_FEEDS)}")
    print(f"   💧 العلامة المائية: {WATERMARK_TEXT}")
    print("=" * 60)
    
    if not OPENROUTER_KEYS:
        print("❌ خطأ: لم يتم العثور على مفاتيح API!")
        print("   تأكد من إضافة OPENROUTER_KEY_1 إلى OPENROUTER_KEY_6 في Environment Variables")
        return
    
    init_db()
    
    articles_per_cycle = 0
    max_articles_per_cycle = 10  # الحد الأقصى للمقالات في كل دورة
    
    while True:
        print(f"\n{'='*60}")
        print(f"⏰ دورة جديدة: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*60}")
        
        articles_per_cycle = 0
        random.shuffle(ALL_FEEDS)  # خلط المصادر
        
        for feed_url in ALL_FEEDS:
            if articles_per_cycle >= max_articles_per_cycle:
                print(f"\n   🛑 تم الوصول للحد الأقصى ({max_articles_per_cycle} مقال)")
                break
            
            try:
                print(f"\n📡 قراءة: {feed_url[:50]}...")
                d = feedparser.parse(feed_url)
                
                if not d.entries:
                    continue
                
                for entry in d.entries[:3]:  # أول 3 أخبار من كل مصدر
                    if articles_per_cycle >= max_articles_per_cycle:
                        break
                    
                    # تخطي المنشور سابقاً
                    if is_published_link(entry.link):
                        continue
                    
                    # تخطي المكرر دلالياً
                    if is_duplicate_semantic(entry.title):
                        continue
                    
                    # معالجة ونشر
                    if process_single_entry(entry):
                        articles_per_cycle += 1
                    
                    # انتظار بين المقالات
                    time.sleep(20)
                    
            except Exception as e:
                print(f"   ⚠️ خطأ في المصدر: {e}")
                continue
        
        print(f"\n{'='*60}")
        print(f"📊 ملخص الدورة: تم نشر {articles_per_cycle} مقال")
        print(f"💤 استراحة 20 دقيقة...")
        print(f"{'='*60}")
        
        time.sleep(1200)  # 20 دقيقة

if __name__ == "__main__":
    main()
