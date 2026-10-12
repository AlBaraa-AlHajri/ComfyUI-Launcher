"""English and Arabic user-visible messages with native Windows font shaping."""

MESSAGES = {
    "checking": ("Checking environment", "جارٍ فحص البيئة"),
    "starting": ("Starting ComfyUI", "جارٍ تشغيل ComfyUI"),
    "waiting": ("Waiting for server", "بانتظار جاهزية الخادم"),
    "ready": ("Ready", "جاهز"),
    "stopping": ("Stopping ComfyUI", "جارٍ إيقاف ComfyUI"),
    "stopped": ("Stopped", "متوقف"),
    "open": ("Open ComfyUI", "فتح ComfyUI"),
    "restart": ("Restart", "إعادة التشغيل"),
    "stop": ("Stop", "إيقاف"),
    "log": ("Open log", "فتح السجل"),
    "folder": ("Open ComfyUI folder", "فتح مجلد ComfyUI"),
    "output": ("Open output folder", "فتح مجلد النتائج"),
    "settings": ("Settings", "الإعدادات"),
    "about": ("About", "حول التطبيق"),
    "exit": ("Exit", "خروج"),
    "hide": ("Hide to tray", "إخفاء إلى شريط النظام"),
    "error": ("ComfyUI could not start", "تعذّر تشغيل ComfyUI"),
    "error_help": (
        "Review the details below, adjust Settings, then Retry.",
        "راجع التفاصيل أدناه، وعدّل الإعدادات، ثم أعد المحاولة.",
    ),
    "copy": ("Copy error", "نسخ الخطأ"),
    "copied": ("Copied", "تم النسخ"),
    "retry": ("Retry", "إعادة المحاولة"),
    "close": ("Close", "إغلاق"),
    "save": ("Save", "حفظ"),
    "cancel": ("Cancel", "إلغاء"),
    "browse": ("Browse", "استعراض"),
    "first_run": ("Connect your ComfyUI installation", "ربط نسخة ComfyUI الموجودة"),
    "comfy_dir": ("ComfyUI folder (contains main.py)", "مجلد ComfyUI الذي يحتوي على main.py"),
    "python_exe": ("Environment python.exe", "ملف python.exe الخاص بالبيئة"),
    "port": ("Server port", "منفذ الخادم"),
    "browser": ("Browser", "المتصفح"),
    "language": ("Language", "اللغة"),
    "timeout": ("Startup timeout (seconds)", "مهلة التشغيل بالثواني"),
    "app_mode": ("Open browser as an app window", "فتح المتصفح كنافذة تطبيق"),
    "open_on_start": ("Open browser when ready", "فتح المتصفح عند الجاهزية"),
    "minimize": ("Hide to tray when ready", "الإخفاء إلى شريط النظام عند الجاهزية"),
    "flags": ("Common startup flags", "خيارات التشغيل الشائعة"),
    "extra": ("Additional arguments (Windows quoting)", "وسائط إضافية بصيغة أوامر Windows"),
    "flags_help": (
        "Choose one memory mode. --listen exposes ComfyUI on your network.",
        "اختر وضع ذاكرة واحداً. خيار --listen يتيح الوصول من الشبكة.",
    ),
    "saved": (
        "Saved. Server changes apply on the next Restart.",
        "تم الحفظ. تُطبّق تغييرات الخادم عند إعادة التشغيل القادمة.",
    ),
    "invalid": ("Check your settings", "تحقق من الإعدادات"),
    "busy": (
        "Port {port} belongs to another program. Use and save port {next_port}?",
        "المنفذ {port} مستخدم من برنامج آخر. هل تريد استخدام وحفظ المنفذ {next_port}؟",
    ),
    "external": (
        "This ComfyUI server was started outside the launcher. Manage it in its original "
        "terminal; the launcher will not stop it.",
        "تم تشغيل هذا الخادم خارج المشغّل. أدره من نافذته الأصلية؛ لن يقوم المشغّل بإيقافه.",
    ),
    "about_text": (
        "ComfyUI Launcher {version}\nUnofficial community project.\n"
        "Not affiliated with Comfy Org.\nMIT License • Original workflow/play artwork",
        "ComfyUI Launcher {version}\nمشروع مجتمعي غير رسمي.\n"
        "غير تابع لـ Comfy Org.\nرخصة MIT • تصميم أصلي لأيقونة سير العمل",
    ),
    "elapsed": ("{seconds}s elapsed", "الوقت المنقضي: {seconds} ث"),
    "subtitle": ("YOUR WORKFLOWS. ONE CLICK.", "سير عملك، بنقرة واحدة"),
    "config_error": (
        "The saved configuration could not be loaded. It will be backed up when "
        "you save corrected settings.",
        "تعذّر تحميل الإعدادات. ستُحفظ نسخة احتياطية منها عند حفظ الإعدادات المصححة.",
    ),
    "tray_error": (
        "System tray unavailable. Keep this window open to manage ComfyUI.",
        "شريط النظام غير متاح. أبقِ هذه النافذة مفتوحة لإدارة ComfyUI.",
    ),
}


def tr(key: str, language: str = "ar", **values: object) -> str:
    """Look up a complete message before interpolation to keep Arabic sentence order."""
    return MESSAGES[key][language == "ar"].format(**values)
