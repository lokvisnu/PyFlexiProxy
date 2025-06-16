from multiprocessing import Process, process
import socket
import os.path
import yaml
from typing import List
from schemas.config_schema import validate_config
from worker_process import WorkerProcess

BACK_LOG = 5
class MasterProcess:
    def __init__(self,config_path:str):
        self.__config_path :str= config_path
        self.__workers: List[WorkerProcess] = list()
        self.__worker_processes:List[Process]  = list()
        self.__worker_count:int = None
        self.__host:str = None
        self.__port:int  = None
        self.__server_socket:socket.SocketKind = None
        self.__socket_fd:int = None

    def start_process(self):
        if not self._check_config_file_path():
            raise Exception(f"config file path does not exists : {self.config_path}")
        config_data = self._load_config().server
        self.__deconstruct_config_data(config_data=config_data)
        self.__listen_socket()
        self.__start_worker_processes()

    
    def _load_config(self):
        with open(self.__config_path,'r') as f:
            yaml_data = yaml.load(f,Loader=yaml.FullLoader)
            validated_yaml = validate_config(yaml_data)
        return validated_yaml

    def _check_config_file_path(self)->bool:
        if os.path.exists(self.__config_path):
            return True
        return False
    
    def __deconstruct_config_data(self,config_data):
        self.__worker_count = int(config_data.workers)
        self.__host = str(config_data.host)
        self.__port  = int(config_data.port)

    def __listen_socket(self):
        self.__server_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.__server_socket.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        self.__server_socket.setblocking(False)
        self.__server_socket.bind(self.__host,self.__port)
        self.__server_socket.listen(BACK_LOG)
        self.__socket_fd = self.__server_socket.fileno()

    def __start_worker_processes(self):
        for _ in range(self.__worker_count):  
            worker = WorkerProcess(config_file_path=self.__config_path, server_socket_fd=self.__socket_fd)
            process = Process(target=worker.start_worker, args=())
            self.__workers.append(worker)
            self.__worker_processes.append(process)
            process.start()


