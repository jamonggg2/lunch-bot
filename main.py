# 텔레그램이 보내 주는 메시지를 받는 서버 (webhook)
import json
import os
import random
import db
import ai
from prompts import SYSTEM_PROMPT_V1
from prompts import SYSTEM_PROMPT_V1, build_prompt_v3
import places
from weather import describe, get_weather, weather_text

import requests
from dotenv import load_dotenv
from fastapi import FastAPI


load_dotenv()
URL = f"https://api.telegram.org/bot{os.getenv('TELEGRAM_TOKEN')}"

MENUS = ["라면", "햄버거", "마라탕", "샐러드"]

app = FastAPI()  # 웹 서버 앱
conn = db.connect()
PLACES = places.load_places("places_sample.csv")  # 서버가 켜질 때 한 번만 읽는다
FOOD_WORDS = ("식당", "맛집", "먹", "메뉴", "추천", "배고", "점심", "밥")

@app.post("/")  # 텔레그램이 메시지(JSON)를 이 주소로 POST 해 준다 (webhook)
def webhook(body: dict):
    # print(json.dumps(body, indent=2, ensure_ascii=False))  # 받은 JSON 전체를 보고 싶으면 앞의 #을 지운다
    message = body.get("message", {})
    if "text" not in message:  # 사진·스티커처럼 글자가 아닌 메시지는 받기만 한다
        return {"ok": True}

    chat_id = message["chat"]["id"]  # 누구에게 답할지 (JSON의 message › chat › id)
    text = message["text"]           # 보낸 글자 (JSON의 message › text)
    print("[받음]", text)

    # /로 시작하면 명령, 아니면 메아리
    if text == "/start":
        output = "안녕하세요! 오늘 뭐 먹지? 봇입니다. /help 로 사용법을 보세요."
    elif text == "/help":
        output = "/lunch 점심 메뉴 하나\n/lotto 로또 번호 6개\n/weather 지금 캠퍼스 날씨\n/ate 먹은메뉴기록\n/history 먹은것확인\n그 밖의 말은 AI가 대답해요"
    elif text == "/lunch":
        output = random.choice(MENUS)
    elif text == "/lotto":
        numbers = random.sample(range(1, 46), 6)  # 1~45 중 겹치지 않게 6개 뽑기
        numbers.sort()                            # 작은 숫자부터 정렬
        output = "이번 주 행운의 번호: " + ", ".join(str(n) for n in numbers)
    elif text == "/weather":
        output = weather_text()
    elif text.startswith("/ate"):   
        menu = text[len("/ate"):].strip()     #메뉴명 확인
        if menu:
            db.save_meal(conn, menu, db.now())  #메뉴명이 정상적으로 입력되어 있는 경우에만 기록
            output = f"기록했어요: {menu}"  
        else:
            output = "사용법: /ate 김치찌개"    #메뉴명 누락인 경우 사용법안내
    elif text == "/history":                #먹은것 확인기능
        meals = db.recent_meals(conn)
        if meals:
            output = "\n".join(f"{when}  {menu}" for when, menu in meals)
        else:
            output = "아직 기록이 없어요. /ate 메뉴명 으로 적어 보세요."
    elif text.startswith("/"):
        output = "모르는 명령이에요. /help 를 보내 보세요."
    else:                                       #AI 답변
        if any(w in text for w in FOOD_WORDS):  # 식당·음식 관련 말이면 목록에서 먼저 찾는다
            found = places.search(text, PLACES)
            weather = get_weather()
            weather_line = describe(weather) if weather else "정보 없음"
            system = build_prompt_v3(weather_line, db.recent_meals(conn), found)
        else:
            system = SYSTEM_PROMPT_V1
        output = ai.ask_ai(system, text)
    requests.get(f"{URL}/sendMessage", params={"chat_id": chat_id, "text": output})  # 답장 보내기
    print("[보냄]", output)
    return {"ok": True}  # 200 OK = 잘 받았다. 중간에 에러로 멈추면(500) 텔레그램이 같은 메시지를 다시 보낸다
