import os
import volcenginesdkcore
from volcenginesdkcore.rest import ApiException
import uuid
import time

if __name__ == '__main__':
    # 从环境变量获取AK/SK
    ak = os.environ.get("VOLC_ACCESSKEY")
    sk = os.environ.get("VOLC_SECRETKEY")
    
    # 配置SDK
    configuration = volcenginesdkcore.Configuration()
    configuration.ak = ak
    configuration.sk = sk
    configuration.region = "cn-north-1"
    
    # 创建API客户端
    api_instance = volcenginesdkcore.UniversalApi(volcenginesdkcore.ApiClient(configuration))
    
    # 配置参数
    product_id = ""  # 云手机产品id
    pod_id = ""  # 云手机实例id
    
    tos_bucket = ""  # tos桶名称
    tos_endpoint = ""  # tos桶endpoint 接入点信息 如：https://tos-cn-beijing.volces.com
    tos_region = ""  # tos桶region 如：cn-beijing
    callback_url = ""  # 状态回调url
    
    try:
        # 1. 创建Agent运行配置 (POST请求)
        body = volcenginesdkcore.Flatten({
            "TosBucket": tos_bucket,
            "TosEndpoint": tos_endpoint,
            "TosRegion": tos_region,
            "CallbackUrl": callback_url
        }).flat()
        
        # 配置账号维度唯一 配置一次即可
        resp = api_instance.do_call(volcenginesdkcore.UniversalInfo(
            method="POST", action="CreateAgentRunConfig", service="ipaas", version="2023-08-01", content_type="application/json"
        ), body)
        
        print("CreateAgentRunConfig response:")
        print(resp)
        
        # 获取ConfigId
        config_id = resp["ConfigId"]
        print(f"ConfigId: {config_id}")
        
        # 2. 运行Agent任务 (POST请求)
        body = volcenginesdkcore.Flatten({
            "RunName": "mobile-use测试demo",
            "ThreadId": str(uuid.uuid4()),
            "PodId": pod_id,
            "ProductId": product_id,
            "UserPrompt": "打开小红书",
        }).flat()
        
        resp = api_instance.do_call(volcenginesdkcore.UniversalInfo(
            method="POST", action="RunAgentTask", service="ipaas", version="2023-08-01", content_type="application/json"
        ), body)
        
        print("\nRunAgentTask response:")
        print(resp)
        
        # 获取RunId
        run_id = resp["RunId"]
        
        # 3. 查看Agent运行当前步骤 (GET请求)
        time.sleep(5)  # 等待任务执行
        
        # GET请求不需要请求体，参数直接放在body中
        body = volcenginesdkcore.Flatten({
            "RunId": run_id
        }).flat()
        
        resp = api_instance.do_call(volcenginesdkcore.UniversalInfo(
            method="GET", action="ListAgentRunCurrentStep", service="ipaas", version="2023-08-01", content_type="application/json"
        ), body)
        
        print("\nListAgentRunCurrentStep response:")
        print(resp)
        
    except ApiException as e:
        print(f"API Exception: {e}")
    except Exception as e:
        print(f"General Exception: {e}")

