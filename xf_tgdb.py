import sqlalchemy as sq
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
import json
import re
import sys
from xf_ya import translate_word

Base = declarative_base()

def load_config(filename):
    with open(filename) as f:
        return json.load(f)

config = load_config('config.json')
ya_token = config['yandex_token']

# def translate(word, ya_token=ya_token):
#     return translate_word(word, ya_token)

def dsn(config):
    db_config = config['database']
    db_config.setdefault('port', 5432)
    db_config.setdefault('host', 'localhost')
    db_config.setdefault('username', 'postgres')
    db_config.setdefault('drivername', 'postgresql')
    db_config.setdefault('password', '')
    return sq.URL.create(**db_config)
    # return f'postgresql://{db_config["user"]}:{db_config["password"]}@{db_config["server"]}:{db_config["port"]}/{db_config["database"]}'

DSN = dsn(config)
#print(DSN)

def create_db(engine):
    try:
        Base.metadata.create_all(engine)
    except sq.exc.OperationalError as e:
        sys.exit(f"Error: Cannot connect to database\n{e}")

class Users(Base):
    __tablename__ = 'users'
    id = sq.Column(sq.Integer, primary_key=True)
    tguser_id = sq.Column(sq.Integer, nullable=False, unique=True)

class Words(Base):
    __tablename__ = 'words'    
    id = sq.Column(sq.Integer, primary_key=True)
    word = sq.Column(sq.String, nullable=False, unique=True)
    translate = sq.Column(sq.String, nullable=False)
    

class TgUserWord(Base):
    __tablename__ = 'user_words'
    id = sq.Column(sq.Integer, primary_key=True)
    user_id = sq.Column(sq.Integer, sq.ForeignKey('users.id'), nullable=False)
    word_id = sq.Column(sq.Integer, sq.ForeignKey('words.id'), nullable=False)
    users = relationship(Users, backref='userwords')
    words = relationship(Words, backref='userwords')

def import_words(session, filename='words.txt', echo=False):
    with open(filename) as f:
        error_stack = []
        words = [word.word for word in session.query(Words).all()]
        # words = [word for word in f.read().split(' ') if word]
        for word in f.read().split(' '):
            if word and word not in words:
                word_translate = translate_word(word, ya_token)
                words.append(word)
                try: # а нужен ли этот обработчик?
                    session.add(Words(word=word, translate=word_translate))
                    session.commit()
                    if echo: print(f'{word} - {word_translate} added')
                except sq.exc.IntegrityError:
                    session.rollback()
                    error_stack.append(f'{word} exists')
            else:
                error_stack.append(f'{word} exists')
    if echo: 
        print(f'Added {len(words)} words : {", ".join(words)}')
        if error_stack:
            print(error_stack) 
        else:
            print('No errors')

def export_to_json(session, filename='words.json'):
    query = sq.select(Words.word, Words.translate).select_from(Words)
    with open(filename, 'w') as f:
        f.write(json.dumps([{'word': row.word, 'translate': row.translate} for row in session.execute(query).all()],
                           ensure_ascii=False, indent=4))

def get_users(session):
    return [user.tguser_id for user in session.query(Users).all()]

def add_new_user(session, tguser_id):
    if session.query(Users).filter_by(tguser_id=tguser_id).first():
         return
    session.add(Users(tguser_id=tguser_id))
    user_id = session.query(Users).filter_by(tguser_id=tguser_id).first().id
    for word in session.query(Words).all():
        # print(word.id, word.word, word.translate)
        session.add(TgUserWord(user_id=user_id, word_id=word.id))
    session.commit()

def get_random_word(session, tguser_id):
    # q = sq.select(Words).order_by(sq.func.random()).limit(1)
    # q = sq.select(TgUserWord).join(Words, TgUserWord.word_id == Words.id).order_by(sq.func.random()).limit(1)
    q = sq.select(Words.word, Words.translate).join(TgUserWord, Words.id == TgUserWord.word_id).join(Users, TgUserWord.user_id == Users.id) \
        .filter(Users.tguser_id == tguser_id).order_by(sq.func.random()).limit(1)
    for word in session.execute(q).all():
        return word

def get_other_words(session, tguser_id, except_word):
    q = sq.select(Words.translate).join(TgUserWord, Words.id == TgUserWord.word_id).join(Users, TgUserWord.user_id == Users.id) \
        .filter(Users.tguser_id == tguser_id).filter(Words.translate != except_word).order_by(sq.func.random()).limit(3)
    other_words = []
    for word in session.execute(q).all():
        other_words.append(word.translate)
    return other_words

def delete_word(session, tguser_id, word):
    session.query(TgUserWord).filter(TgUserWord.user_id == session.query(Users).filter_by(tguser_id=tguser_id).first().id). \
        filter(TgUserWord.word_id == session.query(Words).filter_by(word=word).first().id).delete()
    session.commit()

def add_new_word(session, tguser_id, word, translate):
    if session.query(Words).filter_by(word=word).first():
        return 1
    session.add(Words(word=word, translate=translate))
    session.add(TgUserWord(user_id=session.query(Users).filter_by(tguser_id=tguser_id).first().id,
                           word_id=session.query(Words).filter_by(word=word).first().id))
    session.commit()

def is_cyrillic(word):
    if re.match('^[а-яА-Я]*$', word):
        return True
    return False

def is_english(word):
    if re.match('^[a-zA-Z]*$', word):
        return True
    return False

if __name__ == '__main__':
    DSN = dsn(config)
    engine = sq.create_engine(DSN)
    create_db(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # import_words(session, echo=True)
    # export_to_json(session)
    # print(get_users(session))
    # add_new_user(session, 1782742233)
    # word_tuple = get_random_word(session, 1782742233)
    # print(word_tuple, get_other_words(session, 1782742233, word_tuple[0]))
    # delete_word(session, 1782742233, 'собака')
    print(is_cyrillic('привет'))