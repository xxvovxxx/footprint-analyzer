# Footprint Finder

Веб-скрипт на Flask для порівняння двох HTML-джерел:
- URL vs URL
- файл vs файл
- файл vs URL

## Запуск

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Потім відкрий у браузері:
`http://127.0.0.1:5000`

## Що шукає
- технології та CMS-футпрінти
- JS/CSS ресурси
- meta теги
- форми
- посилання
- CSS-класи
- HTML comments

## Нюанс
Деякі сайти можуть блокувати прямий парсинг по URL. У такому випадку краще зберегти HTML локально і завантажити файл.
