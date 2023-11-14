# vePhone SDK Demo

## 说明

本项目是火山引擎云手机客户端 SDK 的快速演示 demo。获取项目以后，开发者可以快速构建应用，体验云手机服务的主要功能；也能参考其中的代码，在实际的客户端应用中实现相似的功能。

## 环境要求

### 硬件要求

支持 Android 4.3（Android-19+）及以上系统的真机设备，支持 armeabi-v7a。

### 软件要求

- IDE：Android Studio（推荐使用最新版本）
- 搭建 Java 环境，使用 Java 作为开发语言，JDK版本需要1.8+

## 接入流程

### 添加 Maven 仓库地址

1. 在 project 根目录下的 build.gradle 文件中的 repositories 闭包中配置 Maven 仓库地址：

```java
buildscript {
    repositories {
        maven {
            url 'https://artifact.bytedance.com/repository/Volcengine/'
        }
    }
}
allprojects {
    repositories {
        maven {
            url 'https://artifact.bytedance.com/repository/Volcengine/'
        }
    }
}
```

2. 在应用模块的 build.gradle 文件中的 dependencies 中加入依赖项：

```java
dependencies {
    implementation fileTree(include: ['*.jar'], dir: 'libs')
    // 云手机 SDK
    implementation 'com.volcengine.vephone:vephone:1.21.0'
    
    implementation 'androidx.annotation:annotation:1.1.0'
        
    // 选择引用以下三种框架中的任意一种
    implementation 'com.google.code.gson:gson:2.8.5' // gson
        
    implementation 'com.alibaba:fastjson:1.1.72.android' // fastjson
        
    implementation 'com.fasterxml.jackson.core:jackson-databind:2.11.1' // jackson
    implementation 'com.fasterxml.jackson.core:jackson-core:2.11.1' //jackson

    // 大文件传输特性（FileExchange）需要以下依赖项
    implementation 'com.squareup.okhttp3:okhttp:4.9.0'
}
```

3. 设置 Java 版本到 1.8：

```java
android {
    // ...
    compileOptions {
        sourceCompatibility JavaVersion.VERSION_1_8
        targetCompatibility JavaVersion.VERSION_1_8
    }
}
```

### 权限声明

根据实际使用场景在 AndroidManifest.xml 文件中声明 SDK 需要的权限：

```java
//网络权限，使用场景：音视频传输等
<uses-permission android:name="android.permission.INTERNET" />
//WiFi网络状态，使用场景：用户手机网络状态变化监听
<uses-permission android:name="android.permission.CHANGE_WIFI_STATE" />
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
<uses-permission android:name="android.permission.ACCESS_WIFI_STATE" />
//录音权限，使用场景：[开启/关闭] 麦克风
<uses-permission android:name="android.permission.RECORD_AUDIO" />
//设置播放模式的权限：外放 / 听筒
<uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS" />
//同步定位信息，使用场景：当有些应用需要获取用户的地理位置时，需要获取用户的地理位置信息
//并传送给远端Pod
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
<uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION" />
<uses-permission android:name="android.permission.ACCESS_LOCATION_EXTRA_COMMANDS" />
//读写存储
<uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE" />
<uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" />
//相机
<uses-permission android:name="android.permission.CAMERA" />
```

#### 说明
1. 存储写入权限需动态申请。参考：https://developer.android.com/training/permissions/requesting
2. 如果 APP 指向 Android 10 及以上（targetSdkVersion >= 29），而且并未适配 Scoped Storage，那么需要
    将AndroidManifest.xml文件中的requestLegacyExternalStorage设置为true。参考：https://developer.android.com/training/data-storage/use-cases#opt-out-scoped-storage
```java
<manifest>
    <application android:requestLegacyExternalStorage="true">
    </application>
</manifest>
```
### 快速开始

#### 零、鉴权相关

1. 在接入云手机 SDK 之前，需要获取火山引擎账号对应原始的 AccessKey（ak）和 SecretKey（sk），用于生成临时鉴权密钥（登录火山引擎控制台后，点击页面右上角用户信息，选择 账号 > API访问密钥）。

2. 调用 “签发临时Token” 接口，获取用于鉴权的临时密钥（ak/sk/token 的获取方式请参考 [快速入门](https://www.volcengine.com/docs/6394/75735)）。

3. 获取到 ak/sk/token 之后，将其填入 [二、配置PhonePlayConfig](#二、配置PhonePlayConfig) 的对应位置。

4. 除此之外，需要在 [app/src/main/AndroidManifest.xml](app/src/main/AndroidManifest.xml) 文件的 meta-data 中填入注册的火山引擎用户账号，参考以下示例：

```java
<meta-data
    android:name="VOLC_ACCOUNT_ID"
    android:value="21000xxxxx" />
```

#### 一、初始化 VePhoneEngine

```java
VePhoneEngine.getInstance().prepare();
```

注：VePhone SDK版本在1.28.0之后，init()方法会废弃，请使用prepare()方法进行VePhoneEngine的初始化。

#### 二、配置 PhonePlayConfig

```java
PhonePlayConfig.Builder builder = new PhonePlayConfig.Builder();

builder.userId(userId) // 用户userid
    .ak(ak) // 必填参数，临时鉴权 ak
    .sk(sk)  // 必填参数，临时鉴权 sk
    .token(token) // 必填参数，临时鉴权 token
    .container(mContainer) // 必填参数，用来承载画面的 Container, 参数说明: layout 需要是 FrameLayout 或者 FrameLayout 的子类
    .roundId(intent.getStringExtra(KEY_ROUND_ID)) // 必填参数，自定义roundId
    .videoStreamProfileId(intent.getIntExtra(KEY_ClARITY_ID, 1)) // 选填参数，清晰度ID
    .podId(intent.getStringExtra(KEY_POD_ID)) // 必填, podId
    .productId(intent.getStringExtra(KEY_PRODUCT_ID)) // 必填, productId
    .enableGravitySensor(true) // 打开重力传感器开关
    .enableGyroscopeSensor(true) // 打开陀螺仪开关
    .enableMagneticSensor(true) // 打开磁力传感器开关
    .enableOrientationSensor(true) // 打开方向传感器开关
    .enableVibrator(true) // 打开本地振动开关
    .enableLocationService(true) // 打开本地定位功能开关
    .enableLocalKeyboard(true) // 打开本地键盘开关
    .streamListener(IStreamListener streamListener); // 获取音视频流信息回调监听

PhonePlayConfig phonePlayConfig = builder.build();
```

#### 三、开启云手机
```java
vePhoneEngine.start(phonePlayConfig, IPlayerListener playerListener);
```

## 目录结构

```
main
├── AndroidManifest.xml
├── assets // 该目录及文件需要自行创建
│   └── sts.json // 保存鉴权相关的 ak/sk/token
├── java
│   └── com
│       └── example
│           └── sdkdemo
│               ├── FeatureActivity.kt // 用于指定podId及productId以体验SDK的不同特性
│               ├── PhoneActivity.java // 显示云手机的Activity
│               ├── GsonConverter.java // 用于SDK 传入的JSON转换的实现 
│               ├── InitApplication.java // 工程的Application 负责初始化SDK等
│               ├── MainActivity.java // 用于展示SDK的特性列表，并进入对应特性的体验界面
│               ├── TestBean.kt // 用于填写云手机启动的参数
│               ├── WebViewActivity.kt // 用于展示火山引擎的官网
│               ├── base
│               │   ├── BaseListActivity.java
│               │   └── BaseSampleActivity.kt
│               ├── feature // 用于体验SDK不同的特性
│               │   ├── AudioServiceView.java // 音频
│               │   ├── CamaraManagerView.java // 相机
│               │   ├── ClarityServiceView.java // 清晰度
│               │   ├── ClipBoardServiceManagerView.java // 剪切板
│               │   ├── FileChannelExtView.java // 大文件通道
│               │   ├── LocalInputManagerView.java // 本地输入
│               │   ├── LocationServiceView.java // 定位服务
│               │   ├── MessageChannelView.java // 消息通道
│               │   ├── MultiMediaStreamActivity.java // 多屏取流
│               │   ├── PadConsoleManagerView.java // 游戏手柄
│               │   ├── PodControlServiceView.java // 实例控制
│               │   ├── RotationModeActivity.java // 旋转模式
│               │   ├── SensorView.java // 传感器
│               │   └── UnclassifiedView.java // 其他
│               └── util
│                   ├── AssetsUtil.java // 用于读取并解析sts.json文件中的ak/sk/token
│                   ├── DialogUtils.java // 用于在不同特性的体验界面显示对话框
│                   ├── Feature.java // 声明不同的特性id
│                   ├── FileUtil.java // 用于文件传输功能的工具类
│                   ├── ScreenUtil.java // 屏幕工具类，用于适配挖孔屏
│                   └── SizeUtils.java 
```


其中, **sts.json** 的格式如下：
```java
{
    "ak": "your_ak",
    "sk": "your_sk",
    "token": "your_token"
}
```

## 参考资料

火山引擎云手机客户端 SDK 下载：https://www.volcengine.com/docs/6394/75741。

注：如果不能访问以上链接，请参考 [开通云手机服务](https://www.volcengine.com/docs/6394/75735) 说明文档。

