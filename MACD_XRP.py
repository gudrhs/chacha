import os
import ccxt
import pandas as pd
from datetime import datetime, timedelta, timezone
import time
import requests

# 환경 변수에서 API 키와 시크릿 키 가져오기
api_key = os.getenv('5Vo8kRCgO4uVS4Iy8zACmPQYgbukhlgnQE3fu0ws5vVOkMPLIrLLZ6e95aZlO9cq')
api_secret = os.getenv('S3HIoCkFzBSKxcyP5b2q89RsDpUxReJxKWnJHigvRn8teYdf8mp5yfvtQ6zy7Y3D')

# 텔레그램 API 설정
telegram_token = os.getenv('7323611824:AAF9rT54MxrYzLzr5qAX_vOWLTndNMvU4Ao')
chat_id = os.getenv('6492509337')

# 텔레그램 메시지 보내기 함수
def send_telegram_message(text):
    url = f'https://api.telegram.org/bot{telegram_token}/sendMessage'
    data = {
        'chat_id': chat_id,
        'text': text
    }
    response = requests.post(url, data=data)
    return response

# 바이낸스 거래소 객체 생성
exchange = ccxt.binance({
    'apiKey': api_key,
    'secret': api_secret,
    'enableRateLimit': True,
    'options': {
        'defaultType': 'spot',  # 스팟 마켓으로 변경
    },
})

# 히스토리컬 데이터 가져오기
def fetch_historical_data(symbol, timeframe, since):
    attempts = 0
    max_attempts = 5
    while attempts < max_attempts:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
            df.set_index('timestamp', inplace=True)
            return df
        except ccxt.NetworkError as e:
            print(f"Network error: {e}. Retrying...")
            attempts += 1
            time.sleep(5)
    raise Exception("Failed to fetch historical data after multiple attempts")

# MACD 계산
def calculate_macd(df, short_window=14, long_window=21, signal_window=14):
    df['ema_short'] = df['close'].ewm(span=short_window, adjust=False).mean()
    df['ema_long'] = df['close'].ewm(span=long_window, adjust=False).mean()
    df['macd'] = df['ema_short'] - df['ema_long']
    df['signal'] = df['macd'].ewm(span=signal_window, adjust=False).mean()
    df['histogram'] = df['macd'] - df['signal']
    return df

# 실시간 가격 가져오기
def fetch_current_price(symbol):
    ticker = exchange.fetch_ticker(symbol)
    return ticker['last']

# 포지션 열기 함수
def open_position(symbol, side, amount):
    order = exchange.create_market_order(symbol, side, amount)
    return order

# 포지션 닫기 함수
def close_position(symbol, side, amount):
    order = exchange.create_market_order(symbol, side, amount)
    return order

# 실시간 데이터 감시 및 매매 함수
def trade(symbol, timeframe, initial_balance=10000):
    balance = initial_balance
    position = 0
    entry_price = 0
    trades = []
    last_timestamp = None

    while True:
        now = datetime.now(timezone.utc)  # 수정된 부분
        since = exchange.parse8601((now - timedelta(days=30)).isoformat())
        df = fetch_historical_data(symbol, timeframe, since)
        
        if df.empty:
            print("데이터를 가져오지 못했습니다.")
            send_telegram_message("데이터를 가져오지 못했습니다.")
            time.sleep(10)
            continue

        df = calculate_macd(df)
        
        if last_timestamp == df.index[-1]:
            time.sleep(10)
            continue

        last_timestamp = df.index[-1]
        current_price = fetch_current_price(symbol)
        prev_macd = df['macd'].iloc[-2]
        prev_signal = df['signal'].iloc[-2]
        curr_macd = df['macd'].iloc[-1]
        curr_signal = df['signal'].iloc[-1]

        print(f"Current price: {current_price}, Previous MACD: {prev_macd}, Previous Signal: {prev_signal}")
        print(f"Current MACD: {curr_macd}, Current Signal: {curr_signal}")

        if prev_macd <= prev_signal and curr_macd > curr_signal and position == 0:
            balance = exchange.fetch_balance()['total']['USDT']
            amount_to_invest = balance / current_price  # 모든 금액을 투자
            order = open_position(symbol, 'buy', amount_to_invest)
            position = amount_to_invest
            entry_price = current_price
            trades.append(('Buy', now, current_price))
            send_telegram_message(f"Buy: {current_price} at {now}")
            print(f"Buy: {current_price} at {now}")

        elif prev_macd >= prev_signal and curr_macd < curr_signal and position > 0:
            order = close_position(symbol, 'sell', position)
            balance = exchange.fetch_balance()['total']['USDT']
            profit = balance - initial_balance
            trades.append(('Sell', now, current_price, profit))
            position = 0
            send_telegram_message(f"Sell: {current_price} at {now} with profit: {profit}")
            print(f"Sell: {current_price} at {now} with profit: {profit}")

        time.sleep(60)

# 자동 매매 실행
symbol = 'XRP/USDT'
timeframe = '5m'  # 5분봉 데이터 사용

trade(symbol, timeframe)
