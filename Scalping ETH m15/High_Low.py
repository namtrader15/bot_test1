import ccxt
import pandas as pd
import numpy as np

# Kết nối với Binance Futures thông qua CCXT
binance_futures = ccxt.binanceusdm()  # Binance USDT-margined Futures

# Lấy dữ liệu lịch sử (ohlcv) cho một cặp giao dịch Futures
def get_binance_futures_ohlcv(symbol, timeframe='15m', limit=500):
    ohlcv = binance_futures.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    # Chuyển dữ liệu thành DataFrame
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

# Hàm xác định Pivot High (đỉnh cục bộ)
def pivothigh(df, lb, rb):
    df['ph'] = df['high'].rolling(window=lb + rb + 1, center=True).apply(
        lambda x: x[lb] == max(x), raw=True)
    return df['ph'].fillna(0).astype(bool)

# Hàm xác định Pivot Low (đáy cục bộ)
def pivotlow(df, lb, rb):
    df['pl'] = df['low'].rolling(window=lb + rb + 1, center=True).apply(
        lambda x: x[lb] == min(x), raw=True)
    return df['pl'].fillna(0).astype(bool)

# Tính toán các điểm HH, LH, HL, LL và cập nhật HH, LL mới theo thời gian thực
def calculate_hh_ll_lh_hl(df, lb=7, rb=9):
    # Xác định đỉnh và đáy
    df['ph'] = pivothigh(df, lb, rb)
    df['pl'] = pivotlow(df, lb, rb)
    
    # Xác định zigzag dựa trên đỉnh và đáy
    df['zz'] = np.where(df['ph'], df['high'], np.where(df['pl'], df['low'], np.nan))
    df['hl'] = np.where(df['ph'], 1, np.where(df['pl'], -1, np.nan))

    # Tìm các điểm trước đó
    def findprevious(index):
        ehl = -1 if df['hl'].iloc[index] == 1 else 1
        loc = []
        xx = index
        for _ in range(4):
            found = False
            for i in range(xx - 1, -1, -1):
                if df['hl'].iloc[i] == ehl and not np.isnan(df['zz'].iloc[i]):
                    loc.append(df['zz'].iloc[i])
                    xx = i
                    found = True
                    break
            ehl *= -1
            if not found:
                loc.append(np.nan)
        return loc

    hh_list, ll_list, hl_list, lh_list = [], [], [], []

    # Bỏ qua cây nến chưa đóng cửa (cây cuối cùng)
    for i in range(lb + rb, len(df) - 1):  # Bỏ qua cây nến cuối cùng
        # Lấy các giá trị đỉnh/đáy trước đó
        if not np.isnan(df['hl'].iloc[i]):
            loc1, loc2, loc3, loc4 = findprevious(i)
            a = df['zz'].iloc[i]
            b, c, d, e = loc1, loc2, loc3, loc4
            
            # Điều kiện xác định Higher High (HH)
            if a > b and a > c and c > b and c > d:
                hh_list.append((df['timestamp'].iloc[i], a))
            
            # Điều kiện xác định Lower Low (LL)
            if a < b and a < c and c < b and c < d:
                ll_list.append((df['timestamp'].iloc[i], a))
            
            # Điều kiện xác định Higher Low (HL)
            if (a >= c and (b > c and b > d and d > c and d > e)) or (a < b and a > c and b < d):
                hl_list.append((df['timestamp'].iloc[i], a))
            
            # Điều kiện xác định Lower High (LH)
            if (a <= c and (b < c and b < d and d < c and d < e)) or (a > b and a < c and b > d):
                lh_list.append((df['timestamp'].iloc[i], a))

    # Lấy giá trị cuối cùng cho từng cột
    final_hh = hh_list[-1] if hh_list else None
    final_ll = ll_list[-1] if ll_list else None
    final_hl = hl_list[-1] if hl_list else None
    final_lh = lh_list[-1] if lh_list else None

    return final_hh, final_ll, final_hl, final_lh

# Hàm so sánh và cập nhật giá trị Final HH và LL
def update_final_hh_ll(df, final_hh, final_ll):
    last_hh = final_hh[1] if final_hh else -np.inf
    last_ll = final_ll[1] if final_ll else np.inf

    # So sánh với giá trị đóng cửa sau sự kiện HH
    for i in range(df.index[df['timestamp'] == final_hh[0]][0] + 1, len(df) - 1):  # Bỏ qua nến chưa đóng
        if df['close'].iloc[i] > last_hh:
            last_hh = df['close'].iloc[i]

    # So sánh với giá trị đóng cửa sau sự kiện LL
    for i in range(df.index[df['timestamp'] == final_ll[0]][0] + 1, len(df) - 1):  # Bỏ qua nến chưa đóng
        if df['close'].iloc[i] < last_ll:
            last_ll = df['close'].iloc[i]

    return last_hh, last_ll

# In ra kết quả các điểm HH, LL, HL, LH cuối cùng
def print_final_results(final_hh, final_ll, final_hl, final_lh, updated_hh, updated_ll):
    print("\nFinal Higher High (HH):")
    if final_hh:
        print(f"Time: {final_hh[0]}, Value: {final_hh[1]}")
    print(f"Updated HH (if any): {updated_hh}")

    print("\nFinal Lower Low (LL):")
    if final_ll:
        print(f"Time: {final_ll[0]}, Value: {final_ll[1]}")
    print(f"Updated LL (if any): {updated_ll}")

    print("\nFinal Higher Low (HL):")
    if final_hl:
        print(f"Time: {final_hl[0]}, Value: {final_hl[1]}")

    print("\nFinal Lower High (LH):")
    if final_lh:
        print(f"Time: {final_lh[0]}, Value: {final_lh[1]}")

# Hàm trả về kết quả
def get_results():
    symbol = 'ETH/USDT'  # Cặp giao dịch Futures trên Binance
    timeframe = '15m'  # Khung thời gian 15 phút
    limit = 500  # Số lượng nến cần lấy

    # Lấy dữ liệu từ Binance Futures
    df = get_binance_futures_ohlcv(symbol, timeframe, limit)

    # Tính toán các điểm HH, LL, HL, LH cuối cùng
    final_hh, final_ll, final_hl, final_lh = calculate_hh_ll_lh_hl(df, lb=7, rb=9)

    # Cập nhật giá trị HH và LL dựa trên các mốc giá sau sự kiện
    updated_hh, updated_ll = update_final_hh_ll(df, final_hh, final_ll)

    # Trả về các kết quả
    return final_hh, final_ll, final_hl, final_lh, updated_hh, updated_ll
