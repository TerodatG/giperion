# GiperionModel/giperion_model/language/learning_presenter.py         v001
# Тексты и таблица категорий для команд обучения Гипериона.
# Последнее изменение: выделено из learning_handler.

CATEGORY_DESCRIPTIONS = {
    "about_user": "о пользователе (как меня зовут, кто я)",
    "agree": "согласие (да, согласен)",
    "agriculture": "сельское хозяйство (ферма, урожай)",
    "animals": "животные (кошка, собака)",
    "art": "искусство (картина, художник)",
    "astronomy": "астрономия (звёзды, планеты)",
    "books": "книги (роман, чтение)",
    "bot_identity": "о Гиперионе (кто ты, твоё имя)",
    "camping": "походы и лагерь (палатка, костёр)",
    "capabilities": "возможности Гипериона (что умеешь, помощь)",
    "cars": "автомобили (машина, двигатель)",
    "charity": "благотворительность (помощь, пожертвование)",
    "compliment": "комплименты (молодец, ты умный)",
    "construction": "строительство (дом, ремонт)",
    "cooking": "готовка (рецепт, блюдо)",
    "desert": "пустыня (песок, оазис)",
    "disagree": "несогласие (нет, не согласен)",
    "diy": "сделай сам (поделка, своими руками)",
    "ecology": "экология (природа, загрязнение)",
    "economics": "экономика (деньги, рынок)",
    "education": "образование (школа, обучение)",
    "emotions_negative": "негативные эмоции (грусть, злость)",
    "emotions_positive": "позитивные эмоции (радость, счастье)",
    "energy": "энергия (электричество, батарея)",
    "fact": "факты (интересный факт, расскажи факт)",
    "family": "семья (родители, брат)",
    "farewell": "прощание (пока, до свидания)",
    "fashion": "мода (одежда, стиль)",
    "fishing": "рыбалка (удочка, рыба)",
    "food": "еда (продукты, вкусно)",
    "games": "игры (играть, игра)",
    "garden": "сад и огород (грядка, сад)",
    "geology": "геология (камни, минералы)",
    "greeting": "приветствие (привет, здравствуй)",
    "health": "здоровье (самочувствие, здоровье)",
    "help": "помощь (помоги, что делать)",
    "history": "история (прошлое, событие)",
    "how_are_you": "дела Гипериона (как дела, как ты)",
    "humor": "юмор (смешно, шутка)",
    "hunting": "охота (охотник, добыча)",
    "insult": "оскорбления (дурак, глупый)",
    "joke": "шутки (расскажи шутку, анекдот)",
    "language": "языки (русский, иностранный язык)",
    "law": "право и законы (закон, правило)",
    "learning": "обучение Гипериона (научи, обучение)",
    "math": "математика (пример, посчитай)",
    "media": "медиа (новости, телевидение)",
    "medicine": "медицина (болезнь, врач)",
    "memory": "память Гипериона (запомни, помнишь)",
    "meteorology": "метеорология (климат, осадки)",
    "military": "военное дело (армия, оружие)",
    "motivation": "мотивация (поддержи, вдохнови)",
    "mountain": "горы (вершина, поход)",
    "movies": "фильмы (кино, актёр)",
    "music": "музыка (песня, мелодия)",
    "nature": "природа (лес, животный мир)",
    "ocean": "океан (море, волны)",
    "philosophy": "философия (смысл жизни, мысли)",
    "plants": "растения (цветок, дерево)",
    "politics": "политика (власть, государство)",
    "project": "проект Giperion (проект, разработка)",
    "psychology": "психология (характер, эмоции)",
    "python": "Python и программирование (код, функция)",
    "religion": "религия (вера, религия)",
    "science": "наука (исследование, открытие)",
    "smalltalk": "обычный разговор (поговорим, интересно)",
    "space": "космос (планета, галактика)",
    "sport": "спорт (тренировка, футбол)",
    "study": "учёба (урок, задание)",
    "survival": "выживание (опасность, навыки)",
    "technology": "технологии (компьютер, устройство)",
    "thanks": "благодарность (спасибо, благодарю)",
    "time": "время (который час, дата)",
    "transport": "транспорт (автобус, поезд)",
    "travel": "путешествия (поездка, страна)",
    "weather": "погода (дождь, температура)",
    "work": "работа (профессия, дело)",
}


def get_category_description(
    category: str,
) -> str:
    """Возвращает понятное описание категории."""

    return CATEGORY_DESCRIPTIONS.get(
        category.casefold(),
        "пользовательская категория (примеры не добавлены)",
    )


def split_category_description(
    description: str,
) -> tuple[str, str]:
    """Разделяет русское название категории и примеры."""

    opening_bracket_index = description.rfind("(")

    if opening_bracket_index == -1:
        return (
            description.strip(),
            "",
        )

    category_name = description[
        :opening_bracket_index
    ].strip()
    examples = description[
        opening_bracket_index:
    ].strip()

    return (
        category_name,
        examples,
    )


def get_categories_response(
    categories: list[str],
) -> str:
    """Формирует список категорий в трёх выровненных колонках."""

    if not categories:
        return "В intents.json пока нет категорий."

    category_rows = []

    for category in categories:
        description = get_category_description(
            category
        )
        russian_name, examples = split_category_description(
            description
        )
        category_rows.append(
            (
                f"[{category}]",
                russian_name,
                examples,
            )
        )

    technical_name_width = max(
        len(technical_name)
        for technical_name, _, _ in category_rows
    )
    russian_name_width = max(
        len(russian_name)
        for _, russian_name, _ in category_rows
    )

    lines = [
        "Доступные категории:",
        "",
    ]

    for (
        technical_name,
        russian_name,
        examples,
    ) in category_rows:
        formatted_technical_name = technical_name.ljust(
            technical_name_width
        )
        formatted_russian_name = russian_name.ljust(
            russian_name_width
        )
        lines.append(
            f"- {formatted_technical_name}  "
            f"{formatted_russian_name}  "
            f"{examples}"
        )

    return "\n".join(lines)
