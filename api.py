from flask import Flask
from bot import EmotionBot

app = Flask(__name__)


@app.route('/')
def login():
    def qr_callback(uuid, status, qrcode):
        print(uuid, status)

    bot = EmotionBot(qr_callback=qr_callback)
    return '<img src=http://login.weixin.qq.com/qrcode/%s />' % bot.uuid


app.run()
