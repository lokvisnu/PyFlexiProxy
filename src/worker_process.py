import select,socket

def worker_function(server_socket_fd:int):
    server_socket = socket.fromfd(fd=server_socket_fd,family=socket.AF_INET,type=socket.SOCK_STREAM)
    epoll = select.epoll()
    epoll.register(server_socket_fd,select.EPOLLIN | select.EPOLLEXCLUSIVE)
    try:
        
        while True:
            pass
    finally:
        epoll.unregister(server_socket_fd)
        epoll.close()



