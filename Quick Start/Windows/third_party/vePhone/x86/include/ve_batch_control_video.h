#pragma once
#include "ve_type_defines.h"
#include "ve_batch_control_listener.h"
#include "ve_external_sink.h"

class BatchControlVideo
{
public:

    BatchControlVideo(const vecommon::BatchControlVideoConfig& config) :_config(config) {};
    virtual ~BatchControlVideo() = default;

    // 发起小流加房请求
    // - 获取podList与房间对应关系
    // - 获取加房鉴权信息
    virtual int requestBatchPodStart() = 0;

    // 加入所有pod房间
    // 1. 创建引擎
    // 2. 加房
    virtual int start() = 0;

    // 退出所有pod房间并销毁引擎
    // 1. 退房
    // 2. 销毁引擎
    virtual int stop() = 0;

    /// <summary>
    /// 获取单个视频的状态
    /// </summary>
    /// <param name="pod_id">指定要查询的podId</param>
    /// <returns></returns>
    virtual vecommon::SessionStatus getVideoStatus(const char* pod_id) { return vecommon::SessionStatus::Idle; };

    /// <summary>
    /// 获取指定pod的视频配置
    /// </summary>
    /// <param name="pod_id">指定要查询的podId</param>
    /// <returns></returns>
    virtual vecommon::ControlVideoConfig* getVideoConfig(const char* pod_id) = 0;

    /// <summary>
    /// 订阅视频
    /// </summary>
    /// <param name="pod_id">指定要操作的podId</param>
    virtual int subscribe(const char* pod_id) = 0;


    /// <summary>
    /// 退订视频
    /// </summary>
    /// <param name="pod_id">指定要操作的podId</param>
    virtual int unsubscribe(const char* pod_id) = 0;

    /// <summary>
    /// 获取单个视频订阅状态
    /// </summary>
    /// <param name="pod_id">指定要查询的podId</param>
    /// <returns></returns>
    virtual bool isSubscribed(const char* pod_id) = 0;

    /// <summary>
    /// 获取单个视频自动订阅状态
    /// </summary>
    /// <param name="pod_id">指定要查询的podId</param>
    /// <returns>true-自动订阅；false-手动订阅</returns>
    virtual bool isAutoSubscribe(const char* pod_id) = 0;

    /// <summary>
    /// 更新单个视频的渲染画布
    /// </summary>
    /// <param name="pod_id">指定要操作的podId</param>
    /// <param name="canvas">渲染窗口</param>
    virtual int updateCanvas(const char* pod_id, void* canvas) = 0;

    /// <summary>
    /// 设置外部渲染器
    /// </summary>
    /// <param name="pod_id"></param>
    /// <param name="externalSink"></param>
    virtual int setExternalSink(const char* pod_id, VeExternalSink* externalSink) = 0;

    /// <summary>
    /// 获取外部渲染器
    /// </summary>
    /// <param name="pod_id"></param>
    /// <returns></returns>
    virtual VeExternalSink* getExternalSink(const char* pod_id) = 0;

    /// <summary>
    /// 设置群控事件回调
    /// </summary>
    /// <param name="listener"></param>
    virtual void setBatchControlListener(BatchControlListener* listener) = 0;

protected:
    const vecommon::BatchControlVideoConfig& _config;


};

