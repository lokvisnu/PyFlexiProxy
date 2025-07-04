from ast import mod
import errno
import select,socket
from stat import filemode
from typing import List
import yaml
from connections import CONNECTION_STATUS, Connection,ConnectionType
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
                        # self.recieve_incomming_data(fileno=fileno)
                        self._connection_data[fileno].recv_data()
                        recieved_data = self._connection_data[fileno].request_data(byt=True)
                        # EOL1 & EOL2 indicates end of recieved data
                        if EOL1 in recieved_data or EOL2 in recieved_data: 
                            if self._connection_data[fileno].is_internal():
                                # internal connection with upstream server 
                                self._connection_data[fileno].shutdown(mode=socket.SHUT_RDWR) # shutsdown connection with the internal server
                                linked_fd = self._connection_data[fileno].linked_fd()
                                #Modify epoll to listen for termination
                                self._epoll.modify(fd=fileno,eventmask=select.EPOLLET)
                                #Modify epoll to listen for EPOLLOUT( Lvl Triggered)
                                self._epoll.modify(fd=linked_fd,eventmask=select.EPOLLOUT)
                            else:
                                # external client connection 
                                self.forward_to_internal_upstreams(fileno=fileno)

                    elif event & select.EPOLLOUT: # socket ready for output stream
                        if self._connection_data[fileno].status() == CONNECTION_STATUS['ERROR']:
                            self.send_http_error(fileno=fileno)
                        else:
                            linked_fd = self._connection_data[fileno].linked_fd()
                            response_data = self._connection_data[linked_fd].request_data(byt=True)
                            sent_bytes = self._connection_data[fileno].send_data(response=response_data)
                            # Store remaining response data
                            if sent_bytes == len(response_data):
                                if not self._connection_data[fileno].is_internal():
                                    #Shutdown external connection
                                    self._connection_data[fileno].shutdown(mode=socket.SHUT_RDWR)
                                    #Modify epoll to wait for shutdown
                                    self._epoll.modify(fd=fileno,eventmask=select.EPOLLET)
                                else:
                                    self._epoll.modify(fd=fileno,eventmask=select.EPOLLIN | select.EPOLLET)
                            else :
                                # Socket buffer full, modify epoll to wait for EPOLLOUT
                                self._epoll.modify(fd=fileno,eventmask=select.EPOLLOUT | select.EPOLLET)


                    elif event & select.EPOLLHUP: # hang-up event
                        if fileno in self._connection_data:
                            self._epoll.unregister(fd=fileno)
                            self._connection_data[fileno].close()
                            if not self._connection_data[fileno].is_internal():
                                del self._connection_data[self._connection_data[fileno].linked_fd()]
                                del self._connection_data[fileno]
        except Exception as e:
            print(e)

        finally:
            self._epoll.unregister(self._server_socket_fd)
            self._epoll.close()

  

    def send_data(self,fileno,response):
            if fileno in self._connection_data:
                conn_obj: socket.SocketType = self._connection_data[fileno].connection()
                response_bytes = response
                if not isinstance(response_bytes,bytes):
                    response_bytes = response.encode('utf-8')
                
                bytes_sent = 0
                while bytes_sent < len(response_bytes):
                    try:
                        sent = conn_obj.send(response_bytes[bytes_sent:])
                        if sent == 0:
                            break
                        bytes_sent += sent
                    except BlockingIOError as e:
                        if e.errno == errno.EAGAIN:
                            break
                        else:
                            raise
                return bytes_sent
                

    def recieve_incomming_data(self,fileno) -> None: 
         # recieve incoming data stream from the connection and write to connection data
         conn_obj = self._connection_data[fileno].connection()
         while True:
            try:
                    rcv_data = conn_obj.recv(RECV_BYTES)
                    if not rcv_data:
                        break
                    self._connection_data[fileno].append_data(rcv_data=rcv_data)
            except BlockingIOError as e: 
                if e.errno == errno.EAGAIN:
                    break
                else:
                    raise

    def accept_incomming_connection(self) -> None:
         
         try:
            while True:
                conn,__ = self._server_socket.accept()
                conn.setblocking(False)
                #Register epoll, listen to incoming data
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
                    #Longest matching path found
                    redirect_rule:dict = self._redirect_rules.get(matched_path)
                    upstream_server_ids:List = redirect_rule.get("upstreams")
                    # load balancing code goes here
                    # selecting upstream server at index 0
                    selected_upstream_server = self._upstream_server.get(upstream_server_ids[0])
                    try:
                        upstream_socket = socket.socket(family=socket.AF_INET,type=socket.SOCK_STREAM)
                        upstream_socket.setblocking(False)
                        try:
                            upstream_socket.connect((selected_upstream_server["host"],selected_upstream_server["port"]))
                        except socket.error as e:
                            if not e.errno == errno.EINPROGRESS:
                                raise
                        self._connection_data[fileno].set_linked_fd(linked_fd=upstream_socket.fileno())
                        upstream_connection = Connection(is_internal=True,conn_obj=upstream_socket,linked_fd=fileno,fd=upstream_socket.fileno())
                        self._connection_data.__setattr__(name=upstream_socket.fileno(),value=upstream_connection)

                        #Register Epoll to wait for EPOLLOUT in internal connection
                        self._epoll.register(fd=upstream_socket.fileno(),eventmask=select.EPOLLOUT | select.EPOLLET)
                    except Exception as e:
                        print(f"Error forwarding request to upstream server: {e}")
                        self.send_http_error(fileno, 502, "Bad Gateway")  # Internal Server Error
                else:
                    self.send_http_error(fileno, 404)  # 404 not found
            else:
                self.send_http_error(fileno, 404)  # 404 not found
        except  Exception as e:
            print(f"HTTP Request Parsing Error: {e}")
            self.send_http_error(fileno, 400, "Bad Request")  # Bad Request for parsing errors
        pass

    def send_http_error(self, fileno: int, status_code: int = 400, reason_phrase: str = None) -> None:
        """
        Sends an HTTP error response to the client connection identified by fileno.
        Compatible with epoll non-blocking operations.
        
        Args:
            fileno: File descriptor of the client connection
            status_code: Optional HTTP status code (404, 500, etc.)
            reason_phrase: Optional custom reason phrase
        """
        # Standard HTTP status messages
        status_messages = {
            400: "Bad Request",
            404: "Not Found", 
            500: "Internal Server Error",
            502: "Bad Gateway",
            503: "Service Unavailable",
            504: "Gateway Timeout"
        }
        
        if reason_phrase is None:
            reason_phrase = status_messages.get(status_code, "Error")
        
        # Create HTTP error response
        error_body = f"""<!DOCTYPE html>
                    <html>
                    <head><title>{status_code} {reason_phrase}</title></head>
                    <body>
                    <h1>{status_code} {reason_phrase}</h1>
                    <p>The requested resource could not be found or an error occurred.</p>
                    </body>
                    </html>"""
                
        response = "".join((
            f"HTTP/1.1 {status_code} {reason_phrase}\r\n",
            "Content-Type: text/html\r\n",
            f"Content-Length: {len(error_body)}\r\n",
            "Connection: close\r\n",
            "\r\n",
            error_body))
        
        try:
            if fileno in self._connection_data:
                response_bytes = response.encode('utf-8')
                bytes_sent:int = self._connection_data[fileno].send_data(response=response_bytes,err=True)
                response_bytes = response_bytes[bytes_sent:]
                if not len(response_bytes) == 0:
                    # Response yet to be sent
                    self._epoll.modify(fd=fileno,eventmask= select.EPOLLOUT | select.EPOLLET)
                else:
                    # Close connection after sending error
                    self._epoll.modify(fd=fileno, eventmask=select.EPOLLET)
                    self._connection_data[fileno].shutdown(socket.SHUT_RDWR)
                
        except Exception as e:
            print(f"Error sending HTTP error response: {e}")
            # Force close connection on any error
            if fileno in self._connection_data:
                try:
                    self._epoll.unregister(fd=fileno)
                    self._connection_data[fileno].close()
                    del self._connection_data[fileno]
                except:
                    pass
    
    def longest_prefix_match_path(self, request_path) -> str | None:
        for path in self._allowed_paths:
            if request_path.startswith(path):
                return path
        return None