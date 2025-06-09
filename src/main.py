import yaml
from schemaData.validateSchema import validateConfig\

configFile = "config.yaml"

def loadConfig():
    with open(configFile,'r') as f:
        yaml_data = yaml.load(f,Loader=yaml.FullLoader)
        validated_yaml = validateConfig(yaml_data)
    print(validated_yaml)

if __name__=="__main__":
    loadConfig()