"""
텔레그램 봇 — 아무 메시지를 받으면:
1. "분석 중..." 즉시 회신
2. FRED+Yahoo 최신 데이터 수집
3. 모든 지표 계산
4. Gemini API에 판단 요청 (가성비 순 자동 선택)
5. BUY / WAIT + 근거 3줄 회신
"""
import os
import json
import pandas as pd
import telebot
from google import genai
from google.genai import types
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

if not TELEGRAM_TOKEN:
    raise ValueError(".env에 TELEGRAM_TOKEN이 없습니다.")
if not GEMINI_API_KEY:
    raise ValueError(".env에 GEMINI_API_KEY가 없습니다.")

bot    = telebot.TeleBot(TELEGRAM_TOKEN)
client = genai.Client(api_key=GEMINI_API_KEY)

DB_PATH = os.path.join(os.path.dirname(__file__), 'liquidity_db.csv')

# 가성비 순 우선순위 (앞에 있을수록 빠르고 저렴)
CANDIDATE_MODELS = [
    'gemini-2.5-flash-lite',
    'gemini-2.5-flash',
    'gemini-2.0-flash',
    'gemini-2.5-pro',
]

def pick_model() -> str:
    """사용 가능한 모델 목록에서 가성비 순으로 첫 번째 매칭 반환"""
    try:
        available = {m.name.split('/')[-1] for m in client.models.list()}
        for candidate in CANDIDATE_MODELS:
            if candidate in available:
                print(f"[Gemini] 선택된 모델: {candidate}")
                return candidate
    except Exception as e:
        print(f"[Gemini] 모델 목록 조회 실패: {e}")
    # 조회 실패 시 기본값
    return CANDIDATE_MODELS[1]

GEMINI_MODEL = pick_model()

SYSTEM_PROMPT = """당신은 기관급 퀀트 애널리스트입니다.
아래 주식시장 지표 JSON을 분석하여 오늘 S&P500 ETF(SPY)를 매수해야 하는지 판단하세요.

출력 규칙 (반드시 준수):
1번째 줄: BUY 또는 WAIT 중 하나만 (다른 말 금지)
2번째 줄: 빈 줄
3번째 줄~: 핵심 근거를 불릿 포인트(•) 3개 이내로 작성, 각 줄 20자 이내로 간결하게
그 이후: 아무것도 출력하지 않음

판단 기준:
- convergence.score 4 → 강력 BUY
- convergence.score 3 + has_danger false → BUY
- convergence.score 2 이하 or has_danger true → WAIT
- recession_score 3 이상 → 반드시 WAIT
- market_regime BEAR + smart_money.score 2 이하 → 반드시 WAIT
- vix_capitulation true + smart_money.score >= 3 → BUY 가중치
"""


def call_gemini(signals_json: str) -> str:
    """가성비 순으로 모델을 시도, 실패 시 다음 모델로 폴백"""
    prompt = f"{SYSTEM_PROMPT}\n\n지표 데이터:\n{signals_json}"

    for model in CANDIDATE_MODELS:
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=300,
                )
            )
            print(f"[Gemini] 응답 모델: {model}")
            return response.text.strip()
        except Exception as e:
            print(f"[Gemini] {model} 실패: {e} → 다음 모델 시도")

    raise RuntimeError("모든 Gemini 모델 호출 실패")


def fetch_and_analyze() -> str:
    """데이터 수집 → 신호 계산 → Gemini 판단 → 포맷된 메시지 반환"""
    from utils.fetcher import update_database
    from utils.signals import collect_all_signals

    # 1. 최신 데이터 수집
    update_database()

    # 2. 신호 계산
    df = pd.read_csv(DB_PATH)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date').reset_index(drop=True)
    signals = collect_all_signals(df)

    # 3. Gemini 판단
    signals_json = json.dumps(signals, ensure_ascii=False, indent=2)
    raw = call_gemini(signals_json)

    # 4. 파싱
    lines      = [l.strip() for l in raw.splitlines() if l.strip()]
    verdict    = lines[0].upper() if lines else "WAIT"
    verdict_line = "✅  BUY" if "BUY" in verdict else "❌  WAIT"
    reasons    = [l for l in lines[1:] if l and "BUY" not in l.upper()[:4] and "WAIT" not in l.upper()[:4]]

    # 5. 메시지 조립
    s          = signals
    score      = s['convergence']['score']
    alloc      = s['convergence']['allocation_pct']
    regime     = s['market_regime']['regime']
    sm_score   = s['smart_money']['score']
    rec_score  = s['macro']['recession_score']
    vix_val    = s['sentiment']['vix_value']
    date_str   = s['date']
    regime_emoji = {'BULL': '🟢', 'BEAR': '🔴', 'TRANSITION': '🟡'}.get(regime, '⚪')

    msg = (
        f"📊 *AI 투자 판단* | {date_str}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"*{verdict_line}*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
    )
    if reasons:
        msg += "📌 *근거:*\n"
        for r in reasons[:3]:
            msg += f"{'• ' if not r.startswith('•') else ''}{r}\n"
        msg += "\n"

    msg += (
        f"📈 *지표 요약*\n"
        f"• 레짐: {regime_emoji} {regime}\n"
        f"• 통합점수: {score}/4 | 권장비중: {alloc}%\n"
        f"• 스마트머니: {sm_score}/4 | VIX: {vix_val}\n"
        f"• 경기침체 위험: {rec_score}/4\n"
    )
    if s['convergence']['signal_conflict']:
        msg += "\n⚠️ _신호 충돌 감지 — 신중히 판단하세요_"

    return msg


@bot.message_handler(func=lambda m: True)
def handle_message(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "⏳ 분석 중... (약 20초 소요)")
    try:
        result = fetch_and_analyze()
        bot.send_message(chat_id, result, parse_mode='Markdown')
    except Exception as e:
        bot.send_message(chat_id, f"❌ 오류 발생:\n{e}")
        raise


if __name__ == '__main__':
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 봇 시작 — 메시지 대기 중... (모델: {GEMINI_MODEL})")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
