import asyncio
import logging
import re
import time
from dataclasses import dataclass

import requests
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext

import config
import functions

logging.basicConfig(filename=f"logs.log", format='%(asctime)s - %(levelname)s - %(message)s', level=logging.ERROR)
bot = Bot(token=config.bot_token)
dp = Dispatcher(bot, storage=MemoryStorage())

start_text = """
Привет! Я бот, который может скачивать видео из TikTok.
Просто отправь мне ссылку на видео.
"""


@dp.message_handler(commands=["start"], state="*")
async def handler_start(message: types.Message, state: FSMContext):
    functions.first_join(message.from_user.id, message.from_user.username)
    if message.get_args() == "email" and message.from_user.id in config.admin_id:
        await state.set_state("Email.message")
        await message.answer("Отправьте сообщение для рассылки (текст, фото, видео или гиф)")
    else:
        await message.answer(start_text)


@dp.message_handler(state="Email.message", content_types=['text', 'photo', 'video', 'gif', 'animation'])
async def handler_admin_mail_message_id(message: types.Message, state: FSMContext):
    message_id = message.message_id
    await state.set_state("Email.confirm")
    await state.update_data(message_id=message_id)
    await bot.copy_message(message.from_user.id, message.from_user.id, message_id)
    await message.answer("Отправьте + для подтверждения")


@dp.message_handler(state="Email.confirm")
async def handler_admin_mail_confirm(message: types.Message, state: FSMContext):
    if message.text == '+':
        async with state.proxy() as data:
            message_id = data['message_id']
        await state.finish()
        asyncio.create_task(send_email(message, message_id))
    else:
        await state.finish()
        await message.answer("Рассылка отменена")


async def send_email(message, message_id):
    users = functions.get_users()
    await message.answer(f"Рассылка началась\n"
                         f"Всего пользователей: {len(users)}")
    time_start = time.time()
    true_send = 0
    for user_id, in users:
        try:
            await bot.copy_message(user_id, message.from_user.id, message_id)
            true_send += 1
            await asyncio.sleep(0.05)
        except:
            pass
    text = f"""
✅ Рассылка окончена
👍 Отправлено: {true_send}
👎 Не отправлено: {len(users) - true_send}
🕐 Время выполнения: {int(time.time() - time_start)} секунд
"""
    await message.answer(text)


@dp.message_handler()
async def handler_convert_message(message: types.Message):
    functions.update_user(message.from_user.id, message.from_user.username)
    if re.match(r"https?://\w{1,3}.tiktok.com/@?[a-zA-Z0-9/\?\.&_=-]{5,100}", message.text):
        msg = await message.answer("🔁 Загрузка...")
        result = download_video(message.text)
        if result:
            await message.answer_video(result.video_url, caption=result.desc)
            await message.answer_audio(result.audio_url, title=f"result_{message.from_user.id}.mp3")
        else:
            await message.answer("Ошибка! Похоже что такого видео не существует.")
        await msg.delete()
    else:
        await message.answer(start_text)


@dataclass
class Result:
    video_url: str
    audio_url: str
    desc: str


def download_video(video_url: str) -> Result | None:
    res = requests.get(f'https://api.douyin.wtf/api?url={video_url}').json()
    if res["status"] == "success":
        result = Result(
            video_url=res["video_data"]["nwm_video_url_HQ"],
            audio_url=res["music"]["play_url"]["uri"],
            desc=res["desc"]
        )
        return result
    return None


async def on_startup(dp):
    info = await bot.get_me()
    config.bot_username = info.username
    print(f"~~~~~ Bot @{info.username} was started ~~~~~")


if __name__ == '__main__':
    from aiogram import executor

    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
