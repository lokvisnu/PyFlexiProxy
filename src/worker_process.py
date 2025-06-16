import select,socket
from stat import filemode
from typing import List
import yaml
from connections import Connection,ConnectionType
# try to import C parser then fallback in pure python parser.
try:
    from http_parser.parser import HttpParser
except ImportError:
    from http_parser.pyparser import HttpParser
from http_parser.pyparser import InvalidRequestLine,InvalidHeader,InvalidChunkSize
RECV_BYTES = 1024
EOL1 = b'\n\n' # End of Line 1
EOL2 = b'\n\r\n' # End of Line 2

class WorkerProcess():
    def __init__(self,config_file_path:str,server_socket_fd:int):
        self._config_file_path = config_file_path
        self._server_socket_fd = server_socket_fd
        self._connection_data:dict[int,ConnectionType] = dict()
        self._epoll = select.epoll()
        self._server_socket = socket.fromfd(fd=self._server_socket_fd,family=socket.AF_INET,type=socket.SOCK_STREAM)
        self._allowed_paths: List[str] = list()
        self._upstream_server = dict()
        self._domain:str | None = None
        self._load_rules()

    def _load_rules(self) -> None:
        ## load the proxy configuration rules
        with open(file=self._config_file_path,mode='r') as f:
            yaml_data = yaml.load(f,Loader=yaml.FullLoader)
            yaml_data = yaml_data['server']
            # config YAML structure validated in master_process
            self._domain = yaml_data["domain"]
            # redirect rules formatting
            redirect_rules = dict()
            for p in yaml_data['paths']:
                redirect_rules[p['path']] = dict(p) 
                pass # load-balancing implementation

                self._allowed_paths.append(p['path'])
            self._allowed_paths.sort(key=len,reverse=True)
            
            # upstream servers formatting
            upstream_servers = dict()
            for up_server in yaml_data['upstreams']:
                upstream_servers[up_server['id']] = up_server

            self._upstream_server = upstream_servers
            self._redirect_rules =  redirect_rules



        
    def start_worker(self) -> None:
        self._epoll.register(self._server_socket_fd,select.EPOLLIN | select.EPOLLEXCLUSIVE)
        try:
            while True:
                events  = self._epoll.poll(1)
                for fileno,event in events:
                    if fileno == self._server_socket_fd:
                       self.accept_incomming_connection()

                    elif event & select.EPOLLIN: # socket has incoming stream
                        self.recieve_incomming_data(fileno=fileno)
                        if EOL1 in self._connection_data[fileno].get_binary_rcv_data() or EOL2 in self._connection_data[fileno].get_binary_rcv_data(): # EOL1 & EOL2 indicates end of recieved data
                            if self._connection_data[fileno].is_internal():
                                # internal connection with upstream server 
                                self._connection_data[fileno].get_connection_obj().shutdown(socket.SHUT_RDWR)
                                linked_fd = self._connection_data[fileno].linked_fd()
                                self._epoll.modify(fd=fileno,eventmask=select.EPOLLET)
                                self._epoll.modify(fd=linked_fd,eventmask=select.EPOLLOUT | select.EPOLLET) # modify registered fd
                            else:
                                # external client connection 
                                self.forward_to_internal_upstreams(fileno=fileno)

                    elif event & select.EPOLLOUT: # socket ready for output stream
                        linked_fd = self._connection_data[fileno].linked_fd()
                        output_stream_data = self._connection_data[linked_fd].get_binary_rcv_data()
                        try:
                            while len(output_stream_data)>0:
                                bytes_written = self._connection_data[fileno].get_connection_obj().send(output_stream_data)
                                output_stream_data = output_stream_data[bytes_written:]
                        except socket.error:
                            pass
                        self._connection_data[linked_fd].set_rcv_data(output_stream_data) 

                        if not self._connection_data[fileno].is_internal() and len(output_stream_data) == 0 :
                            self._epoll.modify(fd=fileno,eventmask=select.EPOLLET)
                            # self._epoll.modify(fd=linked_fd,eventmask=select.EPOLLET)
                            self._connection_data[fileno].get_connection_obj().shutdown(socket.SHUT_RDWR)
                            # self._connection_data[linked_fd].get_connection_obj().shutdown(socket.SHUT_RDWR)

                        elif self._connection_data[fileno].is_internal() and len(output_stream_data) == 0:
                            self._epoll.modify(fd=fileno,eventmask=select.EPOLLIN | select.EPOLLET)
                        pass

                    elif event & select.EPOLLHUP: # hang-up event
                        if fileno in self._connection_data:
                            self._epoll.unregister(fd=fileno)
                            self._connection_data[fileno].get_connection_obj().close()
                            if not self._connection_data[fileno].is_internal():
                                del self._connection_data[self._connection_data[fileno].linked_fd()]
                                del self._connection_data[fileno]
        except Exception as e:
            print(e)
        finally:
            self._epoll.unregister(self._server_socket_fd)
            self._epoll.close()

    def recieve_incomming_data(self,fileno) -> None: 
         # recieve incoming data stream from the connection and write to connection data
         try:
            conn_obj = self._connection_data[fileno].get_connection_obj()
            while True:
                rcv_data = conn_obj.recv(RECV_BYTES)
                if rcv_data:
                    self._connection_data[fileno].append_data(rcv_data=rcv_data)
                else:
                    break
                # print(f"Recieving Data: {self._connection_data[fileno].get_rcv_data()}")
         except socket.error: # data recieved sucessfully
            pass

    def accept_incomming_connection(self) -> None:
         
         try:
            while True:
                conn,addr = self._server_socket.accept()
                conn.setblocking(False)
                self._epoll.register(conn.fileno(),select.EPOLLIN | select.EPOLLET)
                self._connection_data[conn.fileno()]  = Connection(fd=conn.fileno(),is_internal=False,conn_obj=conn)
         except socket.error:
            pass
        
    def forward_to_internal_upstreams(self,fileno:int) -> None:
        """
        Forwards an incoming HTTP request, identified by the given file descriptor, to the appropriate internal upstream server
        based on the request's Host header and path. The method parses the HTTP request, matches the request path against
        configured redirect rules, and determines the upstream server(s) to forward the request to. If no matching rule is found,
        or if the Host header does not match the expected domain, the request is blocked or a 404 response is sent.
        Handles HTTP parsing errors by deregistering the connection and sending an appropriate error response.
        Note:
            The load-balancing logic should be implemented where indicated. Currently, the code redirects to the server at index 0
            as a placeholder.
        """
        request_len = len(self._connection_data[fileno].get_binary_rcv_data())
        http_parser = HttpParser()
        try:
            http_parser.execute(data=self._connection_data[fileno].get_binary_rcv_data(),length=request_len) # parse recieved http request
            if http_parser.get_headers().get("Host") == self._domain:
                request_path = http_parser.get_path()
                matched_path = self.longest_prefix_match_path(request_path=request_path)
                if matched_path:
                    #longest matching path found
                    redirect_rule = self._redirect_rules[matched_path] 
                    upstream_server_ids = redirect_rule["upstreams"]
                    # load balancing code goes here
                    selected_upstream_server = self._upstream_server[upstream_server_ids[0]] # selecting upstream server at index 0
                    try:
                        upstream_socket = socket.socket(family=socket.AF_INET,type=socket.SOCK_STREAM)
                        upstream_socket.setblocking(False)
                        try:
                            upstream_socket.connect((selected_upstream_server["host"],selected_upstream_server["port"]))
                        except socket.error as e:
                            print(e)
                        self._connection_data[fileno].set_linked_fd(linked_fd=upstream_socket.fileno())
                        upstream_connection = Connection(is_internal=True,conn_obj=upstream_socket,linked_fd=fileno,fd=upstream_socket.fileno())
                        self._connection_data[upstream_socket.fileno()] = upstream_connection

                        ## register for EPOLLOUT( connection established & ready for streaming data) in the socket
                        self._epoll.register(fd=upstream_socket.fileno(),eventmask=select.EPOLLOUT | select.EPOLLET)
                    except Exception as e:
                        print(f"Error forwarding request to upstream server: {e}")
                        pass # Internal Server Error
                else:
                    pass # 404 not found
            else:
                pass # 404 not found
        except  Exception as e:
            # deregister connection FD
            # send appropriate response 
            # end external connection 
            print(f"HTTP Request Parsing Error: {e}")
        pass

    def longest_prefix_match_path(self, request_path) -> str | None:
        for path in self._allowed_paths:
            if request_path.startswith(path):
                return path
        return None