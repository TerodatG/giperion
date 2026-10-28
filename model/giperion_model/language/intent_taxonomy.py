# GiperionModel/giperion_model/language/intent_taxonomy.py            v001
# Пояснения к близким намерениям, которые часто путаются.
# Последнее изменение: первый вариант — правила различения тем.

TAXONOMY_NOTES = {
    ("garden", "plants"): (
        "garden — личный сад, огород и дача; "
        "plants — ботаника, комнатные цветы и деревья."
    ),
    ("garden", "agriculture"): (
        "garden — небольшой личный участок; "
        "agriculture — промышленное выращивание и фермы."
    ),
    ("plants", "agriculture"): (
        "plants — сами растения и уход за ними; "
        "agriculture — отрасль, поля и сельхозтехника."
    ),
    ("astronomy", "space"): (
        "astronomy — наука и наблюдения; "
        "space — полёты, космонавты и космическая техника."
    ),
    ("charity", "help"): (
        "charity — фонды, пожертвования и волонтёрство; "
        "help — просьба о помощи в конкретной задаче."
    ),
    ("study", "education"): (
        "study — процесс учёбы и подготовка; "
        "education — система школ, вузов и образования."
    ),
    ("study", "learning"): (
        "study — школьная и вузовская учёба; "
        "learning — освоение нового навыка или курса."
    ),
    ("education", "learning"): (
        "education — учреждения и уровни образования; "
        "learning — личный процесс обучения."
    ),
    ("history", "nature"): (
        "history — прошлое и эпохи; "
        "nature — природа, леса и заповедники."
    ),
    ("science", "how_are_you"): (
        "science — научные исследования; "
        "how_are_you — вопрос о самочувствии."
    ),
    ("economics", "education"): (
        "economics — финансы и рынок; "
        "education — школа, вуз и обучение."
    ),
    ("about_user", "memory"): (
        "about_user — вопрос о себе; "
        "memory — команда запомнить информацию."
    ),
    ("how_are_you", "smalltalk"): (
        "how_are_you — вопрос о состоянии; "
        "smalltalk — приглашение просто поговорить."
    ),
    ("agree", "compliment"): (
        "agree — согласие с утверждением; "
        "compliment — похвала собеседника."
    ),
    ("insult", "compliment"): (
        "insult — оскорбление; compliment — похвала."
    ),
    ("humor", "joke"): (
        "humor — реакция на смешное; "
        "joke — просьба рассказать шутку."
    ),
}
