import random

from telebot import types, TeleBot, custom_filters
from telebot.storage import StateMemoryStorage
from telebot.handler_backends import State, StatesGroup

import xf_tgdb as xftgdb

config = xftgdb.load_config('config.json')
DSN = xftgdb.dsn(config)
engine = xftgdb.sq.create_engine(DSN)
xftgdb.create_db(engine)
Session = xftgdb.sessionmaker(bind=engine)
session = Session()

print('Start telegram bot...')

state_storage = StateMemoryStorage()
token_bot = config['bot_token']
bot = TeleBot(token_bot, state_storage=state_storage)

known_users = xftgdb.get_users(session)
userStep = {}
buttons = []

print(known_users)

@bot.message_handler(commands=['addme'])
def addme(message):
    cid = message.chat.id
    if cid not in known_users:
        xftgdb.add_user(session, cid)
        known_users.append(cid)
        userStep[cid] = 0
        bot.send_message(cid, f"Hello, {message.from_user.username}, I'll remember you!")
    else:
        bot.send_message(cid, f"Hello, {message.from_user.username}, I already know you!")
    
class MyStates(StatesGroup):
    target_word = State()
    translate_word = State()
    another_words = State()

def get_user_step(uid):
    if uid in userStep:
        return userStep[uid]
    else:
        known_users.append(uid)
        userStep[uid] = 0
        print("New user detected, who hasn't used \"/start\" yet")
        return 0

def show_target(data):
    return f"{data['target_word']} -> {data['translate_word']}"


class Command:
    ADD_WORD = 'Добавить слово ➕'
    DELETE_WORD = 'Удалить слово🔙'
    NEXT = 'Дальше ⏭'


bot.add_custom_filter(custom_filters.StateFilter(bot))

bot.infinity_polling(skip_pending=True)

'''

def show_hint(*lines):
    return '\n'.join(lines)

@bot.message_handler(commands=['cards', 'start'])
def create_cards(message):
    cid = message.chat.id
    if cid not in known_users:
        known_users.append(cid)
        userStep[cid] = 0
        bot.send_message(cid, "Hello, stranger, let study English...")
    markup = types.ReplyKeyboardMarkup(row_width=2)

    global buttons
    buttons = []
    target_word = 'Peace'  # брать из БД
    translate = 'Мир'  # брать из БД
    target_word_btn = types.KeyboardButton(target_word)
    buttons.append(target_word_btn)
    others = ['Green', 'White', 'Hello']  # брать из БД
    other_words_btns = [types.KeyboardButton(word) for word in others]
    buttons.extend(other_words_btns)
    random.shuffle(buttons)
    next_btn = types.KeyboardButton(Command.NEXT)
    add_word_btn = types.KeyboardButton(Command.ADD_WORD)
    delete_word_btn = types.KeyboardButton(Command.DELETE_WORD)
    buttons.extend([next_btn, add_word_btn, delete_word_btn])

    markup.add(*buttons)

    greeting = f"Выбери перевод слова:\n🇷🇺 {translate}"
    bot.send_message(message.chat.id, greeting, reply_markup=markup)
    bot.set_state(message.from_user.id, MyStates.target_word, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['target_word'] = target_word
        data['translate_word'] = translate
        data['other_words'] = others


@bot.message_handler(func=lambda message: message.text == Command.NEXT)
def next_cards(message):
    create_cards(message)


@bot.message_handler(func=lambda message: message.text == Command.DELETE_WORD)
def delete_word(message):
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        print(data['target_word'])  # удалить из БД


@bot.message_handler(func=lambda message: message.text == Command.ADD_WORD)
def add_word(message):
    cid = message.chat.id
    userStep[cid] = 1
    print(message.text)  # сохранить в БД


@bot.message_handler(func=lambda message: True, content_types=['text'])
def message_reply(message):
    text = message.text
    markup = types.ReplyKeyboardMarkup(row_width=2)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        target_word = data['target_word']
        if text == target_word:
            hint = show_target(data)
            hint_text = ["Отлично!❤", hint]
            next_btn = types.KeyboardButton(Command.NEXT)
            add_word_btn = types.KeyboardButton(Command.ADD_WORD)
            delete_word_btn = types.KeyboardButton(Command.DELETE_WORD)
            buttons.extend([next_btn, add_word_btn, delete_word_btn])
            hint = show_hint(*hint_text)
        else:
            for btn in buttons:
                if btn.text == text:
                    btn.text = text + '❌'
                    break
            hint = show_hint("Допущена ошибка!",
                             f"Попробуй ещё раз вспомнить слово 🇷🇺{data['translate_word']}")
    markup.add(*buttons)
    bot.send_message(message.chat.id, hint, reply_markup=markup)



'''