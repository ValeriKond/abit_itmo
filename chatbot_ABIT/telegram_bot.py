import logging
import os
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from chatbot import ITMOAdmissionChatbot

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class TelegramChatbot:
    def __init__(self, token: str):
        self.token = token
        self.chatbot = ITMOAdmissionChatbot()
        self.user_sessions = {}  # Хранение сессий пользователей

    def get_main_keyboard(self):
        """Создает основную клавиатуру"""
        keyboard = [
            [KeyboardButton("🔍 Сравнить программы"), KeyboardButton("💡 Получить рекомендации")],
            [KeyboardButton("📚 Учебные планы"), KeyboardButton("💰 Стоимость обучения")],
            [KeyboardButton("🏠 Общежитие"), KeyboardButton("🎯 Карьерные возможности")],
            [KeyboardButton("📝 Мой профиль"), KeyboardButton("❓ Помощь")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user_id = update.effective_user.id
        self.user_sessions[user_id] = ITMOAdmissionChatbot()

        welcome_message = """
🎓 Добро пожаловать в чат-бот для выбора магистерской программы ИТМО!

Я помогу вам выбрать между двумя программами:
• Искусственный интеллект
• Искусственный интеллект в продуктах

Используйте кнопки меню или задавайте вопросы напрямую.
        """

        await update.message.reply_text(
            welcome_message,
            reply_markup=self.get_main_keyboard()
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = """
🤖 Как пользоваться ботом:

📌 Основные команды:
• /start - Начать работу с ботом
• /help - Показать эту справку
• /profile - Настроить профиль

🔍 Что я умею:
• Сравнивать программы магистратуры
• Давать персональные рекомендации
• Отвечать на вопросы об обучении
• Помогать с выбором дисциплин

💬 Просто задавайте вопросы или используйте кнопки меню!
        """

        await update.message.reply_text(help_text)

    async def profile_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /profile"""
        profile_text = """
📝 Настройка профиля

Расскажите о себе, чтобы получить персональные рекомендации:

• Ваше образование (бакалавриат)
• Опыт работы в IT
• Знание программирования
• Интересы в области ИИ
• Карьерные цели

Просто напишите информацию в свободной форме.
        """

        await update.message.reply_text(profile_text)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений"""
        user_id = update.effective_user.id
        message_text = update.message.text

        # Инициализация сессии пользователя, если её нет
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = ITMOAdmissionChatbot()

        chatbot = self.user_sessions[user_id]

        # Обработка кнопок меню
        if message_text == "🔍 Сравнить программы":
            response = chatbot.compare_programs()
        elif message_text == "💡 Получить рекомендации":
            response = chatbot.get_recommendations()
        elif message_text == "📚 Учебные планы":
            response = self.get_academic_plans_info()
        elif message_text == "💰 Стоимость обучения":
            response = self.get_cost_info()
        elif message_text == "🏠 Общежитие":
            response = self.get_dormitory_info()
        elif message_text == "🎯 Карьерные возможности":
            response = self.get_career_info()
        elif message_text == "📝 Мой профиль":
            response = self.get_profile_info(chatbot)
        elif message_text == "❓ Помощь":
            await self.help_command(update, context)
            return
        else:
            # Обычное сообщение - передаем в чат-бот
            response = chatbot.get_ai_response(message_text)

        await update.message.reply_text(response, reply_markup=self.get_main_keyboard())

    def get_academic_plans_info(self):
        """Информация об учебных планах"""
        return """
📚 Учебные планы программ:

🔹 Искусственный интеллект:
• Ссылка на учебный план будет добавлена после парсинга
• Продолжительность: 2 года
• Форма обучения: Очная

🔹 Искусственный интеллект в продуктах:
• Ссылка на учебный план будет добавлена после парсинга
• Информация уточняется

Для получения актуальных учебных планов обратитесь к официальным источникам.
        """

    def get_cost_info(self):
        """Информация о стоимости"""
        return """
💰 Стоимость обучения:

🔹 Искусственный интеллект:
• Контрактное обучение: 599 000 ₽/год
• Бюджетные места: есть (количество зависит от направления)

🔹 Искусственный интеллект в продуктах:
• Информация уточняется после парсинга

💡 Также доступны:
• Целевые места
• Возможность получения стипендии
• Льготы для отдельных категорий
        """

    def get_dormitory_info(self):
        """Информация об общежитии"""
        return """
🏠 Общежитие:

🔹 Искусственный интеллект:
• Общежитие: ✅ Доступно
• Военный учебный центр: ✅ Есть

🔹 Искусственный интеллект в продуктах:
• Информация уточняется

📍 Адрес ИТМО:
197101, г. Санкт-Петербург, Кронверкский проспект, д.49
        """

    def get_career_info(self):
        """Информация о карьере"""
        return """
🎯 Карьерные возможности:

🔹 Искусственный интеллект:
• ML Engineer (170-300k ₽)
• Data Engineer
• AI Product Developer  
• Data Analyst

🔹 Партнеры программы:
• X5 Group, Ozon Банк, МТС
• Sber AI, Норникель
• Napoleon IT, Genotek
• Raft, AIRI, DeepPavlov

📈 Спрос на AI-экспертов продолжает расти!
        """

    def get_profile_info(self, chatbot):
        """Информация о профиле пользователя"""
        if not chatbot.user_profile:
            return """
📝 Ваш профиль пуст.

Расскажите о себе для получения персональных рекомендаций:
• Образование
• Опыт работы
• Навыки программирования
• Интересы в области ИИ
• Карьерные цели
            """
        else:
            profile_text = "📝 Ваш профиль:\n\n"
            for key, value in chatbot.user_profile.items():
                profile_text += f"• {key}: {value}\n"
            return profile_text

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ошибок"""
        logger.error(f"Update {update} caused error {context.error}")

        if update.effective_message:
            await update.effective_message.reply_text(
                "Извините, произошла ошибка. Попробуйте еще раз или обратитесь к администратору."
            )

    def run(self):
        """Запуск бота"""
        application = Application.builder().token(self.token).build()

        # Добавление обработчиков
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("profile", self.profile_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        # Обработчик ошибок
        application.add_error_handler(self.error_handler)

        # Запуск бота
        print("Бот запущен...")
        application.run_polling()


if __name__ == "__main__":
    # Получение токена из переменной окружения
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

    if not BOT_TOKEN:
        print("Ошибка: Установите переменную окружения TELEGRAM_BOT_TOKEN")
        print("Получить токен можно у @BotFather в Telegram")
        exit(1)

    bot = TelegramChatbot(BOT_TOKEN)
    bot.run()