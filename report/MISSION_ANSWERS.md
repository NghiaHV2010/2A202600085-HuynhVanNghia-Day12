# Day 12 Lab - Cau Tra Loi Mission

Sinh vien: Huynh Van Nghia  
MSSV: 2A202600085  
Ngay: 2026-04-17

## Phan 1: Localhost vs Production

### Bai 1.1: Cac anti-pattern da tim thay
1. Secret de hardcode trong code hoac config khong an toan.
2. Thieu readiness check nen cloud kho dieu phoi traffic an toan.
3. Luu state trong memory cua process nen scale ngang de mat context.
4. Khong co lop bao ve auth/rate/cost de chong lam dung API.
5. Shutdown khong gracefull co the lam rot request khi deploy.

### Bai 1.2: Ket qua chay ban basic
- Ban basic chay duoc de hoc concept.
- Tuy nhien chua dat muc production vi thieu cac co che reliability va security.

### Bai 1.3: Bang so sanh
| Tinh nang | Develop | Production | Vi sao quan trong |
|---|---|---|---|
| Cau hinh | Gia tri mac dinh don gian | Theo bien moi truong | Cung mot codebase chay nhieu moi truong |
| Secret | De ro ri | Quan ly bang env var/platform secret | An toan va de rotate |
| Kiem tra song | Thuong chi co liveness | Co health + readiness | Tranh route traffic vao pod chua san sang |
| Logging | print/thieu cau truc | Log co cau truc | De monitor va truy vet loi |
| State | Nho trong process | Redis stateless | Ho tro scale ngang |
| Shutdown | Dot ngot | Graceful shutdown | Giam loi khi restart/deploy |

## Phan 2: Docker

### Bai 2.1: Tra loi ve Dockerfile
1. Base image: python:3.11-slim (multi-stage cho production).
2. Working directory: /app.
3. Copy requirements truoc de tan dung Docker layer cache.
4. Multi-stage de giam kich thuoc image va giam attack surface.

### Bai 2.2: Ghi chu build va run
- Lenh chay local: docker compose up -d --build
- Dockerfile production co non-root user va HEALTHCHECK.

### Bai 2.3: So sanh kich thuoc image
- Develop: ~800 MB (theo baseline bai lab; local build lai bi Docker Hub rate-limit 429).
- Production: 166 MB (do duoc tu image 06-lab-complete-agent:latest).
- Chenh lech uoc tinh: ~79.25% nho hon.

## Phan 3: Cloud Deployment

### Bai 3.1: Trang thai deploy
- Nen tang: Render
- URL: https://twoa202600085-huynhvannghia-day12.onrender.com
- Trang thai luc cap nhat:
  - GET /health -> 200
  - GET /ready -> 200
  - health.checks.redis -> true
  - health.checks.llm -> openai

### Bai 3.2: Ghi chu cau hinh Render
- REDIS_INTERNAL_URL phai la Internal Redis URL (redis:// hoac rediss://).
- OPENAI_API_KEY bat buoc co neu chay production voi LLM that.
- AGENT_API_KEY phai la key rieng, khong de gia tri default.

## Phan 4: API Security

### Bai 4.1-4.3: Ket qua test

#### Test tren Render
- GET /health: 200
- GET /ready: 200
- POST /ask khong co X-API-Key: 401 (PASS)

#### Test local (06-lab-complete)
- /ask khong key: 401 (PASS)
- /ask co key: 200 (PASS)
- Rate limit lan chay gan nhat (25 request): {"200":20,"429":5} (PASS)
- /ready khi stop redis: 503 (PASS)
- /ready sau khi start redis: 200 (PASS)

### Bai 4.4: Cost guard
- Trien khai tai app/cost_guard.py.
- Gioi han ngan sach theo thang qua MONTHLY_BUDGET_USD.
- Tinh chi phi theo token input/output.
- Vuot budget se chan request va tra loi phu hop.

## Phan 5: Scaling & Reliability

### Bai 5.1: Health va readiness
- /health tra ve trang thai service, redis, llm, uptime.
- /ready chi tra 200 khi dependency da san sang.

### Bai 5.2: Graceful shutdown
- Ung dung co xu ly signal de danh dau not-ready va shutdown dung cach.

### Bai 5.3: Stateless
- Lich su hoi thoai theo user_id luu tren Redis.
- Process co the scale ngang ma van giu duoc context.

### Bai 5.4: Test context continuity
- Buoc 1: user_id co dinh, gui "My name is Alice".
- Buoc 2: cung user_id, gui "What did I just say?".
- Ket qua: Tra ve dung noi dung truoc do.

### Bai 5.5: Ket luan reliability
- He thong da co day du auth, rate, budget, health, readiness, stateless.
- Luong test local va cloud deu dat voi cac endpoint chinh.

## Tong ket
- Source code dat huong production va da verify duong chay chinh.
- Deployment Render truy cap duoc cong khai.
- Viec con lai truoc khi nop: them screenshot minh chung vao report/images.
