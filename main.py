import telebot
from telebot import types
import secret

bot_token = secret.BOT_TOKEN
bot = telebot.TeleBot(token=bot_token)


@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, 'Че надо.')


@bot.message_handler(commands=['help'])
def help(message):
    bot.send_message(message.chat.id, 'Спасение утопающих - дело рук самих утопающих')


@bot.message_handler(func=lambda message: True)
def handle_message(message):
    name = message.from_user.first_name
    bot.reply_to(message, f'{name}, иди нахуй)))0))')


bot.polling(non_stop=True)