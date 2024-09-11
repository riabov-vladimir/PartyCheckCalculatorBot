import sqlite3
import itertools
import telebot
from telebot import types

import secret
from faq_text import faq_text

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
                                                            username TEXT, 
                                                            amount REAL NOT NULL, 
                                                            description TEXT NOT NULL,
                                                            exclude INTEGER DEFAULT 0 NOT NULL,
                                                            CHECK(exclude IN (0, 1)))''')
    conn.commit()
    conn.close()


@bot.message_handler(commands=['start'])
def send_welcome(message):
    # Создаем inline-кнопку
    markup = types.InlineKeyboardMarkup()
    button = types.InlineKeyboardButton("🍻 Я в деле!", callback_data='participate')
    markup.add(button)

    # Отправляем приветственное сообщение с кнопкой
    bot.send_message(message.chat.id, 'Здрасьте! Я пришел помочь вам с бухгалтерией.\nКто будет '
                                      'скидываться - ОБЯЗАТЕЛЬНО жмите "🍻 Я в деле!" под этим сообщением, либо в меню бота!', reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == 'participate')
def inline_participate(call):
    username = call.from_user.username
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO expenses (chat_id, user_id, username, amount, description) VALUES (?, ?, ?, ?, ?)",
                   (call.message.chat.id, call.from_user.id, call.from_user.username, 0, f'{call.from_user.username} added via callback'))
    conn.commit()
    conn.close()
    # bot.send_message(message.chat.id, f'@{username}, понял принял!')
    bot.send_message(call.message.chat.id, f'@{username}, понял принял!')


@bot.message_handler(commands=['participate'])
def participate(message):
    username = message.from_user.username
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO expenses (chat_id, user_id, username, amount, description) VALUES (?, ?, ?, ?, ?)",
                   (message.chat.id, message.from_user.id, message.from_user.username, 0, f'{message.from_user.username} added'))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, f'@{username}, понял принял!')


@bot.message_handler(commands=['drop_expenses'])
def drop_expenses(message):
    username = message.from_user.username
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()

    cursor.execute("""
         SELECT
             SUM(amount) as total_amount
         FROM expenses
         WHERE chat_id = @chat_id
         """, (message.chat.id,))
    total_amount = cursor.fetchone()

    cursor.execute("""
         SELECT
             AVG(amount) as average_amount
         FROM expenses
         WHERE chat_id = @chat_id
         """, (message.chat.id,))
    average_amount = cursor.fetchone()

    text = (f'Ну что, все живы здоровы? Надеюсь вы хорошо провели время)\n\nПо итогу гульнули на {round(total_amount[0])}₽, это по {round(average_amount[0])}₽ с носа.\n\n'
            f'Итого по расходам:\n\n')

    cursor.execute("""
        SELECT amount, username, description FROM expenses WHERE chat_id = @chat_id AND amount > 0
                        """, (message.chat.id, ))
    results = cursor.fetchall()

    i = 1
    for amount, username, description in results:
        text += f'{i}. {round(amount)}₽ от @{username} ({description})\n\n'
        i += 1

    text += '\n\nНа этом извольте откланяться! Всем пока и до новых встреч 👋'

    cursor.execute("""
        DELETE FROM expenses WHERE chat_id = @chat_id
    """, (message.chat.id, ))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, text)


@bot.message_handler(commands=['list_expenses'])
def participate(message):
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()

    cursor.execute("""
         SELECT
             SUM(amount) as total_amount
         FROM expenses
         WHERE chat_id = @chat_id
         """, (message.chat.id,))
    total_amount = cursor.fetchone()

    cursor.execute("""
         SELECT
             AVG(amount) as average_amount
         FROM expenses
         WHERE chat_id = @chat_id
         """, (message.chat.id,))
    average_amount = cursor.fetchone()

    text = (f'По {round(average_amount[0])}₽ с человека. Общая сумма - {round(total_amount[0])}₽\n\n'
            f'Список рарсходов на данный момент:\n\n')

    cursor.execute("""
        SELECT amount, username, description FROM expenses WHERE chat_id = @chat_id AND amount > 0
                        """, (message.chat.id, ))
    results = cursor.fetchall()

    i = 1
    for amount, username, description in results:
        text += f'{i}. {round(amount)}₽ от @{username} ({description})\n\n'
        i += 1

    bot.send_message(message.chat.id, text)

    conn.close()

@bot.message_handler(commands=['help'])
def help(message):
    bot.send_message(message.chat.id, faq_text, parse_mode='MarkdownV2')


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
    print(chat_id)
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()

    cursor.execute("""
        WITH TotalExpenses AS (
            SELECT 
                SUM(amount) AS total_amount
            FROM 
                expenses
            WHERE 
                chat_id = @chat_id
        ),
        UserExpenses AS (
            SELECT 
                username,
                SUM(amount) AS user_total
            FROM 
                expenses
            WHERE 
                chat_id = @chat_id
            GROUP BY 
                username
        ),
        UserBalances AS (
            SELECT 
                ue.username,
                ue.user_total,
                (te.total_amount / (SELECT COUNT(*) FROM UserExpenses)) AS share,
                (ue.user_total - (te.total_amount / (SELECT COUNT(*) FROM UserExpenses))) AS balance
            FROM 
                UserExpenses ue,
                TotalExpenses te
        ),
        Debtors AS (
            SELECT 
                username,
                ABS(balance) AS debt
            FROM 
                UserBalances
            WHERE 
                balance < 0
        ),
        Creditors AS (
            SELECT 
                username,
                user_total - (SELECT total_amount / (SELECT COUNT(*) FROM UserExpenses) FROM TotalExpenses) AS net_contribution
            FROM 
                UserBalances
            WHERE 
                balance > 0
        ),
        TotalDebt AS (
            SELECT 
                SUM(debt) AS total_debt
            FROM 
                Debtors
        )
        
        SELECT 
            d.username AS debtor,
            c.username AS creditor,
            (d.debt * (c.net_contribution / (SELECT SUM(net_contribution) FROM Creditors))) AS amount_to_pay
        FROM 
            Debtors d
        CROSS JOIN 
            Creditors c;
    """, (chat_id,))
    results = cursor.fetchall()
    print(results)

    if results:
        summary_text = "Так кто, кому и сколько должен?\n\n"

        keyfunc = lambda x: x[0]

        results_sorted = sorted(results, key=keyfunc)

        for debtor, creditor in itertools.groupby(results_sorted, key=keyfunc):

            summary_text += f'🔻 @{debtor} скинь:\n'

            order_action = sorted(creditor, key=lambda x: x[2])

            for _, creditor, amount in order_action:
                summary_text += f'    💰 @{creditor} {round(amount)}₽\n'

        conn = sqlite3.connect('expenses.db')
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                SUM(amount) as total_amount
            FROM expenses
            WHERE chat_id = @chat_id
            """, (chat_id,))
        total_amount = cursor.fetchone()

        cursor.execute("""
            SELECT
                AVG(amount) as average_amount
            FROM expenses
            WHERE chat_id = @chat_id
            """, (chat_id,))
        average_amount = cursor.fetchone()

        summary_text += f'\nПо итогу гульнули на {round(total_amount[0])}₽\nИли по {round(average_amount[0])}₽ с человека'

    else:
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
            cursor.execute("INSERT INTO expenses (chat_id, user_id, amount, description) VALUES (?, ?, ?, ?, ?)",
                           (message.chat.id, user_id, message.chat.username, amount, description))
            conn.commit()
            conn.close()

            bot.reply_to(message, f"Расход {amount} добавлен: {description}")
            #TODO: Выводить имя пользователя


# Основной код бота
if __name__ == '__main__':
    init_db()
    bot.polling(none_stop=True)
