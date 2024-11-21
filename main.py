from flask import Flask, request, jsonify
from openai import OpenAI
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv
import os
import threading
import re

app = Flask(__name__)

# .env 파일 로드
load_dotenv()

# API 키 설정
client = OpenAI(
    timeout=20.0,
    api_key=os.environ.get("OPENAI_API_KEY"),
)

slack_client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))

@app.route("/slack/command", methods=["POST"])
def slack_command():
    data = request.form
    command = data.get("command")
    text = data.get("text")
    # user_id = data.get("user_id")
    channel_id = None
    thread_ts = None


    if command == "/summary":
        match = re.search(r"https://leretto2019.slack.com/archives/(C\w+)/p(\d+)", text)

        if match:
            channel_id = match.group(1)
            thread_ts = f"{match.group(2)[:10]}.{match.group(2)[10:]}"

        if not channel_id or not thread_ts:
            return jsonify({"response_type": "ephemeral", "text": "不正なURLです！コピペしたURLもっかい見てみ"})

        # 스레드 메시지 가져오기
        try:
            response = slack_client.conversations_replies(channel=channel_id, ts=thread_ts)
            messages = [msg['text'] for msg in response['messages']]

            threading.Thread(target=process_summary, args=(channel_id, messages, thread_ts)).start()
            return jsonify({"response_type": "ephemeral", "text": "要約、始まるぞ！"})


        except SlackApiError as e:
            return jsonify({"response_type": "ephemeral", "text": f"Error fetching thread: {e.response['error']}"})

    return jsonify({"response_type": "ephemeral", "text": "Unsupported command."})

def process_summary(channel_id, messages, thread_ts):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an assistant designed to facilitate communication between our company's "
                        "Customer Success team and Development team. Your role is to analyze incoming inquiries "
                        "and summarize them in Japanese in a bullet point format. Ensure all key details are present, "
                        "and if any details are missing, suggest follow-up questions to the inquirer."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        "Summarize this Slack thread in Japanese in a bullet point format. Ensure the following details are included:\n"
                        "- Which client or corporation is the inquiry related to? Or is it an internal inquiry?\n"
                        "- Which feature or function experienced an issue?\n"
                        "- Was a file (e.g., CSV) used, and was it attached? If not, request the user to attach it.\n\n"
                        f"Slack thread:\n{messages}"
                    )
                }
            ]
        )


        summary = response.choices[0].message.content
    except Exception as e:
        return jsonify({"response_type": "ephemeral", "text": f"Error summarizing thread: {str(e)}"})
    
    # 결과 반환
    return slack_client.chat_postMessage(channel=channel_id, text=f"Summary:\n{summary}", thread_ts=thread_ts)

if __name__ == "__main__":
    app.run(port=3000)
