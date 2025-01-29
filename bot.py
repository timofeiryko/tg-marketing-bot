import asyncio
import logging
import sys
import os
import datetime
import re
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from apscheduler_di import ContextSchedulerDecorator

from email_validator import validate_email, EmailNotValidError

from messages import MESSAGES_DICT, PATHS_DICT, TG_POST_LINK, PRICE

from backend import TelegramUser, init
from update_sheet import append_user
from tortoise import Tortoise

# <--- Setup --->

load_dotenv(override=True)

TOKEN = os.getenv('TG_BOT_TOKEN')
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
storage = MemoryStorage()

PROVIDER_TOKEN = os.getenv('PROVIDER_TOKEN')

SELLING_DATETIME = os.getenv('SELLING_DATETIME')
# Convert the string to a datetime object
SELLING_DATETIME = datetime.datetime.strptime(SELLING_DATETIME, '%Y-%m-%d %H:%M:%S')

JOBSTORES = {
    'default': RedisJobStore(jobs_key='jobs', run_times_key='run_times', host='localhost', port=6379)
}

scheduler = ContextSchedulerDecorator(AsyncIOScheduler(jobstores=JOBSTORES))
scheduler.ctx.add_instance(bot, Bot)

redis_storage = RedisStorage.from_url('redis://localhost:6379')
dp = Dispatcher(storage=redis_storage)

class PaymentStates(StatesGroup):
    wait_for_email = State()

# <--- Handlers --->

@dp.message(CommandStart())
async def start(message: types.Message):

    user, _ = await TelegramUser.get_or_create(
        telegram_id=message.from_user.id,
        defaults={
            'username': message.from_user.username,
            'first_name': message.from_user.first_name,
            'last_name': message.from_user.last_name
        }
    )

    keyboad = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text=MESSAGES_DICT['start_keyboard'])]
        ],
        resize_keyboard=True
    )

    await message.answer(MESSAGES_DICT['start'], reply_markup=keyboad)

@dp.message(lambda message: message.text == MESSAGES_DICT['start_keyboard'])
async def start_keyboard(message: types.Message):

    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text=MESSAGES_DICT['get_file'])]
        ],
        resize_keyboard=True
    )

    image_path = PATHS_DICT['team_photo']
    image_from_pc = types.FSInputFile(image_path)

    await message.answer_photo(
        photo=image_from_pc,
        caption=MESSAGES_DICT['answer_start_kayboard'],
        reply_markup=keyboard,
        show_caption_above_media=True
    )

TEST = True

@dp.message(lambda message: message.text == MESSAGES_DICT['get_file'])
async def get_file(message: types.Message):

    file_path = PATHS_DICT['pdf_file']
    file_from_pc = types.FSInputFile(file_path)

    await message.answer_document(document=file_from_pc, reply_markup=types.ReplyKeyboardRemove())

    now = datetime.datetime.now()
    if now > SELLING_DATETIME:

        today = now.date()
        tomorrow = today + datetime.timedelta(days=1)
        tomorrow_morning = datetime.datetime.combine(tomorrow, datetime.time(7, 0))

        if TEST:
            tomorrow_morning = now + datetime.timedelta(seconds=30)

        scheduler.add_job(send_morning_selling_message, 'date', run_date=tomorrow_morning, kwargs={'user_id': message.from_user.id}, name=f'bio_morning_{message.from_user.id}')

async def send_selling_message(bot: Bot):
    
    users = await TelegramUser.filter(has_payed_for_intensive=False)
    for user in users:

        user_id = user.telegram_id

        message_text = MESSAGES_DICT['selling_message']

        await bot.send_message(chat_id=user_id, text=message_text)
        asyncio.sleep(10)

        keyboard = types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text=MESSAGES_DICT['buy_button'])]
            ],
            resize_keyboard=True
        )

        await bot.send_message(chat_id=user_id, text=MESSAGES_DICT['buy'], reply_markup=keyboard)

async def send_morning_selling_message(bot: Bot, user_id: int):

    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text=MESSAGES_DICT['buy_button'])]
        ], resize_keyboard=True
    )

    await bot.send_message(chat_id=user_id, text=MESSAGES_DICT['morning'], reply_markup=keyboard)

@dp.message(lambda message: message.text == MESSAGES_DICT['buy_button'])
async def buy_button(message: types.Message, state: FSMContext):

    await state.set_state(PaymentStates.wait_for_email)
    await message.answer(MESSAGES_DICT['ask_for_email'], reply_markup=types.ReplyKeyboardRemove())

@dp.message(PaymentStates.wait_for_email)
async def process_email(message: types.Message, state: FSMContext):

    email = message.text

    try:
        emailinfo = validate_email(email, check_deliverability=True)
    except EmailNotValidError as e:
        await message.answer(f"Адрес электронной почты не валиден:\n\n{e}\n\nПожалуйста, введи правильный адрес 😔")
        await state.set_state(PaymentStates.wait_for_email)
        return

    email = emailinfo.normalized

    try:
        user = await TelegramUser.get(telegram_id=message.from_user.id)
    except TelegramUser.DoesNotExist:
        await message.answer(MESSAGES_DICT['error'])
        return
    
    user.email = email
    await user.save()

    await message.answer_invoice(
        title='Интенсив к перечневым олимпиадам по биологии',
        description='Лекции по часто встречающимся темам и много практики: семинары и созвоны',
        provider_token=PROVIDER_TOKEN,
        currency='rub',
        prices=[
            types.LabeledPrice(label='Интенсив', amount=PRICE*100)
        ],
        payload=f'buy_intensive'
    )

@dp.pre_checkout_query()
async def process_precheckout_query(query: types.PreCheckoutQuery):
    await query.answer(ok=True)

@dp.message(F.successful_payment)
async def process_successful_payment(message: types.Message):

    payload = message.successful_payment.invoice_payload

    if payload == 'buy_intensive':

        user, _ = await TelegramUser.get_or_create(
            telegram_id=message.from_user.id,
            defaults={
                'username': message.from_user.username,
                'first_name': message.from_user.first_name,
                'last_name': message.from_user.last_name
            }
        )

        user.has_payed_for_intensive = True
        await user.save()

        await message.answer(MESSAGES_DICT['after_payment'])

        await append_user(user)




# <--- Run the bot in the main loop --->

async def main() -> None:

    # Initialize the Tortoise ORM
    await init()

    # Initialize Bot instance with default bot properties which will be passed to all API calls
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))

    # Schedule the job to send a message at the selling date
    scheduler.start()
    scheduler.add_job(send_selling_message, 'date', run_date=SELLING_DATETIME, replace_existing=True, name='bio_selling')

    # And the run events dispatching
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())