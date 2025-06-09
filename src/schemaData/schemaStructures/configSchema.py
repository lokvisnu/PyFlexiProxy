from schema import Schema, And, Use, Optional,Regex

DEFAULT_PORT = 8080
VALIDATE_HOST_NAME_REG_EX = "^([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])(\.([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]{0,61}[a-zA-Z0-9]))*$"

ConfigurationSchema = Schema(
    {
        "server" : {
            Optional("port",DEFAULT_PORT):And(int),
            "host":And(Use(str),Regex(VALIDATE_HOST_NAME_REG_EX)),
            "workers":Use(int),
            Optional("headers",list()):[
                {
                    "key":Use(str),
                    "value":Use(str)
                }
            ],
            "upstreams":[
                {
                    "id":Use(str),
                    "host":And(Use(str),Regex(VALIDATE_HOST_NAME_REG_EX)),
                    "port":And(int)
                }
            ],
            "paths":[
                {
                    "path":Use(str),
                    "upstreams":[
                        Use(str)
                    ]
                }
            ]
        }
})