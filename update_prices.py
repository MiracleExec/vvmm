import asyncio
import re
from playwright.async_api import async_playwright

DATABASE_FILE = "database.lua"

# Основные страницы категорий Supreme Values
CATEGORIES = [
    "https://supremevalues.com/mm2/godlies",
    "https://supremevalues.com/mm2/chromas",
    "https://supremevalues.com/mm2/legendaries",
    "https://supremevalues.com/mm2/rares",
    "https://supremevalues.com/mm2/uncommons",
    "https://supremevalues.com/mm2/commons",
    "https://supremevalues.com/mm2/pets"
]

def clean_str(s):
    """Очищает строку от спецсимволов и приводит к нижнему регистру"""
    if not s: return ""
    return re.sub(r'[^\w]', '', str(s).lower())

def read_database_keys():
    """Считывает ключи с сохранением их точного порядка из database.lua"""
    keys = []
    try:
        with open(DATABASE_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        for line in lines:
            # Парсим строки вида ['KeyName'] = Value,
            match = re.search(r"\[['\"](.*?)['\"]\]", line)
            if match:
                keys.append(match.group(1))
    except Exception as e:
        print(f"Ошибка чтения {DATABASE_FILE}: {e}")
    return keys

async def scrape_supreme_prices():
    """Собирает цены всех предметов со всех категорий Supreme Values через Playwright"""
    supreme_data = {}

    async with async_playwright() as p:
        # Запуск Chromium с эмуляцией обычного браузера для обхода защиты
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = await context.new_page()

        for url in CATEGORIES:
            print(f"Парсинг категории: {url}...")
            try:
                await page.goto(url, wait_until="networkidle", timeout=35000)
                await page.wait_for_timeout(2000) # Задержка для подгрузки динамического контента

                items = await page.evaluate('''() => {
                    const results = [];
                    // Селекторы элементов карточек Supreme Values
                    const cards = document.querySelectorAll('.item-card, .item, [class*="item"]');
                    cards.forEach(card => {
                        const nameEl = card.querySelector('.item-name, .name, [class*="name"]');
                        const valEl = card.querySelector('.item-value, .value, [class*="value"]');
                        if (nameEl && valEl) {
                            results.push({
                                name: nameEl.innerText.trim(),
                                value: valEl.innerText.trim()
                            });
                        }
                    });
                    return results;
                }''')

                for item in items:
                    c_name = clean_str(item['name'])
                    # Чистим цену, оставляем только цифры и точку
                    val_clean = re.sub(r'[^\d.]', '', item['value'].replace(',', ''))
                    if val_clean:
                        try:
                            supreme_data[c_name] = float(val_clean)
                        except ValueError:
                            pass

            except Exception as e:
                print(f"Ошибка при обработке {url}: {e}")

        await browser.close()
    return supreme_data

def main():
    print(f"1. Чтение ключей из {DATABASE_FILE}...")
    keys = read_database_keys()
    if not keys:
        print("Ошибок: ключи в database.lua не найдены!")
        return

    print("2. Сбор цен с Supreme Values (обход Cloudflare)...")
    parsed_prices = asyncio.run(scrape_supreme_prices())

    print("3. Обновление значений в таблице...")
    updated_entries = []

    for key in keys:
        c_key = clean_str(key)
        price = parsed_prices.get(c_key, None)

        # Резервный поиск без суффиксов Gun/Knife/Pet (если ключи в файле с ними, а на сайте без)
        if price is None:
            base_key = re.sub(r'(gun|knife|pet)$', '', c_key)
            price = parsed_prices.get(base_key, 0.0)

        updated_entries.append((key, price))

    print(f"4. Перезапись файла {DATABASE_FILE}...")
    with open(DATABASE_FILE, "w", encoding="utf-8") as f:
        f.write("return {\n")
        for key, price in updated_entries:
            # Форматирование под твой стиль: ['Key'] = Value,
            f.write(f"    ['{key}'] = {price},\n")
        f.write("}\n")

    print("Готово! database.lua успешно обновлен актуальными ценами.")

if __name__ == "__main__":
    main()
