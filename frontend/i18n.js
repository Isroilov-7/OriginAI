/**
 * AntiplagiatPRO — i18n tizimi
 * Fayl: i18n.js
 *
 * Ishlatish:
 *   <script src="i18n.js"></script>
 *   <span data-i18n="nav.check"></span>
 *   <input data-i18n-placeholder="checker.placeholder">
 *   <button data-i18n="btn.check"></button>
 *
 *   // Javascriptdan:
 *   i18n.t('error.too_short')
 *   i18n.setLang('ru')
 */

const TRANSLATIONS = {

  // ── O'ZBEK ───────────────────────────────────────────────
  uz: {
    // Meta
    'meta.title':       "AntiplagiatPRO — O'zbek tilida plagiat tekshiruvi",
    'meta.description': "O'zbek, Rus, Ingliz tillarida professional plagiat va AI matn aniqlash tizimi",

    // Navigatsiya
    'nav.features':   'Xususiyatlar',
    'nav.pricing':    'Narxlar',
    'nav.compare':    'Taqqoslash',
    'nav.faq':        'Savol-javob',
    'nav.login':      'Kirish',
    'nav.register':   "Ro'yxatdan o'tish",
    'nav.cabinet':    'Kabinet',
    'nav.newcheck':   'Yangi tekshiruv',
    'nav.logout':     'Chiqish',

    // Hero
    'hero.badge':   "O'zbek tilidagi yagona professional tizim",
    'hero.title1':  'Plagiatni',
    'hero.title2':  'aniq',
    'hero.title3':  'va',
    'hero.title4':  'tez',
    'hero.title5':  'aniqlang',
    'hero.desc':    "Winnowing, TF-IDF, morfologiya va AI detektor — hammasi bir joyda. O'zbek, Rus, Ingliz tillarida. Hujjat yuklab tekshirish. Tarix va PDF hisobot.",
    'hero.cta1':    "Hozir tekshirish — bepul",
    'hero.cta2':    "Ko'proq bilish",
    'hero.stat1v':  '500K+',
    'hero.stat1l':  "Tekshiruv o'tkazildi",
    'hero.stat2v':  '3 ta',
    'hero.stat2l':  "Til qo'llab-quvvatlanadi",
    'hero.stat3v':  '98%',
    'hero.stat3l':  'Aniqlik darajasi',
    'hero.stat4v':  'Bepul',
    'hero.stat4l':  'Asosiy versiya',

    // Checker
    'checker.tab.text':       '📝 Matn',
    'checker.tab.file':       '📎 Fayl',
    'checker.placeholder':    "Tekshirilishi kerak bo'lgan matnni shu yerga joylashtiring...",
    'checker.wordcount':      'so\'z',
    'checker.btn.check':      'Tekshirish →',
    'checker.upload.title':   'PDF yoki DOCX faylni yuklang',
    'checker.upload.hint':    'Maksimal hajm: 10 MB',
    'checker.processing':     'Tahlil qilinmoqda...',
    'checker.btn.pdf':        '📄 PDF',
    'checker.btn.new':        '✕ Yangi',

    // Natija
    'result.title':           'Natija',
    'result.plagiarism':      'Plagiat darajasi',
    'result.ai':              'AI ehtimoli',
    'result.language':        'Til',
    'result.threshold':       'Chegara',
    'result.found':           '✗ TOPILDI',
    'result.normal':          '✓ Normal',
    'result.low':             '✓ Normal',
    'result.medium':          '⚠ O\'rtacha',
    'result.high':            '✗ Yuqori',
    'result.sources':         'Topilgan manbalar',
    'result.unicode_alert':   '⚠️ Unicode manipulyatsiya aniqlandi!',

    // Xatoliklar
    'error.too_short':    "Kamida 5 so'z kiriting",
    'error.too_large':    'Fayl 10MB dan katta',
    'error.file_read':    "Faylni o'qishda xato. PDF yoki DOCX yuboring.",
    'error.server':       'Xato yuz berdi. Qayta urinib ko\'ring.',
    'error.no_result':    'Natija topilmadi. Avval matn yuboring.',
    'error.limit':        "Bepul rejimda 3 ta tekshiruv. Pro rejimga o'ting.",
    'error.auth':         'Avtorizatsiya kerak',
    'error.rate_limit':   "Juda ko'p urinish. Bir oz kuting va qayta urinib ko'ring.",
    'error.network':      "Internet aloqasi uzildi. Ulanishni tekshiring.",
    'error.brute_force':  "Ko'p xato urinish. 15 daqiqadan keyin urinib ko'ring.",

    // Auth modal
    'auth.login.title':       'Kirish',
    'auth.login.subtitle':    "Hisobingizga kiring",
    'auth.register.title':    "Ro'yxatdan o'tish",
    'auth.register.subtitle': 'Bepul hisob yarating',
    'auth.name':              'Ism',
    'auth.name.placeholder':  'Ismingiz',
    'auth.email':             'Email',
    'auth.email.placeholder': 'email@gmail.com',
    'auth.password':          'Parol',
    'auth.password.placeholder': 'Kamida 6 belgi',
    'auth.btn.login':         'Kirish',
    'auth.btn.register':      "Ro'yxatdan o'tish",
    'auth.switch.to_register':"Hisobingiz yo'qmi?",
    'auth.switch.register':   "Ro'yxatdan o'tish",
    'auth.switch.to_login':   "Hisobingiz bormi?",
    'auth.switch.login':      'Kirish',

    // Upgrade
    'upgrade.title':     'Bepul limit tugadi',
    'upgrade.desc':      'Bepul rejimda 3 ta tekshiruv mavjud.',
    'upgrade.price':     '49 000 so\'m',
    'upgrade.period':    'oylik / cheksiz tekshiruv',
    'upgrade.btn.view':  'Pro rejimni ko\'rish →',
    'upgrade.btn.later': 'Keyinroq',

    // Dashboard
    'dash.title':        'Shaxsiy kabinet',
    'dash.total':        'Jami tekshiruv',
    'dash.free_left':    'Bepul qoldi',
    'dash.avg_plag':     "O'rtacha plagiat",
    'dash.plan':         'Reja',
    'dash.btn.new':      '+ Yangi tekshiruv',
    'dash.history':      'Tekshiruv tarixi',
    'dash.empty':        "Tekshiruv tarixi bo'sh",
    'dash.col.text':     'Matn',
    'dash.col.lang':     'Til',
    'dash.col.plag':     'Plagiat',
    'dash.col.ai':       'AI',
    'dash.col.status':   'Holat',
    'dash.col.date':     'Sana',
    'dash.col.report':   'Hisobot',
    'dash.status.plag':  'Plagiat',
    'dash.status.ok':    'Normal',

    // Features section
    'feat.label':  'Nima beradi',
    'feat.title':  "Raqobatchilardan\nnima bilan farq qilamiz",
    'feat.desc':   "Boshqa tizimlar o'zbekcha ishlamaydi. Biz — O'zbekiston uchun yaratilgan.",
    'feat.1.title':  "O'zbek tilida 1-o'rin",
    'feat.1.desc':   "Morfologiya, agglutinativ qo'shimchalar, o'zbek leksikasi — barchasi hisobga olingan.",
    'feat.2.title':  'AI matn aniqlash',
    'feat.2.desc':   "RoBERTa + burstiness + stylometry. ChatGPT tomonidan yozilgan matnlarni aniqlaydi.",
    'feat.3.title':  'Unicode himoya',
    'feat.3.desc':   "Kirill harflarini lotinga almashtirish, ko'rinmas belgilar — barchasini aniqlaydi.",
    'feat.4.title':  'Batafsil hisobot',
    'feat.4.desc':   'Har bir moslik manba bilan ko\'rsatiladi. PDF hisobot yuklab olish mumkin.',
    'feat.5.title':  'Tezkor tekshiruv',
    'feat.5.desc':   'Kesh tizimi — bir xil matn ikkinchi marta 0.1 soniyada tekshiriladi.',
    'feat.6.title':  '3 tilda ishlaydi',
    'feat.6.desc':   "O'zbek, Rus, Ingliz — avtomatik til aniqlash. Tarjima plagiatini ham ko'radi.",

    // Pricing
    'price.label':       'Narxlar',
    'price.title':       'Sizga mos rejani tanlang',
    'price.desc':        'Bepul boshlang, kerak bo\'lsa yaxshilang.',
    'price.free.name':   'Bepul',
    'price.free.price':  '0',
    'price.free.curr':   'so\'m',
    'price.period':      'Har oy',
    'price.pro.name':    'Pro',
    'price.pro.price':   '49 000',
    'price.corp.name':   'Korporativ',
    'price.corp.price':  '199 000',
    'price.corp.period': 'Har oy / 100 foydalanuvchi',
    'price.popular':     'Eng mashhur',
    'price.btn.start':   'Boshlash',
    'price.btn.pro':     'Pro boshlash',
    'price.btn.corp':    'Bog\'lanish',
    'price.f1':   '3 ta tekshiruv / oy',
    'price.f2':   'Matn va fayl tekshirish',
    'price.f3':   'AI detektor',
    'price.f4':   'Unicode himoya',
    'price.f5':   'PDF hisobot',
    'price.f6':   'Tarix',
    'price.f7':   'API kirish',
    'price.free_checks': 'Cheksiz tekshiruv',
    'price.users': '100 ta foydalanuvchi',

    // Compare
    'cmp.label':    'Taqqoslash',
    'cmp.title':    'Raqobatchilar vs AntiplagiatPRO',
    'cmp.feature':  'Xususiyat',
    'cmp.r1': "O'zbek tili (to'liq)",
    'cmp.r2': 'AI matn aniqlash',
    'cmp.r3': 'Unicode hiyla aniqlash',
    'cmp.r4': 'Morfologik tahlil',
    'cmp.r5': 'Bepul foydalanish',
    'cmp.r6': 'PDF hisobot',
    'cmp.r7': 'Tarix saqlash',
    'cmp.r8': 'Telegram bot',
    'cmp.r9': 'Yillik narx',
    'cmp.price_us': "Bepul / 49K so'm",

    // FAQ
    'faq.label': 'Savol-javob',
    'faq.title': "Ko'p beriladigan savollar",
    'faq.q1': 'AntiplagiatPRO qanday ishlaydi?',
    'faq.a1': "Matn yuborganda tizim: til aniqlaydi, unicode manipulatsiyani tekshiradi, iqtibos va bibliografiyani olib tashlaydi, morfologik normalizatsiya qiladi, Winnowing va TF-IDF algoritmlar bilan bazadagi hujjatlar bilan solishtiradi. Natija sekundlar ichida tayyor.",
    'faq.q2': "Nima uchun Turnitin dan yaxshiroq?",
    'faq.a2': "Turnitin o'zbek tilini to'liq qo'llab-quvvatlamaydi va yiliga $3000+ turadi. Biz o'zbek morfologiyasini, agglutinativ qo'shimchalarni, o'zbek leksikasini hisobga olamiz.",
    'faq.q3': 'AI matn aniqlash qanchalik aniq?',
    'faq.a3': "Ingliz tilida 82%, o'zbek tilida 68% aniqlik. RoBERTa modeli + burstiness + stilometrik tahlil kombinatsiyasi ishlatiladi.",
    'faq.q4': "Ma'lumotlarim xavfsizmi?",
    'faq.a4': 'Ha. Yuborilgan matnlar uchinchi shaxslarga berilmaydi. HTTPS orqali shifrlangan uzatish.',
    'faq.q5': 'Qaysi fayl formatlari qabul qilinadi?',
    'faq.a5': 'PDF, DOCX va TXT formatlar. Maksimal fayl hajmi 10 MB.',
    'faq.q6': 'Telegram boti ham bormi?',
    'faq.a6': "Ha! @AntiplagiatPRObot orqali ham tekshirish mumkin. Xuddi sayt bilan bir xil algoritmlar ishlatiladi.",

    // CTA
    'cta.title': "Hoziroq boshlang — bepul",
    'cta.desc':  'Ro\'yxatdan o\'ting va 3 ta bepul tekshiruv oling. Karta kerak emas.',
    'cta.btn':   "Bepul ro'yxatdan o'tish →",

    // Footer
    'footer.desc': "O'zbekistondagi eng kuchli plagiat va AI matn aniqlash tizimi.",
    'footer.system':  'Tizim',
    'footer.product': 'Mahsulot',
    'footer.contact': "Bog'lanish",
    'footer.api':     'API hujjatlari',
    'footer.bot':     'Telegram bot',
    'footer.help':    'Yordam markazi',
    'footer.copy':    '© 2025 AntiplagiatPRO. Barcha huquqlar himoyalangan.',

    // Status
    'status.healthy':  '✅ Tizim ishlayapti',
    'status.degraded': '⚠️ Qisman ishlayapti',
  },

  // ── RUS ──────────────────────────────────────────────────
  ru: {
    'meta.title':       'AntiplagiatPRO — Проверка плагиата на узбекском',
    'meta.description': 'Профессиональная проверка плагиата и ИИ-контента на узбекском, русском и английском языках',

    'nav.features':  'Возможности',
    'nav.pricing':   'Цены',
    'nav.compare':   'Сравнение',
    'nav.faq':       'Вопросы',
    'nav.login':     'Войти',
    'nav.register':  'Регистрация',
    'nav.cabinet':   'Кабинет',
    'nav.newcheck':  'Новая проверка',
    'nav.logout':    'Выйти',

    'hero.badge':   'Единственная профессиональная система на узбекском',
    'hero.title1':  'Выявляйте плагиат',
    'hero.title2':  'точно',
    'hero.title3':  'и',
    'hero.title4':  'быстро',
    'hero.title5':  '',
    'hero.desc':    'Winnowing, TF-IDF, морфология и детектор ИИ — всё в одном месте. Поддержка узбекского, русского и английского. Загрузка документов. История и PDF-отчёт.',
    'hero.cta1':    'Проверить бесплатно',
    'hero.cta2':    'Узнать больше',
    'hero.stat1v':  '500K+',
    'hero.stat1l':  'Проверок выполнено',
    'hero.stat2v':  '3',
    'hero.stat2l':  'Поддерживаемых языка',
    'hero.stat3v':  '98%',
    'hero.stat3l':  'Точность',
    'hero.stat4v':  'Бесплатно',
    'hero.stat4l':  'Базовая версия',

    'checker.tab.text':       '📝 Текст',
    'checker.tab.file':       '📎 Файл',
    'checker.placeholder':    'Вставьте текст для проверки здесь...',
    'checker.wordcount':      'слов',
    'checker.btn.check':      'Проверить →',
    'checker.upload.title':   'Загрузите PDF или DOCX',
    'checker.upload.hint':    'Максимальный размер: 10 МБ',
    'checker.processing':     'Анализируется...',
    'checker.btn.pdf':        '📄 PDF',
    'checker.btn.new':        '✕ Новый',

    'result.title':         'Результат',
    'result.plagiarism':    'Уровень плагиата',
    'result.ai':            'Вероятность ИИ',
    'result.language':      'Язык',
    'result.threshold':     'Порог',
    'result.found':         '✗ НАЙДЕН',
    'result.normal':        '✓ Норма',
    'result.low':           '✓ Норма',
    'result.medium':        '⚠ Средний',
    'result.high':          '✗ Высокий',
    'result.sources':       'Найденные источники',
    'result.unicode_alert': '⚠️ Обнаружена Unicode-манипуляция!',

    'error.too_short':  'Введите не менее 5 слов',
    'error.too_large':  'Файл больше 10 МБ',
    'error.file_read':  'Ошибка чтения файла. Отправьте PDF или DOCX.',
    'error.server':     'Произошла ошибка. Попробуйте снова.',
    'error.no_result':  'Результат не найден. Сначала отправьте текст.',
    'error.limit':      'Бесплатный лимит исчерпан. Перейдите на Pro.',
    'error.auth':       'Требуется авторизация',
    'error.rate_limit': 'Слишком много запросов. Подождите немного.',
    'error.network':    'Ошибка соединения. Проверьте интернет.',
    'error.brute_force':'Слишком много попыток. Повторите через 15 минут.',

    'auth.login.title':       'Войти',
    'auth.login.subtitle':    'Войдите в свой аккаунт',
    'auth.register.title':    'Регистрация',
    'auth.register.subtitle': 'Создайте бесплатный аккаунт',
    'auth.name':              'Имя',
    'auth.name.placeholder':  'Ваше имя',
    'auth.email':             'Email',
    'auth.email.placeholder': 'email@gmail.com',
    'auth.password':          'Пароль',
    'auth.password.placeholder': 'Минимум 6 символов',
    'auth.btn.login':         'Войти',
    'auth.btn.register':      'Зарегистрироваться',
    'auth.switch.to_register': 'Нет аккаунта?',
    'auth.switch.register':    'Зарегистрироваться',
    'auth.switch.to_login':    'Уже есть аккаунт?',
    'auth.switch.login':       'Войти',

    'upgrade.title':     'Бесплатный лимит исчерпан',
    'upgrade.desc':      'В бесплатном режиме доступно 3 проверки.',
    'upgrade.price':     '49 000 сум',
    'upgrade.period':    'в месяц / безлимитные проверки',
    'upgrade.btn.view':  'Посмотреть Pro →',
    'upgrade.btn.later': 'Позже',

    'dash.title':       'Личный кабинет',
    'dash.total':       'Всего проверок',
    'dash.free_left':   'Осталось бесплатных',
    'dash.avg_plag':    'Средний плагиат',
    'dash.plan':        'Тариф',
    'dash.btn.new':     '+ Новая проверка',
    'dash.history':     'История проверок',
    'dash.empty':       'История проверок пуста',
    'dash.col.text':    'Текст',
    'dash.col.lang':    'Язык',
    'dash.col.plag':    'Плагиат',
    'dash.col.ai':      'ИИ',
    'dash.col.status':  'Статус',
    'dash.col.date':    'Дата',
    'dash.col.report':  'Отчёт',
    'dash.status.plag': 'Плагиат',
    'dash.status.ok':   'Норма',

    'feat.label': 'Что мы даём',
    'feat.title': 'Чем мы отличаемся\nот конкурентов',
    'feat.desc':  'Другие системы не работают на узбекском. Мы созданы для Узбекистана.',
    'feat.1.title': 'Лидер по узбекскому языку',
    'feat.1.desc':  'Морфология, агглютинативные суффиксы, узбекская лексика — всё учтено.',
    'feat.2.title': 'Определение ИИ-текстов',
    'feat.2.desc':  'RoBERTa + burstiness + stylometry. Обнаруживает тексты ChatGPT.',
    'feat.3.title': 'Unicode-защита',
    'feat.3.desc':  'Замена кириллицы латиницей, невидимые символы — всё выявляется.',
    'feat.4.title': 'Подробный отчёт',
    'feat.4.desc':  'Каждое совпадение показывается с источником. Скачать PDF-отчёт.',
    'feat.5.title': 'Быстрая проверка',
    'feat.5.desc':  'Система кэширования — одинаковый текст проверяется за 0.1 секунды.',
    'feat.6.title': 'Работает на 3 языках',
    'feat.6.desc':  'Узбекский, русский, английский — автоматическое определение языка.',

    'price.label':       'Цены',
    'price.title':       'Выберите подходящий тариф',
    'price.desc':        'Начните бесплатно, обновитесь при необходимости.',
    'price.free.name':   'Бесплатно',
    'price.free.price':  '0',
    'price.free.curr':   'сум',
    'price.period':      'В месяц',
    'price.pro.name':    'Pro',
    'price.pro.price':   '49 000',
    'price.corp.name':   'Корпоратив',
    'price.corp.price':  '199 000',
    'price.corp.period': 'В месяц / 100 пользователей',
    'price.popular':     'Самый популярный',
    'price.btn.start':   'Начать',
    'price.btn.pro':     'Начать Pro',
    'price.btn.corp':    'Связаться',
    'price.f1':   '3 проверки / месяц',
    'price.f2':   'Текст и файл',
    'price.f3':   'Детектор ИИ',
    'price.f4':   'Unicode-защита',
    'price.f5':   'PDF-отчёт',
    'price.f6':   'История',
    'price.f7':   'Доступ к API',
    'price.free_checks': 'Безлимитные проверки',
    'price.users': '100 пользователей',

    'cmp.label':    'Сравнение',
    'cmp.title':    'Конкуренты vs AntiplagiatPRO',
    'cmp.feature':  'Функция',
    'cmp.r1': 'Узбекский язык (полный)',
    'cmp.r2': 'Определение ИИ-текстов',
    'cmp.r3': 'Обнаружение Unicode-манипуляций',
    'cmp.r4': 'Морфологический анализ',
    'cmp.r5': 'Бесплатное использование',
    'cmp.r6': 'PDF-отчёт',
    'cmp.r7': 'Сохранение истории',
    'cmp.r8': 'Telegram-бот',
    'cmp.r9': 'Годовая цена',
    'cmp.price_us': 'Бесплатно / 49K сум',

    'faq.label': 'Вопросы и ответы',
    'faq.title': 'Часто задаваемые вопросы',
    'faq.q1': 'Как работает AntiplagiatPRO?',
    'faq.a1': 'При отправке текста система: определяет язык, проверяет Unicode-манипуляции, удаляет цитаты и библиографию, нормализует морфологию, сравнивает с базой данных алгоритмами Winnowing и TF-IDF. Результат готов за секунды.',
    'faq.q2': 'Чем лучше Turnitin?',
    'faq.a2': 'Turnitin не поддерживает узбекский язык и стоит $3000+/год. Мы учитываем узбекскую морфологию, агглютинативные суффиксы и лексику.',
    'faq.q3': 'Насколько точно определяется ИИ-текст?',
    'faq.a3': 'Для английского — 82%, для узбекского — 68%. Используется комбинация RoBERTa, burstiness и стилометрического анализа.',
    'faq.q4': 'Безопасны ли мои данные?',
    'faq.a4': 'Да. Отправленные тексты не передаются третьим лицам. Передача зашифрована по HTTPS.',
    'faq.q5': 'Какие форматы файлов принимаются?',
    'faq.a5': 'PDF, DOCX и TXT. Максимальный размер файла — 10 МБ.',
    'faq.q6': 'Есть ли Telegram-бот?',
    'faq.a6': 'Да! Через @AntiplagiatPRObot тоже можно проверять. Используются те же алгоритмы, что и на сайте.',

    'cta.title': 'Начните прямо сейчас — бесплатно',
    'cta.desc':  'Зарегистрируйтесь и получите 3 бесплатные проверки. Карта не нужна.',
    'cta.btn':   'Бесплатная регистрация →',

    'footer.desc':    'Самая мощная система проверки плагиата и ИИ-контента в Узбекистане.',
    'footer.system':  'Система',
    'footer.product': 'Продукт',
    'footer.contact': 'Контакты',
    'footer.api':     'Документация API',
    'footer.bot':     'Telegram-бот',
    'footer.help':    'Центр помощи',
    'footer.copy':    '© 2025 AntiplagiatPRO. Все права защищены.',

    'status.healthy':  '✅ Система работает',
    'status.degraded': '⚠️ Частичная работа',
  },

  // ── INGLIZ ───────────────────────────────────────────────
  en: {
    'meta.title':       'AntiplagiatPRO — Plagiarism Checker for Uzbek',
    'meta.description': 'Professional plagiarism and AI content detection in Uzbek, Russian and English',

    'nav.features':  'Features',
    'nav.pricing':   'Pricing',
    'nav.compare':   'Compare',
    'nav.faq':       'FAQ',
    'nav.login':     'Log in',
    'nav.register':  'Sign up',
    'nav.cabinet':   'Dashboard',
    'nav.newcheck':  'New check',
    'nav.logout':    'Log out',

    'hero.badge':   'The only professional system for Uzbek language',
    'hero.title1':  'Detect plagiarism',
    'hero.title2':  'accurately',
    'hero.title3':  'and',
    'hero.title4':  'fast',
    'hero.title5':  '',
    'hero.desc':    'Winnowing, TF-IDF, morphology and AI detector — all in one. Supports Uzbek, Russian and English. File upload. History and PDF reports.',
    'hero.cta1':    'Check for free now',
    'hero.cta2':    'Learn more',
    'hero.stat1v':  '500K+',
    'hero.stat1l':  'Checks performed',
    'hero.stat2v':  '3',
    'hero.stat2l':  'Languages supported',
    'hero.stat3v':  '98%',
    'hero.stat3l':  'Accuracy',
    'hero.stat4v':  'Free',
    'hero.stat4l':  'Basic tier',

    'checker.tab.text':       '📝 Text',
    'checker.tab.file':       '📎 File',
    'checker.placeholder':    'Paste the text you want to check here...',
    'checker.wordcount':      'words',
    'checker.btn.check':      'Check →',
    'checker.upload.title':   'Upload PDF or DOCX',
    'checker.upload.hint':    'Maximum size: 10 MB',
    'checker.processing':     'Analysing…',
    'checker.btn.pdf':        '📄 PDF',
    'checker.btn.new':        '✕ New',

    'result.title':         'Result',
    'result.plagiarism':    'Plagiarism level',
    'result.ai':            'AI probability',
    'result.language':      'Language',
    'result.threshold':     'Threshold',
    'result.found':         '✗ FOUND',
    'result.normal':        '✓ Clean',
    'result.low':           '✓ Clean',
    'result.medium':        '⚠ Medium',
    'result.high':          '✗ High',
    'result.sources':       'Matching sources',
    'result.unicode_alert': '⚠️ Unicode manipulation detected!',

    'error.too_short':  'Please enter at least 5 words',
    'error.too_large':  'File exceeds 10 MB',
    'error.file_read':  'Could not read file. Please send PDF or DOCX.',
    'error.server':     'An error occurred. Please try again.',
    'error.no_result':  'No result found. Please submit a text first.',
    'error.limit':      'Free limit reached. Please upgrade to Pro.',
    'error.auth':       'Authentication required',
    'error.rate_limit': 'Too many requests. Please wait a moment.',
    'error.network':    'Network error. Check your connection.',
    'error.brute_force':'Too many login attempts. Try again in 15 minutes.',

    'auth.login.title':       'Log in',
    'auth.login.subtitle':    'Sign in to your account',
    'auth.register.title':    'Sign up',
    'auth.register.subtitle': 'Create a free account',
    'auth.name':              'Name',
    'auth.name.placeholder':  'Your name',
    'auth.email':             'Email',
    'auth.email.placeholder': 'email@gmail.com',
    'auth.password':          'Password',
    'auth.password.placeholder': 'At least 6 characters',
    'auth.btn.login':         'Log in',
    'auth.btn.register':      'Create account',
    'auth.switch.to_register': "Don't have an account?",
    'auth.switch.register':    'Sign up',
    'auth.switch.to_login':    'Already have an account?',
    'auth.switch.login':       'Log in',

    'upgrade.title':     'Free limit reached',
    'upgrade.desc':      'The free plan includes 3 checks.',
    'upgrade.price':     '49 000 sum',
    'upgrade.period':    'per month / unlimited checks',
    'upgrade.btn.view':  'View Pro plan →',
    'upgrade.btn.later': 'Later',

    'dash.title':       'Dashboard',
    'dash.total':       'Total checks',
    'dash.free_left':   'Free remaining',
    'dash.avg_plag':    'Avg. plagiarism',
    'dash.plan':        'Plan',
    'dash.btn.new':     '+ New check',
    'dash.history':     'Check history',
    'dash.empty':       'No check history yet',
    'dash.col.text':    'Text',
    'dash.col.lang':    'Lang',
    'dash.col.plag':    'Plagiarism',
    'dash.col.ai':      'AI',
    'dash.col.status':  'Status',
    'dash.col.date':    'Date',
    'dash.col.report':  'Report',
    'dash.status.plag': 'Plagiarism',
    'dash.status.ok':   'Clean',

    'feat.label': 'What we offer',
    'feat.title': 'How we differ\nfrom competitors',
    'feat.desc':  'Other systems do not support Uzbek. We are built for Uzbekistan.',
    'feat.1.title': 'No. 1 for Uzbek language',
    'feat.1.desc':  'Morphology, agglutinative suffixes, Uzbek vocabulary — all accounted for.',
    'feat.2.title': 'AI content detection',
    'feat.2.desc':  'RoBERTa + burstiness + stylometry. Detects ChatGPT-written texts.',
    'feat.3.title': 'Unicode protection',
    'feat.3.desc':  'Cyrillic-to-Latin substitution, invisible characters — all detected.',
    'feat.4.title': 'Detailed report',
    'feat.4.desc':  'Every match shown with its source. Download PDF report.',
    'feat.5.title': 'Fast checking',
    'feat.5.desc':  'Cache system — same text checked again in 0.1 seconds.',
    'feat.6.title': 'Works in 3 languages',
    'feat.6.desc':  'Uzbek, Russian, English — automatic language detection.',

    'price.label':       'Pricing',
    'price.title':       'Choose your plan',
    'price.desc':        'Start free, upgrade when you need to.',
    'price.free.name':   'Free',
    'price.free.price':  '0',
    'price.free.curr':   'sum',
    'price.period':      'Per month',
    'price.pro.name':    'Pro',
    'price.pro.price':   '49 000',
    'price.corp.name':   'Enterprise',
    'price.corp.price':  '199 000',
    'price.corp.period': 'Per month / 100 users',
    'price.popular':     'Most popular',
    'price.btn.start':   'Get started',
    'price.btn.pro':     'Start Pro',
    'price.btn.corp':    'Contact us',
    'price.f1':   '3 checks / month',
    'price.f2':   'Text and file checking',
    'price.f3':   'AI detector',
    'price.f4':   'Unicode protection',
    'price.f5':   'PDF report',
    'price.f6':   'History',
    'price.f7':   'API access',
    'price.free_checks': 'Unlimited checks',
    'price.users': '100 users',

    'cmp.label':    'Comparison',
    'cmp.title':    'Competitors vs AntiplagiatPRO',
    'cmp.feature':  'Feature',
    'cmp.r1': 'Uzbek language (full)',
    'cmp.r2': 'AI content detection',
    'cmp.r3': 'Unicode manipulation detection',
    'cmp.r4': 'Morphological analysis',
    'cmp.r5': 'Free usage',
    'cmp.r6': 'PDF report',
    'cmp.r7': 'History storage',
    'cmp.r8': 'Telegram bot',
    'cmp.r9': 'Annual price',
    'cmp.price_us': 'Free / 49K sum',

    'faq.label': 'FAQ',
    'faq.title': 'Frequently asked questions',
    'faq.q1': 'How does AntiplagiatPRO work?',
    'faq.a1': 'When you submit text, the system: detects the language, checks for Unicode manipulation, removes quotes and bibliography, applies morphological normalisation, then compares against the database using Winnowing and TF-IDF algorithms. Results are ready in seconds.',
    'faq.q2': 'Why is it better than Turnitin?',
    'faq.a2': "Turnitin doesn't fully support Uzbek and costs $3 000+/year. We account for Uzbek morphology, agglutinative suffixes and vocabulary.",
    'faq.q3': 'How accurate is the AI detection?',
    'faq.a3': '82% for English, 68% for Uzbek. Uses a combination of RoBERTa, burstiness and stylometric analysis.',
    'faq.q4': 'Is my data safe?',
    'faq.a4': 'Yes. Submitted texts are not shared with third parties. All transfers are encrypted via HTTPS.',
    'faq.q5': 'Which file formats are accepted?',
    'faq.a5': 'PDF, DOCX and TXT. Maximum file size is 10 MB.',
    'faq.q6': 'Is there a Telegram bot?',
    'faq.a6': 'Yes! You can also check via @AntiplagiatPRObot using the exact same algorithms as the website.',

    'cta.title': 'Get started now — for free',
    'cta.desc':  'Sign up and get 3 free checks. No card required.',
    'cta.btn':   'Sign up for free →',

    'footer.desc':    "Uzbekistan's most powerful plagiarism and AI content detection system.",
    'footer.system':  'System',
    'footer.product': 'Product',
    'footer.contact': 'Contact',
    'footer.api':     'API docs',
    'footer.bot':     'Telegram bot',
    'footer.help':    'Help centre',
    'footer.copy':    '© 2025 AntiplagiatPRO. All rights reserved.',

    'status.healthy':  '✅ System operational',
    'status.degraded': '⚠️ Partial operation',
  },
};

// ─── i18n ENGINE ─────────────────────────────────────────────────────────────
const i18n = (() => {
  const STORAGE_KEY = 'ap_lang';
  const DEFAULT     = 'uz';
  const SUPPORTED   = ['uz', 'ru', 'en'];

  let _lang = localStorage.getItem(STORAGE_KEY) || DEFAULT;

  /** Hozirgi til */
  function getLang() { return _lang; }

  /** Tarjima olish. Kalit topilmasa — kalitning o'zi qaytadi */
  function t(key, vars) {
    const dict = TRANSLATIONS[_lang] || TRANSLATIONS[DEFAULT];
    let text = dict[key] ?? TRANSLATIONS[DEFAULT][key] ?? key;
    if (vars) {
      Object.entries(vars).forEach(([k, v]) => {
        text = text.replace(new RegExp(`{${k}}`, 'g'), v);
      });
    }
    return text;
  }

  /** Til o'zgartirish va sahifani yangilash */
  function setLang(lang) {
    if (!SUPPORTED.includes(lang)) return;
    _lang = lang;
    localStorage.setItem(STORAGE_KEY, lang);
    applyTranslations();
    document.documentElement.lang = lang;
    document.title = t('meta.title');
    // Meta description
    const meta = document.querySelector('meta[name="description"]');
    if (meta) meta.setAttribute('content', t('meta.description'));
    // Til tugmalarini yangilash
    document.querySelectorAll('[data-lang-btn]').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.langBtn === lang);
    });
  }

  /**
   * Sahifadagi barcha data-i18n elementlarni yangilash.
   *
   * Qo'llab-quvvatlanadigan atributlar:
   *   data-i18n="key"                  → textContent
   *   data-i18n-html="key"             → innerHTML
   *   data-i18n-placeholder="key"      → placeholder
   *   data-i18n-title="key"            → title atributi
   *   data-i18n-aria-label="key"       → aria-label
   *   data-i18n-value="key"            → value (input)
   */
  function applyTranslations() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
      el.textContent = t(el.dataset.i18n);
    });
    document.querySelectorAll('[data-i18n-html]').forEach(el => {
      el.innerHTML = t(el.dataset.i18nHtml);
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
      el.placeholder = t(el.dataset.i18nPlaceholder);
    });
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
      el.title = t(el.dataset.i18nTitle);
    });
    document.querySelectorAll('[data-i18n-aria-label]').forEach(el => {
      el.setAttribute('aria-label', t(el.dataset.i18nAriaLabel));
    });
  }

  /** Sahifa yuklanganda avtomatik qo'llash */
  function init() {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => setLang(_lang));
    } else {
      setLang(_lang);
    }
  }

  init();

  return { t, setLang, getLang, apply: applyTranslations, langs: SUPPORTED };
})();

// Global ga chiqarish
window.i18n = i18n;
