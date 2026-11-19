# دانلود Digital Concert Hall

> **وضعیت (۲۰۲۶-۱۱-۱۷):** پیاده‌سازی کامل و در محیط آزمایشی راستی‌آزمایی شده (۲۴۵+ تست واحد، و یک آزمون end-to-end
> با Chromium واقعی، افزونه‌ی واقعی، host واقعی و کارگر واقعی روی سایت **جعلی با توکن جعلی**).
> **دانلود واقعی با حساب شما هنوز اجرا نشده** — کیفیت، DRM و عمر توکن فقط با «مرحله‌ی آزمایش» پایین مشخص می‌شود.
> پیشینه و دلیل طراحی: [مرور پلن](archive/digital-concert-hall-plan-review.md).

## دو روش

| | روش الف: پل Brave (پیشنهادی) | روش ب: توکن دستی |
| --- | --- | --- |
| دستور | `dch-start` یا ابزار MCP `dch_start` | `dch` |
| توکن را چه کسی می‌گیرد | افزونه‌ی Brave، خودکار | شما، با کپی از DevTools |
| مناسب | استفاده با Codex / ChatGPT / Claude Desktop | یک بار آزمایش یا اسکریپت |
| اجرا | پس‌زمینه، با وضعیت قابل پیگیری | پیش‌زمینه |

## روش الف: پل Brave

### معماری

```text
Codex / ChatGPT Desktop / Claude Desktop
        │  MCP (stdio): dch_start · dch_status · dch_jobs     ← هیچ ابزاری توکن نمی‌گیرد یا برنمی‌گرداند
        ▼
  ytdlp_tool.dch_mcp ──(loopback 127.0.0.1 + راز تصادفی)──► ytdlp_tool.dch_host  (Native Messaging)
                                                                  │ «get_token»
                                                                  ▼
                                              افزونه‌ی Brave (فقط https://www.digitalconcerthall.com/*)
                                              از localStorage خود سایت می‌خواند و پاسخ می‌دهد
                                                                  │ توکن
                                                                  ▼
       host ──(stdin یک پردازش جدا)──► dch-worker  ─► yt-dlp  ─► فایل‌ها + status.json
```

توکن فقط در مسیر «افزونه ← host ← stdin کارگر» می‌گذرد؛ در آرگومان، متغیر محیطی، فایل، لاگ، کلیپ‌بورد، پاسخ MCP و متن گفتگو
**نمی‌آید** (با آزمون‌های واحد و آزمون مرورگر واقعی بررسی شده؛ مثلاً `grep` توکن در پوشه‌ی وضعیت چیزی پیدا نمی‌کند).

### نصب (یک‌بار)

۱. روی Ops (PowerShell عادی، بدون admin):

```powershell
cd C:\GitHub\yt-dlp
python -m ytdlp_tool.dch_install install        # host + ثبت برای Brave + تنظیم Claude Desktop و Codex (با backup)
python -m ytdlp_tool.dch_install status
```

۲. در Brave: `brave://extensions` ← **Developer mode** ← **Load unpacked** ← پوشه‌ی `C:\GitHub\yt-dlp\extensions\dch-bridge`.
شناسه‌ی افزونه باید `bcohebdjklmiaddlkbemjfioeloajdlj` باشد (ثابت است؛ host فقط همین افزونه را می‌پذیرد).

۳. Claude Desktop و Codex را یک‌بار ببندید و باز کنید تا MCP جدید را بخوانند. (ChatGPT Desktop: پلاگین `ytdl` نسخه‌ی ۰.۲.۹
دستورالعمل را دارد و از همان مسیر CLI/MCP استفاده می‌کند.)

۴. در Brave وارد digitalconcerthall.com شوید (همیشه همین است) و صفحه‌ی کنسرت را باز بگذارید.

حذف: `python -m ytdlp_tool.dch_install uninstall` و حذف افزونه از Brave.

### استفاده

در گفتگو بگویید: «کنسرت Digital Concert Hall بازشده در Brave را دانلود کن» یا آدرس را بدهید. یا از ترمینال:

```powershell
python -m ytdlp_tool dch-start --list                       # بخش‌ها و بهترین کیفیت؛ چیزی دانلود نمی‌شود
python -m ytdlp_tool dch-start                              # تب کنسرت باز را دانلود کن
python -m ytdlp_tool dch-start "https://www.digitalconcerthall.com/en/concert/56205" --item 2
python -m ytdlp_tool dch-status                             # کارهای اخیر
python -m ytdlp_tool dch-status JOB_ID                      # یک کار
```

* بدون آدرس: اگر دقیقاً یک تب کنسرت/فیلم/اثر باز باشد (یا فقط یکی فعال باشد) همان انتخاب می‌شود. اگر چند تب باشد،
  افزونه خطای روشن می‌دهد و آدرس را می‌خواهد (تب فعال ChatGPT یا هر تب غیر DCH هرگز انتخاب نمی‌شود).
* خروجی: `output\chatgpt\digital-concert-hall\<عنوان> [<شناسه>]\NN - <بخش> [<id>].<ext>` (قابل تغییر با `YTDLP_DCH_OUTPUT`).
  فایل موجود بازنویسی نمی‌شود.
* وضعیت و لاگ: `%LOCALAPPDATA%\ytdlp-tool\dch\jobs\<id>\status.json` و `host.log` (بدون توکن).

### رفتار کارهای طولانی (دانلود ممکن است دقایق تا ساعت‌ها طول بکشد)

* کارگر مستقل و جداشده از host/مرورگر است؛ بستن گفتگو یا مرورگر دانلود را قطع نمی‌کند.
* `status.json` شامل pid، زمان شروع، سقف زمان، وضعیت (`running`/`done`/`failed`)، خطای پاک‌سازی‌شده و فایل‌های نهایی است.
* سقف زمان پیش‌فرض ۶ ساعت است؛ پس از آن خود کارگر شکست را ثبت می‌کند و فایل‌های موقت `.part` را پاک می‌کند.
* `done` فقط وقتی ثبت می‌شود که همه‌ی فایل‌های گزارش‌شده موجود و غیرخالی باشند. کارگر مرده/کشته‌شده `failed` گزارش می‌شود، نه `running`.
* درخواست یکسانِ در حال اجرا دوباره شروع نمی‌شود (`duplicate`)؛ درخواست یکسانِ تمام‌شده نتیجه‌ی قبلی را برمی‌گرداند (`already_done`).
* دستیار پس از شروع باید **متوقف شود** و فقط با درخواست بعدی شما، یک‌بار وضعیت را بخواند (بدون polling).

### مجوزهای افزونه (تصمیم باز پلن، اکنون بسته شده)

مجوز دائمی **محدود به یک دامنه**: `https://www.digitalconcerthall.com/*` + `scripting` + `nativeMessaging` + `alarms` (اتصال مجدد).
`activeTab` انتخاب نشد چون «تب باز را تشخیص بده» بدون کلیک ممکن نمی‌شد. افزونه به سایت دیگری، به `tabs` عمومی یا
شبکه دسترسی ندارد و فقط به host با نام `com.ytdlp_tool.dch` جواب می‌دهد (و آن host فقط به همین افزونه).
هر پردازش هم‌کاربرِ محلی می‌تواند از طریق پل «شروع دانلود یک URL معتبر DCH» را بخواهد ولی هرگز به **خود توکن** نمی‌رسد.

## روش ب: توکن دستی (`dch`)

در Brave: DevTools ← Application ← Local Storage ← `https://www.digitalconcerthall.com` ← مقدار `access_token_production`.
روی Ops (توکن با ورودی مخفی پرسیده می‌شود؛ چیزی نمایش داده نمی‌شود):

```powershell
ytdlp-tool dch "https://www.digitalconcerthall.com/en/concert/56205" --list
ytdlp-tool dch "https://www.digitalconcerthall.com/en/concert/56205" --item 2 --format-selector "bv*[height<=1080]+ba/b"
# اسکریپت: توکن از stdin (هرگز آرگومان یا متغیر محیطی نه)
... | ytdlp-tool dch URL --token-stdin
```

## تضمین‌های امنیتی و راستی‌آزمایی

| قاعده | چگونه تأمین و آزموده شده |
| --- | --- |
| توکن در argv / env / فایل / لاگ / پاسخ MCP نیست | stdin کارگر؛ تست‌ها وجود نداشتن توکن در همه‌ی فایل‌های وضعیت، پاسخ‌ها و خطاها را بررسی می‌کنند |
| توکن روی دیسک (کش yt-dlp) ثبت نمی‌شود | `cachedir=False`؛ با extractor واقعی آزموده شد: بدون آن `tokens.json` ساخته می‌شود، با آن نه |
| پل فقط برای کاربر محلی | فقط `127.0.0.1`، راز تصادفی ۲۵۶بیتی در فایل کاربر، مقایسه‌ی زمان‌ثابت؛ بدون راز هرگز از افزونه توکن نمی‌خواهد |
| فقط افزونه‌ی ما با host حرف بزند | `allowed_origins` مرورگر + بررسی دوباره‌ی origin در host؛ شناسه‌ی افزونه با کلید manifest تطبیق داده می‌شود (تست) |
| فقط این سایت | URL باید `https` + دامنه‌ی DCH + مسیر `film/concert/work`؛ بدون user:pass؛ افزونه فقط به همین دامنه مجوز دارد |
| ابزار MCP محدود | فقط start/status/jobs؛ بدون اجرای فرمان، بدون خواندن فایل دلخواه، بدون توکن؛ `start` به‌عنوان عملیات نوشتنی علامت‌گذاری شده |
| توکن منقضی بی‌جهت مصرف نمی‌شود | انقضای JWT پیش از هر تماس بررسی می‌شود |
| بدون refresh token | طبق پلن؛ پس توکن عمر محدود دارد (پایین) |

## محدودیت‌ها و عدم‌قطعیت‌ها

* **عمر توکن نامعلوم است.** کنسرت چندبخشی ممکن است وسط کار با «token rejected» بایستد؛ بخش‌های کامل می‌مانند و با `--item N`
  ادامه می‌دهید. (با refresh token این مشکل حل می‌شد ولی پلن آن را عمداً کنار گذاشته است.)
* کیفیت: extractor خودش می‌گوید جریان‌های ۴K/FLAC دیگر در دسترس نیست؛ `--list` کیفیت واقعی حساب را نشان می‌دهد.
* محتوای DRM یا بدون دسترسی با پیام صریح گزارش می‌شود؛ دور زدن آن‌ها بخشی از این ابزار نیست.
* به `ffmpeg` در PATH نیاز دارد. مرحله‌ی دانلود روی Ops نیازمند روشن بودن Ops، Brave و شبکه است.
* مسیر **وب** (ChatGPT/Claude تحت وب) پیاده نشده: توکن و فایل نباید از Ops خارج شوند و این نیازمند MCP راه‌دور احراز‌شده
  است که بدون نیاز واقعی ساخته نشد (پلن مرحله ۶).
* شرایط استفاده‌ی سایت درباره‌ی دانلود را بررسی نکرده‌ام؛ مسئولیت استفاده با شماست و فقط برای محتوایی است که حساب شما
  مجاز به پخش آن است.

## عیب‌یابی

| نشانه | بررسی |
| --- | --- |
| «The Brave bridge is not running» | Brave باز باشد و افزونه فعال؛ `python -m ytdlp_tool.dch_install status`؛ در `brave://extensions` برای افزونه روی service worker بزنید و خطای اتصال را ببینید |
| «No Digital Concert Hall tab is open» | سایت را در Brave باز و وارد شوید |
| «N concert pages are open» | آدرس را صریح بدهید |
| «Not signed in … no access token» | وارد سایت شوید؛ صفحه را reload کنید |
| «Access token has expired» / «rejected the token» | صفحه‌ی سایت را reload کنید (توکن تازه می‌شود) و دوباره شروع کنید |
| Claude Desktop ابزار را نشان نمی‌دهد | بعد از `install` برنامه را کامل ببندید و باز کنید |
| بررسی لاگ host | `%LOCALAPPDATA%\ytdlp-tool\dch\host.log` |

## مرحله‌ی آزمایش (یک‌بار، چند دقیقه)

۱. `dch-start --list` ← بخش‌ها و کیفیت واقعی را ببینید.
۲. `dch-start --item 1` روی کوتاه‌ترین بخش ← با `dch-status` پیگیری کنید و فایل نهایی را باز کنید.
۳. زمان بین «reload صفحه» تا «خطای انقضا» را یادداشت کنید (عمر توکن).

## آزمون end-to-end (برای توسعه‌دهنده)

`tests/e2e/run_dch_e2e.sh` (به node + playwright + Xvfb نیاز دارد): Chromium واقعی با افزونه‌ی واقعی، صفحه‌ی جعلی
digitalconcerthall.com با توکن جعلی، host ثبت‌شده، سپس `dch-start` ← کارگر. خروجی مورد انتظار: `E2E PASSED`
(کارگر توکن را از مرورگر می‌گیرد، extractor واقعی آن را با سرور واقعی امتحان می‌کند و چون جعلی است ۴۰۱ می‌گیرد).
