# راهنمای کامل استفاده از promptctl با Docker و Extension

## مقدمه
promptctl یه ابزار Git-backed برای مدیریت prompt هاست که قابلیت‌های زیر رو داره:
- ذخیره و version control پرامپت‌ها با Git
- تگ‌گذاری و فیلتر کردن (AND/OR logic)
- **Optimization با DSPy** - بهینه‌سازی خودکار پرامپت‌ها
- Browser extension - ذخیره سریع از مرورگر
- Daemon mode با HTTP socket - برای integration

---

## ۱. راه‌اندازی Docker

### Build کردن Image

```bash
cd /Users/omid/dev/promptctl
docker build -t promptctl:latest .
```

**نکته:** Warning مربوط به `dspy-ai not installed` نگران‌کننده نیست - dspy نصب شده و کار می‌کنه.

### ایجاد Volume برای Persistence

```bash
docker volume create promptctl-data
```

### تست اولیه

```bash
# کمک
docker run --rm promptctl:latest --help

# ذخیره یه prompt
echo "You are a helpful AI assistant" | docker run --rm -i \
  -v promptctl-data:/home/promptctl/.promptctl \
  promptctl:latest save --name test --tags ai

# لیست prompt ها
docker run --rm -v promptctl-data:/home/promptctl/.promptctl \
  promptctl:latest list
```

---

## ۲. استفاده از DSPy برای Optimization

DSPy برای optimize کردن پرامپت‌ها استفاده می‌شه. می‌تونی از چند راه ازش استفاده کنی:

### A) با OpenAI API

```bash
# اول API key رو set کن
export OPENAI_API_KEY="sk-your-key-here"

# Optimize کردن یه prompt
docker run --rm \
  -v promptctl-data:/home/promptctl/.promptctl \
  -e OPENAI_API_KEY \
  promptctl:latest optimize test --rounds 3
```

### B) با Local Ollama (رایگان و Local!)

```bash
# ۱. نصب Ollama (خارج از Docker)
brew install ollama

# ۲. شروع Ollama service
brew services start ollama

# ۳. دانلود model (مثلاً Phi-3.5، حدود 2.2GB)
ollama pull phi3.5

# ۴. تست Ollama
ollama run phi3.5 "Hello"

# ۵. حالا می‌تونی از Docker استفاده کنی
# باید Docker container به host machine دسترسی داشته باشه
docker run --rm \
  --add-host=host.docker.internal:host-gateway \
  -v promptctl-data:/home/promptctl/.promptctl \
  promptctl:latest optimize test --rounds 3 --use-ollama
```

**نکته مهم:** Ollama باید روی host machine (macOS) اجرا بشه، نه داخل Docker!

---

## ۳. راه‌اندازی Browser Extension

Extension نیاز به یه **daemon** داره که روی پورت 9090 listen کنه.

### Step 1: Run Daemon با Socket

```bash
# با Docker
docker run -d \
  --name promptctl-daemon \
  -v promptctl-data:/home/promptctl/.promptctl \
  -p 9090:9090 \
  promptctl:latest daemon --interval 60 --socket --socket-port 9090
```

یا با docker-compose (راحت‌تر):

```bash
cd /Users/omid/dev/promptctl
docker-compose --profile daemon up -d
```

### Step 2: بررسی که Daemon در حال اجراست

```bash
# بررسی که container اجرا شده
docker ps | grep promptctl

# تست endpoint
curl http://localhost:9090/health
# باید بگه: {"status": "ok", "service": "promptctl"}

# لاگ‌ها رو ببین
docker logs -f promptctl-daemon
```

### Step 3: نصب Extension در مرورگر

#### Chrome/Brave/Edge:
1. مرورگر رو باز کن
2. برو به: `chrome://extensions/`
3. "Developer mode" رو فعال کن
4. کلیک کن "Load unpacked"
5. پوشه `/Users/omid/dev/promptctl/extension` رو انتخاب کن

#### Firefox:
1. برو به: `about:debugging#/runtime/this-firefox`
2. کلیک کن "Load Temporary Add-on"
3. فایل `manifest.json` رو از پوشه `extension` انتخاب کن

### Step 4: استفاده از Extension

#### روش ۱: از popup استفاده کن
1. آیکون extension رو کلیک کن (در toolbar)
2. Status باید "Connected" باشه (نقطه سبز)
3. متنی که می‌خوای رو بنویس
4. (اختیاری) نام و تگ بده
5. "Save Prompt" رو بزن

#### روش ۲: Context Menu (کلیک راست)
1. متن دلخواه رو در صفحه select کن
2. کلیک راست کن
3. انتخاب کن "Save to PromptCtl"
4. ✅ ذخیره شد! (notification می‌بینی)

#### روش ۳: Keyboard Shortcut
1. متن رو select کن
2. بزن: `Cmd+Shift+S` (macOS) یا `Ctrl+Shift+S` (Windows/Linux)
3. ✅ ذخیره شد!

---

## ۴. workflow کامل: از Browser تا DSPy Optimization

حالا می‌تونی یه workflow کامل داشته باشی:

```bash
# ۱. Daemon رو start کن (با socket)
docker-compose --profile daemon up -d

# ۲. از extension متن رو save کن (مثلاً از یه صفحه وب)
# فرض کن prompt ای با نام "my-web-prompt" ذخیره کردی

# ۳. لیست prompts رو ببین
docker run --rm -v promptctl-data:/home/promptctl/.promptctl \
  promptctl:latest list

# ۴. Optimize کن با DSPy (با Ollama مثلاً)
# اول مطمئن شو Ollama اجرا شده:
ollama list  # باید phi3.5 رو ببینی

# حالا optimize کن:
docker run --rm \
  --add-host=host.docker.internal:host-gateway \
  -v promptctl-data:/home/promptctl/.promptctl \
  promptctl:latest optimize my-web-prompt --rounds 5 --use-ollama

# ۵. نتیجه رو ببین
docker run --rm -v promptctl-data:/home/promptctl/.promptctl \
  promptctl:latest show my-web-prompt_optimized_v1
```

---

## ۵. دستورات مفید دیگه

### Chain Prompts (زنجیره کردن)

```bash
# چند prompt رو به هم وصل کن
docker run --rm \
  -v promptctl-data:/home/promptctl/.promptctl \
  promptctl:latest chain prompt1 prompt2 prompt3 --name my-chain
```

### Evaluate با Test Cases

```bash
# ایجاد test file
cat > /tmp/tests.json << 'EOF'
[
  {"input": "test 1", "expected": "output 1"},
  {"input": "test 2", "expected": "output 2"}
]
EOF

# Evaluate کن
docker run --rm \
  -v promptctl-data:/home/promptctl/.promptctl \
  -v /tmp:/tmp \
  promptctl:latest evaluate my-prompt --test-file /tmp/tests.json
```

### Agent Mode (خودکار بهینه‌سازی تا رسیدن به target score)

```bash
docker run --rm \
  -v promptctl-data:/home/promptctl/.promptctl \
  -v /tmp:/tmp \
  promptctl:latest agent my-prompt \
    --rounds 10 \
    --min-score 85.0 \
    --test-file /tmp/tests.json \
    --report
```

---

## ۶. Git Version Control

همه چیز تحت version control گیت:

```bash
# تاریخچه رو ببین
docker run --rm -v promptctl-data:/home/promptctl/.promptctl \
  promptctl:latest /bin/bash -c \
  "cd /home/promptctl/.promptctl && git log --oneline"

# تغییرات رو ببین
docker run --rm -v promptctl-data:/home/promptctl/.promptctl \
  promptctl:latest diff

# Status
docker run --rm -v promptctl-data:/home/promptctl/.promptctl \
  promptctl:latest status -v
```

---

## ۷. مدیریت Daemon

### بررسی وضعیت

```bash
# Container logs
docker logs promptctl-daemon

# Live logs
docker logs -f promptctl-daemon

# بررسی health
curl http://localhost:9090/health
```

### Restart/Stop

```bash
# Stop
docker stop promptctl-daemon
docker rm promptctl-daemon

# یا با compose:
docker-compose --profile daemon down

# Start دوباره
docker-compose --profile daemon up -d
```

---

## ۸. Troubleshooting

### مشکل: Extension نمی‌تونه connect بشه

```bash
# بررسی daemon اجرا شده؟
docker ps | grep promptctl

# بررسی پورت 9090 باز هست؟
curl http://localhost:9090/health

# بررسی لاگ‌ها
docker logs promptctl-daemon

# اگر daemon اجرا نشده، دوباره start کن:
docker-compose --profile daemon up -d
```

### مشکل: DSPy optimize کار نمی‌کنه

```bash
# با Ollama:
# ۱. بررسی Ollama اجرا شده
ollama list

# ۲. بررسی model دانلود شده
ollama pull phi3.5

# ۳. تست Ollama
ollama run phi3.5 "test"

# ۴. مطمئن شو flag --use-ollama رو اضافه کردی
# و --add-host=host.docker.internal:host-gateway

# با OpenAI:
# مطمئن شو OPENAI_API_KEY set شده
echo $OPENAI_API_KEY
```

### مشکل: Volume پاک شده یا data از بین رفته

```bash
# لیست volumes
docker volume ls | grep promptctl

# بررسی محتویات volume
docker run --rm -v promptctl-data:/data alpine ls -la /data

# اگر خالیه، یه نمونه دوباره بساز:
echo "test" | docker run --rm -i \
  -v promptctl-data:/home/promptctl/.promptctl \
  promptctl:latest save --name test --tags demo
```

---

## ۹. پاکسازی (Cleanup)

```bash
# توقف همه containers
docker-compose --profile daemon down
docker stop promptctl-daemon 2>/dev/null || true
docker rm promptctl-daemon 2>/dev/null || true

# پاک کردن volume (⚠️ همه prompt ها پاک می‌شن!)
docker volume rm promptctl-data

# پاک کردن image
docker rmi promptctl:latest
```

---

## ۱۰. خلاصه Commands

### با Docker (بدون compose)

```bash
# Save
echo "text" | docker run --rm -i -v promptctl-data:/home/promptctl/.promptctl promptctl:latest save --name NAME --tags TAG1 TAG2

# List
docker run --rm -v promptctl-data:/home/promptctl/.promptctl promptctl:latest list

# Show
docker run --rm -v promptctl-data:/home/promptctl/.promptctl promptctl:latest show NAME

# Optimize (با Ollama)
docker run --rm --add-host=host.docker.internal:host-gateway -v promptctl-data:/home/promptctl/.promptctl promptctl:latest optimize NAME --use-ollama

# Daemon با socket
docker run -d --name promptctl-daemon -v promptctl-data:/home/promptctl/.promptctl -p 9090:9090 promptctl:latest daemon --socket
```

### با Docker Compose (راحت‌تر!)

```bash
# Save
echo "text" | docker-compose run --rm -T promptctl save --name NAME --tags TAG1 TAG2

# List
docker-compose run --rm promptctl list

# Show
docker-compose run --rm promptctl show NAME

# Daemon
docker-compose --profile daemon up -d

# Stop daemon
docker-compose --profile daemon down
```

---

## نتیجه‌گیری

حالا می‌تونی:
1. ✅ از Docker استفاده کنی برای run کردن promptctl
2. ✅ از Browser extension prompt ها رو save کنی
3. ✅ با DSPy prompt ها رو optimize کنی (با Ollama یا OpenAI)
4. ✅ همه چیز تحت Git version control باشه
5. ✅ با daemon mode، extension و Docker ارتباط داشته باشه

---

## لینک‌های مفید

- راهنمای Docker: [DOCKER.md](DOCKER.md)
- راهنمای سریع Docker: [DOCKER_QUICKSTART.md](DOCKER_QUICKSTART.md)
- نتایج تست: [DOCKER_TEST_RESULTS.md](DOCKER_TEST_RESULTS.md)
- راهنمای اصلی: [README.md](README.md)
- راهنمای DSPy: [DSPY_GUIDE.md](DSPY_GUIDE.md)
- راهنمای Extension: [EXTENSION_GUIDE.md](EXTENSION_GUIDE.md)
