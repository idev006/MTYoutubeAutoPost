# MTYoutubeAutoPost - Action Plan

> แผนการพัฒนาแบ่งเป็น 7 เฟส พร้อมหัวข้อย่อย

---

## 📋 Requirements Summary

| Requirement | Description |
|-------------|-------------|
| **Playlist** | รองรับการสร้าง playlist ใหม่อัตโนมัติ |
| **Multi-video** | 1 folder หลาย video → ตั้งชื่อต่างกัน (ep.1, ep.2, ...) |
| **UI** | PySide6 Desktop Application |
| **Threading** | Multithreading + Thread-safe |
| **State Control** | Start / Pause / Stop / Resume |
| **Retry** | Auto-retry เมื่อ upload ล้มเหลว |
| **Crash Recovery** | บันทึก state ลง DB, เปิดมาทำงานต่อได้ |
| **Worker Count** | ผู้ใช้เลือกจำนวน workers (1-5) |
| **Random Delay** | `delay_from_ss` ถึง `delay_to_ss` สุ่มก่อนเริ่มงาน |
| **Config Persistence** | จดจำการตั้งค่าจาก UI, config files รวมที่เดียว |
| **Progress Display** | แสดงความคืบหน้าอย่างราบรื่น (real-time) |
| **Duplicate Check** | ตรวจสอบ prod_sku บน YT + ดึง YouTube URL |

---

## 📋 Progress Tracker

| Phase | Status | Progress |
|-------|--------|----------|
| Phase 1: Foundation | ⏳ Pending | 0% |
| Phase 2: Core Services | ⏳ Pending | 0% |
| Phase 3: Scanner & Parser | ⏳ Pending | 0% |
| Phase 4: Upload & Update | ⏳ Pending | 0% |
| Phase 5: Playlist Management | ⏳ Pending | 0% |
| Phase 6: PySide6 UI | ⏳ Pending | 0% |
| Phase 7: Testing & Polish | ⏳ Pending | 0% |

---

## Phase 1: Foundation (โครงสร้างพื้นฐาน)

### 1.1 Project Setup
- [ ] สร้างโครงสร้าง folder ตาม blueprint
- [ ] สร้าง `requirements.txt`
- [ ] สร้าง virtual environment
- [ ] Install dependencies

### 1.2 Configuration (Centralized)
- [ ] สร้าง `data/config/` - **ที่เก็บ config ทั้งหมด**
- [ ] สร้าง `app/config.py` - Config manager
  - [ ] `load_config()` - โหลด config จากไฟล์
  - [ ] `save_config()` - บันทึก config ลงไฟล์
  - [ ] `get()` / `set()` - อ่าน/เขียนค่า
- [ ] Config files:
  - [ ] `data/config/settings.json` - การตั้งค่าทั่วไป (worker_count, delay_range, etc.)
  - [ ] `data/config/youtube_auth.json` - YouTube credentials/tokens
  - [ ] `data/config/ui_state.json` - สถานะหน้าจอ (window size, last folder, etc.)
- [ ] Setup logging with Loguru

### 1.3 Database Setup
- [ ] สร้าง `app/models/database.py` - SQLite connection (thread-safe)
- [ ] สร้าง tables ตาม schema
- [ ] เพิ่ม `playlists` table สำหรับ cache playlist
- [ ] สร้าง migration helper

### 1.4 Pydantic Schemas
- [ ] สร้าง `app/models/schemas.py`:
  - [ ] `ProdDetailSchema`
  - [ ] `AffDetailSchema`
  - [ ] `UploadConfigSchema`
  - [ ] `VideoItemSchema` (รองรับ episode number)
  - [ ] `ProdJsonSchema` (main)

---

## Phase 2: Core Services (บริการหลัก)

### 2.1 YouTube API Service
- [ ] สร้าง `app/services/youtube_api.py`:
  - [ ] OAuth2 authentication flow
  - [ ] Token storage & refresh
  - [ ] `upload_video()` - Resumable upload
  - [ ] `update_video()` - Update metadata
  - [ ] `list_channel_videos()` - List all videos
  - [ ] `search_by_title()` - Search for duplicate
  - [ ] Thread-safe API calls

### 2.2 Playlist Service
- [ ] เพิ่มใน `youtube_api.py`:
  - [ ] `list_playlists()` - Get all playlists
  - [ ] `create_playlist()` - **สร้าง playlist ใหม่**
  - [ ] `add_to_playlist()` - Add video to playlist
  - [ ] `remove_from_playlist()` - Remove from playlist
  - [ ] `get_or_create_playlist()` - Get by name or create new

### 2.3 Template Engine
- [ ] สร้าง `app/services/template_engine.py`:
  - [ ] `generate_title()` - Format: `{{prod_code}}-{{prod_name}}-{{prod_short_descr}} ep.{{episode}}`
  - [ ] `generate_description()` - With affiliate links
  - [ ] `generate_tags()` - Combine prod_tags + custom_tags

### 2.4 Video Info Service
- [ ] สร้าง `app/utils/video_info.py`:
  - [ ] `get_video_metadata()` - FFprobe wrapper
  - [ ] `detect_video_type()` - 16:9 vs 9:16
  - [ ] `get_duration()`
  - [ ] `get_file_size()`

---

## Phase 3: Scanner & Parser (สแกนและประมวลผล)

### 3.1 Folder Scanner
- [ ] สร้าง `app/core/scanner.py`:
  - [ ] `scan_folder()` - Scan single folder
  - [ ] `scan_folders()` - Scan multiple folders
  - [ ] `find_prod_json()` - Check for prod.json
  - [ ] `find_videos()` - Find all MP4/MOV files
  - [ ] `validate_folder()` - Check completeness
  - [ ] `assign_episode_numbers()` - **Auto-assign ep.1, ep.2, ...**

### 3.2 Prod.json Parser
- [ ] สร้าง `app/core/parser.py`:
  - [ ] `parse_prod_json()` - Parse and validate
  - [ ] `validate_required_fields()` - Check required
  - [ ] `build_video_tasks()` - Create task list with episode numbers

### 3.3 Duplicate Checker (ตรวจสอบ prod_sku บน YouTube)
- [ ] สร้าง `app/core/duplicate_checker.py`:
  - [ ] `sync_channel_videos()` - **Sync ทุก video จาก channel → เก็บใน DB**
  - [ ] `check_duplicate(prod_code)` - ตรวจสอบว่า prod_sku มีบน YT หรือยัง
  - [ ] `get_youtube_url(prod_code)` - **ดึง YouTube URL ถ้ามี**
  - [ ] `get_youtube_video_id(prod_code)` - ดึง video_id สำหรับ update
  - [ ] `extract_prod_code_from_title()` - Parse prod_code จาก title ที่มีอยู่
  - [ ] `build_duplicate_cache()` - สร้าง cache จาก DB (เร็วกว่า API call)
  - [ ] **Return: `{exists: bool, youtube_id: str, youtube_url: str}`**

---

## Phase 4: Upload & Update (อัพโหลดและอัพเดท)

### 4.1 Worker Thread
- [ ] สร้าง `app/workers/upload_worker.py`:
  - [ ] `UploadWorker(QThread)` - Thread-safe worker
  - [ ] **Random delay ก่อนเริ่มงาน** (delay_from_ss ถึง delay_to_ss)
  - [ ] Signal: `progress_updated(task_id, percent)`
  - [ ] Signal: `upload_completed(task_id, youtube_id)`
  - [ ] Signal: `upload_failed(task_id, error)`
  - [ ] Thread-safe queue handling

### 4.2 Worker Manager
- [ ] สร้าง `app/workers/worker_manager.py`:
  - [ ] `WorkerManager` - Manage worker pool
  - [ ] **`set_worker_count(n)`** - ผู้ใช้กำหนดจำนวน workers
  - [ ] **`set_delay_range(from_ss, to_ss)`** - ตั้งค่า delay range
  - [ ] `add_task()` - Add to queue (thread-safe)
  - [ ] `start_workers(count)` - Start N workers
  - [ ] `stop_all()` - Stop all workers gracefully
  - [ ] `pause_all()` - **หยุดชั่วคราว**
  - [ ] `resume_all()` - **ทำต่อ**
  - [ ] `get_status()` - Get queue status

### 4.3 State Manager (Crash Recovery)
- [ ] สร้าง `app/core/state_manager.py`:
  - [ ] `save_state()` - บันทึก state ลง DB
  - [ ] `load_state()` - โหลด state จาก DB เมื่อเปิดโปรแกรม
  - [ ] `get_pending_tasks()` - ดึง tasks ที่ยังไม่เสร็จ
  - [ ] `mark_task_status()` - อัพเดท status ทันที
  - [ ] `get_resumable_session()` - เช็คว่ามี session ค้างอยู่ไหม

### 4.4 Retry Manager
- [ ] สร้าง `app/core/retry_manager.py`:
  - [ ] `should_retry()` - ตรวจสอบว่าควร retry ไหม
  - [ ] `get_retry_delay()` - Exponential backoff
  - [ ] `increment_retry_count()` - เพิ่ม retry count
  - [ ] `max_retries` - Config (default: 3)

### 4.5 Uploader
- [ ] สร้าง `app/core/uploader.py`:
  - [ ] `upload_video()` - Upload new video
  - [ ] `upload_with_progress()` - With progress callback
  - [ ] `handle_upload_error()` - Error handling + retry
  - [ ] `save_upload_result()` - Save to DB

### 4.6 Updater
- [ ] สร้าง `app/core/updater.py`:
  - [ ] `update_video_metadata()` - Update title/desc/tags
  - [ ] `update_thumbnail()` - Update thumbnail
  - [ ] `save_update_result()` - Save to DB

### 4.7 Orchestrator
- [ ] สร้าง `app/core/orchestrator.py`:
  - [ ] `start()` - **เริ่มทำงาน**
  - [ ] `pause()` - **หยุดชั่วคราว**
  - [ ] `stop()` - **หยุดทำงาน**
  - [ ] `resume()` - **ทำต่อจากที่ค้าง**
  - [ ] `process_folder()` - Process single folder
  - [ ] `process_batch()` - Process multiple folders
  - [ ] `decide_action()` - Upload vs Update
  - [ ] `resume_from_crash()` - **เริ่มต่อหลังเครื่องดับ**

---

## Phase 5: Playlist Management (จัดการ Playlist)

### 5.1 Playlist Operations
- [ ] สร้าง `app/core/playlist_manager.py`:
  - [ ] `get_or_create_playlist()` - **สร้างใหม่ถ้าไม่มี**
  - [ ] `add_video_to_playlist()` - Add after upload
  - [ ] `sync_playlists()` - Sync from YouTube
  - [ ] `get_playlist_by_name()` - Find playlist
  - [ ] `ensure_video_in_playlist()` - Add if not exists

### 5.2 Playlist in prod.json
- [ ] รองรับ 2 แบบ:
  - [ ] `playlist_id`: ใช้ playlist ที่มีอยู่
  - [ ] `playlist_name`: สร้างใหม่ถ้าไม่มี

---

## Phase 6: PySide6 UI (หน้าจอโปรแกรม)

### 6.1 Main Window
- [ ] สร้าง `app/ui/main_window.py`:
  - [ ] Layout: Sidebar + Main content
  - [ ] Menu bar
  - [ ] Status bar with progress

### 6.2 Folder Selector Panel
- [ ] สร้าง `app/ui/folder_selector.py`:
  - [ ] Drag & Drop area
  - [ ] Browse button
  - [ ] Folder list with validation status
  - [ ] Remove folder button

### 6.3 Task Queue Panel
- [ ] สร้าง `app/ui/task_queue.py`:
  - [ ] Table view: filename, status, progress, action
  - [ ] Progress bars per task
  - [ ] Color coding: pending, uploading, completed, failed

### 6.4 Settings Panel
- [ ] สร้าง `app/ui/settings_panel.py`:
  - [ ] YouTube account (OAuth)
  - [ ] Worker count (1-5)
  - [ ] Delay settings
  - [ ] Default privacy

### 6.5 Progress View (แสดงความคืบหน้าอย่างราบรื่น)
- [ ] สร้าง `app/ui/progress_view.py`:
  - [ ] **Overall progress bar** (animated, smooth)
  - [ ] **Per-task progress bars** (real-time update)
  - [ ] Statistics: uploaded, updated, failed, remaining
  - [ ] **ETA display** (เวลาที่เหลือโดยประมาณ)
  - [ ] **Speed indicator** (MB/s)
  - [ ] Logs view with auto-scroll
  - [ ] **Status icons**: ⏳ pending, 🔄 uploading, ✅ completed, ❌ failed
  - [ ] **Duplicate indicator**: 🔗 มี URL บน YT แล้ว → แสดง link

### 6.6 Thread Safety
- [ ] สร้าง `app/ui/signals.py`:
  - [ ] Custom signals for worker → UI communication
  - [ ] Thread-safe state updates
  - [ ] QMutex for shared data

---

## Phase 7: Testing & Polish (ทดสอบและปรับปรุง)

### 7.1 Unit Tests
- [ ] `tests/test_scanner.py` - Test folder scanning
- [ ] `tests/test_parser.py` - Test prod.json parsing
- [ ] `tests/test_template_engine.py` - Test title generation with episode
- [ ] `tests/test_duplicate_checker.py` - Test duplicate detection
- [ ] `tests/test_worker.py` - Test thread safety

### 7.2 Integration Tests
- [ ] `tests/test_youtube_api.py` - Test API (with mocks)
- [ ] `tests/test_orchestrator.py` - Test full flow
- [ ] `tests/test_playlist.py` - Test playlist creation

### 7.3 Manual Testing
- [ ] สร้าง sample folder structure (multi-video)
- [ ] Test upload flow (unlisted)
- [ ] Test update flow
- [ ] Test playlist creation
- [ ] Test multi-threading
- [ ] **Test Start/Pause/Stop/Resume**
- [ ] **Test Retry mechanism**
- [ ] **Test Crash Recovery** (ปิดโปรแกรมกลางทาง แล้วเปิดใหม่)

### 7.4 Documentation
- [ ] Update README.md
- [ ] Create user guide
- [ ] Document API credentials setup

---

## 🎯 Title Format (Multi-video)

```
{{prod_code}}-{{prod_name}}-{{prod_short_descr}} ep.{{episode}}
```

**ตัวอย่าง (1 folder มี 3 videos):**
```
SKU001-รองเท้าวิ่ง Nike-สวมใส่สบาย ep.1
SKU001-รองเท้าวิ่ง Nike-สวมใส่สบาย ep.2
SKU001-รองเท้าวิ่ง Nike-สวมใส่สบาย ep.3
```

---

## 🔧 Threading Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Main Thread (UI)                      │
│                      PySide6                            │
└─────────────────────┬───────────────────────────────────┘
                      │ Qt Signals (thread-safe)
                      ▼
┌─────────────────────────────────────────────────────────┐
│                  WorkerManager                           │
│              (Thread-safe Queue)                         │
└─────────────────────┬───────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
   ┌─────────┐   ┌─────────┐   ┌─────────┐
   │ Worker1 │   │ Worker2 │   │ WorkerN │
   │(QThread)│   │(QThread)│   │(QThread)│
   └─────────┘   └─────────┘   └─────────┘
        │             │             │
        └─────────────┼─────────────┘
                      ▼
              ┌──────────────┐
              │ YouTube API  │
              └──────────────┘
```

---

**พร้อมเริ่ม Phase 1: Foundation ครับ!**

