# 🚀 دليل إعداد Coolify لـ "دليل العصر"

## الخطوة 1: إنشاء مشروع جديد

1. سجل الدخول إلى لوحة تحكم Coolify
2. اضغط على **+ New Resource**
3. اختر **Docker Compose** أو **Dockerfile**

---

## الخطوة 2: رفع الملفات

ارفع الملفات التالية:
- `dalilaleasr_bot.py`
- `requirements.txt`
- `Dockerfile`
- `docker-compose.yml` (إذا اخترت Docker Compose)

---

## الخطوة 3: إضافة Environment Variables

### في Coolify، اذهب إلى: Settings → Environment Variables

اضغط على **+ Add** لكل متغير:

### المتغيرات المطلوبة:

| Variable Name | Value | مثال |
|--------------|-------|------|
| `OPENROUTER_KEY_1` | مفتاح API الأول | `sk-or-v1-xxx...` |
| `OPENROUTER_KEY_2` | مفتاح API الثاني | `sk-or-v1-xxx...` |
| `OPENROUTER_KEY_3` | مفتاح API الثالث | `sk-or-v1-xxx...` |
| `OPENROUTER_KEY_4` | مفتاح API الرابع | `sk-or-v1-xxx...` |
| `OPENROUTER_KEY_5` | مفتاح API الخامس | `sk-or-v1-xxx...` |
| `OPENROUTER_KEY_6` | مفتاح API السادس | `sk-or-v1-xxx...` |
| `WP_DOMAIN` | رابط موقعك | `https://dalilaleasr.com` |
| `WP_USER` | اسم مستخدم WordPress | `admin` |
| `WP_APP_PASS` | Application Password | `xxxx xxxx xxxx xxxx xxxx xxxx` |
| `WATERMARK_TEXT` | نص العلامة المائية | `dalilaleasr.com` |

### مثال بالصور:

```
┌─────────────────────────────────────────────────────┐
│ Environment Variables                               │
├─────────────────────────────────────────────────────┤
│ Name: OPENROUTER_KEY_1                              │
│ Value: sk-or-v1-d5059063e45018671880eaa898138788... │
│ [✓] Secret                                          │
├─────────────────────────────────────────────────────┤
│ Name: OPENROUTER_KEY_2                              │
│ Value: sk-or-v1-b61df3390438e21da7ebe8db549783...   │
│ [✓] Secret                                          │
├─────────────────────────────────────────────────────┤
│ ... (كرر لباقي المفاتيح)                            │
├─────────────────────────────────────────────────────┤
│ Name: WP_DOMAIN                                     │
│ Value: https://dalilaleasr.com                      │
│ [ ] Secret                                          │
├─────────────────────────────────────────────────────┤
│ Name: WP_USER                                       │
│ Value: admin                                        │
│ [ ] Secret                                          │
├─────────────────────────────────────────────────────┤
│ Name: WP_APP_PASS                                   │
│ Value: DBy4 QJKf grn2 XsY5 CKm9 jQlD               │
│ [✓] Secret                                          │
├─────────────────────────────────────────────────────┤
│ Name: WATERMARK_TEXT                                │
│ Value: dalilaleasr.com                              │
│ [ ] Secret                                          │
└─────────────────────────────────────────────────────┘
```

---

## الخطوة 4: إعداد Persistent Storage

لحفظ قاعدة البيانات (history.db):

1. اذهب إلى **Storages**
2. أضف Volume جديد:
   - **Source**: `dalilaleasr-data`
   - **Destination**: `/app/data`

---

## الخطوة 5: Deploy!

1. اضغط على **Deploy**
2. انتظر حتى يكتمل البناء
3. راقب السجلات للتأكد من العمل

---

## 🔍 مراقبة السجلات

في Coolify، اذهب إلى **Logs** لمشاهدة:

```
🚀 دليل العصر - نظام النشر التلقائي V1.0
============================================================
   🌐 الموقع: https://dalilaleasr.com
   👤 المستخدم: admin
   🔑 عدد مفاتيح API: 6
   📰 عدد مصادر RSS: 50
   💧 العلامة المائية: dalilaleasr.com
============================================================

⏰ دورة جديدة: 2024-01-15 10:30
📡 قراءة: https://cointelegraph.com/rss...
   ⚡ معالجة: Bitcoin Surges Past $50,000...
   📝 العنوان العربي: البيتكوين يتجاوز 50,000 دولار...
   🖼️ صورة من المصدر: https://...
   🔍 فحص العلامة المائية...
   📋 نتيجة الفحص: CLEAN
   ✅ تمت إضافة العلامة المائية: dalilaleasr.com
   ⬆️ رفع الصورة...
   ✅ تم رفع الصورة بنجاح
   🔑 استخدام مفتاح API: ...b304ee3
   🤖 محاولة 1/5 - النموذج: google/gemini-2.0-flash-exp:free
   ✅ تم توليد المحتوى بنجاح (2500 حرف)
   ✅ تم النشر: https://dalilaleasr.com/bitcoin-surges/
```

---

## ⚠️ حل المشاكل الشائعة

### ❌ خطأ: "لم يتم العثور على مفاتيح API"
**الحل**: تأكد من إضافة `OPENROUTER_KEY_1` على الأقل في Environment Variables

### ❌ خطأ: "فشل النشر 401"
**الحل**: تأكد من صحة `WP_USER` و `WP_APP_PASS`

### ❌ خطأ: "فشل رفع الصورة"
**الحل**: تأكد من تفعيل REST API في WordPress وصلاحيات المستخدم

### ❌ الصور لا تظهر
**الحل**: تأكد من تثبيت `libjpeg` و `Pillow` (موجودة في Dockerfile)

---

## 📞 نصائح إضافية

1. **راقب الاستهلاك**: تحقق من استهلاك API في OpenRouter
2. **النسخ الاحتياطي**: احتفظ بنسخة من `history.db` بشكل دوري
3. **تحديث المصادر**: يمكنك إضافة/حذف مصادر RSS في الكود
4. **تعديل التردد**: غيّر `time.sleep(1200)` لتعديل فترة الراحة

---

**تم بنجاح! 🎉 موقع دليل العصر جاهز للنشر التلقائي**
