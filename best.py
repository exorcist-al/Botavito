import logging
from datetime import datetime
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    ConversationHandler
)
import pytz

# Состояния разговора
CATEGORY, TITLE, DESCRIPTION, PHOTO, PRICE, CONTACT = range(6)

# Константы для callback данных
SHOW_ALL = "show_all"
MY_ADS = "my_ads"
ADD_AD = "add_ad"
DELETE_AD = "delete_ad"
SEARCH_CAT = "search_cat"
CATEGORY_PREFIX = "cat_"

# Список администраторов (замените на реальные ID)
ADMIN_IDS = [6431899370]

# Создаем планировщик с явным указанием временной зоны через pytz
timezone = pytz.timezone('Europe/Moscow')  # Пример для Москвы

# Передаем кастомный планировщик в JobQueue
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

def init_db():
    conn = sqlite3.connect('avito_bot.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS advertisements
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         user_id INTEGER,
         category TEXT,
         title TEXT,
         description TEXT,
         photo_id TEXT,
         price REAL,
         contact TEXT,
         created_at TIMESTAMP)
    ''')
    conn.commit()
    conn.close()

class AvitoBot:
    def __init__(self):
        self.categories = ["до 1000р", "до 2000р", "до 3000р", "до 4000р", "свыше 4000"]

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("📢 Все объявления", callback_data=SHOW_ALL)],
            [InlineKeyboardButton("🔍 Поиск по категориям", callback_data=SEARCH_CAT)],
            [InlineKeyboardButton("📝 Мои объявления", callback_data=MY_ADS)],
            [InlineKeyboardButton("➕ Добавить объявление", callback_data=ADD_AD)]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Добро пожаловать в бота для выставления своих объявлении!\nПо вчем вопросам и предложениям @yatomatsu\nВыберите действие:",
            reply_markup=reply_markup
        )

    async def show_categories(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = []
        # Создаем кнопки для каждой категории
        for category in self.categories:
            keyboard.append([InlineKeyboardButton(category, callback_data=f"{CATEGORY_PREFIX}{category}")])
        # Добавляем кнопку возврата в главное меню
        keyboard.append([InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Если это ответ на callback query, редактируем сообщение
        if update.callback_query:
            await update.callback_query.message.edit_text(
                "Выберите категорию для просмотра объявлений:",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                "Выберите категорию для просмотра объявлений:",
                reply_markup=reply_markup
            )

    async def show_category_ads(self, update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
        conn = sqlite3.connect('avito_bot.db')
        c = conn.cursor()
        c.execute('SELECT * FROM advertisements WHERE category = ? ORDER BY created_at DESC', (category,))
        ads = c.fetchall()
        conn.close()

        if not ads:
            # Создаем кнопку возврата к категориям
            keyboard = [[InlineKeyboardButton("🔙 К категориям", callback_data=SEARCH_CAT)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.callback_query.message.edit_text(
                f"В категории {category} пока нет объявлений.",
                reply_markup=reply_markup
            )
            return

        # Сначала удаляем сообщение с кнопками категорий
        await update.callback_query.message.delete()

        # Отправляем новое сообщение с заголовком категории
        await update.callback_query.message.reply_text(f"📂 Объявления в категории: {category}")

        for ad in ads:
            text = f"📌 {ad[3]}\n" \
                   f"Описание: {ad[4]}\n" \
                   f"Цена: {ad[6]} ₽\n" \
                   f"Контакт: {ad[7]}"
            
            keyboard = []
            if update.callback_query.from_user.id in ADMIN_IDS or update.callback_query.from_user.id == ad[1]:
                keyboard.append([InlineKeyboardButton("🗑 Удалить", callback_data=f"{DELETE_AD}_{ad[0]}")])
            
            # Добавляем кнопку возврата к категориям для последнего объявления
            if ad == ads[-1]:
                keyboard.append([InlineKeyboardButton("🔙 К категориям", callback_data=SEARCH_CAT)])
            
            reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
            
            if ad[5]:  # если есть фото
                await update.callback_query.message.reply_photo(
                    photo=ad[5],
                    caption=text,
                    reply_markup=reply_markup
                )
            else:
                await update.callback_query.message.reply_text(
                    text,
                    reply_markup=reply_markup
                )

    async def button_click(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        if query.data == SHOW_ALL:
            # Удаляем сообщение с кнопками перед показом объявлений
            await query.message.delete()
            await self.show_all_ads(update, context)
        elif query.data == MY_ADS:
            # Удаляем сообщение с кнопками перед показом объявлений
            await query.message.delete()
            await self.show_my_ads(update, context)
        elif query.data == ADD_AD:
            # Удаляем сообщение с кнопками перед началом добавления
            await query.message.delete()
            return await self.start_add_ad(update, context)
        elif query.data == SEARCH_CAT:
            await self.show_categories(update, context)
        elif query.data.startswith(CATEGORY_PREFIX):
            category = query.data[len(CATEGORY_PREFIX):]
            await self.show_category_ads(update, context, category)
        elif query.data == "back_to_menu":
            keyboard = [
                [InlineKeyboardButton("📢 Все объявления", callback_data=SHOW_ALL)],
                [InlineKeyboardButton("🔍 Поиск по категориям", callback_data=SEARCH_CAT)],
                [InlineKeyboardButton("📝 Мои объявления", callback_data=MY_ADS)],
                [InlineKeyboardButton("➕ Добавить объявление", callback_data=ADD_AD)]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(
                "Выберите действие:",
                reply_markup=reply_markup
            )
        elif query.data.startswith(DELETE_AD):
            ad_id = int(query.data.split('_')[2])
            await self.delete_ad(update, context, ad_id)

    async def show_all_ads(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        conn = sqlite3.connect('avito_bot.db')
        c = conn.cursor()
        c.execute('SELECT * FROM advertisements ORDER BY created_at DESC LIMIT 10')
        ads = c.fetchall()
        conn.close()

        if not ads:
            keyboard = [[InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.callback_query.message.reply_text(
                "Объявлений пока нет.",
                reply_markup=reply_markup
            )
            return

        # Отправляем заголовок
        await update.callback_query.message.reply_text("📢 Все объявления:")

        for ad in ads:
            text = f"📌 {ad[3]}\n" \
                   f"Категория: {ad[2]}\n" \
                   f"Описание: {ad[4]}\n" \
                   f"Цена: {ad[6]} ₽\n" \
                   f"Контакт: {ad[7]}"
            
            keyboard = []
            if update.callback_query.from_user.id in ADMIN_IDS or update.callback_query.from_user.id == ad[1]:
                keyboard.append([InlineKeyboardButton("🗑 Удалить", callback_data=f"{DELETE_AD}_{ad[0]}")])
            
            # Добавляем кнопку возврата в меню для последнего объявления
            if ad == ads[-1]:
                keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")])
            
            reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
            
            if ad[5]:  # если есть фото
                await update.callback_query.message.reply_photo(
                    photo=ad[5],
                    caption=text,
                    reply_markup=reply_markup
                )
            else:
                await update.callback_query.message.reply_text(
                    text,
                    reply_markup=reply_markup
                )

    async def show_my_ads(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.callback_query.from_user.id
        
        conn = sqlite3.connect('avito_bot.db')
        c = conn.cursor()
        c.execute('SELECT * FROM advertisements WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
        ads = c.fetchall()
        conn.close()

        if not ads:
            keyboard = [[InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.callback_query.message.reply_text(
                "У вас пока нет объявлений.",
                reply_markup=reply_markup
            )
            return

        # Отправляем заголовок
        await update.callback_query.message.reply_text("📝 Ваши объявления:")

        for ad in ads:
            text = f"📌 {ad[3]}\n" \
                   f"Категория: {ad[2]}\n" \
                   f"Описание: {ad[4]}\n" \
                   f"Цена: {ad[6]} ₽\n" \
                   f"Контакт: {ad[7]}"
            
            keyboard = [[InlineKeyboardButton("🗑 Удалить", callback_data=f"{DELETE_AD}_{ad[0]}")]]
            
            # Добавляем кнопку возврата в меню для последнего объявления
            if ad == ads[-1]:
                keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if ad[5]:  # если есть фото
                await update.callback_query.message.reply_photo(
                    photo=ad[5],
                    caption=text,
                    reply_markup=reply_markup
                )
            else:
                await update.callback_query.message.reply_text(
                    text,
                    reply_markup=reply_markup
                )

    async def start_add_ad(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [[KeyboardButton(cat)] for cat in self.categories]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        if update.callback_query:
            await update.callback_query.message.reply_text(
                "Выберите категорию объявления:",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                "Выберите категорию объявления:",
                reply_markup=reply_markup
            )
        return CATEGORY

    async def category_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['category'] = update.message.text
        await update.message.reply_text(
            "Введите название объявления:",
            reply_markup=ReplyKeyboardRemove()
        )
        return TITLE

    async def title_entered(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['title'] = update.message.text
        await update.message.reply_text("Введите описание объявления:")
        return DESCRIPTION

    async def description_entered(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['description'] = update.message.text
        await update.message.reply_text("Отправьте фотографию товара (или отправьте /skip, чтобы пропустить):")
        return PHOTO

    async def photo_sent(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        photo_file = await update.message.photo[-1].get_file()
        context.user_data['photo_id'] = photo_file.file_id
        await update.message.reply_text("Введите цену в рублях (только число):")
        return PRICE

    async def skip_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['photo_id'] = None
        await update.message.reply_text("Введите цену в рублях (только число):")
        return PRICE

    async def price_entered(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            price = float(update.message.text)
            context.user_data['price'] = price
            await update.message.reply_text("Введите контактные данные (телефон или @username):")
            return CONTACT
        except ValueError:
            await update.message.reply_text("Пожалуйста, введите корректную цену (только число):")
            return PRICE

    async def contact_entered(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = context.user_data
        user_data['contact'] = update.message.text

        conn = sqlite3.connect('avito_bot.db')
        c = conn.cursor()
        c.execute('''
            INSERT INTO advertisements 
            (user_id, category, title, description, photo_id, price, contact, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            update.message.from_user.id,
            user_data['category'],
            user_data['title'],
            user_data['description'],
            user_data['photo_id'],
            user_data['price'],
            user_data['contact'],
            datetime.now()
        ))
        conn.commit()
        conn.close()

        await update.message.reply_text("✅ Объявление успешно добавлено!")
        
        # Возвращаемся к главному меню
        keyboard = [
            [InlineKeyboardButton("📢 Все объявления", callback_data=SHOW_ALL)],
            [InlineKeyboardButton("🔍 Поиск по категориям", callback_data=SEARCH_CAT)],
            [InlineKeyboardButton("📝 Мои объявления", callback_data=MY_ADS)],
            [InlineKeyboardButton("➕ Добавить объявление", callback_data=ADD_AD)]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Выберите действие:",
            reply_markup=reply_markup
        )
        return ConversationHandler.END
        
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Возвращаемся к главному меню
        keyboard = [
            [InlineKeyboardButton("📢 Все объявления", callback_data=SHOW_ALL)],
            [InlineKeyboardButton("🔍 Поиск по категориям", callback_data=SEARCH_CAT)],
            [InlineKeyboardButton("📝 Мои объявления", callback_data=MY_ADS)],
            [InlineKeyboardButton("➕ Добавить объявление", callback_data=ADD_AD)]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "❌ Действие отменено. Выберите действие:",
            reply_markup=reply_markup
        )
        return ConversationHandler.END

    async def delete_ad(self, update: Update, context: ContextTypes.DEFAULT_TYPE, ad_id: int):
        user_id = update.callback_query.from_user.id
        
        conn = sqlite3.connect('avito_bot.db')
        c = conn.cursor()
        
        # Проверяем, является ли пользователь владельцем объявления или администратором
        c.execute('SELECT user_id FROM advertisements WHERE id = ?', (ad_id,))
        result = c.fetchone()
        
        if result and (result[0] == user_id or user_id in ADMIN_IDS):
            c.execute('DELETE FROM advertisements WHERE id = ?', (ad_id,))
            conn.commit()
            await update.callback_query.message.reply_text("✅ Объявление успешно удалено!")
            
            # Возвращаем кнопки меню
            keyboard = [
                [InlineKeyboardButton("📢 Все объявления", callback_data=SHOW_ALL)],
                [InlineKeyboardButton("🔍 Поиск по категориям", callback_data=SEARCH_CAT)],
                [InlineKeyboardButton("📝 Мои объявления", callback_data=MY_ADS)],
                [InlineKeyboardButton("➕ Добавить объявление", callback_data=ADD_AD)]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.callback_query.message.reply_text(
                "Выберите действие:",
                reply_markup=reply_markup
            )
        else:
            await update.callback_query.message.reply_text("⚠️ У вас нет прав для удаления этого объявления!")
        
        conn.close()

def main():
    init_db()
    bot = AvitoBot()
    
    application = Application.builder().token("7699190840:AAFNgP1LxSKl1PdvUdlpVRxTXBN3XYkGSFQ").build()

    # Обработчик диалога добавления объявления
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(bot.start_add_ad, pattern=f"^{ADD_AD}$")],
        states={
            CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.category_selected)],
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.title_entered)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.description_entered)],
            PHOTO: [
                MessageHandler(filters.PHOTO, bot.photo_sent),
                CommandHandler("skip", bot.skip_photo)
            ],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.price_entered)],
            CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.contact_entered)]
        },
        fallbacks=[CommandHandler("cancel", bot.cancel)],
        per_message=False  # Установлено в False для совместимости
    )

    # Добавление обработчиков
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(bot.button_click))

    # Запуск бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()