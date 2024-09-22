from Entry_Super import get_final_trend  # Import hàm phân tích xu hướng tổng thể 
from binance.client import Client
from flask import Flask
import time
import threading
import pytz
from datetime import datetime
from PNL_Check import extract_pnl_and_position_info, get_pnl_percentage, get_pnl_usdt  # Sử dụng hàm từ PNL_Check
from trade_history import save_trade_history  # Import từ trade_history.py
import socket
from playsound import playsound

# Biến toàn cục để lưu trữ client và thông tin giao dịch
client = None
last_order_status = None  # Biến lưu trữ trạng thái lệnh cuối cùng
stop_loss_price = None  # Biến toàn cục để lưu giá trị stop-loss

# Khởi tạo ứng dụng Flask
app = Flask(__name__)

# Hàm kiểm tra kết nối Internet
def is_connected():
    try:
        socket.create_connection(("8.8.8.8", 53), 2)
        return True
    except OSError:
        return False

def alert_sound():
    try:
        playsound(r"C:\Users\DELL\Desktop\GPT train\noconnect.mp3")
    except Exception as e:
        print(f"Lỗi phát âm thanh: {str(e)}")

def check_internet_and_alert():
    try:
        if not is_connected():
            print("Mất kết nối internet. Đang phát cảnh báo...")
            playsound(r"C:\Users\DELL\Desktop\GPT train\noconnect.mp3")
            time.sleep(5)
            return False
    except Exception as e:
        print(f"Lỗi khi kiểm tra kết nối: {str(e)}")
        playsound(r"C:\Users\DELL\Desktop\GPT train\noconnect.mp3")
        time.sleep(5)
        return False
    return True

@app.route('/')
def home():
    global last_order_status
    current_balance = get_account_balance(client)
    extract_pnl_and_position_info(client, 'BTCUSDT')
    pnl_percentage = get_pnl_percentage()
    position_info = client.futures_position_information(symbol='BTCUSDT')
    entry_price = float(position_info[0]['entryPrice'])
    mark_price = float(position_info[0]['markPrice'])
    pnl_display = f"{pnl_percentage:.2f}%" if pnl_percentage is not None else "PNL chưa có giá trị"
    tz = pytz.timezone('Asia/Ho_Chi_Minh')
    current_time = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    
    return f'''
    <html>
    <head>
        <title>Binance Bot Status</title>
        <meta http-equiv="refresh" content="20">
    </head>
    <body>
        <h1>Namtrader BTCUSDT.P Status</h1>
        <p>Giá trị tài khoản hiện tại: {current_balance:.2f} USDT</p>
        <p>Entry Price: {entry_price:.2f} USDT</p>
        <p>Mark Price: {mark_price:.2f} USDT</p>
        <p>Lợi nhuận hiện tại (PNL%): {pnl_display}</p>
        <p>Trạng thái lệnh cuối cùng: {last_order_status}</p>
        <p>Thời gian hiện tại (UTC+7): {current_time}</p>
        <footer>
            <p>&copy; 2024 NamTrading Bot</p>
        </footer>
    </body>
    </html>
    '''

# Hàm lấy giá trị tài khoản Futures
def get_account_balance(client):
    account_info = client.futures_account()
    usdt_balance = float(account_info['totalWalletBalance'])
    return usdt_balance

# Hàm cài đặt đòn bẩy cho giao dịch Futures
def set_leverage(client, symbol, leverage):
    try:
        response = client.futures_change_leverage(symbol=symbol, leverage=leverage)
        print(f"Đã cài đặt đòn bẩy {response['leverage']}x cho {symbol}.")
    except Exception as e:
        print(f"Lỗi khi cài đặt đòn bẩy: {str(e)}")

# Hàm tính ATR với khung thời gian 4 giờ (4h)
#def calculate_atr(client, symbol, length=14):
#    klines = client.futures_klines(symbol=symbol, interval='4h', limit=length + 1)  # Chuyển sang khung thời gian 4h
#    trs = []
#    for i in range(1, len(klines)):
#        high = float(klines[i][2])
#        low = float(klines[i][3])
#        close_prev = float(klines[i - 1][4])
#        tr = max(high - low, abs(high - close_prev), abs(low - close_prev))
#        trs.append(tr)
#    atr = sum(trs) / len(trs)
#    return atr
# Hàm tính ATR với khung thời gian 1 giờ (1h)
def calculate_atr(client, symbol, length=14):
    klines = client.futures_klines(symbol=symbol, interval='1h', limit=length + 1)  # Chuyển sang khung thời gian 1h
    trs = []
    for i in range(1, len(klines)):
        high = float(klines[i][2])
        low = float(klines[i][3])
        close_prev = float(klines[i - 1][4])
        tr = max(high - low, abs(high - close_prev), abs(low - close_prev))
        trs.append(tr)
    atr = sum(trs) / len(trs)
    return atr

# Hàm kiểm tra điều kiện StopLoss và TakeProfit
def check_sl_tp(client, symbol):
    global last_order_status, stop_loss_price
    extract_pnl_and_position_info(client, symbol)
    pnl_percentage = get_pnl_percentage()
    pnl_usdt = get_pnl_usdt()
    position_info = client.futures_position_information(symbol=symbol)
    qty = float(position_info[0]['positionAmt'])
    mark_price = float(position_info[0]['markPrice'])

    if qty != 0 and stop_loss_price is not None:
        if qty > 0 and mark_price <= stop_loss_price:
            print(f"Điều kiện StopLoss đạt được cho lệnh Buy. Đóng lệnh tại giá: {stop_loss_price:.2f}.")
            close_position(client, pnl_percentage, pnl_usdt)
            stop_loss_price = None
            return "stop_loss"
        elif qty < 0 and mark_price >= stop_loss_price:
            print(f"Điều kiện StopLoss đạt được cho lệnh Sell. Đóng lệnh tại giá: {stop_loss_price:.2f}.")
            close_position(client, pnl_percentage, pnl_usdt)
            stop_loss_price = None
            return "stop_loss"

    if pnl_percentage is not None and pnl_percentage >= 180:
        print(f"Điều kiện TakeProfit đạt được: TP 180%. Đóng lệnh.")
        close_position(client, pnl_percentage, pnl_usdt)
        stop_loss_price = None
        return "take_profit"
    
    return None

# Hàm kiểm tra nếu có lệnh nào đang mở
def check_open_position(client, symbol):
    position_info = client.futures_position_information(symbol=symbol)
    qty = float(position_info[0]['positionAmt'])
    return qty != 0

# Hàm thực hiện lệnh mua hoặc bán
def place_order(client, order_type):
    global last_order_status, stop_loss_price
    symbol = 'BTCUSDT'
    usdt_balance = get_account_balance(client)
    atr = calculate_atr(client, symbol)
    klines = client.futures_klines(symbol=symbol, interval='1h', limit=1)  # Chuyển sang khung thời gian 1h
    high = float(klines[0][2])
    low = float(klines[0][3])
    mark_price = float(klines[0][4])

    percent_change = None
    if order_type == "buy":
        stop_loss_price = low - atr
        percent_change = ((stop_loss_price - mark_price) / mark_price) * 100
    elif order_type == "sell":
        stop_loss_price = high + atr
        percent_change = ((mark_price - stop_loss_price) / mark_price) * 100

    if percent_change is not None and percent_change != 0:
        leverage = 100 / abs(percent_change)
        leverage = max(1, min(round(leverage), 125))
        if leverage > 125:
            leverage = 125
        set_leverage(client, symbol, leverage)
    
    trading_balance = 4 * leverage #Nhập R:R ở đây (4$)
    ticker = client.get_symbol_ticker(symbol=symbol)
    btc_price = float(ticker['price'])
    quantity = round(trading_balance / btc_price, 3)

    if quantity <= 0:
        print("Số lượng giao dịch không hợp lệ. Hủy giao dịch.")
        return

    if order_type == "buy":
        client.futures_create_order(symbol=symbol, side='BUY', type='MARKET', quantity=quantity)
        last_order_status = f"Đã mua {quantity} BTC. Stop-loss đặt tại: {stop_loss_price:.2f} USDT."
        print(f"Giá trị stop-loss cho lệnh Buy: {stop_loss_price:.2f} USDT")
    elif order_type == "sell":
        client.futures_create_order(symbol=symbol, side='SELL', type='MARKET', quantity=quantity)
        last_order_status = f"Đã bán {quantity} BTC. Stop-loss đặt tại: {stop_loss_price:.2f} USDT."
        print(f"Giá trị stop-loss cho lệnh Sell: {stop_loss_price:.2f} USDT")

# Hàm đóng lệnh
def close_position(client, pnl_percentage, pnl_usdt):
    global last_order_status
    symbol = 'BTCUSDT'
    position_info = client.futures_position_information(symbol=symbol)
    qty = float(position_info[0]['positionAmt'])
    entry_price = float(position_info[0]['entryPrice'])
    entry_type = "Long" if qty > 0 else "Short" if qty < 0 else "Không có vị thế"

    if qty > 0:
        client.futures_create_order(symbol=symbol, side='SELL', type='MARKET', quantity=qty)
        last_order_status = f"Đã đóng lệnh long {qty} BTC."
    elif qty < 0:
        client.futures_create_order(symbol=symbol, side='BUY', type='MARKET', quantity=abs(qty))
        last_order_status = f"Đã đóng lệnh short {abs(qty)} BTC."
    else:
        last_order_status = "Không có vị thế mở."

    pnl_percentage_display = f"+{pnl_percentage:.2f}%" if pnl_percentage > 0 else f"-{abs(pnl_percentage):.2f}%"
    pnl_usdt_display = f"+{pnl_usdt:.2f} USDT" if pnl_usdt > 0 else f"-{abs(pnl_usdt):.2f} USDT"
    print(f"Đóng lệnh - PNL hiện tại (USDT): {pnl_usdt_display}, PNL hiện tại (%): {pnl_percentage_display}, Entry Price: {entry_price:.2f} USDT, Entry Type: {entry_type}")
    save_trade_history(pnl_percentage, pnl_usdt, entry_price, entry_type)

# Hàm bot giao dịch chạy mỗi 10 giây
def trading_bot():
    global client
    api_key = 'ac70a8029ffb37a35a68eda35460d930306c61a7967d6396305ba0cfe15954d6'
    api_secret = '3043815a600c91f6aea4545b5949a9b1a4e2c97e2244fa8fdc62dfac1fa717d9'
    client = Client(api_key, api_secret, tld='com', testnet=True)
    symbol = 'BTCUSDT'

    while True:
        try:
            if not check_internet_and_alert():
                continue

            result = check_sl_tp(client, symbol)
            if result == "stop_loss" or result == "take_profit":
                break

            # Gọi hàm get_final_trend() và truyền đối tượng client
            final_trend = get_final_trend(client)
            print(f"Kết quả xu hướng từ hàm get_final_trend(): {final_trend}")

            # Lấy thông tin vị thế để kiểm tra và sử dụng trong điều kiện xu hướng
            position_info = client.futures_position_information(symbol=symbol)
            qty = float(position_info[0]['positionAmt'])

            if check_open_position(client, symbol):
                if final_trend == "Xu hướng không rõ ràng":
                    print("Xu hướng không rõ ràng")
                    time.sleep(10)
                    continue

                # Đóng lệnh nếu xu hướng thay đổi
                if final_trend == "Xu hướng tăng" and qty < 0:  # Đóng lệnh sell nếu có tín hiệu mua
                    close_position(client, get_pnl_percentage(), get_pnl_usdt())
                elif final_trend == "Xu hướng giảm" and qty > 0:  # Đóng lệnh buy nếu có tín hiệu bán
                    close_position(client, get_pnl_percentage(), get_pnl_usdt())

                print("Hiện đã có lệnh mở. Không thực hiện thêm lệnh mới.")
                time.sleep(10)
                continue

            if final_trend == "Xu hướng tăng":
                print("Xu hướng tăng. Thực hiện lệnh mua.")
                place_order(client, "buy")
            elif final_trend == "Xu hướng giảm":
                print("Xu hướng giảm. Thực hiện lệnh bán.")
                place_order(client, "sell")

            time.sleep(10)

        except Exception as e:
            print(f"Lỗi khi gọi API hoặc xử lý giao dịch: {str(e)}")
            playsound(r"C:\Users\DELL\Desktop\GPT train\noconnect.mp3")
            time.sleep(5)




if __name__ == "__main__":
    trading_thread = threading.Thread(target=trading_bot)
    trading_thread.start()
    app.run(host='0.0.0.0', port=8080)
