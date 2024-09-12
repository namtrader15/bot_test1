from Entry import get_final_trend  # Import hàm phân tích xu hướng tổng thể
from binance.client import Client
from flask import Flask
import time
import threading
import pytz
from datetime import datetime
from PNL_Check import extract_pnl_and_position_info, get_pnl_percentage  # Sử dụng hàm từ PNL_Check
from trade_history import save_trade_history  # Import từ trade_history.py

# Khởi tạo ứng dụng Flask
app = Flask(__name__)

# Biến toàn cục để lưu trữ client và thông tin giao dịch
client = None
last_order_status = None  # Biến lưu trữ trạng thái lệnh cuối cùng

@app.route('/')
def home():
    global last_order_status
    current_balance = get_account_balance(client)

    # Gọi hàm để cập nhật các thông số từ Binance API
    extract_pnl_and_position_info(client, 'BTCUSDT')

    # Lấy PNL% từ PNL_Check
    pnl_percentage = get_pnl_percentage()

    # Lấy thông tin về Entry Price và Mark Price
    position_info = client.futures_position_information(symbol='BTCUSDT')
    entry_price = float(position_info[0]['entryPrice'])
    mark_price = float(position_info[0]['markPrice'])

    # Hiển thị PNL% hoặc thông báo nếu không có giá trị PNL%
    pnl_display = f"{pnl_percentage:.2f}%" if pnl_percentage is not None else "PNL chưa có giá trị"

    # Lấy múi giờ UTC+7 (giờ Việt Nam)
    tz = pytz.timezone('Asia/Ho_Chi_Minh')
    current_time = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")  # Lấy thời gian hiện tại với múi giờ UTC+7

    return f'''
    <html>
    <head>
        <title>Binance Bot Status</title>
        <meta http-equiv="refresh" content="20">  <!-- Tự động reload trang mỗi 20 giây -->
    </head>
    <body>
        <h1>Namtrader BTCUSDT.P Status</h1>
        <p>Giá trị tài khoản hiện tại: {current_balance:.2f} USDT</p>
        <p>Entry Price: {entry_price:.2f} USDT</p>
        <p>Mark Price: {mark_price:.2f} USDT</p>
        <p>Lợi nhuận hiện tại (PNL%): {pnl_display}</p>
        <p>Trạng thái lệnh cuối cùng: {last_order_status}</p>
        <p>Thời gian hiện tại (UTC+7): {current_time}</p>  <!-- Hiển thị thời gian UTC+7 -->
        <footer>
            <p>&copy; 2024 NamTrading Bot</p>
        </footer>
    </body>
    </html>
    '''
    

# Hàm lấy giá trị tài khoản Futures
def get_account_balance(client):
    account_info = client.futures_account()
    usdt_balance = float(account_info['totalWalletBalance'])  # Số dư USDT trong tài khoản Futures
    return usdt_balance
# Hàm cài đặt đòn bẩy cho giao dịch Futures
def set_leverage(client, symbol, leverage):
    try:
        response = client.futures_change_leverage(symbol=symbol, leverage=leverage)
        print(f"Đã cài đặt đòn bẩy {response['leverage']}x cho {symbol}.")
    except Exception as e:
        print(f"Lỗi khi cài đặt đòn bẩy: {str(e)}")

# Hàm tính PNL (USDT)
def get_pnl_usdt(client, symbol):
    # Lấy thông tin vị thế hiện tại
    position_info = client.futures_position_information(symbol=symbol)
    
    # Lấy giá trị Entry Price và Mark Price
    entry_price = float(position_info[0]['entryPrice'])
    mark_price = float(position_info[0]['markPrice'])
    
    # Lấy khối lượng vị thế
    position_amt = float(position_info[0]['positionAmt'])
    
    # Tính PNL (USDT): (Mark Price - Entry Price) * Position Amount
    pnl_usdt = (mark_price - entry_price) * position_amt
    
    return pnl_usdt

# Hàm kiểm tra điều kiện StopLoss và TakeProfit dựa trên PNL%
def check_sl_tp(client, symbol):
    # Gọi hàm để cập nhật giá trị PNL%
    extract_pnl_and_position_info(client, symbol)

    # Lấy giá trị pnl_percentage và pnl_usdt từ các hàm
    pnl_percentage = get_pnl_percentage()
    pnl_usdt = get_pnl_usdt(client, symbol)  # Gọi đúng hàm get_pnl_usdt

    # Kiểm tra nếu PNL% có giá trị
    if pnl_percentage is not None:
        print(f"Lợi nhuận hiện tại (PNL%): {pnl_percentage:.2f}%")
    else:
        print("PNL% chưa có giá trị.")
        return None

    # Điều kiện StopLoss: Nếu PNL% <= -50
    if pnl_percentage <= -50:
        print(f"Điều kiện StopLoss đạt được: Lỗ hơn 50%. Đóng lệnh.")
        close_position(client, pnl_percentage, pnl_usdt)
        return "stop_loss"

    # Điều kiện TakeProfit: Nếu PNL% >= 100
    if pnl_percentage >= 100:
        print(f"Điều kiện TakeProfit đạt được: Lãi hơn 100%. Đóng lệnh.")
        close_position(client, pnl_percentage, pnl_usdt)
        return "take_profit"

    return None


# Hàm đóng lệnh
def close_position(client, pnl_percentage, pnl_usdt):
    global last_order_status
    symbol = 'BTCUSDT'

    # Lấy thông tin vị thế hiện tại
    position_info = client.futures_position_information(symbol=symbol)
    qty = float(position_info[0]['positionAmt'])  # Số lượng vị thế hiện tại

    if qty > 0:
        client.futures_create_order(symbol=symbol,
                                    side='SELL',
                                    type='MARKET',
                                    quantity=qty)
        last_order_status = f"Đã đóng lệnh long {qty} BTC."
    elif qty < 0:
        client.futures_create_order(symbol=symbol,
                                    side='BUY',
                                    type='MARKET',
                                    quantity=abs(qty))
        last_order_status = f"Đã đóng lệnh short {abs(qty)} BTC."
    else:
        last_order_status = "Không có vị thế mở."

    # In ra thông tin lệnh đóng với đúng dấu
    pnl_percentage_display = f"+{pnl_percentage:.2f}%" if pnl_percentage > 0 else f"-{abs(pnl_percentage):.2f}%"
    pnl_usdt_display = f"+{pnl_usdt:.2f} USDT" if pnl_usdt > 0 else f"-{abs(pnl_usdt):.2f} USDT"
    
    print(f"Đóng lệnh - PNL hiện tại (USDT): {pnl_usdt_display}, PNL hiện tại (%): {pnl_percentage_display}")

    # Lưu lịch sử giao dịch
    save_trade_history(pnl_percentage, pnl_usdt)


# Hàm kiểm tra nếu có lệnh nào đang mở
def check_open_position(client, symbol):
    position_info = client.futures_position_information(symbol=symbol)
    qty = float(position_info[0]['positionAmt'])

    if qty != 0:
        return True  # Có lệnh mở
    return False  # Không có lệnh mở

# Hàm thực hiện lệnh mua hoặc bán trên Binance
def place_order(client, order_type):
    global last_order_status
    symbol = 'BTCUSDT'
    usdt_balance = get_account_balance(client)
    leverage = 125

    trading_balance = usdt_balance * leverage * 0.005  # Giảm tỷ lệ xuống để đảm bảo đủ ký quỹ

    ticker = client.get_symbol_ticker(symbol=symbol)
    btc_price = float(ticker['price'])
    quantity = round(trading_balance / btc_price, 3)

    if quantity <= 0:
        return  # Không thực hiện giao dịch nếu quantity nhỏ hơn hoặc bằng 0

    if order_type == "buy":
        client.futures_create_order(symbol=symbol,
                                    side='BUY',
                                    type='MARKET',
                                    quantity=quantity)
        last_order_status = f"Đã mua {quantity} BTC."
    elif order_type == "sell":
        client.futures_create_order(symbol=symbol,
                                    side='SELL',
                                    type='MARKET',
                                    quantity=quantity)
        last_order_status = f"Đã bán {quantity} BTC."

# Hàm bot giao dịch chạy mỗi 10 giây
def trading_bot():
    global client
    api_key = 'ac70a8029ffb37a35a68eda35460d930306c61a7967d6396305ba0cfe15954d6'
    api_secret = '3043815a600c91f6aea4545b5949a9b1a4e2c97e2244fa8fdc62dfac1fa717d9'
    client = Client(api_key, api_secret, tld='com', testnet=True)

    symbol = 'BTCUSDT'
    leverage = 125
    set_leverage(client, symbol, leverage)

    while True:
        # Kiểm tra điều kiện StopLoss và TakeProfit
        result = check_sl_tp(client, symbol)
        if result == "stop_loss" or result == "take_profit":
            continue

        # Lấy kết quả xu hướng từ chương trình phân tích xu hướng
        final_trend = get_final_trend()

        # Kiểm tra nếu đã có lệnh mở
        if check_open_position(client, symbol):
            if final_trend == "Xu hướng không rõ ràng" or final_trend == "Xu hướng chưa rõ ràng!":
                print("Xu hướng không rõ ràng")
                time.sleep(10)  # Đợi 10 giây trước khi kiểm tra lại
                continue

            print("Hiện đã có lệnh mở. Không thực hiện thêm lệnh mới.")
            time.sleep(10)  # Đợi 10 giây trước khi kiểm tra lại
            continue

        # Kiểm tra điều kiện giao dịch dựa trên kết quả xu hướng tổng thể
        if final_trend == "Xu Hướng Tăng!":
            print("Xu hướng tăng. Thực hiện lệnh mua.")
            place_order(client, "buy")

        elif final_trend == "Xu Hướng Giảm!":
            print("Xu hướng giảm. Thực hiện lệnh bán.")
            place_order(client, "sell")

        time.sleep(10)  # Chạy lại sau 10 giây

# Khởi chạy Flask server và bot trong một thread riêng
if __name__ == "__main__":
    # Tạo thread để chạy bot giao dịch
    trading_thread = threading.Thread(target=trading_bot)
    trading_thread.start()

    # Chạy Flask server song song với bot giao dịch
    app.run(host='0.0.0.0', port=8080)
