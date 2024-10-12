import configparser
import httpx
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from aiogram import Bot, Dispatcher
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
import requests
import asyncio
from aiogram.types import BufferedInputFile
from datetime import datetime

config = configparser.ConfigParser(interpolation=None)
config.read('config.ini')

cookies = {
    'dfuid': config['cookies']['dfuid'],
    'xf_user': config['cookies']['xf_user'],
    'xf_session': config['cookies']['xf_session'],
    'xf_tfa_trust': config['cookies']['xf_tfa_trust'],
    'lolz.live_xf_tc_lmad': config['cookies']['lolz_live_xf_tc_lmad'],
}

user_id = config['telegram']['user_id']
API_TOKEN = config['telegram']['bot_token']

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
}

params = {
    'node_id': '766',
    'order': 'post_date',
    'direction': 'desc',
}

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

async def hourly_check():
    while True:
        await asyncio.sleep(3600)
        
        try:
            username, avatar_url, number = await fetch_user_data()

            try:
                n_str, y_str = number.split(" / ")
                n = int(n_str)
                y = int(y_str)
            except ValueError:
                print("Ошибка при разборе чисел. Убедитесь, что формат правильный.")
                continue

            if n > y:
                border_color = "#CC0000"
                message_suffix = "Срочно делай новый розыгрыш!"
                
                image = await create_image(username, f"{n} / {y}", avatar_url, border_color)

                bio = BytesIO()
                image.save(bio, 'PNG')
                bio.seek(0)

                input_file = BufferedInputFile(bio.read(), filename="user_image.png")

                await bot.send_photo(
                    chat_id=user_id,
                    photo=input_file,
                    caption=(
                        f"<b>Доступно:</b> {n} / {y}\n"
                        f"<b>Пользователь:</b> {username}\n"
                        "🟥 <i>Срочно:</i> превышен лимит!\n\n"
                        "<i>Автор: hashcrack</i>"
                    ),
                    parse_mode="HTML"
                )
        except Exception as e:
            print(f"Error during hourly check: {e}")

button = KeyboardButton(text='🔍Узнать')
keyboard = ReplyKeyboardMarkup(keyboard=[[button]], resize_keyboard=True)

@dp.message(Command("start"))
async def send_welcome(message):
    if str(message.from_user.id) == user_id:
        await message.answer("Привет, узнай, сколько сколько у тебя доступно участий. ", reply_markup=keyboard)

@dp.message(lambda message: message.text == "🔍Узнать")
async def handle_current_number(message):
    if str(message.from_user.id) == user_id:
        loading_message = await message.answer("⌛️", reply_markup=keyboard)

        try:
            username, avatar_url, number = await fetch_user_data()

            try:
                n_str, y_str = number.split(" / ")
                n = int(n_str)
                y = int(y_str)
            except ValueError:
                await message.answer("Ошибка")
                return

            if n > y:
                border_color = "#CC0000"
                message_suffix = "Срочно делай новый розыгрыш!"
            elif (y - n) > 1000:
                border_color = "#00CC99"
                message_suffix = ""
            else:
                border_color = "#FF9933"
                message_suffix = ""

            image = await create_image(username, f"{n} / {y}", avatar_url, border_color)

            bio = BytesIO()
            image.save(bio, 'PNG')
            bio.seek(0)
    
            input_file = BufferedInputFile(bio.read(), filename="user_image.png")

            await bot.send_photo(
                message.chat.id,
                photo=input_file,
                caption=(
                    f"<b>Доступно:</b> {n} / {y}\n"
                    f"<b>Пользователь:</b> {username}\n"
                    f"{message_suffix}\n\n"
                    "<b>Статусы:</b>\n"
                    "🟩 <i>Безопасно:</i> больше 1000\n"
                    "🟧 <i>Близко к лимиту:</i> меньше 1000\n"
                    "🟥 <i>Срочно:</i> превышен лимит\n\n"
                    "<i>Автор: hashcrack</i>"
                ),
                parse_mode="HTML"
            )
        finally:
            await loading_message.delete()

async def fetch_user_data():
    retries = 3
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(http2=True, timeout=30.0) as client:
                response = await client.get('https://lolz.live/forums/contests/', params=params, cookies=cookies, headers=headers)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                username_elem = soup.find(class_='hiddenNarrowUnder accountUsername username')
                username = username_elem.find(class_='style60').get_text(strip=True)
                
                avatar_elem = soup.find(class_='avatar').find('img')
                avatar_url = avatar_elem['src']
                
                number_elem = soup.find_all(class_='counterText')
                number = number_elem[0].get_text() if number_elem else "0"
                
                return username, avatar_url, number
        except httpx.ConnectTimeout:
            if attempt < retries - 1:
                await asyncio.sleep(5)
            else:
                raise

async def create_image(username, number, avatar_url, border_color):
    base_image = Image.new('RGB', (800, 300), '#A09378')
    
    avatar_response = requests.get(avatar_url)
    avatar_img = Image.open(BytesIO(avatar_response.content)).resize((200, 200))
    
    avatar_mask = Image.new('L', (200, 200), 0)
    draw_mask = ImageDraw.Draw(avatar_mask)
    draw_mask.rounded_rectangle([0, 0, 200, 200], radius=15, fill=255)
    avatar_img.putalpha(avatar_mask)

    border_size = 5
    
    draw = ImageDraw.Draw(base_image)
    draw.rounded_rectangle(
        [50 - border_size, 50 - border_size, 250 + border_size, 250 + border_size],
        radius=border_size + 15,
        fill=border_color
    )

    draw.rounded_rectangle([50, 50, 250, 250], radius=15, fill="#FFF")
    base_image.paste(avatar_img, (50, 50), avatar_img)
    
    try:
        font_large_bold = ImageFont.truetype("arialbd.ttf", 36)
        font_medium_bold = ImageFont.truetype("arialbd.ttf", 28)
        font_medium = ImageFont.truetype("arial.ttf", 24)
    except IOError:
        font_large_bold = ImageFont.load_default()
        font_medium_bold = ImageFont.load_default()
        font_medium = ImageFont.load_default()

    draw.text((280, 50), "Сейчас у тебя", font=font_medium, fill="#44433F")
    draw.text((280, 100), number, font=font_large_bold, fill="#FFF")
    draw.text((280, 150), username, font=font_medium_bold, fill="#FFF")
    draw.text((280, 200), f"Время мск: {datetime.now().strftime('%H:%M')}", font=font_medium, fill="#FFF")

    return base_image

async def main():
    asyncio.create_task(hourly_check())
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
