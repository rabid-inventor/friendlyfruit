import asynchat, struct, traceback

class Rpc(asynchat.async_chat):
    def __init__(self, server=None, sock=None, addr=None):
        asynchat.async_chat.__init__(self, sock)
        self.__ibuffer = ""
        self.__awaiting_count = True
        self.set_terminator(4)

    def collect_incoming_data(self, data):
        self.__ibuffer += data

    def uncaught_exception(self, e):
        pass

    def found_terminator(self):
        try:
            if self.__awaiting_count:
                self.__awaiting_count = False
                message_size = struct.unpack('!i', self.__ibuffer)[0]
                self.set_terminator(message_size)
            else:
                self.__awaiting_count = True
                self.set_terminator(4)

                name, msg = self.__ibuffer.split("\0", 1)
                self.message_received(name, msg)

            self.__ibuffer = ""
        except Exception as e:
            traceback.print_exc()
            self.uncaught_exception(e)
            raise

    def send_rpc(self, msg):
        rpc_name = msg.__module__
        rpc_name = rpc_name[rpc_name.rfind(".") + 1:]
        rpc_name = rpc_name + "." + msg.__class__.__name__
        binary = rpc_name + "\0" + msg.SerializeToString()
        length = struct.pack("!i", len(binary))
        self.push(length + binary)
