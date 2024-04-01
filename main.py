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

xftgdb.import_words(session)

print('Start telegram bot...')

state_storage = StateMemoryStorage()
token_bot = config['bot_token']
bot = TeleBot(token_bot, state_storage=state_storage)

known_users = xftgdb.get_users(session)
userStep = {}
buttons = []

# print()
    
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
    '''Class for buttons and reply messages'''
    ADD_WORD = 'Добавить слово ➕'
    DELETE_WORD = 'Удалить слово🔙'
    NEXT = 'Дальше ⏭'
    CANCEL = 'Отмена ❌'
    YES = 'Да ✅'

def show_hint(*lines):
    '''Show hints, joining lines with '\n'''
    return '\n'.join(lines)

@bot.message_handler(commands=['start'])
def create_cards(message, step=0):
    '''Create cards for user
    step = 0 - for user who just started bot,
    else step = 1'''
    cid = message.chat.id
    if cid not in known_users:
        xftgdb.add_new_user(session, cid)
        known_users.append(cid)
        userStep[cid] = 0
        bot.send_message(cid, f"Hello, new user {message.from_user.username}, let study English...")
    else:
        if step == 0: bot.send_message(cid, f"Hello, {message.from_user.username}, I already know you!")
    markup = types.ReplyKeyboardMarkup(row_width=2)

    global buttons
    buttons = []
    word_tuple = xftgdb.get_random_word(session, cid)
    if not word_tuple:
        markup.add(types.KeyboardButton(Command.ADD_WORD))
        bot.send_message(cid, "В базе нет слов для изучения, хочешь добавить новое слово?", reply_markup=markup)
        return
    target_word = word_tuple[1]
    translate = word_tuple[0]

    target_word_btn = types.KeyboardButton(target_word)
    buttons.append(target_word_btn)
    others = xftgdb.get_other_words(session, cid, target_word)
    # others = ['Green', 'White', 'Hello']  # брать из БД
    other_words_btns = [types.KeyboardButton(word) for word in others]
    buttons.extend(other_words_btns)
    random.shuffle(buttons)
    next_btn = types.KeyboardButton(Command.NEXT)
    add_word_btn = types.KeyboardButton(Command.ADD_WORD)
    delete_word_btn = types.KeyboardButton(Command.DELETE_WORD)
    buttons.extend([add_word_btn, delete_word_btn, next_btn])

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
    '''Handler for NEXT button'''
    create_cards(message, 1)

@bot.message_handler(func=lambda message: message.text == Command.DELETE_WORD)
def delete_word(message):
    '''Handler for DELETE_WORD button'''
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        xftgdb.delete_word(session, message.from_user.id, data['translate_word'])
        bot.send_message(message.chat.id, f"Слово {data['translate_word']} удалено")
        print(f'Слово {data["target_word"]} удалено у {message.from_user.id}')  # удалить из БД
    create_cards(message, step=1)

@bot.message_handler(func=lambda message: message.text == Command.ADD_WORD)
def add_word(message):
    '''Handler for ADD_WORD button'''
    cid = message.chat.id
    userStep[cid] = 1
    markup = types.ReplyKeyboardMarkup(row_width=1)
    markup.add(types.KeyboardButton(Command.CANCEL))
    bot.send_message(cid, "Напиши новое слово(ru):", reply_markup=markup)
    bot.register_next_step_handler(message, get_ru_word)
def get_ru_word(message):
    '''Get russian word from user'''
    cid = message.chat.id
    if message.text == Command.CANCEL:
        create_cards(message,1)
    elif message.text == None:
        bot.send_message(message.chat.id, f"Пустые значения запрещены!\nНапиши новое слово(ru):")
        bot.register_next_step_handler(message, get_ru_word)
    elif xftgdb.is_cyrillic(message.text):
        target_word = xftgdb.translate_word(message.text, token=xftgdb.ya_token)
        markup = types.ReplyKeyboardMarkup(row_width=2)
        markup.add(types.KeyboardButton(Command.YES), types.KeyboardButton(Command.CANCEL))
        if target_word:
            answer = f'{target_word} - правильный перевод?\nЕсли да - оставьте поле пустым\nЕсли нет - напишите перевод'
        else:
            answer = f'Автоперевод не работает\nВведите перевод слова {message.text} на английском'
        bot.send_message(cid, answer, reply_markup=markup)
        bot.register_next_step_handler(message, get_en_word, message.text, target_word)
    else:
        bot.send_message(message.chat.id, "Нужно написать русскими буквами")
        bot.register_next_step_handler(message, get_ru_word)

def get_en_word(message, word, target_word):
    '''Get english word from user'''
    def send_to_add_db(message, tid, word, target_word):
        add_word_to_db(tid, word, target_word)
        create_cards(message, 1)
    tid = message.from_user.id
    if message.text == Command.CANCEL:
        create_cards(message,1)
    elif message.text == Command.YES:
        send_to_add_db(message, tid, word, target_word)
    else:
        if message.text == None:
            bot.send_message(message.chat.id, f"Пустые значения запрещены!\nВведите перевод для слова {word}:")
            bot.register_next_step_handler(message, get_en_word, word, target_word)
        elif xftgdb.is_english(message.text):
            send_to_add_db(message, tid, word, message.text)
        else:
            bot.send_message(message.chat.id, f"Нужно написать английскими буквами\nВведите перевод для слова {word}:")
            bot.register_next_step_handler(message, get_en_word, word, target_word)



def add_word_to_db(tid, word, translate):
    '''Add new word to user dictionary'''
    resp = xftgdb.add_new_word(session, tid, word, translate)
    if resp == 1:
        bot.send_message(tid, f"Слово {word} с переводом {translate} уже существует")
    else:
        bot.send_message(tid, f"Слово {word} с переводом {translate} добавлено")


@bot.message_handler(func=lambda message: True, content_types=['text'])
def message_reply(message):
    '''Handler for messages'''
    text = message.text
    markup = types.ReplyKeyboardMarkup(row_width=2)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        target_word = data['target_word']
        if text == target_word:
            hint = show_target(data)
            hint_text = ["Отлично!❤", hint]
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


bot.add_custom_filter(custom_filters.StateFilter(bot))

try:
    bot.infinity_polling(skip_pending=True)
except Exception as e:
    print(f"Error connecting to bot\n {e}")