from Entry import get_final_trend  # Import hàm phân tích xu hướng tổng thể
from binance.client import Client
from flask import Flask
import time
import threading
import pytz
from datetime import datetime
# Khởi tạo ứng dụng Flask
app = Flask(__name__)

# Biến toàn cục để lưu trữ client và thông tin giao dịch
client = None
last_order_status = None  # Biến lưu trữ trạng thái lệnh cuối cùng


@app.route('/')
def home():
    global last_order_status
    current_balance = get_account_balance(client)
    pnl = get_position_profit(client, 'BTCUSDT')  # Lấy PNL hiện tại

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
        <p>Giá trị tài khoản hiện tại: {current_balance} USDT</p>
        <p>Lợi nhuận hiện tại (PNL): {pnl} USDT</p>
        <p>Trạng thái lệnh cuối cùng: {last_order_status}</p>
        <p>Thời gian hiện tại (UTC+7): {current_time}</p>  <!-- Hiển thị thời gian UTC+7 -->
        <footer>
            <p>&copy; 2024 Binance Trading Bot</p>
        </footer>
    </body>
    </html>
    '''



# Hàm lấy giá trị tài khoản Futures
def get_account_balance(client):
    account_info = client.futures_account()
    usdt_balance = float(account_info['totalWalletBalance']
                         )  # Số dư USDT trong tài khoản Futures
    return usdt_balance


# Hàm lấy lợi nhuận từ vị thế hiện tại
def get_position_profit(client, symbol):
    position_info = client.futures_position_information(symbol=symbol)

    # Kiểm tra nếu không có vị thế mở (positionAmt == 0)
    if float(position_info[0]['positionAmt']) == 0:
        print("Không có vị thế mở, không có lợi nhuận.")
        return 0.0  # Không có lợi nhuận nếu không có vị thế mở

    pnl = float(position_info[0]['unRealizedProfit']
                )  # Lợi nhuận chưa ghi nhận (P&L) từ vị thế hiện tại
    return pnl


# Hàm lấy giá trị vào lệnh ban đầu
def get_entry_price(client, symbol):
    position_info = client.futures_position_information(symbol=symbol)

    # Kiểm tra nếu không có vị thế mở
    if float(position_info[0]['positionAmt']) == 0:
        return 0.0

    entry_price = float(position_info[0]['entryPrice'])  # Giá vào lệnh ban đầu
    return entry_price


# Hàm lấy khối lượng vào lệnh
def get_position_quantity(client, symbol):
    position_info = client.futures_position_information(symbol=symbol)
    qty = float(
        position_info[0]
        ['positionAmt'])  # Số lượng vị thế hiện tại (khối lượng vào lệnh)
    return qty


# Hàm đóng lệnh
def close_position(client):
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


# Hàm cài đặt đòn bẩy cho giao dịch Futures
def set_leverage(client, symbol, leverage):
    try:
        response = client.futures_change_leverage(symbol=symbol,
                                                  leverage=leverage)
        print(f"Đã cài đặt đòn bẩy {leverage}x cho {symbol}.")
    except Exception as e:
        print(f"Lỗi khi cài đặt đòn bẩy: {str(e)}")


# Hàm kiểm tra nếu có lệnh nào đang mở
def check_open_position(client, symbol):
    position_info = client.futures_position_information(symbol=symbol)
    qty = float(position_info[0]['positionAmt'])

    if qty != 0:
        return True  # Có lệnh mở
    return False  # Không có lệnh mở


# Hàm kiểm tra điều kiện TakeProfit và StopLoss
def check_sl_tp(client, symbol):
    # Kiểm tra nếu không có vị thế mở
    quantity = get_position_quantity(client, symbol)
    if quantity == 0:
        print("Không có vị thế mở, bỏ qua kiểm tra SL/TP.")
        return None  # Bỏ qua nếu không có vị thế mở

    # Nếu có vị thế, tiếp tục kiểm tra lợi nhuận và giá trị vị thế
    profit = get_position_profit(client, symbol)
    entry_price = get_entry_price(client, symbol)
    position_value = entry_price * abs(quantity)

    print(f"Lợi nhuận hiện tại: {profit} USDT")
    print(f"Giá trị vị thế ban đầu: {position_value} USDT")
    # Điều kiện StopLoss: Nếu lỗ 50% so với giá trị đầu tư ban đầu
    if profit <= -0.5 * position_value:
        print("Điều kiện StopLoss đạt được: Lợi nhuận giảm 50%. Đóng lệnh.")
        close_position(client)
        return "stop_loss"

    # Điều kiện TakeProfit: Lợi nhuận từ vị thế >= 100% của khối lượng vào lệnh
    elif profit >= position_value:
        print("Điều kiện TakeProfit đạt được: Lợi nhuận đạt 100%. Đóng lệnh.")
        close_position(client)
        return "take_profit"

    return None


# Hàm thực hiện lệnh mua hoặc bán trên Binance
def place_order(client, order_type):
    global last_order_status
    symbol = 'BTCUSDT'
    usdt_balance = get_account_balance(client)
    leverage = 125

    trading_balance = usdt_balance * leverage * 0.75  # Giảm tỷ lệ xuống để đảm bảo đủ ký quỹ

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
                print("Xu hướng không rõ ràng. Đóng tất cả các lệnh.")
                close_position(client)
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
    # app.run(host='0.0.0.0', port=8080)
      app.run()
