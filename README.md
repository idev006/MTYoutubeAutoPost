# MTYoutubeAutoPost

YouTube Bulk Video Uploader สำหรับนายหน้า Shopee พร้อมระบบ Affiliate Links

## Features

- ✅ อัพโหลดวิดีโอแนวนอน (16:9) และแนวตั้ง (9:16 Shorts)
- ✅ แนบ Affiliate Links อัตโนมัติ
- ✅ ตรวจจับ duplicate และอัพเดทแทนการอัพโหลดซ้ำ
- ✅ สร้าง Playlist อัตโนมัติ
- ✅ PySide6 Desktop UI
- ✅ Multithreading (configurable workers)
- ✅ Start/Pause/Stop/Resume
- ✅ Crash Recovery

## Requirements

- Python 3.12+
- YouTube Data API v3 credentials
- FFprobe (for video metadata)

## Installation

```bash
# Create virtual environment
python -m venv .

# Activate (Windows)
.\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

1. สร้าง YouTube API credentials ที่ [Google Cloud Console](https://console.cloud.google.com/)
2. ดาวน์โหลด `client_secrets.json` ไปไว้ที่ `data/config/`
3. รันโปรแกรมและ authorize

## Usage

```bash
python app/main.py
```

## Project Structure

```
app/
├── core/           # Business logic
├── models/         # Database models
├── services/       # YouTube API, Template Engine
├── ui/             # PySide6 UI
├── utils/          # Utilities
└── workers/        # Upload workers

data/
├── config/         # Configuration files
├── db/             # SQLite database
└── logs/           # Log files
```

## License

MIT
