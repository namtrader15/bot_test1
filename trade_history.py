import os
from datetime import datetime
import pytz  # Import pytz để xử lý múi giờ

# Hàm để ghi lịch sử giao dịch vào file
def save_trade_history(pnl_percentage, pnl_usdt, file_name="trade_history.txt"):
    # Kiểm tra nếu file đã tồn tại hay chưa, nếu không thì tạo mới
    file_exists = os.path.isfile(file_name)
    
    # Mở file trong chế độ append (thêm vào cuối file)
    with open(file_name, "a") as file:
        # Nếu file chưa có, ghi tiêu đề cột
        if not file_exists:
            file.write(f"Số thứ tự | Date/Time (UTC+7) | PNL (%) | PNL (USDT)\n")
        
        # Lấy thời gian hiện tại ở múi giờ UTC+7
        tz = pytz.timezone('Asia/Ho_Chi_Minh')
        current_time = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
        
        # Đếm số thứ tự (dòng) hiện có trong file
        with open(file_name, "r") as count_file:
            lines = count_file.readlines()
            order_number = len(lines) - 1  # Trừ 1 vì dòng đầu là tiêu đề

        # Xử lý dấu cho PNL% và PNL (USDT)
        if pnl_percentage >= 0:
            pnl_percentage_display = f"+{pnl_percentage:.2f}%"  # Thêm dấu + nếu dương
        else:
            pnl_percentage_display = f"-{abs(pnl_percentage):.2f}%"  # Thêm dấu - nếu âm

        if pnl_usdt >= 0:
            pnl_usdt_display = f"+{pnl_usdt:.2f} USDT"  # Thêm dấu + nếu dương
        else:
            pnl_usdt_display = f"-{abs(pnl_usdt):.2f} USDT"  # Thêm dấu - nếu âm

        # Ghi thông tin giao dịch mới vào file
        file.write(f"{order_number + 1} | {current_time} | {pnl_percentage_display} | {pnl_usdt_display}\n")
    
    print(f"Lịch sử giao dịch đã được lưu vào {file_name}")
