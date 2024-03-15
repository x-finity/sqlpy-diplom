import sqlalchemy as sq
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
import json
from xf_ya import translate_word

Base = declarative_base()

def load_config(filename):
    with open(filename) as f:
        return json.load(f)

config = load_config('config.json')
ya_token = config['yandex_token']

def dsn(config):
    db_config = config['database']
    db_config.setdefault('port', 5432)
    db_config.setdefault('server', 'localhost')
    if not db_config['port']: db_config['port'] = 5432
    return f'postgresql://{db_config["user"]}:{db_config["password"]}@{db_config["server"]}:{db_config["port"]}/{db_config["database"]}'

DSN = dsn(config)
#print(DSN)

def create_db(engine):
    Base.metadata.create_all(engine)

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

def get_users(session):
    return [user.tguser_id for user in session.query(Users).all()]

def add_user(session, tguser_id):
    if session.query(Users).filter_by(tguser_id=tguser_id).first():
        return
    session.add(Users(tguser_id=tguser_id))
    session.commit()

if __name__ == '__main__':
    DSN = dsn(config)
    engine = sq.create_engine(DSN)
    create_db(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # import_words(session, echo=True)
    # print([word.word for word in session.query(Words).all()])
    print(get_users(session))