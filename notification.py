from wxpusher import WxPusher


class Notify:
    def __init__(self):
        self.uids = ['UID_0UhoJ977fvwsJhzXokMmhzgIqFRZ']
        self.token = 'AT_a5ARmQl4Mi8mCjv6xImNDesNfjSla8OW'

    def send(self, text):
        WxPusher.send_message(text, uids=self.uids, token=self.token)
