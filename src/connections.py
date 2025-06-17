import errno
import re
import socket
CONNECTION_STATUS={
    "ERROR":"ERROR",
    "SENDING_DATA":"SENDING_DATA",
    "SHUTDOWN":"SHUTDOWN",
    "RECIEVING_DATA":"RECIEVING_DATA",
    "INITIALISED":"INITIALISED"
}
class Connection:
    def __init__(self,fd:int,is_internal:bool,conn_obj:socket.SocketType,linked_fd:int=None,rcv_data=""):
        self._fd = fd
        self._is_interanl = is_internal
        self._linked_fd = linked_fd
        self._conn_obj = conn_obj
        self._rcv_data:str = ""
        self._recieved:str=""
        self.append_data(rcv_data=rcv_data)
        self._bytes_sent:int = 0
        self._response_data: None | bytes = None
        self._status = CONNECTION_STATUS["INITIALISED"]

    def set_linked_fd(self,linked_fd):
        self._linked_fd = linked_fd

    def set_rcv_data(self,rcv_data)->None:
        if self.is_binary(rcv_data) :
            rcv_data = rcv_data.decode('utf-8')
        self._rcv_data = rcv_data 

    def recv_data(self) -> int | None:
        self._status = CONNECTION_STATUS['RECIEVING_DATA']
        while True:
            try:
                recieved: bytes = self._conn_obj.recv(1024)
                self.append_request_data(recieved)
                if not recieved:
                    break
            except BlockingIOError as e:
                if e.errno == errno.EAGAIN:
                    return errno.EAGAIN
                else:
                    raise

    def append_request_data(self,recieved):
        decoded_data = recieved
        if self.is_binary(recieved):
            decoded_data = recieved.decode('utf-8')

        self._recieved.join(decoded_data)

    def request_data(self,byt:bool=False) -> str:
        if byt:
            return self._recieved.encode('utf-8')
        return self._recieved
    
    def send_data(self,response:bytes | str,err:bool=False) -> int:
            if err:
                self._status = CONNECTION_STATUS["ERROR"]
            else:
                self._status = CONNECTION_STATUS["SENDING_DATA"]

            if not self._response_data:
                response_bytes = response
            else:
                response_bytes = self._response_data
            if not isinstance(response_bytes,bytes):
                response_bytes = response_bytes.encode('utf-8')
            conn_obj = self._conn_obj
            bytes_sent = self._bytes_sent
            while bytes_sent < len(response_bytes):
                try:
                    sent = conn_obj.send(response_bytes[bytes_sent:])
                    if sent == 0:
                        break
                    bytes_sent += sent
                except BlockingIOError as e:
                    if e.errno == errno.EAGAIN:
                        # Socket buffer full
                        break
                        
                    else:
                        raise
            self._bytes_sent = bytes_sent
            self._response_data = response_bytes[bytes_sent:]
            return bytes_sent
    
    def append_data(self,rcv_data) -> None:
        decoded_rcv_data = rcv_data
        if self.is_binary(rcv_data):
            decoded_rcv_data = rcv_data.decode('utf-8')
        self._rcv_data = self._rcv_data.join(decoded_rcv_data)

    def status(self)->str:
        return self._status
    
    def fileno(self) -> int:
        return self._fd
    
    def is_internal(self)->bool:
        """returns True if it's a internal upstream server connection"""
        return self._is_interanl
    
    def linked_fd (self) -> int:
        """returns the FD of the linked internal or external connection"""
        return self._linked_fd
    
    def shutdown(self,mode) -> None:
        self._status = CONNECTION_STATUS['SHUTDOWN']
        self._conn_obj.shutdown(mode)

    def close(self):
        self._conn_obj.close()

    def connection(self)->socket.SocketType:
        """returns the Socket object associated with the connection"""
        return self._conn_obj
    
    def get_binary_rcv_data(self) -> bytes:
        """returns data recieved from connection in bytes"""
        return self._rcv_data.encode('utf-8')
    
    def get_rcv_data(self) -> str:
        """returns data recieved from connections in unitary str"""
        return self._rcv_data
    
    def is_binary(self,data):
        """returns True if the data is byte encoded"""
        return isinstance(data,bytes)
    
ConnectionType = type[Connection]

