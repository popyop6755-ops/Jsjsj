import os
import json
import re
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# قراءة التوكن من إعدادات الاستضافة بأمان
BOT_TOKEN = os.getenv("BOT_TOKEN")


def scrape_amazon_product(url: str):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
            " like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        ),
    }

    response = requests.get(url, headers=headers, timeout=15)
    if response.status_code != 200:
        raise Exception(f"تعذر فتح الرابط (كود الحالة: {response.status_code})")

    soup = BeautifulSoup(response.content, "html.parser")

    # 1. الاسم
    title_tag = soup.find(id="productTitle")
    raw_name = title_tag.get_text(strip=True) if title_tag else "غير معروف"
    short_name = " ".join(raw_name.split()[:3]) if raw_name else "item"

    # 2. السعر
    target_price = 0.0
    price_whole = soup.find("span", class_="a-price-whole")
    price_fraction = soup.find("span", class_="a-price-fraction")

    if price_whole:
        clean_str = re.sub(r"[^\d]", "", price_whole.get_text(strip=True))
        if price_fraction:
            fraction_str = re.sub(
                r"[^\d]", "", price_fraction.get_text(strip=True)
            )
            clean_str += f".{fraction_str}"
        try:
            target_price = float(clean_str)
        except ValueError:
            target_price = 0.0
    else:
        alt_price = soup.find("span", class_="a-offscreen")
        if alt_price:
            match = re.search(
                r"[\d,]+(?:\.\d+)?", alt_price.get_text(strip=True)
            )
            if match:
                try:
                    target_price = float(match.group(0).replace(",", ""))
                except ValueError:
                    target_price = 0.0

    # 3. الفئة
    category = "عام"
    breadcrumbs = soup.find("div", id="wayfinding-breadcrumbs_feature_div")
    if breadcrumbs:
        crumbs = [
            a.get_text(strip=True)
            for a in breadcrumbs.find_all("a")
            if a.get_text(strip=True)
        ]
        if crumbs:
            category = crumbs[-1]

    if any(
        kw in raw_name.lower() or kw in category.lower()
        for kw in ["هاتف", "موبايل", "phone", "mobile"]
    ):
        category = "موبايل"

    return {
        "name": short_name,
        "url": url,
        "target_price": target_price,
        "category": category,
    }


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً بك! 👋\nأرسل رابط أمازون وسأقوم باستخراج بياناته كـ JSON."
    )


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    url_match = re.search(r"https?://[^\s]+", text)
    if not url_match:
        await update.message.reply_text("يرجى إرسال رابط صحيح.")
        return

    target_url = url_match.group(0)
    wait_msg = await update.message.reply_text("⏳ جارٍ جلب البيانات...")

    try:
        data = scrape_amazon_product(target_url)
        json_output = json.dumps(data, ensure_ascii=False, indent=2)
        await update.message.reply_text(
            f"```json\n{json_output}\n```", parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {str(e)}")
    finally:
        await wait_msg.delete()


if __name__ == "__main__":
    if not BOT_TOKEN:
        print("خطأ: لم يتم ضبط BOT_TOKEN!")
        exit(1)

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(
        MessageHandler(filters.TEXT & (~filters.COMMAND), handle_url)
    )

    print("البوت يعمل...")
    app.run_polling()
