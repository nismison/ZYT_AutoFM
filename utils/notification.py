import threading
from wxpusher import WxPusher


class Notify:
    def __init__(self):
        self.uids = ['UID_0UhoJ977fvwsJhzXokMmhzgIqFRZ']
        self.token = 'AT_a5ARmQl4Mi8mCjv6xImNDesNfjSla8OW'

    def _send_sync(self, text: str) -> None:
        try:
            WxPusher.send_message(text, uids=self.uids, token=self.token)
        except Exception:
            # “尝试发送”：失败无所谓，直接吞掉
            pass

    def send(self, text: str) -> None:
        # 异步发送：不阻塞主流程
        t = threading.Thread(target=self._send_sync, args=(text,), daemon=True)
        t.start()
