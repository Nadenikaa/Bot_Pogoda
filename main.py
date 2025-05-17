from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker

engine = create_engine('sqlite:///users.db', echo=False)
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True)
    last_city = Column(String)

Base.metadata.create_all(bind=engine)



from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import requests

OPENWEATHER_API_KEY = '28e98a498862694b331c8f89a99eca2b'
TELEGRAM_TOKEN = '7428899117:AAEWdqy5WsRKrJ8jIcDIQChNi5lcBpL-QPw'


def get_or_create_user(session, telegram_id):
    user = session.query(User).filter_by(telegram_id=telegram_id).first()
    if not user:
        user = User(telegram_id=telegram_id)
        session.add(user)
        session.commit()
    return user


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Напиши мне название города, и я пришлю погоду.\n"
                                    "Также ты можешь использовать команду /city для быстрого получения погоды по последнему городу.")


async def weather_by_city(city: str):
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ru"
    response = requests.get(url)
    if response.status_code != 200:
        return None, None

    data = response.json()
    if data.get("cod") != 200:
        return None, None

    weather_descr = data['weather'][0]['description'].capitalize()
    temp = data['main']['temp']
    feels_like = data['main']['feels_like']
    humidity = data['main']['humidity']
    wind_speed = data['wind']['speed']
    icon_code = data['weather'][0]['icon']  # добавляем код иконки

    text = (f"Погода в городе {city}:\n"
            f"{weather_descr}\n"
            f"Температура: {temp}°C, ощущается как {feels_like}°C\n"
            f"Влажность: {humidity}%\n"
            f"Ветер: {wind_speed} м/с")

    icon_url = f"http://openweathermap.org/img/wn/{icon_code}@2x.png"  # формируем URL иконки
    return text, icon_url


async def handle_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = update.message.text.strip()
    session = SessionLocal()

    user = get_or_create_user(session, update.effective_user.id)
    user.last_city = city
    session.commit()

    log_request(update.effective_user.id, city)

    answer, icon_url = await weather_by_city(city)
    if answer:
        # Отправляем фото с подписью:
        await update.message.reply_photo(photo=icon_url, caption=answer)
    else:
        await update.message.reply_text("Не удалось получить погоду по этому городу. Проверьте имя.")

    session.close()


def log_request(telegram_id, city):
    with open('requests_log.txt', 'a', encoding='utf-8') as f:
        f.write(f"Пользователь {telegram_id} запросил погоду для {city}\n")


async def weather_last_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=update.effective_user.id).first()
    if not user or not user.last_city:
        await update.message.reply_text("Вы ещё не указали город. Напишите его название обычным сообщением.")
    else:
        answer, icon_url = await weather_by_city(user.last_city)
        if answer:
            await update.message.reply_photo(photo=icon_url, caption=answer)
        else:
            await update.message.reply_text("Не удалось получить погоду по сохранённому городу.")
    session.close()


def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("city", weather_last_city))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_city))

    print("Бот запущен...")
    app.run_polling()


if __name__ == '__main__':
    main()
