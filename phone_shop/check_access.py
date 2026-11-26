"""Проверка Python, ODBC-драйвера и файла базы Access."""
import os
import struct
import sys

print("=== Проверка подключения к Microsoft Access ===")
print("Python:", sys.version.split()[0])
print("Разрядность Python:", struct.calcsize("P") * 8, "бит")
print("Папка проекта:", os.path.dirname(os.path.abspath(__file__)))

try:
    import pyodbc
except Exception as exc:
    print("ОШИБКА: библиотека pyodbc не установлена:", exc)
    print("Выполните: python -m pip install -r requirements.txt")
    input("Нажмите Enter для выхода...")
    raise SystemExit(1)

drivers = pyodbc.drivers()
print("ODBC-драйверы:", drivers or "не найдены")
access = [d for d in drivers if "access" in d.lower() and ("mdb" in d.lower() or "accdb" in d.lower())]
if not access:
    print("\nОШИБКА: драйвер Microsoft Access Database Engine (ACE) не найден.")
    print("Установите ACE той же разрядности, что и Python (выше указано).")
    print("После установки закройте и заново откройте PowerShell/IDE.")
    input("Нажмите Enter для выхода...")
    raise SystemExit(2)

try:
    import db
    conn = db.connect()
    cur = conn.cursor()
    tables = [r.table_name for r in cur.tables(tableType="TABLE")]
    print("\nУСПЕХ: база открылась!")
    print("Файл базы:", os.path.abspath(__import__("config").DB_PATH))
    print("Таблицы:", ", ".join(tables) if tables else "не найдены")
    conn.close()
except Exception as exc:
    print("\nОШИБКА ПОДКЛЮЧЕНИЯ:")
    print(exc)
    input("Нажмите Enter для выхода...")
    raise SystemExit(3)

input("\nПроверка завершена. Нажмите Enter для выхода...")
