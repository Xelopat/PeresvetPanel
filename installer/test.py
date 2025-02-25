import json
import requests
import os
import pandas as pd

# Путь к исходному и обновленному JSON-файлу
input_file = "versions.json"
output_file = "updated_versions.json"

# Загрузка данных из JSON-файла
with open(input_file, "r", encoding="utf-8") as file:
    data = json.load(file)

# Функция для получения размера файла через HTTP-запрос
def get_file_size(url):
    try:
        response = requests.head(url, allow_redirects=True)
        size = int(response.headers.get("Content-Length", 0))
        return size if size > 0 else None
    except Exception as e:
        return None

# Обход всех программ и их версий
for software, versions in data.items():
    for version, details in versions.items():
        url = details.get("link")
        size = details.get("size", None)

        # Если размер отсутствует, получаем его через HTTP-запрос
        if size is None and url:
            size = get_file_size(url)
            if size:
                data[software][version]["size"] = size  # Обновляем JSON-данные

# Сохранение обновленного JSON
with open(output_file, "w", encoding="utf-8") as file:
    json.dump(data, file, indent=2, ensure_ascii=False)

# Формирование данных для таблицы
results = []
for software, versions in data.items():
    for version, details in versions.items():
        results.append({"Software": software, "Version": version, "Size (bytes)": details.get("size"), "URL": details.get("link")})

# Создание DataFrame
df = pd.DataFrame(results)

# Отображение результатов
import ace_tools as tools
tools.display_dataframe_to_user(name="Updated Software File Sizes", dataframe=df)

print(f"Обновленный JSON сохранен в файл: {output_file}")
