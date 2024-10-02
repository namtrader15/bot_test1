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
from atr_check import atr_stop_loss_finder  # Gọi hàm từ file atr_calculator.py
from High_Low import get_results
import os
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
    position_info = client.futures_position_information(symbol='ETHUSDT')
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

# Hàm kiểm tra nếu có lệnh nào đang mở
def check_open_position(client, symbol):
    position_info = client.futures_position_information(symbol=symbol)
    qty = float(position_info[0]['positionAmt'])
    return qty != 0
# tải lại SL
def load_stoploss():
    global stop_loss_price
    # Đọc giá trị stoploss cho lệnh Buy nếu file tồn tại
    if os.path.exists("stoploss_buy.txt"):
        with open("stoploss_buy.txt", "r") as file:
            stop_loss_price = float(file.read())
        print(f"Giá trị stop-loss cho lệnh Buy đã được khởi động lại: {stop_loss_price} USDT")
    
    # Đọc giá trị stoploss cho lệnh Sell nếu file tồn tại
    if os.path.exists("stoploss_sell.txt"):
        with open("stoploss_sell.txt", "r") as file:
            stop_loss_price = float(file.read())
        print(f"Giá trị stop-loss cho lệnh Sell đã được khởi động lại: {stop_loss_price} USDT")

def place_order(client, order_type):
    global last_order_status, stop_loss_price
    symbol = 'ETHUSDT'

    # Gọi hàm get_results để lấy các giá trị HH, LL, HL, LH
    final_hh, final_ll, final_hl, final_lh, updated_hh, updated_ll = get_results()

    # Gọi hàm atr_stop_loss_finder để lấy các giá trị ATR
    atr_short_stop_loss, atr_long_stop_loss = atr_stop_loss_finder(client, symbol)
    
    usdt_balance = get_account_balance(client)
    klines = client.futures_klines(symbol=symbol, interval='15m', limit=1)  # Lấy nến hiện tại
    mark_price = float(klines[0][4])  # Giá mark price hiện tại

    # Tính phần trăm chênh lệch so với HL, LL hoặc HH, LH
    percent_change_hl = abs((mark_price - final_hl[1]) / mark_price) * 100 if final_hl else None
    percent_change_ll = abs((mark_price - final_ll[1]) / mark_price) * 100 if final_ll else None
    percent_change_hh = abs((mark_price - final_hh[1]) / mark_price) * 100 if final_hh else None
    percent_change_lh = abs((mark_price - final_lh[1]) / mark_price) * 100 if final_lh else None

    # Kiểm tra điều kiện mua (buy) và bán (sell)
    if order_type == "buy":
        if (percent_change_hl is not None and percent_change_hl <= 0.11) or \
           (percent_change_ll is not None and percent_change_ll <= 0.11):
            # Điều kiện mua khi giá hiện tại không chênh lệch quá 0.11% so với HL hoặc LL
            percent_change = ((atr_long_stop_loss - mark_price) / mark_price) * 100
            stop_loss_price = atr_long_stop_loss  # Đặt Stop Loss cho lệnh Buy
            # Ghi giá trị stoploss vào file
            with open("stoploss_buy.txt", "w") as file:
                file.write(str(stop_loss_price))
        else:
            # In ra lý do không phù hợp để mua
            if percent_change_hl is None and percent_change_ll is None:
                print("Không có giá trị Higher Low (HL) hoặc Lower Low (LL) để so sánh.")
            else:
                print("Giá hiện tại chênh lệch quá 0.11% so với HL hoặc LL.")
            return  # Không thực hiện lệnh nếu không thỏa mãn điều kiện

    elif order_type == "sell":
        if (percent_change_hh is not None and percent_change_hh <= 0.11) or \
           (percent_change_lh is not None and percent_change_lh <= 0.11):
            # Điều kiện bán khi giá hiện tại không chênh lệch quá 0.11% so với HH hoặc LH
            percent_change = ((mark_price - atr_short_stop_loss) / mark_price) * 100
            stop_loss_price = atr_short_stop_loss  # Đặt Stop Loss cho lệnh Sell
            # Ghi giá trị stoploss vào file
            with open("stoploss_sell.txt", "w") as file:
                file.write(str(stop_loss_price))
        else:
            # In ra lý do không phù hợp để bán
            if percent_change_hh is None and percent_change_lh is None:
                print("Không có giá trị Higher High (HH) hoặc Lower High (LH) để so sánh.")
            else:
                print("Giá hiện tại chênh lệch quá 0.11% so với HH hoặc LH.")
            return  # Không thực hiện lệnh nếu không thỏa mãn điều kiện

    if percent_change is not None and percent_change != 0:
        leverage = 15 / abs(percent_change)
        leverage = max(1, min(round(leverage), 125))  # Đảm bảo leverage nằm trong khoảng 1-125
        set_leverage(client, symbol, leverage)

    trading_balance = 15 * leverage  # Risk=2$
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




# Hàm kiểm tra điều kiện Stop Loss/Take Profit 
def check_sl_tp(client, symbol):
    global last_order_status, stop_loss_price  # Sử dụng biến toàn cục stop_loss_price

    # Lấy thông tin PNL và vị thế
    extract_pnl_and_position_info(client, symbol)
    pnl_percentage = get_pnl_percentage()  # Giá trị PNL hiện tại (%)
    pnl_usdt = get_pnl_usdt()  # Giá trị PNL hiện tại (USDT)

    # Lấy thông tin vị thế hiện tại
    position_info = client.futures_position_information(symbol=symbol)
    qty = float(position_info[0]['positionAmt'])  # Số lượng vị thế hiện tại (BTC)
    
    # Lấy giá mark price hiện tại từ API Binance
    mark_price = float(position_info[0]['markPrice'])

    # Lấy giá trị HH và LL từ hàm get_results, sử dụng updated_hh và updated_ll
    final_hh, final_ll, final_hl, final_lh, updated_hh, updated_ll = get_results()

    # Kiểm tra giá trị trả về của updated_ll và updated_hh để tránh lỗi truy cập
    if updated_ll and isinstance(updated_ll, (list, tuple)) and len(updated_ll) > 1:
        percent_change_ll = abs((mark_price - updated_ll) / mark_price) * 100
    else:
        percent_change_ll = None

    if updated_hh and isinstance(updated_hh, (list, tuple)) and len(updated_hh) > 1:
        percent_change_hh = abs((mark_price - updated_hh) / mark_price) * 100
    else:
        percent_change_hh = None

    # Kiểm tra nếu PNL là None để tránh lỗi
    if pnl_percentage is None:
        print("Lỗi: PNL không có giá trị hợp lệ.")
        return None
    # Lấy giá mark price hiện tại từ API Binance
    mark_price = float(position_info[0]['markPrice'])

 #Hàm SL
    if qty > 0:  # Lệnh Buy đang mở
        if mark_price <= stop_loss_price:
            print(f"Điều kiện Stop Loss cho lệnh Buy đạt được (mark_price <= stop_loss_price: {stop_loss_price:.2f}). Đóng lệnh Buy.")
            close_position(client, pnl_percentage, pnl_usdt)
            return "stop_loss_buy"

    # Kiểm tra nếu là lệnh Sell và giá mark hiện tại >= stop_loss_price (Stop Loss cho Sell)
    elif qty < 0:  # Lệnh Sell đang mở
        if mark_price >= stop_loss_price:
            print(f"Điều kiện Stop Loss cho lệnh Sell đạt được (mark_price >= stop_loss_price: {stop_loss_price:.2f}). Đóng lệnh Sell.")
            close_position(client, pnl_percentage, pnl_usdt)
            return "stop_loss_sell"

 #Hàm TP
    ### Lệnh Sell (qty < 0)
    if qty < 0:  # Lệnh Sell đang mở
        # Kiểm tra điều kiện Take Profit: mark price không chênh quá 0.11% so với updated LL hoặc nhỏ hơn updated LL
        if (percent_change_ll is not None and percent_change_ll <= 0.11) or (updated_ll and mark_price <= updated_ll):
            print(f"Điều kiện Take Profit đạt được cho lệnh Sell (mark_price <= updated LL: {updated_ll:.2f}). Đóng lệnh Sell.")
            close_position(client, pnl_percentage, pnl_usdt)
            return "take_profit_sell"

    ### Lệnh Buy (qty > 0)
    elif qty > 0:  # Lệnh Buy đang mở
        # Kiểm tra điều kiện Take Profit: mark price không chênh quá 0.11% so với updated HH hoặc lớn hơn updated HH
        if (percent_change_hh is not None and percent_change_hh <= 0.11) or (updated_hh and mark_price >= updated_hh):
            print(f"Điều kiện Take Profit đạt được cho lệnh Buy (mark_price >= updated HH: {updated_hh:.2f}). Đóng lệnh Buy.")
            close_position(client, pnl_percentage, pnl_usdt)
            return "take_profit_buy"

    return None



# Hàm đóng lệnh
def close_position(client, pnl_percentage, pnl_usdt):
    global last_order_status
    symbol = 'ETHUSDT'
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

# Hàm bot giao dịch chạy mỗi 60 giây
def trading_bot():
    global client
    api_key = 'WIQ9isqoeJOTjaaoEO27Ycgcx1RNySNNC2X9PMdYhusHT8gFOTcBH9EGJ5G0Lnxc'
    api_secret = 'eFX13NMDauEJuHE9vMzJjDG9CNqYriJUGGfT1CAnY8wSH5vYMDbHrp7dJc7GBHW6'
    client = Client(api_key, api_secret, tld='com', testnet=False)
    
    # Nạp giá trị stop-loss từ file nếu có
    load_stoploss()

    symbol = 'ETHUSDT'

    while True:
        try:
            # Kiểm tra kết nối Internet
            if not check_internet_and_alert():
                continue

            # Kiểm tra điều kiện Stop Loss hoặc Take Profit cho ETHUSDT
            result = check_sl_tp(client, symbol)
            if result == "stop_loss" or result == "take_profit":
                break

            # Gọi hàm get_final_trend() để lấy kết quả xu hướng cho ETHUSDT
            final_trend = get_final_trend(client)
            print(f"Kết quả xu hướng từ hàm get_final_trend(): {final_trend}")

            # Lấy thông tin vị thế hiện tại cho ETHUSDT
            position_info = client.futures_position_information(symbol=symbol)
            qty = float(position_info[0]['positionAmt'])  # Số lượng vị thế hiện tại cho ETH

            # Kiểm tra nếu đã có lệnh mở cho ETHUSDT, không thực hiện thêm lệnh mới cho cặp này
            if qty != 0:  # Nếu có vị thế mở cho ETHUSDT
                if final_trend == "Xu hướng không rõ ràng":
                    print("Xu hướng không rõ ràng cho ETHUSDT")
                    time.sleep(300)  # Nếu xu hướng không rõ ràng, nghỉ 300 giây (5 phút)
                    continue

                # Đóng lệnh nếu xu hướng thay đổi cho ETHUSDT
                if final_trend == "Xu hướng tăng" and qty < 0:  # Đóng lệnh sell nếu có tín hiệu mua
                    close_position(client, get_pnl_percentage(), get_pnl_usdt())
                elif final_trend == "Xu hướng giảm" and qty > 0:  # Đóng lệnh buy nếu có tín hiệu bán
                    close_position(client, get_pnl_percentage(), get_pnl_usdt())

                print("Hiện đã có lệnh mở cho ETHUSDT. Không thực hiện thêm lệnh mới.")
                time.sleep(20)  # Nếu xu hướng rõ ràng, nghỉ 20 giây
                continue

            # Lấy giá trị mark price hiện tại từ API của Binance cho ETHUSDT
            mark_price = float(position_info[0]['markPrice'])

            # Dựa trên xu hướng, thực hiện lệnh mua/bán cho ETHUSDT
            if final_trend == "Xu hướng tăng":
                print("Xu hướng tăng. Thực hiện lệnh mua cho ETHUSDT.")
                place_order(client, "buy")
            elif final_trend == "Xu hướng giảm":
                print("Xu hướng giảm. Thực hiện lệnh bán cho ETHUSDT.")
                place_order(client, "sell")

            # Sau khi xử lý giao dịch, thời gian nghỉ sẽ dựa vào xu hướng
            if final_trend == "Xu hướng không rõ ràng":
                time.sleep(300)  # Nếu xu hướng không rõ ràng, nghỉ 300 giây
            else:
                time.sleep(20)  # Nếu xu hướng rõ ràng, nghỉ 20 giây

        except Exception as e:
            print(f"Lỗi khi gọi API hoặc xử lý giao dịch: {str(e)}")
            playsound(r"C:\Users\DELL\Desktop\GPT train\noconnect.mp3")
            time.sleep(5)


if __name__ == "__main__":
    trading_thread = threading.Thread(target=trading_bot)
    trading_thread.start()
    app.run(host='0.0.0.0', port=8080)
