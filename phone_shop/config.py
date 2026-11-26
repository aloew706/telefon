import os

# Путь к вашему файлу Access. По умолчанию — рядом с программой.
# Если файл лежит в другом месте, впишите полный путь, например:
# DB_PATH = r"C:\Users\Имя\Documents\phones.accdb"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "phones.accdb")

# Вход администратора (поменяйте пароль!)
ADMIN_LOGIN = "admin"
ADMIN_PASSWORD = "admin123"

# Любая случайная строка для защиты сессий
SECRET_KEY = "change-me-please"
