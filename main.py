import sqlite3

import telebot
from telebot import types
import secret

# telegram bot token
bot_token = secret.BOT_TOKEN
bot = telebot.TeleBot(token=bot_token)

# Словарь для хранения состояний пользователей
user_states = {}

# db migrations
def init_db():
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS expenses (
                                                            expense_id INTEGER PRIMARY KEY AUTOINCREMENT, 
                                                            chat_id INTEGER NOT NULL, 
                                                            user_id INTEGER NOT NULL, 
                                                            amount REAL NOT NULL, 
                                                            description TEXT NOT NULL,
                                                            exclude INTEGER DEFAULT 0 NOT NULL,
                                                            CHECK(exclude IN (0, 1)))''')
    conn.commit()
    conn.close()


@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, 'Че надо?')


@bot.message_handler(commands=['help'])
def help(message):
    bot.send_message(message.chat.id, '''
/start
/help
/add_expense
/summary''')


# Команда /add_expense
@bot.message_handler(commands=['add_expense'])
def add_expense(message):
    user_id = message.from_user.id
    user_states[user_id] = 'waiting_for_amount'
    bot.reply_to(message, "Пожалуйста, введите сумму расхода:")


# Команда /summary
@bot.message_handler(commands=['summary'])
def summary(message):
    chat_id = message.chat.id
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()

    cursor.execute("""
WITH TotalExpenses AS (
    SELECT 
        chat_id,
        SUM(amount) AS total_amount,
        COUNT(DISTINCT user_id) AS user_count
    FROM 
        expenses
    WHERE 
        chat_id = @chat_id
    GROUP BY 
        chat_id
),
UserExpenses AS (
    SELECT 
        chat_id,
        user_id,
        SUM(amount) AS user_total
    FROM 
        expenses
    WHERE 
        chat_id = @chat_id
    GROUP BY 
        chat_id, user_id
),
UserBalances AS (
    SELECT 
        ue.chat_id,
        ue.user_id,
        ue.user_total,
        te.total_amount / te.user_count AS share,
        (ue.user_total - (te.total_amount / te.user_count)) AS balance
    FROM 
        UserExpenses ue
    JOIN 
        TotalExpenses te ON ue.chat_id = te.chat_id
)

SELECT 
    ub1.user_id AS debtor,
    ub2.user_id AS creditor,
    ABS(ub1.balance) AS amount
FROM 
    UserBalances ub1
JOIN 
    UserBalances ub2 ON ub1.chat_id = ub2.chat_id
WHERE 
    ub1.balance < 0 AND ub2.balance > 0
    AND ABS(ub1.balance) <= ub2.balance;

    """, (chat_id,))
    results = cursor.fetchall()

    summary_text = "Итоги расходов:\n"

    for debtor, creditor, amount in results:
        summary_text += f"Пользователь {debtor} должен заплатить пользователю {creditor} {amount} рублей\n"

    if not results:
        summary_text = "Нет зарегистрированных расходов."

    bot.reply_to(message, summary_text)

    conn.close()


# Обработка текстовых сообщений
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id

    if user_id in user_states:
        state = user_states[user_id]

        if state == 'waiting_for_amount':
            try:
                amount = float(message.text)
                user_states[user_id] = 'waiting_for_description'
                user_states[f'{user_id}_amount'] = amount  # Сохраняем сумму
                bot.reply_to(message, "Теперь введите описание расхода:")
            except ValueError:
                bot.reply_to(message, "Пожалуйста, введите корректную сумму.")

        elif state == 'waiting_for_description':
            description = message.text
            amount = user_states.pop(f'{user_id}_amount')  # Получаем сохраненную сумму
            user_states.pop(user_id)  # Удаляем состояние пользователя

            # Сохранение расхода в базе данных
            conn = sqlite3.connect('expenses.db')
            cursor = conn.cursor()
            cursor.execute("INSERT INTO expenses (chat_id, user_id, amount, description) VALUES (?, ?, ?, ?)",
                           (message.chat.id, user_id, amount, description))
            conn.commit()
            conn.close()

            bot.reply_to(message, f"Расход {amount} добавлен: {description}")
            #TODO: Выводить имя пользователя

# Основной код бота
if __name__ == '__main__':
    init_db()
    bot.polling(none_stop=True)