import meme
import re
import threading
from wxpy import *
from logger import logger
from functools import lru_cache
from tempfile import NamedTemporaryFile


class EmotionBot(Bot):
    class TimeoutException(Exception):
        def __init__(self, uuid, status):
            self.uuid = uuid
            self.status = status

    def __init__(self, name=None, need_login=True, timeout_max=15, qr_callback=None, *args, **kwargs):
        self.name = name
        self.timeout_count = 0  # QR code timeout count
        self.at_reply_groups = set()  # auto reply is_at msg from these groups

        if need_login:
            self.login(timeout_max=timeout_max, qr_callback=qr_callback, *args, **kwargs)

    def login(self, timeout_max=15, qr_callback=None, *args, **kwargs):
        def _qr_callback(uuid, status, qrcode):
            if status == '408':
                self.timeout_count += 1
                if self.timeout_count > timeout_max:
                    raise self.TimeoutException(uuid, status)
            elif status == '400':  # exit thread when time out at QR code waiting for scan
                raise self.TimeoutException(uuid, status)
            if callable(qr_callback):
                qr_callback(uuid, status, qrcode)

        super().__init__(qr_callback=_qr_callback, *args, **kwargs)
        self.reg_event()

    def reg_event(self):
        @lru_cache()
        def gif_media_id(*url):
            tmp = NamedTemporaryFile()
            try:
                meme.download_gif(tmp, *url)
                media_id = self.upload_file(tmp.name)
            finally:
                tmp.close()
            return media_id

        @self.register(msg_types=TEXT, except_self=False)
        def reply(msg):
            if msg.sender == self.self and '开启自动斗图' in msg.text:
                self.at_reply_groups.add(msg.receiver)
                logger.info('群聊<%s>已开启自动斗图' % msg.receiver.name)
                return '已开启，@我发送文字可以自动斗图'
            elif msg.sender == self.self and '关闭自动斗图' in msg.text and msg.receiver in self.at_reply_groups:
                self.at_reply_groups.remove(msg.receiver)
                logger.info('群聊<%s>已关闭自动斗图' % msg.receiver.name)
                return '已关闭'

            keyword = None
            if msg.text[-4:] in ('.gif', '.jpg'):
                keyword = msg.text[:-4]
            elif msg.is_at and msg.sender in self.at_reply_groups:
                keyword = re.sub('@\S+', '', msg.text)
            if keyword:
                img = meme.image_url(keyword)
                if img:
                    logger.info('Uploading image, URLs: %s', img)
                    media_id = gif_media_id(*img)
                    logger.info('Received keyword "%s", reply image with media_id %s', keyword, media_id)
                    msg.reply_image('.gif', media_id=media_id)


class SyncEmotionBot(EmotionBot):
    def __init__(self, need_login=True, *args, **kwargs):
        super().__init__(need_login=False, *args, **kwargs)
        self.uuid_lock = threading.Event()
        self.login_lock = threading.Event()
        self.timeout_count = 0  # QR code timeout count
        self.thread = None

        if need_login:
            self.login(*args, **kwargs)

    def login(self, qr_callback=None, *args, **kwargs):
        def _qr_callback(uuid, status, qrcode):
            if status == '0':
                self.uuid = uuid
                self.uuid_lock.set()
            if callable(qr_callback):
                qr_callback(uuid, status, qrcode)

        kwargs.update(qr_callback=_qr_callback)
        self.thread = threading.Thread(target=self._login_thread, args=args, kwargs=kwargs)
        self.thread.start()
        self.uuid_lock.wait()  # lock release when QR code uuid got
        return self.uuid

    def _login_thread(self, *args, **kwargs):
        try:
            super().login(*args, **kwargs)
        except self.TimeoutException as e:
            logger.warning('uuid=%s, status=%s, timeout', e.uuid, e.status)
            return
        self.login_lock.set()

    def is_logged(self, timeout=None):
        return self.login_lock.wait(timeout)
