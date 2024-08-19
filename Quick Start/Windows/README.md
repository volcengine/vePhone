# VePhone SDK Demo

## 说明

本项目是火山引擎云手机客户端SDK（Windows端）的快速演示Demo。获取项目以后，开发者可以快速构建应用，体验云手机服务的主要功能；也可以参考其中的代码，在实际的客户端应用中实现相似的功能。


## 环境要求

### 推荐环境

Windows 10、Visual Studio 2022、C++14 或以上版本。


## 名词解释

PCSDK的应用场景与Android、iOS、Web略有不同，除了单路拉流之外，还存在批量拉流和群控两种特殊使用方式。

下面对一些频繁使用的名词作出解释：

**拉流** : 用户通过云手机 PC 应用程序，从云手机实时获取视频和音频数据的过程。当用户打开应用程序并连接到云手机后，可以选择启动拉流功能，此时应用程序会开始接收并显示云手机上的媒体内容。拉流允许用户远程查看和监控云手机的屏幕活动。当前高性能机型单屏拉流上限为 500 路。

**群控** : 用户通过一个主控设备对多台云手机进行批量管理和同步操作的过程。在云手机PC应用程序中，用户可以选择多台云手机进行拉流，并指定其中一台作为主控设备，通过主控设备执行一系列操控指令，包括点击屏幕、输入文本、调节音量等操作，这些操作会被同步到所有选中的云手机上。

**小流** : 批量拉流场景下，仅供预览的低清晰度视频流画面。

**大流** : 批量拉流场景下，可供操作的高清晰度视频流画面。点击某个小流画面可以将其切换为大流。

**主控** : 用户选定并直接控制的一台云手机，用于发出控制指令，管理和操作其他多台云手机。

**被控** : 用户间接控制的多台云手机，这些设备将接收并执行主控设备发出的同步操作。


## 接入流程

### 零、鉴权相关

1. 在接入云手机SDK之前，需要获取火山引擎账号对应原始的AccessKey（ak）和SecretKey（sk），用于生成临时鉴权密钥（登录火山引擎控制台后，点击页面右上角用户信息，选择 账号 > API访问密钥）。

2. 调用 “签发临时Token” 接口，获取用于鉴权的临时密钥（ak/sk/token 的获取方式请参考 [快速入门](https://www.volcengine.com/docs/6394/75735)）。

3. 获取到 ak/sk/token 之后，将其填入 [初始化BCV](#初始化BCV)、[发起群控](#发起群控)、[创建Session](#创建Session) 的对应位置。

4. 由于涉及安全问题，本Demo中的鉴权信息从**sts.ini**文件中读取，该文件位于工程根目录，需要用户自行创建。

**sts.ini** 的格式如下：
```C++
ak:your_ak
sk:your_sk
token:your_token
accountId:your_account_id
productId:your_product_id
```


### 一、初始化SDK

```C++
vecommon::VeCloudRenderX* _renderX = vecommon::CreateVeCloudRenderX();
_renderX->prepare();
_renderX->setDebug(true, ".\\qk_demo_logs");
```


### 二、批量拉流

#### 初始化BCV

```C++
BatchControlVideo* _batchControlVideo;
vecommon::BatchControlVideoConfig _bcvConfig;
std::string _bcvRoundId, _bcvUserId;
std::vector<std::string> _podIdList;

if (_renderX) {
    _bcvUserId = "bcv_user_id_" + std::string(_renderX->getDeviceId());
    _bcvRoundId = "bcv_round_id_" + std::to_string(getCurrentTimeMs());
    _bcvConfig.accountId = "your_account_id";
    _bcvConfig.ak = "your_ak";
    _bcvConfig.sk = "your_sk";
    _bcvConfig.token = "your_token";
    _bcvConfig.userId = _bcvUserId.c_str(); // 建议与大流设置不同的userId
    _bcvConfig.roundId = _bcvRoundId.c_str();
    _bcvConfig.videoStreamProfileId = 9514;
    _bcvConfig.waitTime = 10;
    _bcvConfig.productId = "your_product_id";
    _bcvConfig.externalRenderFormat = vecommon::FrameFormat::ARGB;
    _bcvConfig.externalRender = true;
    _bcvConfig.autoRecycleTime = 7200;
    
    _podIdList.push_back("7395806755290xxxxxx");
    _bcvConfig.videoConfigs.clear();
    for (auto& id : _podIdList) {
        const char* podId = id.c_str();
        HWND win = createSubWindow(podId); // 为每个云机创建一个窗口
        vecommon::ControlVideoConfig config;
        config.canvas = win;
        config.podId = podId;
        config.autoSubscribe = true; // 订阅视频流的方式，非自动订阅的情况下，需要在onPodJoin回调中进行手动订阅
        _bcvConfig.videoConfigs.push_back(config);
    }
    _batchControlVideo = _renderX->createBatchControlVideo(_bcvConfig);
    _batchControlVideo->setBatchControlListener(this); // 该类需要继承BatchControlListener
}
```


#### 发起批量PodStart请求

```C++
if (_batchControlVideo) {
    _batchControlVideo->requestBatchPodStart();
}
```

```C++
/**
 * 调用requestBatchPodStart后，会收到onBatchPodStartResult回调。
 * 注意：
 * 1. pod_list表示可拉小流的pod列表，当pod_list为nullptr或者为空时，不应当继续调用start接口发起拉流；
 * 2. 在onBatchStartResult成功返回且满足发起start的条件时，推荐等5s再发起调用start。
 */
void onBatchPodStartResult(int code, const char* msg, const std::vector<vecommon::PodInfo>* pod_list,
    const std::vector<vecommon::PodError>* pod_errors) {}
```


#### 开始批量拉流

```C++
if (_batchControlVideo) {
    _batchControlVideo->start();
}
```

```C++
void onPodJoin(const char* pod_id) {
    bool isAutoSub = _batchControlVideo == nullptr ? false : _batchControlVideo->isAutoSubscribe(pod_id);
    bool isSub = _batchControlVideo == nullptr ? false : _batchControlVideo->isSubscribed(pod_id);
    if (_batchControlVideo) {
        // 如果使用外部渲染，需要设置外部渲染的画布。注：目前批量拉流只支持使用外部渲染
        if (_config.externalRender) {
            auto vc = _batchControlVideo->getVideoConfig(pod_id);
            if (vc) {
                QkVeExternalSink* sink = new QkVeExternalSink();
                sink->setCanvas(static_cast<HWND>(vc->canvas));
                _batchControlVideo->setExternalSink(pod_id, sink);
            }
        }
        
        // 需要手动订阅视频流
        if (!isAutoSub) {
            _batchControlVideo->subscribe(pod_id);
        }
    }
}
```


#### 停止批量拉流

```C++
if (_batchControlVideo) {
    _batchControlVideo->stop();
}
```


### 三、群控

#### 发起群控

```C++
vecommon::EventSyncConfig _eventSyncConfig;
std::string _eventSyncRoundId, _eventSyncUserId;
std::vector<std::string> _controlledPodIdList; // 被控podId列表

bool ret = false;
if (_renderX) {
    _eventSyncRoundId = "event_sync_round_id_" + std::to_string(getCurrentTimeMs());
    _eventSyncUserId = "event_sync_user_id_" + std::string(_renderX->getDeviceId());    
    _eventSyncConfig.ak = "your_ak";
    _eventSyncConfig.sk = "your_sk";
    _eventSyncConfig.token = "your_token";
    _eventSyncConfig.roundId = _eventSyncRoundId.c_str();
    _eventSyncConfig.productId = "your_product_id";
    _eventSyncConfig.userId = _eventSyncUserId.c_str();
    _eventSyncConfig.controlledPodIdList = _controlledPodIdList;
    _eventSyncConfig.enableForce = true;
    _eventSyncConfig.softwareVersion = "3010609"; // 支持切换主控的云机镜像版本
    ret = _renderX->startEventSync(_eventSyncConfig, dynamic_cast<IEventSyncListener*>(this)); // 该类需要继承IEventSyncListener
}
```

```C++
/**
 * 调用startEventSync后可以收到onContorlledUserJoined和onContorlledUserLeave回调，
 * 可以通过这两个回调来判断被控Pod是否加入群控房间，发起群控后5s内被控Pod全部加房成功可认为群控成功。
 */
void onContorlledUserJoined(const char* userId, const char* roomId) {}

void onContorlledUserLeave(const char* userId, const char* roomId) {}
```


#### 设置主控

```C++
/**
 * 设置主控需要传入一个PhoneSession指针
 */
if (_renderX) {
    _renderX->setMasterSession(masterSession); 
}
```


#### 同步操作

```C++
/**
 * 发起群控后，调用masterSession的相关接口来实现同步操作。
 * 
 * 目前支持的同步操作有：
 * 1. 触控指令(sendMouseKey、sendMouseMove、sendMulitTouch)
 * 2. 鼠标滚轮事件(sendMouseWheel)
 * 3. KeyCode(sendKeyCode)
 * 4. 音量+/-(volumeUp、volumeDown)
 * 5. 文本输入(sendImeComposition)
 * 6. 导航栏开启/隐藏(setNavBarStatus)
 * 7. 发送摇一摇事件(sendShakeEventToRemote)
 * 8. 发送音频注入事件(sendAudioInjectionEventToRemote)
 */
if (masterSession) {
    masterSession->volumeUp();
}
```


#### 切换主控

```C++
/**
 * 切换主控需要先传入nullptr，再传入一个新的PhoneSession指针
 */
if (_renderX) {
    _renderX->setMasterSession(nullptr);
    _renderX->setMasterSession(newSession);
}
```


#### 暂停群控

```C++
/**
 * 暂停群控需要传入nullptr即可
 */
if (_renderX) {
    _renderX->setMasterSession(nullptr);
}
```


#### 继续群控

```C++
/**
 * 继续群控传入之前的PhoneSession指针即可
 */
if (_renderX) {
    _renderX->setMasterSession(session);
}
```


#### 结束群控

```C++
if (_renderX) {
    ret = _renderX->stopEventSync();
}
```


### 四、小流切大流

#### 创建Session

```C++
/**
 * 小流切大流需要创建一个新的PhoneSession，并拉流
 */
vecommon::PhoneSessionConfig _sessionConfig;
std::string _sessionRoundId, _sessionUserId;

if (_renderX) {
    _sessionRoundId = "session_round_id_" + std::to_string(getCurrentTimeMs());
    _sessionUserId = "session_user_id_" + std::string(demo->_renderX->getDeviceId());
    _sessionConfig.basicConfig.userId = _sessionUserId.c_str(); // 建议和小流设置不同的userId
    _sessionConfig.podId = "your_pod_id";
    _sessionConfig.productId = "your_product_id";
    _sessionConfig.basicConfig.accountId = "your_account_id";
    _sessionConfig.basicConfig.ak = "your_ak";
    _sessionConfig.basicConfig.sk = "your_sk";
    _sessionConfig.basicConfig.token = "your_token";
    _sessionConfig.roundId = _sessionRoundId.c_str();
    _sessionConfig.basicConfig.autoRecycleTime = 7200;
    _sessionConfig.basicConfig.videoStreamProfileId = 15307;
    _sessionConfig.enableLocalKeyboard = true;
    _sessionConfig.basicConfig.canvas = hwnd;
    
    PhoneSession* session = (PhoneSession*)_renderX->createPhoneSession(_sessionConfig, this); // 该类需要继承ISessionListener
    
    session->start();
}
```


## 参考资料

火山引擎云手机客户端SDK下载：https://www.volcengine.com/docs/6394/75741。

注：如果不能访问以上链接，请参考 [开通云手机服务](https://www.volcengine.com/docs/6394/75735) 说明文档。

