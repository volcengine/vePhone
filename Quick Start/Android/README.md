



# CloudPhone SDK

###### 说明

> 本项目 是云手机的sdk的simple demo, 提供一个快速的接入演示。


###### 快速开始
> 点击运行，编译生成apk 在手机预览
> 相关的运行信息 在打印的log里查看


###### 目录结构

```
└── com
    └── example
        └── sdkdemo
            ├── InitApplication.java  // 初始Application 初始SDK 一些操作
            ├── MainActivity.kt   // 说明和跳转页
            ├── PhoneActivity.java // 云手机展示的activity
            └── ScreenUtil.java   //屏幕工具类用于适配 挖孔屏
```

###### 接入的流程

1. 初始化sdk，（初始化失败 请检查网络）
2. 填入ak ，sk ，token productId ，调用start
3. 切到后台 可以选择调用 pause() 来停止音视屏流
4. 切回前台 可以选择调用 resume() 来恢复音视频流
5. 结束 调用stop（）接口 结束游戏并释放Pod资源

###### 后续替换

**接入服务端鉴权接口获取鉴权 的 ak sk token productId**



