import socket

class Connection:
    def __init__(self,fd:int,is_internal:bool,conn_obj:socket.SocketType,linked_fd:int=None,rcv_data=""):
        self._fd = fd
        self._is_interanl = is_internal
        self._linked_fd = linked_fd
        self._conn_obj = conn_obj
        self._rcv_data = ""
        self.append_data(rcv_data==rcv_data)

    def set_linked_fd(self,linked_fd):
        self._linked_fd = linked_fd

    def set_rcv_data(self,rcv_data)->None:
        if self.is_binary(rcv_data) :
            rcv_data = rcv_data.decode('utf-8')
        self._rcv_data = rcv_data 

    def append_data(self,rcv_data) -> None:
        decoded_rcv_data = rcv_data
        if self.is_binary(rcv_data):
            decoded_rcv_data = rcv_data.decode('utf-8')
        self._rcv_data = self._recv_data.join(decoded_rcv_data)

    def fileno(self) -> int:
        return self._fd
    
    def is_internal(self)->bool:
        """returns True if it's a internal upstream server connection"""
        return self._is_interanl
    
    def linked_fd (self) -> int:
        """returns the FD of the linked internal or external connection"""
        return self._linked_fd
    
    def get_connection_obj(self)->socket.SocketType:
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

