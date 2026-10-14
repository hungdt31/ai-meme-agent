from slowapi import Limiter

from app.security import client_ip

# Giới hạn theo IP, lưu trong bộ nhớ từng instance (lượt tạo meme đếm riêng trong database: app/quota.py)
limiter = Limiter(key_func=client_ip)
